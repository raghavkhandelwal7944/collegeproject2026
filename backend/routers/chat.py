"""
POST /api/v1/chat — Firewall LLM full pipeline (Phases 1-3).

Request flow:
    1.  Validate JWT (get_current_user dependency).
    2.  Layer 0  — Gemini injection / jailbreak detection (detect_injection).
        → Block with 403 if malicious intent is found.
    3.  Layer 1  — Presidio PII scan (PresidioService.scan).
        → Replace PII spans with deterministic hash tokens.
    4a. Token Vault — store token↔original mapping in Redis (TTL 3600s).
        → No-op if Redis unavailable (graceful degradation).
    4b. Semantic Cache check — embed the anonymized prompt; query Redis for a
        cosine-similar prior response (threshold ≥ 0.95).
        → CACHE HIT:  de-anonymize cached response → return directly (LLM bypassed).
        → CACHE MISS: continue to Layer 2.
    5.  Layer 2  — Llama Guard gatekeeper (LLMService.check_with_gatekeeper).
        → Block with 400 if prompt violates safety policies.
        → Taxonomy code logged server-side only (never returned).
    6.  Layer 3  — Main instruction LLM (LLMService.call_main_llm).
    7.  Cache store — persist new embedding + response in Redis.
    8.  De-anonymize — replace tokens in LLM response with original PII
        via Token Vault lookup.
    9.  Persist conversation to MongoDB (save_conversation).
    10. Persist audit log entry (log_request).
    11. Return ChatResponse with the full pipeline output.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from ..database import (generate_session_title, get_conversation_history,
                        get_user_policies, log_request, save_conversation)
from ..dependencies import get_current_user
from ..firewall import detect_injection
from ..models.schemas import ChatRequest, ChatResponse
from ..services.embedding_service import get_embedding_service
from ..services.llm_service import GatekeeperResult, get_llm_service
from ..services.presidio_service import ScanResult, get_presidio_service
from ..services.redis_service import get_redis_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


def _storage_safe_prompt(raw_prompt: str, anonymized_prompt: str, aggressive_pii: bool) -> str:
    """Return the prompt variant safe to persist in logs/storage."""
    return anonymized_prompt if aggressive_pii else raw_prompt


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Firewall LLM — full pipeline (Phases 1-3)",
    description=(
        "Runs the complete firewall pipeline: injection detection (Layer 0), "
        "Presidio PII anonymization (Layer 1), Token Vault + Semantic Cache (Phase 3), "
        "Llama Guard safety gate (Layer 2), and main LLM inference (Layer 3)."
    ),
)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user),
) -> ChatResponse:
    """
    Layer 1 firewall pipeline handler.

    Args:
        request:      Validated ChatRequest containing the raw user prompt.
        current_user: Authenticated user dict injected by the JWT dependency.

    Returns:
        ChatResponse with the full pipeline output including the de-anonymized answer.

    Raises:
        HTTPException 403: If injection / jailbreak is detected.
        HTTPException 400: If the Llama Guard gatekeeper flags the prompt as unsafe.
        HTTPException 503: If the inference server is unreachable or times out.
        HTTPException 500: On unexpected internal errors.
    """
    username: str = current_user["username"]
    raw_prompt: str = request.prompt

    logger.info("[Chat] User '%s' submitted a prompt (%d chars).", username, len(raw_prompt))

    # Load this user's policy flags from MySQL
    policies = get_user_policies(username)
    result = ScanResult(anonymized_text=raw_prompt, entities=[], duration_ms=0.0)
    storage_prompt: str = raw_prompt
    model_prompt: str = raw_prompt

    # Policy: Aggressive PII Redaction — pre-scan once so any DB/log persistence
    # uses the anonymized prompt instead of raw secrets.
    if policies["aggressive_pii"]:
        logger.debug("[Chat] Pre-scanning prompt for storage-safe persistence for user '%s'…", username)
        try:
            result = get_presidio_service().scan(raw_prompt, aggressive=True)
            storage_prompt = _storage_safe_prompt(
                raw_prompt,
                result.anonymized_text,
                aggressive_pii=True,
            )
            model_prompt = result.anonymized_text
        except RuntimeError as exc:
            logger.critical("[Chat] PresidioService unavailable during pre-scan: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Firewall scanning service is unavailable. Please retry.",
            )

    # Policy: Code Execution Block — checked before any expensive pipeline step
    if policies["code_block"]:
        import re as _re
        _CODE_PAT = _re.compile(
            r'\b(exec|eval|os\.system|subprocess|shell=|cmd\.exe|powershell|bash|sh -c'  # noqa
            r'|DROP TABLE|DELETE FROM|TRUNCATE|INSERT INTO|UPDATE .* SET)\b',
            _re.IGNORECASE,
        )
        if _CODE_PAT.search(raw_prompt):
            logger.warning("[Chat] BLOCKED by code_block policy for user '%s'.", username)
            log_request(storage_prompt, blocked=True, violation_type="CodeBlock")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Security policy violation: code execution or destructive commands are not allowed.",
            )

    # ------------------------------------------------------------------
    # Gate 1: Injection / jailbreak detection (Gemini-backed)
    # ------------------------------------------------------------------
    logger.debug("[Chat] Running injection detection for user '%s'…", username)
    is_injection: bool = detect_injection(raw_prompt)

    if is_injection:
        logger.warning(
            "[Chat] BLOCKED — injection detected for user '%s'. Prompt (truncated): %.80s",
            username,
            raw_prompt,
        )
        log_request(storage_prompt, blocked=True, violation_type="Injection")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Security violation: malicious or injection-style content detected.",
        )

    # ------------------------------------------------------------------
    # Gate 2: PII scan & anonymization (only when policy is enabled)
    # ------------------------------------------------------------------
    if policies["aggressive_pii"]:
        storage_prompt = _storage_safe_prompt(
            raw_prompt,
            result.anonymized_text,
            aggressive_pii=True,
        )
        model_prompt = result.anonymized_text
    else:
        logger.debug("[Chat] PII policy disabled for user '%s' — skipping prompt redaction.", username)

    # Determine violation type for the audit log
    violation_type: str = "PII" if result.entities else "None"

    if result.entities:
        logger.info(
            "[Chat] PII detected for user '%s': %d entity/entities — types: %s. "
            "Scan took %.2f ms.",
            username,
            len(result.entities),
            [e.entity_type for e in result.entities],
            result.duration_ms,
        )
    else:
        logger.info(
            "[Chat] Clean prompt for user '%s'. Scan took %.2f ms.",
            username,
            result.duration_ms,
        )

    # ------------------------------------------------------------------
    # Phase 3a — Token Vault: store token↔original mapping in Redis
    # ------------------------------------------------------------------
    # chat_session_id ties all messages in one user conversation together.
    chat_session_id: str = request.chat_session_id or uuid.uuid4().hex

    # vault_id ties the Redis Token Vault entry to this specific request.
    vault_id: str = uuid.uuid4().hex
    redis_svc = get_redis_service()

    if redis_svc and policies["aggressive_pii"] and result.entities:
        token_map = {e.token: e.original_text for e in result.entities}
        await redis_svc.store_vault(vault_id, token_map)
        logger.debug(
            "[Chat] Vault stored for vault '%s' (%d token(s)).",
            vault_id,
            len(token_map),
        )

    # ------------------------------------------------------------------
    # Phase 3b — Semantic Cache: check for a similar prior response
    # ------------------------------------------------------------------
    embedding: list[float] | None = None
    cached_response: str | None = None

    if redis_svc and policies["semantic_cache"]:
        embedding = get_embedding_service().embed(model_prompt)
        cached_response = await redis_svc.get_cached_response(embedding)

    if cached_response is not None:
        # Cache HIT — de-anonymize the cached response and return immediately,
        # bypassing Layers 2 and 3 entirely.
        logger.info(
            "[Chat] Semantic cache HIT for user '%s' — LLM bypassed.", username
        )
        final_response = (
            await redis_svc.restore_tokens(vault_id, cached_response)
            if redis_svc and policies["aggressive_pii"]
            else cached_response
        )
        log_request(storage_prompt, blocked=False, violation_type=violation_type)
        # Determine session title (re-use existing if session already has messages)
        _existing = get_conversation_history(username, limit=1, session_id=chat_session_id)
        _title = None if _existing else generate_session_title(storage_prompt)
        save_conversation(username, storage_prompt, cached_response,
                          session_id=chat_session_id, session_title=_title)
        return ChatResponse(
            anonymized_prompt=result.anonymized_text,
            entities_found=result.entities,
            pii_detected=bool(result.entities),
            scan_duration_ms=result.duration_ms,
            gatekeeper_verdict="cache_hit",
            llm_response=cached_response,
            final_response=final_response,
            cache_hit=True,
        )

    # Cache MISS — proceed through Layers 2 and 3.

    # ------------------------------------------------------------------
    # Gate 3: Llama Guard — Layer 2 safety gatekeeper
    # ------------------------------------------------------------------
    logger.debug("[Chat] Running Llama Guard gatekeeper for user '%s'…", username)
    try:
        gatekeeper_result: GatekeeperResult = (
            await get_llm_service().check_with_gatekeeper(model_prompt)
        )
    except RuntimeError as exc:
        logger.critical("[Chat] LLMService unavailable: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Inference service is unavailable. Please retry.",
        )

    if gatekeeper_result.verdict == "unsafe":
        # Log the taxonomy code server-side; never surface it in the response
        # body to prevent category-enumeration probing.
        logger.warning(
            "[Chat] BLOCKED by gatekeeper for user '%s'. "
            "Category: %s. Prompt (truncated): %.80s",
            username,
            gatekeeper_result.category,
            model_prompt,
        )
        log_request(
            storage_prompt,
            blocked=True,
            violation_type=f"GatekeeperBlock:{gatekeeper_result.category or 'UNKNOWN'}",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Your request could not be processed because it was flagged by "
                "our content safety system. Please revise your prompt and try again."
            ),
        )

    # ------------------------------------------------------------------
    # Layer 3: Main instruction LLM
    # ------------------------------------------------------------------
    # Load per-session conversation history from MongoDB (last 20 turns)
    # so a brand-new chat starts clean while old chats preserve their own context.
    history = get_conversation_history(username, limit=20, session_id=chat_session_id)

    # Also prepend any history the client sent in this request
    # (frontend in-memory turns not yet persisted to MongoDB)
    client_history = [{"role": m.role, "content": m.content} for m in request.messages]
    combined_history = client_history if client_history else history

    logger.debug("[Chat] Forwarding to main LLM for user '%s' with %d history turns…", username, len(combined_history))
    llm_response: str = await get_llm_service().call_main_llm(
        model_prompt, history=combined_history
    )

    # ------------------------------------------------------------------
    # Phase 3c — Cache store: persist embedding + response for future hits
    # ------------------------------------------------------------------
    if redis_svc and policies["semantic_cache"] and embedding is not None:
        await redis_svc.store_cache_entry(embedding, llm_response)

    # ------------------------------------------------------------------
    # Phase 3d — De-anonymize: restore original PII in the LLM response
    # ------------------------------------------------------------------
    final_response: str = (
        await redis_svc.restore_tokens(vault_id, llm_response)
        if redis_svc and policies["aggressive_pii"]
        else llm_response
    )
    if final_response != llm_response:
        logger.info(
            "[Chat] De-anonymized LLM response for user '%s' (vault '%s').",
            username,
            vault_id,
        )
    else:
        logger.debug(
            "[Chat] No tokens to restore for vault '%s' "
            "(no PII or Redis unavailable).",
            vault_id,
        )

    # ------------------------------------------------------------------
    # Persist conversation to MongoDB (with session tracking)
    # ------------------------------------------------------------------
    _existing2 = get_conversation_history(username, limit=1, session_id=chat_session_id)
    _title2 = None if _existing2 else generate_session_title(storage_prompt)
    save_conversation(username, storage_prompt, llm_response,
                      session_id=chat_session_id, session_title=_title2)

    # ------------------------------------------------------------------
    # Audit log — record the completed, allowed request
    # ------------------------------------------------------------------
    log_request(storage_prompt, blocked=False, violation_type=violation_type)

    return ChatResponse(
        anonymized_prompt=result.anonymized_text,
        entities_found=result.entities,
        pii_detected=bool(result.entities),
        scan_duration_ms=result.duration_ms,
        gatekeeper_verdict="safe",
        llm_response=llm_response,
        final_response=final_response,
        cache_hit=False,
    )

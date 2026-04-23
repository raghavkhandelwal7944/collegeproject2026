"""
Pydantic models for the Firewall LLM API.

These schemas define the contract for the /api/v1/chat endpoint.
The AnonymizedEntity shape is intentionally designed for Phase 3 Redis integration:
    HSET firewall:vault:<session_id> <token> <original_text>
"""

from pydantic import BaseModel, Field


class HistoryMessage(BaseModel):
    """A single prior turn used to build Mistral's conversation context."""
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text")


class ChatRequest(BaseModel):
    """
    Incoming payload for the /api/v1/chat endpoint.

    Attributes:
        prompt:   The raw user prompt to be scanned and anonymized.
        messages: Optional prior conversation turns for multi-turn context.
    """

    prompt: str = Field(
        ...,
        min_length=1,
        description="The raw user-supplied prompt to be evaluated by the firewall pipeline.",
        examples=["My name is John Smith and my email is john@example.com"],
    )
    messages: list[HistoryMessage] = Field(
        default_factory=list,
        description="Prior conversation history (oldest first) for contextual replies.",
    )
    chat_session_id: str | None = Field(
        default=None,
        description="Client-supplied session ID; a new UUID is generated if omitted.",
    )


class AnonymizedEntity(BaseModel):
    """
    Represents a single detected-and-replaced PII entity.

    Phase 3 note: Iterate over `entities_found` and call:
        redis_client.hset(f"firewall:session:{session_id}", entity.token, entity.original_text)
    to build a fully reversible token map.

    Attributes:
        original_text:  The raw PII string as it appeared in the prompt (e.g. "John Smith").
        token:          The deterministic hash-based replacement token (e.g. "<PERSON_a3f2c1>").
        entity_type:    Presidio entity category (e.g. "PERSON", "EMAIL_ADDRESS").
        start:          Inclusive start character index in the ORIGINAL prompt.
        end:            Exclusive end character index in the ORIGINAL prompt.
        score:          Presidio confidence score (0.0 – 1.0).
    """

    original_text: str = Field(..., description="The raw PII value extracted from the prompt.")
    token: str = Field(..., description="The opaque replacement token inserted into the anonymized prompt.")
    entity_type: str = Field(..., description="Presidio entity type label.")
    start: int = Field(..., ge=0, description="Start char index in the original prompt.")
    end: int = Field(..., ge=0, description="End char index (exclusive) in the original prompt.")
    score: float = Field(..., ge=0.0, le=1.0, description="Presidio detection confidence.")


class ChatResponse(BaseModel):
    """
    Response payload returned by the /api/v1/chat endpoint.

    Populated across the full three-layer pipeline:
      Layer 1 (Presidio)   → anonymized_prompt, entities_found, pii_detected, scan_duration_ms
      Layer 2 (Gatekeeper) → gatekeeper_verdict
      Layer 3 (Main LLM)   → llm_response

    Phase 3 note: `entities_found` carries the full token-map needed for
    `HSET firewall:session:<id> <token> <original_text>` in Redis.

    Attributes:
        anonymized_prompt:   The sanitized prompt with PII replaced by tokens.
        entities_found:      Ordered list of every PII entity detected and replaced.
        pii_detected:        Convenience boolean — True when entities_found is non-empty.
        scan_duration_ms:    Presidio scan wall-clock time in milliseconds.
        gatekeeper_verdict:  Layer 2 outcome — always "safe" in a successful response.
                             Useful for audit dashboards without needing to parse logs.
        llm_response:        The main LLM's answer to the (anonymized) prompt.
    """

    anonymized_prompt: str = Field(
        ..., description="The prompt with all detected PII replaced by tokens."
    )
    entities_found: list[AnonymizedEntity] = Field(
        default_factory=list,
        description="All PII entities detected. Use this list to populate the Phase 3 Redis token map.",
    )
    pii_detected: bool = Field(..., description="True if one or more PII entities were found.")
    scan_duration_ms: float = Field(..., description="Presidio scan wall-clock time in milliseconds.")
    gatekeeper_verdict: str = Field(
        default="safe",
        description="Layer 2 safety verdict — 'safe' in every non-blocked response.",
    )
    llm_response: str = Field(
        default="",
        description="The main LLM's answer to the anonymized prompt (Layer 3 output, tokens intact for audit).",
    )
    final_response: str = Field(
        default="",
        description=(
            "The de-anonymized LLM answer with original PII values restored via the "
            "Token Vault. This is the field that should be displayed to the end user. "
            "Equals llm_response when Redis is unavailable (graceful degradation)."
        ),
    )
    cache_hit: bool = Field(
        default=False,
        description=(
            "True when the semantic cache was used and the LLM was bypassed entirely. "
            "Expect lower latency and no LLM cost when this is True."
        ),
    )

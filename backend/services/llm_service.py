"""
Firewall LLM — LLM inference service (Layer 2 + Layer 3).

Layer 2 — Gatekeeper (Llama Guard)
------------------------------------
  Sends the Presidio-anonymized prompt to the safety classification model.
  Llama Guard's response format is well-defined:
      safe               → allow the request to proceed
      unsafe\n<CODE>     → block immediately (e.g. "unsafe\nS2")

  The taxonomy category code (S1–S14) is logged server-side for audit
  purposes but is NEVER returned to the API caller, preventing category
  enumeration attacks by a malicious probe.

Layer 3 — Main LLM (Instruction model)
----------------------------------------
  Sends the same anonymized prompt to the primary instruction model only
  after the gatekeeper has cleared it.  Returns the raw completion text.

Design notes:
  - A single httpx.AsyncClient is created in FastAPI's lifespan context and
    injected here at construction time.  This means one connection pool is
    shared across all requests (no per-request TCP handshakes) and the pool
    drains cleanly on shutdown via client.aclose().
  - The client is injected (not self-created) so tests can pass an
    httpx.AsyncMock without monkey-patching.
  - Both model calls target the OpenAI-compatible /chat/completions endpoint,
    which is the standard for Ollama (>=0.1.14), vLLM, and LM Studio.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

import httpx
from fastapi import HTTPException, status

from ..config import Settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Llama Guard system prompt
# Instructs the model to respond ONLY with "safe" or "unsafe\n<CODE>".
# Keeping this as a module constant makes it easy to version / A-B test.
# ---------------------------------------------------------------------------
_LLAMA_GUARD_SYSTEM_PROMPT: str = (
    "You are a safety classifier. "
    "Your only task is to evaluate whether the following user message violates "
    "any of the defined safety policies. "
    "Respond with exactly one of:\n"
    "  safe\n"
    "  unsafe\n<CATEGORY_CODE>\n"
    "where <CATEGORY_CODE> is the most relevant violation taxonomy code "
    "(e.g. S1, S2, … S14). "
    "Do NOT add any explanation or extra text."
)


# ---------------------------------------------------------------------------
# Internal result type for Layer 2
# ---------------------------------------------------------------------------

@dataclass
class GatekeeperResult:
    """
    Structured output from the Llama Guard safety check.

    Attributes:
        verdict:   "safe" or "unsafe".
        category:  Llama Guard taxonomy code when unsafe (e.g. "S2"), else None.
        raw_output: The full, unmodified string returned by the model — kept for
                    internal logging / audit.  Never forwarded to the API caller.
    """

    verdict: Literal["safe", "unsafe"]
    category: str | None
    raw_output: str


# ---------------------------------------------------------------------------
# LLM Service
# ---------------------------------------------------------------------------

class LLMService:
    """
    Async wrapper around the OpenAI-compatible /chat/completions endpoint.

    Instantiate once at application startup (see main.py lifespan) with a
    shared httpx.AsyncClient.  Exposes two public coroutines consumed by the
    chat router:

        result  = await llm_svc.check_with_gatekeeper(anonymized_prompt)
        answer  = await llm_svc.call_main_llm(anonymized_prompt)

    Args:
        client:   A live httpx.AsyncClient.  The caller owns its lifecycle
                  (create on startup, aclose() on shutdown).
        settings: Application settings carrying model names, base URL, and timeout.
    """

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        # Pre-build the completions URL once — avoids string concat per request.
        self._completions_url = (
            f"{settings.inference_server_url.rstrip('/')}/chat/completions"
        )
        logger.info(
            "[LLMService] Initialized. Completions endpoint: %s | "
            "Gatekeeper: %s | Main model: %s | Timeout: %.1fs",
            self._completions_url,
            settings.gatekeeper_model_name,
            settings.main_model_name,
            settings.llm_request_timeout_s,
        )

    # ------------------------------------------------------------------
    # Layer 2 — Safety Gatekeeper
    # ------------------------------------------------------------------

    async def check_with_gatekeeper(self, prompt: str) -> GatekeeperResult:
        """
        Send the anonymized prompt to Llama Guard for safety classification.

        The gatekeeper is queried with temperature=0 and max_tokens=20 — we
        only need the verdict token(s), not a long completion.

        Args:
            prompt: The Presidio-anonymized prompt (PII already replaced).

        Returns:
            GatekeeperResult with verdict, optional taxonomy code, and raw output.

        Raises:
            HTTPException 503: If the inference server is unreachable or times out.
        """
        start = time.perf_counter()
        payload = {
            "model": self._settings.gatekeeper_model_name,
            "messages": [
                {"role": "system", "content": _LLAMA_GUARD_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            # Short, deterministic output — Llama Guard is a classifier, not a generator.
            "temperature": 0,
            "max_tokens": 20,
        }

        raw_text = await self._post_completions(
            payload, label="[Gatekeeper]"
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        # ---- Parse Llama Guard output ----------------------------------
        # Expected formats (case-insensitive, may have trailing whitespace):
        #   "safe"
        #   "unsafe\nS2"
        #   "unsafe\nS11"
        cleaned = raw_text.strip().lower()
        result = self._parse_gatekeeper_output(raw_text)

        if result.verdict == "unsafe":
            # Log taxonomy code server-side; NEVER include in 400 response body.
            logger.warning(
                "[Gatekeeper] BLOCKED — verdict=unsafe, category=%s, duration=%.2f ms. "
                "Prompt (truncated): %.80s",
                result.category,
                elapsed_ms,
                prompt,
            )
        else:
            logger.info(
                "[Gatekeeper] PASSED — verdict=safe, duration=%.2f ms.", elapsed_ms
            )

        return result

    # ------------------------------------------------------------------
    # Layer 3 — Main Instruction LLM
    # ------------------------------------------------------------------

    async def call_main_llm(self, prompt: str, history: list[dict] | None = None) -> str:
        """
        Forward the cleared, anonymized prompt to the main instruction model.

        Only called after Layer 2 has returned a "safe" verdict.

        Args:
            prompt:  The Presidio-anonymized prompt, cleared by the gatekeeper.
            history: Optional prior conversation turns [{role, content}] oldest-first.
                     Prepended before the current user turn so Mistral has context.

        Returns:
            The raw completion text from the main model.

        Raises:
            HTTPException 503: If the inference server is unreachable or times out.
        """
        start = time.perf_counter()

        # Build the message list: prior history + current turn
        messages: list[dict] = list(history or [])
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self._settings.main_model_name,
            "messages": messages,
            "temperature": 0.7,
        }

        response_text = await self._post_completions(
            payload, label="[MainLLM]"
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "[MainLLM] Response received. Duration: %.2f ms. "
            "Response length: %d chars.",
            elapsed_ms,
            len(response_text),
        )
        return response_text

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _post_completions(
        self, payload: dict, label: str
    ) -> str:
        """
        POST to the /chat/completions endpoint and return the first choice's
        message content as a plain string.

        Args:
            payload: The full request body dict (model, messages, etc.).
            label:   A log prefix string for attribution (e.g. "[Gatekeeper]").

        Returns:
            Content string from choices[0].message.content.

        Raises:
            HTTPException 503: On timeout or connection failure.
            HTTPException 502: If the model server returns a non-2xx status.
        """
        try:
            response = await self._client.post(
                self._completions_url,
                json=payload,
                timeout=self._settings.llm_request_timeout_s,
            )
        except httpx.TimeoutException:
            logger.error(
                "%s Inference server timed out after %.1fs.",
                label,
                self._settings.llm_request_timeout_s,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "The inference server did not respond in time. "
                    "Please try again or contact support."
                ),
            )
        except httpx.ConnectError:
            logger.error(
                "%s Cannot connect to inference server at %s.",
                label,
                self._completions_url,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    f"Inference server is unreachable. "
                    "Ensure the model server is running and try again."
                ),
            )

        # Surface non-2xx errors from the model server clearly.
        if response.status_code >= 400:
            logger.error(
                "%s Model server returned HTTP %d: %s",
                label,
                response.status_code,
                response.text[:200],
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"Inference server returned an error ({response.status_code}). "
                    "Please check model availability."
                ),
            )

        data = response.json()
        try:
            content: str = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            logger.error(
                "%s Unexpected response schema from inference server: %s",
                label,
                data,
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Inference server returned an unexpected response format.",
            ) from exc

        return content

    @staticmethod
    def _parse_gatekeeper_output(raw: str) -> GatekeeperResult:
        """
        Parse Llama Guard's raw completion into a structured GatekeeperResult.

        Llama Guard emits one of:
            "safe"
            "unsafe\\nS2"
            "unsafe\\nS11"

        We lowercase + strip before checking, then preserve the original case
        for the raw_output field (useful for audit logs).

        Args:
            raw: The raw string from choices[0].message.content.

        Returns:
            GatekeeperResult with verdict and extracted category code.
        """
        normalised = raw.strip().lower()

        if normalised == "safe" or normalised.startswith("safe"):
            return GatekeeperResult(verdict="safe", category=None, raw_output=raw)

        # Extract category code if present (e.g. "unsafe\nS2" → "S2")
        category: str | None = None
        lines = raw.strip().splitlines()
        if len(lines) >= 2:
            # The second line is the category code; uppercase it for consistency.
            category = lines[1].strip().upper()

        return GatekeeperResult(
            verdict="unsafe",
            category=category,
            raw_output=raw,
        )


# ---------------------------------------------------------------------------
# Singleton accessor — populated by FastAPI lifespan, consumed by routers.
# ---------------------------------------------------------------------------

_llm_service: LLMService | None = None


def set_llm_service(service: LLMService) -> None:
    """
    Register the application-wide LLMService instance.

    Called exactly once inside FastAPI's lifespan context manager during startup,
    after the httpx.AsyncClient has been created.

    Args:
        service: A fully initialized LLMService instance.
    """
    global _llm_service
    _llm_service = service
    logger.info("[LLMService] Singleton registered successfully.")


def get_llm_service() -> LLMService:
    """
    Retrieve the application-wide LLMService instance.

    Raises:
        RuntimeError: If called before set_llm_service() (i.e. before startup).

    Returns:
        The live LLMService singleton.
    """
    if _llm_service is None:
        raise RuntimeError(
            "LLMService has not been initialized. "
            "Ensure set_llm_service() is called inside the FastAPI lifespan."
        )
    return _llm_service

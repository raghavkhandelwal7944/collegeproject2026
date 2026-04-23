"""
Presidio scanning service for Firewall LLM — Layer 1 PII Heuristics.

Design decisions:
  - AnalyzerEngine and AnonymizerEngine are instantiated ONCE inside PresidioService.__init__()
    and reused across all requests. This eliminates the cold-start overhead (~2-4 s) that would
    occur if engines were rebuilt per-request.

  - A custom Presidio operator generates deterministic, typed hash tokens:
        Format:  <ENTITY_TYPE_xxxxxx>
        Example: <PERSON_a3f2c1>
    The 6-char hash is the first 6 hex digits of SHA-256(original_text).
    Being deterministic, the same PII value always produces the same token — which means:
        * Phase 3 Redis map: HSET firewall:session:<id> <PERSON_a3f2c1> "John Smith"
        * A repeated entity in the same prompt maps to ONE Redis key (no duplicates).
        * The entity_type prefix lets Phase 3 deserialize the correct field when restoring.

  - The module exposes a singleton accessor pattern (set_presidio_service / get_presidio_service)
    so FastAPI's lifespan injects the live instance once, and routers retrieve it without
    importing the class directly — making the service trivially mockable in unit tests.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from presidio_anonymizer.entities import \
    RecognizerResult as AnonRecognizerResult

from ..models.schemas import AnonymizedEntity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entities to scan for — extend this list in later phases as needed.
# ---------------------------------------------------------------------------
_TARGET_ENTITIES: list[str] = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
]


def _make_token(entity_type: str, original_text: str) -> str:
    """
    Build a deterministic, typed replacement token.

    The token encodes the Presidio entity type so Phase 3 can infer the
    correct Redis field name / restoration strategy without extra metadata.

    Args:
        entity_type:    Presidio label, e.g. "PERSON".
        original_text:  The raw PII string, e.g. "John Smith".

    Returns:
        A token string, e.g. "<PERSON_a3f2c1>".
    """
    short_hash = hashlib.sha256(original_text.encode()).hexdigest()[:6]
    return f"<{entity_type}_{short_hash}>"


@dataclass
class ScanResult:
    """
    The structured output of a single Presidio scan pass.

    This is an internal datatype used between the service and the router.
    It maps 1-to-1 onto ChatResponse (see models/schemas.py).

    Attributes:
        anonymized_text:  Prompt with PII replaced by hash tokens.
        entities:         One AnonymizedEntity per detected PII span.
        duration_ms:      Wall-clock time of the Presidio scan in milliseconds.
    """

    anonymized_text: str
    entities: list[AnonymizedEntity] = field(default_factory=list)
    duration_ms: float = 0.0


class PresidioService:
    """
    Wrapper around Microsoft Presidio's Analyzer and Anonymizer engines.

    Instantiate once at application startup via FastAPI's lifespan context.
    The engines are heavyweight objects; creating them per-request would add
    several seconds of latency.

    Usage (in lifespan):
        service = PresidioService()
        set_presidio_service(service)

    Usage (in router):
        result: ScanResult = get_presidio_service().scan(prompt)
    """

    def __init__(self) -> None:
        """
        Register the service without loading any models.

        spaCy en_core_web_lg is ~750 MB. Loading it eagerly at server startup
        alongside PyTorch, Redis, and the Next.js compiler exhausts RAM on
        consumer laptops and causes the OS to crash or swap heavily.

        Engines are initialised on the first scan() call (lazy loading), so
        startup is near-instant and the memory spike only happens when the
        first real request arrives — by which time all other services are
        already settled.
        """
        self._analyzer: AnalyzerEngine | None = None
        self._anonymizer: AnonymizerEngine | None = None
        logger.info(
            "[PresidioService] Registered (lazy — spaCy model loads on first scan())."
        )

    def _ensure_loaded(self) -> None:
        """Initialise Presidio engines on first use."""
        if self._analyzer is not None:
            return
        init_start = time.perf_counter()
        logger.info("[PresidioService] Loading AnalyzerEngine (spaCy NLP backend)…")
        self._analyzer = AnalyzerEngine()
        logger.info("[PresidioService] Loading AnonymizerEngine…")
        self._anonymizer = AnonymizerEngine()
        elapsed_ms = (time.perf_counter() - init_start) * 1000
        logger.info("[PresidioService] Engines ready in %.2f ms.", elapsed_ms)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, prompt: str) -> ScanResult:
        """
        Run the full Layer 1 Presidio pipeline on a raw prompt.

        Pipeline:
            1. AnalyzerEngine.analyze()  → locate PII spans + confidence scores.
            2. Build per-entity custom operator configs with deterministic tokens.
            3. AnonymizerEngine.anonymize() → replace spans in the text.
            4. Zip analyzer + anonymizer outputs → AnonymizedEntity list.

        The entire pass is timed; duration is logged at INFO level.

        Args:
            prompt: The raw user prompt string.

        Returns:
            ScanResult with the anonymized text, entity list, and timing.
        """
        scan_start = time.perf_counter()

        # Ensure engines are loaded (no-op after first call).
        self._ensure_loaded()
        assert self._analyzer is not None and self._anonymizer is not None

        # ---- Step 1: Analyze — discover PII spans ----------------------
        analyzer_results: list[RecognizerResult] = self._analyzer.analyze(
            text=prompt,
            entities=_TARGET_ENTITIES,
            language="en",
        )

        if not analyzer_results:
            duration_ms = (time.perf_counter() - scan_start) * 1000
            logger.info(
                "[PresidioService] Scan complete — no PII detected. Duration: %.2f ms.",
                duration_ms,
            )
            return ScanResult(
                anonymized_text=prompt,
                entities=[],
                duration_ms=round(duration_ms, 2),
            )

        # ---- Step 2: Build per-entity operator configs -----------------
        # We need the original text for each span to compute the deterministic hash.
        # Presidio provides start/end indices into the original prompt.
        operators: dict[str, OperatorConfig] = {}
        # Map entity_type → list of (original_text, token) for post-processing.
        # Multiple spans of the same type are handled by using the text-specific lambda.
        # We use a single "custom" operator per entity type; the lambda captures the
        # full prompt so it can slice out original text by position.

        # Build a quick span→token lookup so we can populate entities after anonymization.
        span_token_map: dict[tuple[int, int], tuple[str, str, float]] = {}
        # {(start, end): (original_text, token, score)}

        for result in analyzer_results:
            original_text = prompt[result.start : result.end]
            token = _make_token(result.entity_type, original_text)
            span_token_map[(result.start, result.end)] = (
                original_text,
                token,
                result.score,
            )

        # Build operator configs: one per entity type, lambda returns the precomputed token.
        # Because Presidio calls the lambda with the detected text as its argument,
        # we compute the token from that text directly — no closure-capture issues.
        for entity_type in _TARGET_ENTITIES:
            operators[entity_type] = OperatorConfig(
                "custom",
                {
                    # `text` here is what Presidio extracted for this span.
                    "lambda": lambda text, et=entity_type: _make_token(et, text)
                },
            )

        # ---- Step 3: Anonymize — replace spans with tokens -------------
        # Convert analyzer results to the format expected by AnonymizerEngine.
        anonymizer_results = [
            AnonRecognizerResult(
                entity_type=r.entity_type,
                start=r.start,
                end=r.end,
                score=r.score,
            )
            for r in analyzer_results
        ]

        anonymized = self._anonymizer.anonymize(
            text=prompt,
            analyzer_results=anonymizer_results,
            operators=operators,
        )

        # ---- Step 4: Build AnonymizedEntity list -----------------------
        entities: list[AnonymizedEntity] = []
        for result in analyzer_results:
            key = (result.start, result.end)
            original_text, token, score = span_token_map[key]
            entities.append(
                AnonymizedEntity(
                    original_text=original_text,
                    token=token,
                    entity_type=result.entity_type,
                    start=result.start,
                    end=result.end,
                    score=round(score, 4),
                )
            )

        # Sort entities by position for deterministic output
        entities.sort(key=lambda e: e.start)

        duration_ms = (time.perf_counter() - scan_start) * 1000
        logger.info(
            "[PresidioService] Scan complete — %d PII entity/entities detected. Duration: %.2f ms.",
            len(entities),
            duration_ms,
        )

        return ScanResult(
            anonymized_text=anonymized.text,
            entities=entities,
            duration_ms=round(duration_ms, 2),
        )


# ---------------------------------------------------------------------------
# Singleton accessor — populated by FastAPI lifespan, consumed by routers.
# ---------------------------------------------------------------------------

_presidio_service: PresidioService | None = None


def set_presidio_service(service: PresidioService) -> None:
    """
    Register the application-wide PresidioService instance.

    Called exactly once inside FastAPI's lifespan context manager during startup.

    Args:
        service: A fully initialized PresidioService instance.
    """
    global _presidio_service
    _presidio_service = service
    logger.info("[PresidioService] Singleton registered successfully.")


def get_presidio_service() -> PresidioService:
    """
    Retrieve the application-wide PresidioService instance.

    Raises:
        RuntimeError: If called before set_presidio_service() (i.e., before startup).

    Returns:
        The live PresidioService singleton.
    """
    if _presidio_service is None:
        raise RuntimeError(
            "PresidioService has not been initialized. "
            "Ensure set_presidio_service() is called inside the FastAPI lifespan."
        )
    return _presidio_service

"""
Firewall LLM — Embedding Service (Phase 3 Semantic Cache).

Loads a sentence-transformers model once at application startup and exposes
a synchronous embed() method.  sentence-transformers inference is CPU-bound
(no async benefit), so we keep it synchronous and call it directly from the
async task without an executor — acceptable because the model is small
(all-MiniLM-L6-v2, ~22 MB) and typically completes in < 5 ms on CPU.

For larger models or high-throughput production use, wrap embed() in
asyncio.get_event_loop().run_in_executor(None, self.embed, text) to avoid
blocking the event loop for extended periods.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    # Import only for type-checker; the real import is deferred to first use
    # so PyTorch DLLs are not mapped into memory at server startup.
    from sentence_transformers import \
        SentenceTransformer as _SentenceTransformerT

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Thin wrapper around a SentenceTransformer model.

    Instantiate once at application startup via FastAPI's lifespan context.
    The model is heavyweight (~22–380 MB depending on choice); creating it
    per-request would add hundreds of milliseconds of latency.

    Args:
        model_name: A sentence-transformers model identifier, e.g.
                    "all-MiniLM-L6-v2" for a fast, small CPU model.
    """

    def __init__(self, model_name: str) -> None:
        # Store the model name but do NOT load the model yet.
        # Lazy loading defers PyTorch DLL mapping (shm.dll etc.) until the
        # first actual embed() call, which prevents WinError 1455 "paging
        # file too small" failures when the OS paging file is exhausted at
        # server startup time while other services are also initialising.
        self._model_name = model_name
        self._model: "_SentenceTransformerT | None" = None
        logger.info(
            "[EmbeddingService] Registered model '%s' (lazy — loads on first embed()).",
            model_name,
        )

    def _ensure_loaded(self) -> None:
        """Load the SentenceTransformer model on first use."""
        if self._model is not None:
            return
        # Defer the heavy import here so torch DLLs are only mapped when we
        # actually need embeddings, not at application startup.
        from sentence_transformers import SentenceTransformer  # noqa: PLC0415

        init_start = time.perf_counter()
        logger.info("[EmbeddingService] Loading model '%s'…", self._model_name)
        self._model = SentenceTransformer(self._model_name, device="cpu")
        elapsed_ms = (time.perf_counter() - init_start) * 1000
        logger.info(
            "[EmbeddingService] Model '%s' ready in %.2f ms.",
            self._model_name,
            elapsed_ms,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def embed(self, text: str) -> list[float]:
        """
        Convert a text string into a dense vector embedding.

        The vector is L2-normalised by sentence-transformers (encode with
        normalize_embeddings=True), so cosine similarity is equivalent to
        a dot product — used by cosine_similarity() below.

        Args:
            text: The text to embed (prompt or cached query).

        Returns:
            A list of floats representing the embedding vector.
            Serialized to a plain list so it can be JSON-encoded for Redis.
        """
        self._ensure_loaded()
        assert self._model is not None  # guaranteed by _ensure_loaded
        vector: np.ndarray = self._model.encode(
            text,
            normalize_embeddings=True,   # unit-norm → cosine sim == dot product
            show_progress_bar=False,
        )
        return vector.tolist()

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """
        Compute cosine similarity between two embedding vectors.

        Because embed() normalises to unit length, this is equivalent to
        the dot product, which is faster than the full cosine formula.
        We use the full formula anyway for safety when inputs come from an
        external source and may not be perfectly normalised.

        Args:
            a: First embedding vector (list of floats).
            b: Second embedding vector (list of floats).

        Returns:
            Cosine similarity in the range [-1.0, 1.0].
            Values above ~0.95 indicate near-identical prompts.
        """
        va = np.array(a, dtype=np.float32)
        vb = np.array(b, dtype=np.float32)
        norm_a = np.linalg.norm(va)
        norm_b = np.linalg.norm(vb)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(va, vb) / (norm_a * norm_b))


# ---------------------------------------------------------------------------
# Singleton accessor — populated by FastAPI lifespan, consumed by services.
# ---------------------------------------------------------------------------

_embedding_service: EmbeddingService | None = None


def set_embedding_service(service: EmbeddingService) -> None:
    """
    Register the application-wide EmbeddingService instance.

    Called exactly once inside FastAPI's lifespan context manager.

    Args:
        service: A fully initialized EmbeddingService instance.
    """
    global _embedding_service
    _embedding_service = service
    logger.info("[EmbeddingService] Singleton registered.")


def get_embedding_service() -> EmbeddingService:
    """
    Retrieve the application-wide EmbeddingService instance.

    Raises:
        RuntimeError: If called before set_embedding_service().

    Returns:
        The live EmbeddingService singleton.
    """
    if _embedding_service is None:
        raise RuntimeError(
            "EmbeddingService has not been initialized. "
            "Ensure set_embedding_service() is called inside the FastAPI lifespan."
        )
    return _embedding_service

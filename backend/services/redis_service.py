"""
Firewall LLM — Redis Service (Phase 3: Token Vault + Semantic Cache).

Resilience contract
-------------------
Every public method catches redis.RedisError (and generic Exception as a
final safety net) and logs a WARNING before returning a safe default value.
This means if Redis is unreachable, crashes, or returns an unexpected error:

  * store_vault()            → no-op  (vault not written, request continues)
  * restore_tokens()         → returns the input text unchanged
  * get_cached_response()    → returns None  (treated as a cache miss)
  * store_cache_entry()      → no-op  (cache not populated, request continues)

The caller (routers/chat.py) never needs try/except around Redis calls.
The API always returns a 200 even when Redis is down.

Token Vault key schema
----------------------
  firewall:vault:{session_id}   → Redis Hash
      field = token             (e.g. "<PERSON_a3f2c1>")
      value = original_text     (e.g. "John Smith")
  TTL: token_vault_ttl_s seconds (default 3600)

Semantic Cache key schema
-------------------------
  firewall:cache:index          → Redis Set  (holds all cache-entry UUIDs)
  firewall:cache:{uuid}         → Redis String (JSON: {"embedding": [...], "response": "..."})
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import TYPE_CHECKING

import redis.asyncio as aioredis
from redis.asyncio import Redis

from .embedding_service import get_embedding_service

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Redis key prefixes — centralised so refactoring is a one-line change.
_VAULT_PREFIX = "firewall:vault:"
_CACHE_ENTRY_PREFIX = "firewall:cache:"
_CACHE_INDEX_KEY = "firewall:cache:index"


class RedisService:
    """
    Async Redis wrapper providing the Token Vault and Semantic Cache.

    The caller creates and owns the redis.asyncio.Redis client (opened in
    FastAPI lifespan, closed on shutdown via client.aclose()).  Injecting
    the client makes the service trivially mockable in unit tests.

    Args:
        client:   A connected redis.asyncio.Redis instance.
        vault_ttl_s:   Seconds before vault entries expire (default 3600).
        similarity_threshold:  Cosine threshold for a cache hit (default 0.95).
    """

    def __init__(
        self,
        client: Redis,
        vault_ttl_s: int = 3600,
        similarity_threshold: float = 0.95,
    ) -> None:
        self._client = client
        self._vault_ttl_s = vault_ttl_s
        self._similarity_threshold = similarity_threshold
        logger.info(
            "[RedisService] Initialized. Vault TTL: %ds | Cache threshold: %.2f",
            vault_ttl_s,
            similarity_threshold,
        )

    # ==================================================================
    # Token Vault
    # ==================================================================

    async def store_vault(
        self, session_id: str, token_map: dict[str, str]
    ) -> None:
        """
        Persist the token↔original mapping for a single request session.

        Stores the mapping as a Redis Hash so each token is an individual
        field — efficient for partial lookups and HDEL in Phase 4 cleanup.

        Schema:
            HSET firewall:vault:{session_id}  <token_1> <original_1>  …
            EXPIRE firewall:vault:{session_id} {ttl}

        Args:
            session_id:  Unique identifier for this request (uuid4().hex).
            token_map:   Mapping of replacement token → original PII text.
                         e.g. {"<PERSON_a3f2c1>": "John Smith", …}
        """
        if not token_map:
            # Nothing to store; skip the round-trip entirely.
            return
        try:
            key = f"{_VAULT_PREFIX}{session_id}"
            await self._client.hset(key, mapping=token_map)  # type: ignore[arg-type]
            await self._client.expire(key, self._vault_ttl_s)
            logger.debug(
                "[TokenVault] Stored %d token(s) under key '%s' (TTL %ds).",
                len(token_map),
                key,
                self._vault_ttl_s,
            )
        except Exception as exc:
            logger.warning(
                "[TokenVault] Failed to store vault entry for session '%s': %s. "
                "Continuing without vault.",
                session_id,
                exc,
            )

    async def restore_tokens(self, session_id: str, text: str) -> str:
        """
        Scan *text* for stored tokens and replace them with original values.

        Performs a simple string substitution for every token found in the
        vault for this session.  Only tokens that actually appear in *text*
        are replaced — extra vault entries are silently ignored.

        Args:
            session_id: The session identifier used in store_vault().
            text:       The LLM's raw response (contains anonymized tokens).

        Returns:
            The de-anonymized response with original PII values restored.
            Returns *text* unchanged on any Redis error.
        """
        try:
            key = f"{_VAULT_PREFIX}{session_id}"
            # HGETALL returns {bytes: bytes} when decode_responses=False,
            # or {str: str} when decode_responses=True (which we set below).
            token_map: dict[str, str] = await self._client.hgetall(key)  # type: ignore[assignment]
            if not token_map:
                logger.debug(
                    "[TokenVault] No vault entries for session '%s' "
                    "(expired or never stored).",
                    session_id,
                )
                return text

            restored = text
            replacements_made = 0
            for token, original in token_map.items():
                if token in restored:
                    restored = restored.replace(token, original)
                    replacements_made += 1

            logger.debug(
                "[TokenVault] De-anonymized %d/%d token(s) for session '%s'.",
                replacements_made,
                len(token_map),
                session_id,
            )
            return restored

        except Exception as exc:
            logger.warning(
                "[TokenVault] Failed to restore tokens for session '%s': %s. "
                "Returning anonymized text as-is.",
                session_id,
                exc,
            )
            return text

    # ==================================================================
    # Semantic Cache
    # ==================================================================

    async def get_cached_response(
        self,
        embedding: list[float],
        threshold: float | None = None,
    ) -> str | None:
        """
        Search the semantic cache for a response to a similar prior prompt.

        Algorithm:
          1. SMEMBERS firewall:cache:index  → set of cache-entry UUIDs
          2. For each UUID: GET firewall:cache:{uuid} → JSON blob
          3. Deserialise embedding, compute cosine similarity
          4. Return the first response whose similarity ≥ threshold

        The O(n) scan is acceptable for a college project scale.
        For production, replace with Redis Stack's VSIM or a vector DB.

        Args:
            embedding:  The dense vector of the incoming prompt.
            threshold:  Override the service-level similarity threshold.

        Returns:
            Cached LLM response string, or None on a miss / Redis error.
        """
        effective_threshold = threshold if threshold is not None else self._similarity_threshold
        try:
            cache_keys: set[str] = await self._client.smembers(_CACHE_INDEX_KEY)  # type: ignore[assignment]
            if not cache_keys:
                return None

            embed_svc = get_embedding_service()
            best_score = 0.0
            best_response: str | None = None

            for key in cache_keys:
                raw = await self._client.get(key)  # type: ignore[arg-type]
                if raw is None:
                    # Entry expired between SMEMBERS and GET — stale index ref.
                    continue
                try:
                    entry: dict = json.loads(raw)
                    cached_embedding: list[float] = entry["embedding"]
                    score = embed_svc.cosine_similarity(embedding, cached_embedding)
                    if score > best_score:
                        best_score = score
                        best_response = entry["response"]
                except (json.JSONDecodeError, KeyError, TypeError) as parse_err:
                    logger.warning(
                        "[SemanticCache] Malformed cache entry at key '%s': %s — skipping.",
                        key,
                        parse_err,
                    )
                    continue

            if best_response is not None and best_score >= effective_threshold:
                logger.info(
                    "[SemanticCache] HIT — similarity=%.4f (threshold=%.2f).",
                    best_score,
                    effective_threshold,
                )
                return best_response

            logger.debug(
                "[SemanticCache] MISS — best similarity=%.4f (threshold=%.2f).",
                best_score,
                effective_threshold,
            )
            return None

        except Exception as exc:
            logger.warning(
                "[SemanticCache] Cache lookup failed: %s. Treating as cache miss.",
                exc,
            )
            return None

    async def store_cache_entry(
        self, embedding: list[float], response: str
    ) -> None:
        """
        Persist a new prompt embedding + LLM response in the semantic cache.

        Each entry is stored as a JSON string under a UUID key with no TTL
        (cached responses are valid indefinitely for the same model/config;
        flush the cache manually or add a TTL here when rotating models).

        The entry UUID is also added to the cache index set so
        get_cached_response() can enumerate all entries without a SCAN.

        Args:
            embedding:  The dense vector of the prompt (from EmbeddingService).
            response:   The raw (anonymized) LLM response to cache.
        """
        try:
            entry_id = uuid.uuid4().hex
            entry_key = f"{_CACHE_ENTRY_PREFIX}{entry_id}"
            payload = json.dumps(
                {"embedding": embedding, "response": response},
                # Compact separators reduce storage size.
                separators=(",", ":"),
            )
            await self._client.set(entry_key, payload)
            await self._client.sadd(_CACHE_INDEX_KEY, entry_key)  # type: ignore[arg-type]
            logger.debug(
                "[SemanticCache] Stored new entry '%s' (%d chars).",
                entry_key,
                len(response),
            )
        except Exception as exc:
            logger.warning(
                "[SemanticCache] Failed to store cache entry: %s. "
                "Continuing without caching.",
                exc,
            )


# ---------------------------------------------------------------------------
# Singleton accessors — both populated by FastAPI lifespan.
#
# Raw-client accessor (used by health checks and the lifespan shutdown):
#     client = get_redis_client()   → redis.asyncio.Redis | None
#
# High-level service accessor (used by chat pipeline routers):
#     if (redis_svc := get_redis_service()):
#         await redis_svc.store_vault(...)
#
# Both return None gracefully when Redis is unavailable, so callers never
# need to guard against AttributeError — a simple None check suffices.
# ---------------------------------------------------------------------------

# ── Raw async client ────────────────────────────────────────────────────────
_redis_client: Redis | None = None


def set_redis_client(client: Redis) -> None:
    """
    Register the application-wide raw async Redis client.

    Called once during FastAPI lifespan startup, *before*
    set_redis_service(), so health endpoints can reach Redis independently
    of whether the full RedisService layer was also initialised.

    Args:
        client: A connected redis.asyncio.Redis instance.
    """
    global _redis_client
    _redis_client = client
    logger.info("[RedisClient] Raw async client registered.")


def get_redis_client() -> Redis | None:
    """
    Retrieve the application-wide raw async Redis client.

    Returns:
        The live redis.asyncio.Redis singleton, or None if Redis is
        unavailable (startup ping failed or lifespan has not run yet).
    """
    return _redis_client


# ── High-level service ───────────────────────────────────────────────────────
_redis_service: RedisService | None = None


def set_redis_service(service: RedisService) -> None:
    """
    Register the application-wide RedisService instance.

    Args:
        service: A fully initialized RedisService instance.
    """
    global _redis_service
    _redis_service = service
    logger.info("[RedisService] Singleton registered.")


def get_redis_service() -> RedisService | None:
    """
    Retrieve the application-wide RedisService instance.

    Unlike other service getters, this returns None instead of raising when
    Redis is unavailable.  This is deliberate: the entire Redis layer is
    optional and the application must degrade gracefully without it.

    Returns:
        The live RedisService singleton, or None if not initialized.
    """
    return _redis_service

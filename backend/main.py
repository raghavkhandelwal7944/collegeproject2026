"""
Firewall LLM — FastAPI application entry point.

Startup sequence (via lifespan):
    1. Initialize MySQL / MongoDB schema (init_db).
    2. Warm up PresidioService — loads spaCy NLP model once so the first
       request does not incur a cold-start penalty.

All chat pipeline logic lives in routers/chat.py (POST /api/v1/chat).
Auth utilities live in dependencies.py to avoid circular imports.
"""

import logging
import time
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import AsyncGenerator

import httpx
import redis.asyncio as aioredis
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from .config import get_settings
from .database import (create_user, get_recent_logs, get_session_messages,
                       get_stats, get_user, get_user_conversations,
                       get_user_policies, init_db, list_user_sessions)
from .dependencies import (ACCESS_TOKEN_EXPIRE_MINUTES, create_access_token,
                           get_current_user, get_password_hash,
                           verify_password)
from .routers.chat import router as chat_router
from .routers.policies import router as policies_router
from .services.embedding_service import EmbeddingService, set_embedding_service
from .services.llm_service import LLMService, set_llm_service
from .services.presidio_service import PresidioService, set_presidio_service
from .services.redis_service import (RedisService, get_redis_client,
                                     set_redis_client, set_redis_service)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

load_dotenv()

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager.

    Startup:
        - Initializes the MySQL and MongoDB schemas (idempotent).
        - Instantiates PresidioService, which loads the spaCy NLP model.
          Done here so the model is resident before the first request arrives.

    Shutdown:
        - Logs a clean shutdown message.
    """
    # ---- Database ----
    logger.info("[Startup] Initializing database schema…")
    try:
        init_db()
        logger.info("[Startup] Database schema ready.")
    except Exception as exc:
        logger.critical("[Startup] Database initialization failed: %s", exc)

    # ---- Presidio — warm up once, reuse across all requests ----
    logger.info("[Startup] Warming up Presidio engines (spaCy NLP model loading)…")
    presidio_init_start = time.perf_counter()
    try:
        presidio_service = PresidioService()
        set_presidio_service(presidio_service)
        elapsed_ms = (time.perf_counter() - presidio_init_start) * 1000
        logger.info("[Startup] Presidio engines initialized in %.2f ms.", elapsed_ms)
    except Exception as exc:
        logger.critical("[Startup] Failed to initialize Presidio: %s", exc)

    # ---- LLM Service — one shared AsyncClient for all inference calls ----
    # The client is created here so its connection pool (and its cleanup) is
    # owned by the lifespan, not by individual requests.
    settings = get_settings()
    logger.info(
        "[Startup] Creating httpx.AsyncClient → inference server: %s",
        settings.inference_server_url,
    )
    http_client = httpx.AsyncClient()
    try:
        llm_service = LLMService(client=http_client, settings=settings)
        set_llm_service(llm_service)
        logger.info("[Startup] LLMService ready.")
    except Exception as exc:
        logger.critical("[Startup] Failed to initialize LLMService: %s", exc)

    # ---- Embedding Service — load sentence-transformers model once ----
    emb_init_start = time.perf_counter()
    logger.info(
        "[Startup] Loading embedding model '%s'…", settings.embedding_model_name
    )
    try:
        embedding_service = EmbeddingService(settings.embedding_model_name)
        set_embedding_service(embedding_service)
        elapsed_ms = (time.perf_counter() - emb_init_start) * 1000
        logger.info("[Startup] EmbeddingService ready in %.2f ms.", elapsed_ms)
    except Exception as exc:
        logger.critical("[Startup] Failed to initialize EmbeddingService: %s", exc)

    # ---- Redis Service — async connection pool ----
    # Failure here is WARNING (not CRITICAL): the app runs without Redis,
    # just without the Token Vault and Semantic Cache.
    redis_client: aioredis.Redis | None = None
    logger.info("[Startup] Connecting to Redis at '%s'…", settings.redis_url)
    try:
        redis_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,   # all keys/values are str, not bytes
            encoding="utf-8",
        )
        # Ping to verify connectivity before declaring it ready.
        await redis_client.ping()
        # Register the raw client *first* so the health endpoint works even
        # if RedisService construction somehow raises below.
        set_redis_client(redis_client)
        redis_service = RedisService(
            client=redis_client,
            vault_ttl_s=settings.token_vault_ttl_s,
            similarity_threshold=settings.cache_similarity_threshold,
        )
        set_redis_service(redis_service)
        logger.info("[Startup] RedisService ready. Token Vault + Semantic Cache enabled.")
    except Exception as exc:
        logger.warning(
            "[Startup] Redis unavailable (%s). "
            "Token Vault and Semantic Cache are DISABLED — all other features work normally.",
            exc,
        )

    yield  # Application is now serving requests

    # ---- Shutdown — drain connection pools cleanly ----
    logger.info("[Shutdown] Closing httpx.AsyncClient connection pool…")
    await http_client.aclose()
    if redis_client is not None:
        logger.info("[Shutdown] Closing Redis connection pool…")
        await redis_client.aclose()
    logger.info("[Shutdown] Firewall LLM shutting down gracefully.")


app = FastAPI(
    title="Firewall LLM",
    description=(
        "Enterprise-grade Local LLM Firewall — intercepts, sanitizes, and evaluates "
        "prompts before they reach a local Large Language Model or a database."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---- CORS ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers ----
# Phase 1: Layer 1 Presidio pipeline → POST /api/v1/chat
app.include_router(chat_router)
app.include_router(policies_router)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
class UserCreate(BaseModel):
    username: str
    password: str
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None

@app.post("/register", status_code=status.HTTP_201_CREATED, tags=["auth"])
def register(user: UserCreate) -> dict:
    """Register a new user account."""
    hashed_password = get_password_hash(user.password)
    if not create_user(user.username, hashed_password, user.first_name, user.last_name, user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered.",
        )
    return {"message": "User created successfully."}


@app.post("/token", tags=["auth"])
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> dict:
    """Exchange username + password for a Bearer JWT."""
    user = get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.get("/health/redis", tags=["health"])
async def health_redis() -> dict:
    """
    Verify end-to-end Redis connectivity with a write-then-read round-trip.

    Procedure:
        1. Resolve the raw async Redis client from the lifespan singleton.
        2. SET a temporary key with a 10-second TTL.
        3. GET the key back and assert the value matches.
        4. DEL the key immediately — no leftover test debris.

    Returns:
        200 {"status": "healthy",   "redis": "connected"}   on success.
        503 {"detail": "<reason>"}                           on any failure.

    Note:
        This endpoint is intentionally *unauthenticated* so infrastructure
        monitoring tools (e.g. Docker health checks, load balancer probes)
        can ping it without needing a JWT.
    """
    _PROBE_KEY   = "firewall:health:probe"
    _PROBE_VALUE = "ok"
    _PROBE_TTL   = 10  # seconds — auto-expires if DEL is somehow skipped

    client = get_redis_client()

    if client is None:
        # Redis was down at startup (or lifespan hasn't run — dev anomaly).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis client not initialised. Check startup logs.",
        )

    try:
        # Write probe key.
        await client.set(_PROBE_KEY, _PROBE_VALUE, ex=_PROBE_TTL)

        # Read it back and verify.
        returned: str | None = await client.get(_PROBE_KEY)  # type: ignore[assignment]
        if returned != _PROBE_VALUE:
            raise ValueError(
                f"Round-trip mismatch: wrote '{_PROBE_VALUE}', got '{returned}'."
            )

        # Clean up immediately — don't wait for TTL.
        await client.delete(_PROBE_KEY)

        logger.info("[Health] Redis probe: PASS.")
        return {"status": "healthy", "redis": "connected"}

    except Exception as exc:
        logger.warning("[Health] Redis probe FAILED: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Redis unavailable: {exc}",
        )


# ---------------------------------------------------------------------------
# Monitoring / utility endpoints
# ---------------------------------------------------------------------------

@app.get("/activity_logs", tags=["monitoring"])
def activity_logs(current_user: dict = Depends(get_current_user)) -> list:
    """Return the 20 most recent firewall audit log entries."""
    return get_recent_logs(limit=20)


@app.get("/stats", tags=["monitoring"])
def stats(current_user: dict = Depends(get_current_user)) -> dict:
    """Return aggregate request statistics (total, blocked, %)."""
    return get_stats()


@app.get("/history", tags=["monitoring"])
def history(current_user: dict = Depends(get_current_user)) -> list:
    """Return the authenticated user's conversation history."""
    return get_user_conversations(current_user["username"])


@app.get("/chat/sessions", tags=["monitoring"])
def chat_sessions(current_user: dict = Depends(get_current_user)) -> list:
    """Return all chat sessions for the authenticated user."""
    return list_user_sessions(current_user["username"])


@app.get("/history/{session_id}", tags=["monitoring"])
def session_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> list:
    """Return all messages for a specific chat session."""
    return get_session_messages(current_user["username"], session_id)


# ---------------------------------------------------------------------------
# Dev runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logger.info("[Startup] Starting Firewall LLM server…")
    uvicorn.run(app, host="0.0.0.0", port=8000)

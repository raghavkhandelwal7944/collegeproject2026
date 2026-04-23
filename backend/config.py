"""
Firewall LLM — centralised application configuration.

All values are read from environment variables (or a .env file at the project
root).  Pydantic-Settings validates types at startup, so a missing or
malformed INFERENCE_SERVER_URL fails loudly before any request is served.

Override any setting by exporting the corresponding env-var, e.g.:
    export INFERENCE_SERVER_URL=http://remotehost:8080/v1
    export MAIN_MODEL_NAME=llama-3-70b-instruct

The module-level get_settings() is lru_cache'd so the .env file is parsed
exactly once per process, not on every import or request.
"""

from __future__ import annotations

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application-wide settings sourced from environment variables / .env.

    Attributes:
        inference_server_url:   Base URL of the OpenAI-compatible local inference
                                server (Ollama, vLLM, LM Studio, etc.).
                                Must NOT have a trailing slash.
        gatekeeper_model_name:  Model id served by the inference server that acts
                                as the Layer 2 safety gatekeeper (Llama Guard).
        main_model_name:        Model id for the Layer 3 main instruction LLM.
        llm_request_timeout_s:  Wall-clock seconds before an inference call is
                                abandoned and a 503 is returned to the caller.
                                Tune upward for slower hardware.
    """

    # -----------------------------------------------------------------
    # Inference server
    # -----------------------------------------------------------------
    inference_server_url: str = "http://localhost:11434/v1"

    # -----------------------------------------------------------------
    # Model identifiers
    # -----------------------------------------------------------------
    gatekeeper_model_name: str = "mistral:latest"
    main_model_name: str = "mistral:latest"

    # -----------------------------------------------------------------
    # HTTP client
    # -----------------------------------------------------------------
    llm_request_timeout_s: float = 300.0

    # -----------------------------------------------------------------
    # Phase 3 — Redis state store
    # -----------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # Seconds before a token-vault entry expires. Shorter = more secure;
    # longer = allows very slow LLM conversations to still de-anonymize.
    token_vault_ttl_s: int = 3600

    # Cosine similarity threshold for a semantic cache hit (0.0 – 1.0).
    # 0.95 means prompts must be almost identical to reuse a cached answer.
    cache_similarity_threshold: float = 0.95

    # sentence-transformers model name. "all-MiniLM-L6-v2" is ~22 MB and
    # runs entirely on CPU; switch to a larger model for better recall.
    embedding_model_name: str = "all-MiniLM-L6-v2"

    # -----------------------------------------------------------------
    # Pydantic-settings config
    # -----------------------------------------------------------------
    model_config = SettingsConfigDict(
        # Look for a .env file relative to the working directory (project root).
        env_file=".env",
        # Silently ignore extra keys in .env so other services' vars don't
        # cause a validation error.
        extra="ignore",
        # Case-insensitive env lookup: INFERENCE_SERVER_URL == inference_server_url
        case_sensitive=False,
    )


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached Settings singleton.

    The lru_cache means .env is read and validated only once per process
    lifetime.  Tests can clear the cache with get_settings.cache_clear().
    """
    return Settings()

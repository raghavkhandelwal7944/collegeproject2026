"""
GET  /api/v1/policies — return the calling user's policy flags from MySQL.
PUT  /api/v1/policies — persist updated policy flags to MySQL.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..database import get_user_policies, set_user_policies
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["policies"])


class PolicyPayload(BaseModel):
    aggressive_pii: bool
    semantic_cache: bool
    code_block: bool


@router.get("/policies", response_model=PolicyPayload)
def read_policies(current_user: dict = Depends(get_current_user)) -> PolicyPayload:
    """Return this user's saved policy flags."""
    data = get_user_policies(current_user["username"])
    return PolicyPayload(**data)


@router.put("/policies", response_model=PolicyPayload)
def update_policies(
    payload: PolicyPayload,
    current_user: dict = Depends(get_current_user),
) -> PolicyPayload:
    """Persist updated policy flags and echo them back."""
    set_user_policies(
        current_user["username"],
        aggressive_pii=payload.aggressive_pii,
        semantic_cache=payload.semantic_cache,
        code_block=payload.code_block,
    )
    logger.info(
        "[Policies] '%s' updated: aggressive_pii=%s semantic_cache=%s code_block=%s",
        current_user["username"],
        payload.aggressive_pii,
        payload.semantic_cache,
        payload.code_block,
    )
    return payload

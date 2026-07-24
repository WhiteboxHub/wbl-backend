"""FastAPI Routes for LLM Provider Registry and Dynamic Model Discovery."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from fapi.utils.auth_dependencies import get_current_user
from fapi.db.models import AuthUserORM
from fapi.utils.llm_provider_registry import provider_registry

router = APIRouter(prefix="/llm", tags=["LLM Providers"])


class DetectAndValidateIn(BaseModel):
    api_key: str = Field(..., description="API key to detect provider and fetch models")
    provider_name: Optional[str] = Field(None, description="Optional provider override")


class DetectAndValidateOut(BaseModel):
    detected_provider: Optional[str] = None
    display_name: Optional[str] = None
    status: str
    message: str
    available_models: List[str] = []
    default_model: Optional[str] = None


class ProviderMetadataOut(BaseModel):
    id: str
    label: str
    key_prefixes: List[str] = []


@router.get("/providers", response_model=List[ProviderMetadataOut])
def get_all_providers(
    current_user: AuthUserORM = Depends(get_current_user),
):
    """List metadata and key prefixes for all registered LLM providers."""
    return provider_registry.list_providers_metadata()


@router.post("/providers/detect-and-validate", response_model=DetectAndValidateOut)
def detect_and_validate_key(
    body: DetectAndValidateIn,
    current_user: AuthUserORM = Depends(get_current_user),
):
    """
    Auto-detect provider from API key pattern, test live provider connectivity,
    and return dynamically discovered models list.
    """
    result = provider_registry.detect_and_validate(
        body.api_key, override_provider_id=body.provider_name
    )
    return DetectAndValidateOut(**result)


@router.get("/providers/{provider_id}/models")
def get_provider_models(
    provider_id: str,
    current_user: AuthUserORM = Depends(get_current_user),
):
    """Get static/fallback models for a registered provider by ID."""
    provider = provider_registry.get_provider_by_id(provider_id)
    if not provider:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Provider '{provider_id}' not found in registry",
        )
    return {
        "provider_id": provider.provider_id,
        "display_name": provider.display_name,
        "key_prefixes": provider.key_prefixes,
    }

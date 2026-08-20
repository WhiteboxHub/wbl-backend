import logging
from fastapi import APIRouter
from fapi.ai_prep.api.media_routes import router as media_router
from fapi.ai_prep.api.assessment_routes import router as assessment_router

logger = logging.getLogger("wbl.ai_prep.router")

router = APIRouter(prefix="/ai-prep", tags=["AIPrep"])

# Include sub-routers
router.include_router(media_router)
router.include_router(assessment_router)


@router.get("/health")
async def aiprep_health():
    """Health check endpoint for AIPrep module."""
    from fapi.ai_prep.services.storage_service import get_storage_service
    from fapi.ai_prep.services.youtube_service import get_youtube_service

    storage = get_storage_service()
    youtube = get_youtube_service()

    return {
        "status": "ok",
        "storage_backend": storage.__class__.__name__,
        "youtube_configured": youtube.is_configured(),
        "module": "ai_prep"
    }

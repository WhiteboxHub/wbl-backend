import os
import logging
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger(__name__)

OBSERVABILITY_URL = os.getenv("OBSERVABILITY_SERVICE_URL", "http://localhost:8001/api/events")


async def emit_pipeline_metric(
    assessment_id: int,
    stage: str,
    status: str = "SUCCESS",
    duration_ms: Optional[int] = None,
    candidate_id: Optional[int] = None,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Non-blocking, fire-and-forget metric emitter to wbl-observability.
    If the observability service is unreachable or slow, this will NEVER crash
    or slow down the assessment pipeline execution.
    """
    payload = {
        "assessment_id": assessment_id,
        "candidate_id": candidate_id,
        "stage": stage.upper(),
        "status": status.upper(),
        "duration_ms": duration_ms,
        "message": message,
        "metadata": metadata or {}
    }

    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            response = await client.post(OBSERVABILITY_URL, json=payload)
            return response.status_code == 201
    except Exception as exc:
        logger.debug("Observability service not reachable (%s): %s", OBSERVABILITY_URL, exc)
        return False

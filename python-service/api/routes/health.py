"""
Health check routes.
"""

import os
import sys
import platform
from datetime import datetime
from typing import Dict, Any

from fastapi import APIRouter

from ..models import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns basic service status and environment information.
    """
    return HealthResponse(
        status="healthy",
        service="groundwater-mapper-api",
        version="2.0.0",
        timestamp=datetime.utcnow().isoformat(),
        environment={
            "python_version": sys.version,
            "platform": platform.platform(),
            "gee_available": os.getenv("EARTHENGINE_TOKEN") is not None,
            "llama_cloud_key": bool(os.getenv("LLAMA_CLOUD_API_KEY"))
        },
        llamaparse=bool(os.getenv("LLAMA_CLOUD_API_KEY")),
        gee=os.getenv("EARTHENGINE_TOKEN") is not None
    )


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check endpoint.
    
    Verifies that all required services are available.
    """
    checks = {
        "api": True,
        "excel_parser": True,
        "coordinate_converter": True,
        "contour_generator": True
    }
    
    # Check optional services
    gee_available = False
    try:
        import ee
        gee_available = True
    except ImportError:
        pass
    
    checks["google_earth_engine"] = gee_available
    
    llama_available = bool(os.getenv("LLAMA_CLOUD_API_KEY"))
    checks["llama_parse"] = llama_available
    
    all_ready = all(checks.values())
    
    return {
        "ready": all_ready,
        "checks": checks
    }


@router.get("/live")
async def liveness_check() -> Dict[str, str]:
    """
    Liveness check endpoint.
    
    Simple ping endpoint for Kubernetes liveness probes.
    """
    return {"status": "alive"}

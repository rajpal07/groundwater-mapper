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


def check_gee_available() -> bool:
    """
    Check if Google Earth Engine is available.
    
    Checks for GEE in order:
    1. EARTHENGINE_TOKEN environment variable (JSON string)
    2. Secret file at /etc/secrets/gee-service-account.json (or path in GEE_SECRET_FILE env var)
    3. Any .json file in /etc/secrets/ (for Render secret files)
    4. Standard GEE credentials file ~/.config/gcloud/application_default_credentials.json
    """
    # Check 1: Environment variable
    if os.getenv("EARTHENGINE_TOKEN"):
        return True
    
    # Check 2: Secret file (for Render deployment)
    secret_file = os.environ.get('GEE_SECRET_FILE', '/etc/secrets/gee-service-account.json')
    if os.path.exists(secret_file):
        return True
    
    # Check 3: Auto-detect any JSON file in /etc/secrets/ (for Render)
    secrets_dir = '/etc/secrets'
    if os.path.exists(secrets_dir):
        try:
            for filename in os.listdir(secrets_dir):
                if filename.endswith('.json'):
                    # Found a JSON secret file - likely GEE credentials
                    return True
        except Exception as e:
            print(f"Warning: Error scanning secrets directory: {e}")
    
    # Check 4: Standard GCP credentials file
    gcp_creds = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
    if os.path.exists(gcp_creds):
        return True
    
    return False


# Helper function for GEE check used across modules
HAS_GEE = check_gee_available()


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
            "gee_available": check_gee_available(),
            "llama_cloud_key": bool(os.getenv("LLAMA_CLOUD_API_KEY"))
        },
        llamaparse=bool(os.getenv("LLAMA_CLOUD_API_KEY")),
        gee=check_gee_available()
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

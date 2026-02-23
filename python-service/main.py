"""
Groundwater Mapper API - FastAPI Application

A modern Python API for groundwater data processing and visualization.
Provides endpoints for Excel file parsing, coordinate conversion, and contour map generation.

Features:
- Excel file parsing with LlamaParse AI integration
- UTM to Lat/Lon coordinate conversion with Australian zone auto-detection
- Contour map generation with multiple interpolation methods
- Multi-layer aquifer visualization
- Smart Excel export with conditional formatting
- Firebase JWT authentication
- OpenAPI documentation (auto-generated)

Author: Groundwater Mapper Team
Version: 2.0.0
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    # Try to load from various locations
    env_paths = [
        os.path.join(os.path.dirname(__file__), '.env'),
        os.path.join(os.path.dirname(__file__), '.env.local'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.local'),
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print(f"Loaded environment from {env_path}")
            break
except ImportError:
    print("dotenv not installed, using system environment variables")

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

# Import routes
from api.routes import health, preview, process, export_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment configuration
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = ENVIRONMENT == "development"
API_VERSION = "2.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(f"Starting Groundwater Mapper API v{API_VERSION}")
    logger.info(f"Environment: {ENVIRONMENT}")
    
    # Check for required environment variables
    required_vars = ["LLAMA_CLOUD_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")
        logger.warning("Some features may not work correctly")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Groundwater Mapper API")


# Create FastAPI application
app = FastAPI(
    title="Groundwater Mapper API",
    description="""
## Groundwater Mapper API

A comprehensive API for groundwater data processing and visualization.

### Features

- **Excel Parsing**: Parse Excel files with AI-powered LlamaParse integration
- **Coordinate Conversion**: Convert UTM to Lat/Lon with Australian zone auto-detection
- **Contour Generation**: Generate contour maps with multiple interpolation methods
- **Multi-layer Visualization**: Visualize multiple aquifer layers on a single map
- **Smart Export**: Export Excel files with conditional formatting based on thresholds

### Authentication

Most endpoints support optional Firebase JWT authentication. Include the `Authorization: Bearer <token>` header for authenticated requests.

### Coordinate Systems

The API automatically detects and handles:
- UTM coordinates (Australian zones 49-56)
- Latitude/Longitude (decimal degrees)
- Custom coordinate systems

### Interpolation Methods

Supported interpolation methods:
- `linear`: Fast, good for smooth data
- `cubic`: Smoother, good for continuous data
- `nearest`: Fast, good for discrete data
    """,
    version=API_VERSION,
    docs_url="/docs" if DEBUG else None,
    redoc_url="/redoc" if DEBUG else None,
    lifespan=lifespan
)

# Configure CORS
import re
# Default origins include localhost and all groundwater-mapper Vercel deployments (including preview branches)
allowed_origins_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,https://groundwater-mapperpushed.vercel.app,https://groundwater-mapper-pushed.vercel.app").split(",")
allowed_origins = []
allowed_origin_regexes = []

for origin in allowed_origins_raw:
    origin = origin.strip()
    if not origin:
        continue
    if "*" in origin:
        # Convert wildcard to a regex block, e.g. https://*-app.vercel.app -> ^https://.*\-app\.vercel\.app$
        regex_pattern = "^" + re.escape(origin).replace("\\*", ".*") + "$"
        allowed_origin_regexes.append(regex_pattern)
    else:
        allowed_origins.append(origin)

allow_origin_regex = None
if allowed_origin_regexes:
    allow_origin_regex = "|".join(allowed_origin_regexes)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Validation error",
            "errors": errors
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error" if not DEBUG else str(exc),
            "status_code": 500
        }
    )


# Include routers
app.include_router(health.router)
app.include_router(preview.router)
app.include_router(process.router)
app.include_router(export_router)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint.
    
    Returns basic API information and available endpoints.
    """
    return {
        "name": "Groundwater Mapper API",
        "version": API_VERSION,
        "status": "operational",
        "environment": ENVIRONMENT,
        "documentation": {
            "swagger": "/docs" if DEBUG else "disabled",
            "redoc": "/redoc" if DEBUG else "disabled"
        },
        "endpoints": {
            "health": "/health",
            "preview": "/preview",
            "process": "/process",
            "export": "/export/smart-excel"
        }
    }


# Debug endpoint (only in development)
if DEBUG:
    @app.get("/debug/env", tags=["Debug"])
    async def debug_env():
        """Show environment configuration (development only)."""
        return {
            "environment": ENVIRONMENT,
            "debug": DEBUG,
            "api_version": API_VERSION,
            "allowed_origins": allowed_origins,
            "llama_cloud_api_key_set": bool(os.getenv("LLAMA_CLOUD_API_KEY")),
            "firebase_project_id": os.getenv("NEXT_PUBLIC_FIREBASE_PROJECT_ID", "not set")
        }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 5000))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=DEBUG,
        log_level="info"
    )

"""
Pydantic models for request/response validation.
Provides type-safe API contracts with automatic validation.
"""

from typing import Optional, List, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime


# ============================================
# Common Response Models
# ============================================

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    service: str = "groundwater-mapper-api"
    version: str = "2.0.0"
    timestamp: Optional[str] = None
    environment: Optional[Dict[str, Any]] = None
    llamaparse: bool = False
    gee: bool = False


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    available_parameters: Optional[List[str]] = None
    hint: Optional[str] = None


class APIInfoResponse(BaseModel):
    """Root endpoint response."""
    message: str = "Groundwater Mapper API"
    version: str = "2.0.0"
    documentation: str = "/docs"
    endpoints: List[str] = ["/health", "/debug", "/preview", "/process"]


class DebugResponse(BaseModel):
    """Debug endpoint response."""
    gee_available: bool
    gee_initialized: bool
    llamaparse_available: bool
    environment: Optional[Dict[str, Any]] = None


# ============================================
# Preview Endpoint Models
# ============================================

class ColumnStats(BaseModel):
    """Statistics for a numeric column."""
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    count: Optional[int] = None
    std: Optional[float] = None


class ColumnInfo(BaseModel):
    """Information about a column in the Excel file."""
    name: str
    type: str = "unknown"
    is_numeric: bool = False
    sample_values: List[Any] = []
    stats: Optional[ColumnStats] = None


class CoordinateSystemInfo(BaseModel):
    """Information about detected coordinate system."""
    type: str = "unknown"
    utm_zone: Optional[int] = None
    epsg_code: Optional[str] = None
    easting_column: Optional[str] = None
    northing_column: Optional[str] = None
    latitude_column: Optional[str] = None
    longitude_column: Optional[str] = None
    bounds: Optional[Dict[str, float]] = None


class PreviewResponse(BaseModel):
    """Response for file preview endpoint."""
    filename: str
    sheet_names: List[str] = []
    current_sheet: Optional[str] = None
    row_count: int = 0
    column_count: int = 0
    columns: List[ColumnInfo] = []
    coordinate_system: Optional[CoordinateSystemInfo] = None
    numeric_columns: List[str] = []
    preview_data: List[Dict[str, Any]] = []


# ============================================
# Process Endpoint Models
# ============================================

class ProcessRequest(BaseModel):
    """Request for processing Excel file (JSON mode)."""
    file_content: str = Field(..., description="Base64 encoded Excel file content")
    parameter: str = Field(..., description="Column name to visualize")
    colormap: str = Field(default="viridis", description="Matplotlib colormap name")
    show_contours: bool = Field(default=True, description="Show contour fill")
    show_scatter: bool = Field(default=True, description="Show scatter points")
    use_llamaparse: bool = Field(default=True, description="Use LlamaParse for parsing")
    title: Optional[str] = Field(default=None, description="Custom plot title")
    resolution: int = Field(default=100, ge=50, le=500, description="Grid resolution")


class AquiferLayer(BaseModel):
    """Detected aquifer layer."""
    name: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    point_count: int = 0


class ContourData(BaseModel):
    """Contour data for the map legend."""
    levels: List[float]
    colors: List[str]


class Statistics(BaseModel):
    """Statistics for plotted parameter."""
    min: float
    max: float
    mean: float
    std: float
    count: int


class ProcessResponse(BaseModel):
    """Response for process endpoint."""
    success: bool = True
    message: str = "Map generated successfully"
    filename: Optional[str] = None
    parameter: str
    colormap: str = "viridis"
    row_count: int = 0
    coordinate_system: Optional[CoordinateSystemInfo] = None
    map_html: Optional[str] = None
    contour_data: Optional[ContourData] = None
    statistics: Optional[Statistics] = None
    image_base64: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    aquifer_layers: Optional[List[AquiferLayer]] = None
    # Legacy fields for backward compatibility
    image: Optional[str] = None
    parse_method: Optional[str] = None
    coord_system: Optional[str] = None
    bounds: Optional[Dict[str, float]] = None
    gee_available: bool = False
    interpolation_method: str = "linear"
    min_value: Optional[float] = None
    max_value: Optional[float] = None


# ============================================
# Coordinate System Models
# ============================================

class CoordinateSystem(str, Enum):
    """Coordinate system types."""
    UNKNOWN = "unknown"
    LATLON = "latlon"
    UTM = "utm"


class CoordinateInfo(BaseModel):
    """Information about detected coordinate system."""
    system_type: str = Field(..., description="latlon or utm")
    utm_zone: Optional[int] = None
    epsg_code: Optional[str] = None
    bounds: Optional[Dict[str, float]] = None


# ============================================
# Smart Export Models (Phase 3)
# ============================================

class ThresholdConfig(BaseModel):
    """Threshold configuration for smart export."""
    column: str
    operator: str = Field(..., description="gt, lt, gte, lte, eq, neq, between")
    value: float
    value2: Optional[float] = Field(default=None, description="Second value for 'between' operator")
    highlight_color: str = Field(default="FF0000", description="Hex color for highlighting")


class SmartExportRequest(BaseModel):
    """Request for smart Excel export."""
    file_content: str = Field(..., description="Base64 encoded Excel file content")
    thresholds: List[ThresholdConfig]
    output_format: str = Field(default="xlsx", description="xlsx or csv")
    include_summary: bool = Field(default=True, description="Include summary sheet")
    conditional_formatting: bool = Field(default=True, description="Apply conditional formatting")


class SmartExportResponse(BaseModel):
    """Response for smart Excel export."""
    success: bool = True
    message: str = "Excel file generated successfully"
    filename: str
    parameter: str
    thresholds: List[float] = []
    statistics: Optional[Dict[str, Any]] = None
    excel_base64: Optional[str] = None
    # Legacy fields
    file_content: Optional[str] = None
    rows_processed: int = 0
    rows_flagged: int = 0
    thresholds_applied: List[str] = []
    summary: Optional[Dict[str, Any]] = None


# ============================================
# Aquifer Analysis Models (Phase 3)
# ============================================

class AquiferLayerInfo(BaseModel):
    """Detected aquifer layer."""
    name: str
    depth_min: Optional[float] = None
    depth_max: Optional[float] = None
    well_count: int
    avg_value: float
    parameter: str


class AquiferAnalysisResponse(BaseModel):
    """Response for aquifer stratification analysis."""
    layers: List[AquiferLayerInfo]
    total_wells: int
    parameter: str
    stratification_detected: bool
    recommended_visualization: str = "multi-layer"


# ============================================
# Multi-layer Map Models (Phase 3)
# ============================================

class MultiLayerMapRequest(BaseModel):
    """Request for multi-layer map generation."""
    file_content: str
    parameter: str
    layer_column: str = Field(..., description="Column to use for layer separation (e.g., 'Aquifer', 'Depth')")
    colormap_per_layer: Optional[Dict[str, str]] = Field(default=None, description="Colormap for each layer")
    show_legend: bool = Field(default=True)
    opacity: float = Field(default=0.7, ge=0.1, le=1.0)


class MultiLayerProcessResponse(BaseModel):
    """Response for multi-layer map generation."""
    success: bool = True
    map_html: Optional[str] = None
    bounds: Optional[Dict[str, float]] = None
    layers: Optional[List[AquiferLayer]] = None
    statistics: Optional[Dict[str, Statistics]] = None
    
    # Legacy compatibility
    image: Optional[str] = None
    parameter: str = ""
    layer_names: List[str] = []
    layer_count: int = 0
    legend: Dict[str, str] = {}


# ============================================
# Interactive Map Models
# ============================================

class InteractiveMapRequest(BaseModel):
    """Request for interactive HTML map generation."""
    file_content: str = Field(..., description="Base64 encoded Excel file content")
    parameter: str = Field(..., description="Column name to visualize")
    colormap: str = Field(default="viridis", description="Matplotlib colormap name")
    show_contours: bool = Field(default=True, description="Show contour fill overlay")
    show_wells: bool = Field(default=True, description="Show well point markers")
    show_legend: bool = Field(default=True, description="Show interactive legend")
    show_compass: bool = Field(default=True, description="Show draggable compass")
    show_controls: bool = Field(default=True, description="Show map controls (reset, snapshot)")
    use_llamaparse: bool = Field(default=True, description="Use LlamaParse for parsing")
    title: Optional[str] = Field(default=None, description="Custom map title")
    resolution: int = Field(default=100, ge=50, le=500, description="Grid resolution")
    legend_label: str = Field(default="Groundwater Elevation (mAHD)", description="Legend label")
    opacity: float = Field(default=0.7, ge=0.1, le=1.0, description="Contour overlay opacity")


class WellPoint(BaseModel):
    """A well point on the map."""
    latitude: float
    longitude: float
    value: float
    label: Optional[str] = None


class InteractiveMapResponse(BaseModel):
    """Response for interactive HTML map generation."""
    success: bool = True
    message: str = "Interactive map generated successfully"
    filename: Optional[str] = None
    parameter: str
    colormap: str = "viridis"
    row_count: int = 0
    coordinate_system: Optional[CoordinateSystemInfo] = None
    html_content: Optional[str] = None
    well_points: List[WellPoint] = []
    bounds: Optional[Dict[str, float]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    legend_colors: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None

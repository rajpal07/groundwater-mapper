"""
Map processing routes.
"""

import logging
from typing import Optional, List

import pandas as pd
import numpy as np

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse

from ..models import (
    ProcessResponse, CoordinateSystemInfo, AquiferLayer,
    InteractiveMapRequest, InteractiveMapResponse, WellPoint,
    ContourData, Statistics, MultiLayerProcessResponse
)
from ..services.excel_parser import excel_parser
from ..services.coordinate_converter import coordinate_converter
from ..services.contour_generator import contour_generator
from ..services.interactive_map_generator import InteractiveMapGeneratorService
from ..auth import get_current_user_optional

logger = logging.getLogger(__name__)

# Initialize services
interactive_map_generator = InteractiveMapGeneratorService()

router = APIRouter(prefix="/process", tags=["Processing"])


@router.post("", response_model=ProcessResponse)
async def process_excel(
    file: UploadFile = File(..., description="Excel file to process"),
    parameter: str = Form(..., description="Column name for the parameter to visualize"),
    sheet_name: Optional[str] = Form(None, description="Sheet name to process"),
    colormap: str = Form("viridis", description="Matplotlib colormap name"),
    easting_col: Optional[str] = Form(None, description="Easting/X column name"),
    northing_col: Optional[str] = Form(None, description="Northing/Y column name"),
    lat_col: Optional[str] = Form(None, description="Latitude column name"),
    lon_col: Optional[str] = Form(None, description="Longitude column name"),
    show_contours: bool = Form(True, description="Show filled contours"),
    show_scatter: bool = Form(True, description="Show scatter points"),
    interpolation_method: str = Form("linear", description="Interpolation method: linear, cubic, nearest"),
    resolution: int = Form(100, description="Grid resolution for interpolation"),
    user: Optional[dict] = Depends(get_current_user_optional)
) -> ProcessResponse:
    """
    Process an Excel file and generate a contour map.
    
    This endpoint:
    1. Parses the Excel file
    2. Detects or uses provided coordinate columns
    3. Converts UTM to Lat/Lon if needed
    4. Generates a contour plot
    5. Returns the base64-encoded image and metadata
    
    The coordinate system is auto-detected if not specified.
    Australian UTM zones (49-56) are automatically detected.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename = file.filename.lower()
    if not (filename.endswith('.xlsx') or filename.endswith('.xls') or filename.endswith('.csv')):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Only .xlsx, .xls, and .csv files are supported."
        )
    
    # Read file content
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    
    # Parse Excel file
    try:
        df = excel_parser.parse_file(content, filename=file.filename, sheet_name=sheet_name)
    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        raise HTTPException(status_code=422, detail=f"Error parsing Excel file: {str(e)}")
    
    # Validate parameter column exists
    if parameter not in df.columns:
        raise HTTPException(
            status_code=400, 
            detail=f"Parameter column '{parameter}' not found. Available columns: {list(df.columns)}"
        )
    
    # Detect or validate coordinate system
    coord_system_info = coordinate_converter.detect_coordinate_system(df, easting_col, northing_col)
    
    # Determine coordinate columns
    lat_col_name = None
    lon_col_name = None
    
    if coord_system_info.type == "utm":
        # Use provided columns or detected ones
        east_col = easting_col or coord_system_info.easting_column
        north_col = northing_col or coord_system_info.northing_column
        
        if not east_col or not north_col:
            raise HTTPException(
                status_code=400,
                detail="Could not determine UTM coordinate columns. Please specify easting_col and northing_col."
            )
        
        if east_col not in df.columns or north_col not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Coordinate columns not found. Easting: {east_col}, Northing: {north_col}"
            )
        
        # Convert UTM to Lat/Lon
        try:
            df = coordinate_converter.convert_to_latlon(
                df, 
                easting_col=east_col,
                northing_col=north_col,
                zone=coord_system_info.utm_zone
            )
            lat_col_name = "Latitude"
            lon_col_name = "Longitude"
        except Exception as e:
            logger.error(f"Error converting coordinates: {e}")
            raise HTTPException(status_code=422, detail=f"Error converting coordinates: {str(e)}")
    
    elif coord_system_info.type == "latlon":
        # Use Lat/Lon columns
        lat_col_name = lat_col or coord_system_info.latitude_column
        lon_col_name = lon_col or coord_system_info.longitude_column
        
        if not lat_col_name or not lon_col_name:
            raise HTTPException(
                status_code=400,
                detail="Could not determine Lat/Lon coordinate columns. Please specify lat_col and lon_col."
            )
        
        if lat_col_name not in df.columns or lon_col_name not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Coordinate columns not found. Lat: {lat_col_name}, Lon: {lon_col_name}"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Could not detect coordinate system. Please specify coordinate columns."
        )
    
    # Determine easting/northing column names for the interactive map generator
    east_col_for_map = None
    north_col_for_map = None
    if coord_system_info.type == "utm":
        east_col_for_map = easting_col or coord_system_info.easting_column
        north_col_for_map = northing_col or coord_system_info.northing_column

    # Generate interactive html map
    try:
        html_content, well_points, bounds, legend_colors, coord_info = interactive_map_generator.create_interactive_map_from_dataframe(
            df=df,
            parameter=parameter,
            easting_col=east_col_for_map,
            northing_col=north_col_for_map,
            lat_col=lat_col_name,
            lon_col=lon_col_name,
            colormap=colormap,
            show_contours=show_contours,
            show_wells=show_scatter,
            show_legend=True,
            show_compass=True,
            show_controls=True,
            interpolation_method=interpolation_method,
            resolution=resolution
        )
    except ValueError as e:
        logger.error(f"Error generating interactive map: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating interactive map: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating interactive map: {str(e)}")
    
    # Calculate statistics
    values = pd.to_numeric(df[parameter], errors='coerce').dropna()
    stats = Statistics(
        min=float(values.min()),
        max=float(values.max()),
        mean=float(values.mean()),
        std=float(values.std()),
        count=int(len(values))
    )
    
    # Format contour data
    contour_data = ContourData(
        levels=[float(values.min()), float(values.mean()), float(values.max())],
        colors=[legend_colors['low'], legend_colors['mid'], legend_colors['high']]
    )

    # Detect aquifer layers (if applicable)
    aquifer_layers = detect_aquifer_layers(df, parameter)
    
    # Build coordinate system info for response
    coord_system_response = CoordinateSystemInfo(
        type=coord_system_info.type,
        utm_zone=coord_system_info.utm_zone,
        epsg_code=coord_system_info.epsg_code,
        easting_column=coord_system_info.easting_column,
        northing_column=coord_system_info.northing_column,
        latitude_column=coord_system_info.latitude_column,
        longitude_column=coord_system_info.longitude_column,
        bounds=coord_system_info.bounds
    )
    
    return ProcessResponse(
        success=True,
        message="Map generated successfully",
        filename=file.filename,
        parameter=parameter,
        colormap=colormap,
        row_count=len(df),
        coordinate_system=coord_system_response,
        map_html=html_content,
        contour_data=contour_data,
        statistics=stats,
        bounds=bounds,
        aquifer_layers=aquifer_layers if aquifer_layers else None
    )


@router.post("/multi-layer", response_model=MultiLayerProcessResponse)
async def process_multi_layer(
    file: UploadFile = File(..., description="Excel file to process"),
    parameter: str = Form(..., description="Column name for the parameter to visualize"),
    layer_column: str = Form(..., description="Column name for layer separation (e.g., aquifer depth)"),
    sheet_name: Optional[str] = Form(None, description="Sheet name to process"),
    colormap: str = Form("viridis", description="Base colormap name"),
    user: Optional[dict] = Depends(get_current_user_optional)
) -> MultiLayerProcessResponse:
    """
    Process an Excel file and generate a multi-layer contour map.
    
    This endpoint creates a single map showing multiple aquifer layers
    with different colormaps for each layer.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename = file.filename.lower()
    if not (filename.endswith('.xlsx') or filename.endswith('.xls') or filename.endswith('.csv')):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Only .xlsx, .xls, and .csv files are supported."
        )
    
    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    
    # Parse Excel file
    try:
        df = excel_parser.parse_file(content, filename=file.filename, sheet_name=sheet_name)
    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        raise HTTPException(status_code=422, detail=f"Error parsing Excel file: {str(e)}")
    
    # Validate columns
    if parameter not in df.columns:
        raise HTTPException(
            status_code=400, 
            detail=f"Parameter column '{parameter}' not found."
        )
    
    if layer_column not in df.columns:
        raise HTTPException(
            status_code=400, 
            detail=f"Layer column '{layer_column}' not found."
        )
    
    # Detect coordinate system
    coord_system_info = coordinate_converter.detect_coordinate_system(df)
    
    # Determine coordinate columns
    lat_col_name = None
    lon_col_name = None
    
    if coord_system_info.type == "utm":
        east_col = coord_system_info.easting_column
        north_col = coord_system_info.northing_column
        
        try:
            df = coordinate_converter.convert_to_latlon(
                df, 
                easting_col=east_col,
                northing_col=north_col,
                zone=coord_system_info.utm_zone
            )
            lat_col_name = "Latitude"
            lon_col_name = "Longitude"
        except Exception as e:
            logger.error(f"Error converting coordinates: {e}")
            raise HTTPException(status_code=422, detail=f"Error converting coordinates: {str(e)}")
    elif coord_system_info.type == "latlon":
        lat_col_name = coord_system_info.latitude_column
        lon_col_name = coord_system_info.longitude_column
    else:
        raise HTTPException(
            status_code=400,
            detail="Could not detect coordinate system. Please specify coordinate columns."
        )
    
    # Determine easting/northing column names for the interactive map generator
    east_col_for_map = None
    north_col_for_map = None
    if coord_system_info.type == "utm":
        east_col_for_map = coord_system_info.easting_column
        north_col_for_map = coord_system_info.northing_column

    # Generate multi-layer map
    try:
        html_content, bounds, legend_info, coord_info = interactive_map_generator.create_interactive_multi_layer_map_from_dataframe(
            df=df,
            parameter=parameter,
            layer_column=layer_column,
            easting_col=east_col_for_map,
            northing_col=north_col_for_map,
            lat_col=lat_col_name,
            lon_col=lon_col_name,
            colormap_per_layer=None, 
            show_legend=True,
            show_compass=True,
            show_controls=True
        )
    except ValueError as e:
        logger.error(f"Error generating multi-layer map: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating multi-layer map: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating multi-layer map: {str(e)}")

    # Calculate statistics for each layer
    layer_names = df[layer_column].dropna().unique()
    layer_stats = {}
    for layer in layer_names:
        layer_df = df[df[layer_column] == layer]
        values = pd.to_numeric(layer_df[parameter], errors='coerce').dropna()
        if len(values) > 0:
            layer_stats[str(layer)] = Statistics(
                min=float(values.min()),
                max=float(values.max()),
                mean=float(values.mean()),
                std=float(values.std()),
                count=int(len(values))
            )
    
    return MultiLayerProcessResponse(
        success=True,
        map_html=html_content,
        bounds=bounds,
        statistics=layer_stats,
        parameter=parameter,
        layer_names=[str(layer) for layer in layer_names],
        layer_count=len(layer_names),
        legend=legend_info
    )


def detect_aquifer_layers(df: pd.DataFrame, parameter: str) -> Optional[List[AquiferLayer]]:
    """
    Detect aquifer layers based on parameter value clustering.
    
    Uses simple statistical analysis to identify potential aquifer zones.
    """
    # Get parameter values
    values = pd.to_numeric(df[parameter], errors='coerce').dropna()
    
    if len(values) < 10:
        return None
    
    # Simple layer detection based on value ranges
    # This is a basic implementation - can be enhanced with clustering algorithms
    try:
        # Calculate percentiles for layer boundaries
        percentiles = [0, 25, 50, 75, 100]
        bounds = np.percentile(values, percentiles)
        
        layers = []
        for i in range(len(bounds) - 1):
            lower = bounds[i]
            upper = bounds[i + 1]
            
            # Count points in this layer
            mask = (values >= lower) & (values <= upper)
            count = mask.sum()
            
            if count > 0:
                layers.append(AquiferLayer(
                    name=f"Layer {i + 1}",
                    min_value=float(lower),
                    max_value=float(upper),
                    mean_value=float(values[mask].mean()),
                    point_count=int(count)
                ))
        
        return layers if layers else None
    
    except Exception as e:
        logger.warning(f"Error detecting aquifer layers: {e}")
        return None


# Initialize interactive map generator service
interactive_map_generator = InteractiveMapGeneratorService()


@router.post("/interactive", response_model=InteractiveMapResponse)
async def process_interactive(
    file: UploadFile = File(..., description="Excel file to process"),
    parameter: str = Form(..., description="Column name for the parameter to visualize"),
    sheet_name: Optional[str] = Form(None, description="Sheet name to process"),
    colormap: str = Form("viridis", description="Matplotlib colormap name"),
    easting_col: Optional[str] = Form(None, description="Easting/X column name"),
    northing_col: Optional[str] = Form(None, description="Northing/Y column name"),
    lat_col: Optional[str] = Form(None, description="Latitude column name"),
    lon_col: Optional[str] = Form(None, description="Longitude column name"),
    show_contours: bool = Form(True, description="Show contour fill overlay"),
    show_wells: bool = Form(True, description="Show well point markers"),
    show_legend: bool = Form(True, description="Show interactive legend"),
    show_compass: bool = Form(True, description="Show draggable compass"),
    show_controls: bool = Form(True, description="Show map controls (reset, snapshot)"),
    interpolation_method: str = Form("linear", description="Interpolation method: linear, cubic, nearest"),
    resolution: int = Form(100, description="Grid resolution for interpolation"),
    user: Optional[dict] = Depends(get_current_user_optional)
) -> InteractiveMapResponse:
    """
    Process an Excel file and generate an interactive HTML map.
    
    This endpoint:
    1. Parses the Excel file
    2. Detects or uses provided coordinate columns
    3. Converts UTM to Lat/Lon if needed
    4. Generates an interactive folium-based HTML map with:
       - Contour overlay
       - Well point markers with tooltips
       - Draggable compass
       - Resizable legend with gradient
       - Snapshot functionality
       - Professional footer for reports
    
    The coordinate system is auto-detected if not specified.
    Australian UTM zones (49-56) are automatically detected.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename = file.filename.lower()
    if not (filename.endswith('.xlsx') or filename.endswith('.xls') or filename.endswith('.csv')):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Only .xlsx, .xls, and .csv files are supported."
        )
    
    # Read file content
    try:
        content = await file.read()
        if len(content) == 0:
            raise HTTPException(status_code=400, detail="Empty file uploaded")
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    
    # Parse Excel file
    try:
        df = excel_parser.parse_file(content, filename=file.filename, sheet_name=sheet_name)
    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        raise HTTPException(status_code=422, detail=f"Error parsing Excel file: {str(e)}")
    
    # Validate parameter column exists
    if parameter not in df.columns:
        raise HTTPException(
            status_code=400, 
            detail=f"Parameter column '{parameter}' not found. Available columns: {list(df.columns)}"
        )
    
    # Detect or validate coordinate system
    coord_system_info = coordinate_converter.detect_coordinate_system(df, easting_col, northing_col)
    
    # Determine coordinate columns
    lat_col_name = None
    lon_col_name = None
    
    if coord_system_info.type == "utm":
        # Use provided columns or detected ones
        east_col = easting_col or coord_system_info.easting_column
        north_col = northing_col or coord_system_info.northing_column
        
        if not east_col or not north_col:
            raise HTTPException(
                status_code=400,
                detail="Could not determine UTM coordinate columns. Please specify easting_col and northing_col."
            )
        
        if east_col not in df.columns or north_col not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Coordinate columns not found. Easting: {east_col}, Northing: {north_col}"
            )
        
        # Convert UTM to Lat/Lon
        try:
            df = coordinate_converter.convert_to_latlon(
                df, 
                easting_col=east_col,
                northing_col=north_col,
                zone=coord_system_info.utm_zone
            )
            lat_col_name = "Latitude"
            lon_col_name = "Longitude"
        except Exception as e:
            logger.error(f"Error converting coordinates: {e}")
            raise HTTPException(status_code=422, detail=f"Error converting coordinates: {str(e)}")
    
    elif coord_system_info.type == "latlon":
        # Use Lat/Lon columns
        lat_col_name = lat_col or coord_system_info.latitude_column
        lon_col_name = lon_col or coord_system_info.longitude_column
        
        if not lat_col_name or not lon_col_name:
            raise HTTPException(
                status_code=400,
                detail="Could not determine Lat/Lon coordinate columns. Please specify lat_col and lon_col."
            )
        
        if lat_col_name not in df.columns or lon_col_name not in df.columns:
            raise HTTPException(
                status_code=400,
                detail=f"Coordinate columns not found. Lat: {lat_col_name}, Lon: {lon_col_name}"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="Could not detect coordinate system. Please specify coordinate columns."
        )
    
    # Determine easting/northing column names for the interactive map generator
    east_col_for_map = None
    north_col_for_map = None
    if coord_system_info.type == "utm":
        east_col_for_map = easting_col or coord_system_info.easting_column
        north_col_for_map = northing_col or coord_system_info.northing_column
    
    # Generate interactive map
    try:
        html_content, well_points, bounds, legend_colors, coord_info = interactive_map_generator.create_interactive_map_from_dataframe(
            df=df,
            parameter=parameter,
            easting_col=east_col_for_map,
            northing_col=north_col_for_map,
            lat_col=lat_col_name,
            lon_col=lon_col_name,
            colormap=colormap,
            show_contours=show_contours,
            show_wells=show_wells,
            show_legend=show_legend,
            show_compass=show_compass,
            show_controls=show_controls,
            interpolation_method=interpolation_method,
            resolution=resolution
        )
    except ValueError as e:
        logger.error(f"Error generating interactive map: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating interactive map: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating interactive map: {str(e)}")
    
    # Build coordinate system info for response
    coord_system_response = CoordinateSystemInfo(
        type=coord_system_info.type,
        utm_zone=coord_system_info.utm_zone,
        epsg_code=coord_system_info.epsg_code,
        easting_column=coord_system_info.easting_column,
        northing_column=coord_system_info.northing_column,
        latitude_column=coord_system_info.latitude_column,
        longitude_column=coord_system_info.longitude_column,
        bounds=coord_system_info.bounds
    )
    
    return InteractiveMapResponse(
        success=True,
        message="Interactive map generated successfully",
        filename=file.filename,
        parameter=parameter,
        colormap=colormap,
        row_count=len(df),
        coordinate_system=coord_system_response,
        html_content=html_content,
        well_points=well_points,
        bounds=bounds,
        legend_colors=legend_colors
    )

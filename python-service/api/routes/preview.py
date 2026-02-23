"""
Excel file preview routes.
"""

import logging
from typing import Optional, List

import pandas as pd

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse

from ..models import PreviewResponse, ColumnInfo, ColumnStats, CoordinateSystemInfo
from ..services.excel_parser import excel_parser
from ..services.coordinate_converter import coordinate_converter
from ..auth import get_current_user_optional

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preview", tags=["Preview"])


@router.post("", response_model=PreviewResponse)
async def preview_excel(
    file: UploadFile = File(..., description="Excel file to preview"),
    sheet_name: Optional[str] = Form(None, description="Sheet name to preview (optional)"),
    use_llamaparse: Optional[str] = Form("true", description="Whether to use LlamaParse (default true)"),
    user: Optional[dict] = Depends(get_current_user_optional)
) -> PreviewResponse:
    """
    Preview an Excel file.
    
    Parses the Excel file and returns:
    - Sheet names
    - Column names and types
    - Sample data
    - Detected coordinate system
    - Numeric column statistics
    
    This endpoint is used to help users select the correct columns for map generation.
    
    OPTIMIZATION: If no sheet_name is provided for a multi-sheet Excel file,
    only sheet names are returned (without processing full data) for faster response.
    Full data is returned only when sheet_name is explicitly provided.
    """
    # Convert use_llamaparse string to boolean
    use_llamaparse_bool = use_llamaparse.lower() in ('true', '1', 'yes') if use_llamaparse else False
    
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename = file.filename.lower()
    is_csv = filename.endswith('.csv')
    is_excel = filename.endswith('.xlsx') or filename.endswith('.xls')
    
    if not (is_excel or is_csv):
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
    
    # Get sheet names first (fast operation)
    sheet_names = []
    if is_excel:
        sheet_names = excel_parser.get_sheet_names(content)
    
    # OPTIMIZATION: For multi-sheet Excel files without sheet_name, return only sheet names
    # This is a lightweight response that doesn't parse the actual data
    is_multi_sheet = is_excel and len(sheet_names) > 1
    needs_full_data = sheet_name is not None or is_csv or not is_multi_sheet
    
    if is_multi_sheet and not needs_full_data:
        # Return only sheet names without processing data (fast response for initial upload)
        logger.info(f"Multi-sheet Excel detected ({len(sheet_names)} sheets), returning sheet list only")
        return PreviewResponse(
            filename=file.filename,
            sheet_names=sheet_names,
            current_sheet=None,
            row_count=0,
            column_count=0,
            columns=[],
            coordinate_system=None,
            numeric_columns=[],
            preview_data=[],
            needs_sheet_selection=True  # Signal frontend that user needs to select a sheet
        )
    
    # For CSV, single-sheet Excel, or when sheet_name is provided, process full data
    use_llamaparse_for_parsing = sheet_name is not None and use_llamaparse_bool
    
    try:
        df = excel_parser.parse_file(content, filename=file.filename, sheet_name=sheet_name, use_llamaparse=use_llamaparse_for_parsing)
    except Exception as e:
        logger.error(f"Error parsing Excel file: {e}")
        raise HTTPException(status_code=422, detail=f"Error parsing Excel file: {str(e)}")
    
    # Get sheet names
    sheet_names = excel_parser.get_sheet_names(content)
    
    # Get column information
    columns = []
    for col in df.columns:
        col_type = str(df[col].dtype)
        sample_values = df[col].dropna().head(5).tolist()
        
        # Check if numeric
        is_numeric = pd.api.types.is_numeric_dtype(df[col])
        
        # Get stats for numeric columns
        stats = None
        if is_numeric:
            stats_dict = excel_parser.get_column_stats(df, col)
            stats = ColumnStats(
                min=stats_dict.get("min"),
                max=stats_dict.get("max"),
                mean=stats_dict.get("mean"),
                count=stats_dict.get("count"),
                std=stats_dict.get("std")
            )
        
        columns.append(ColumnInfo(
            name=col,
            type=col_type,
            is_numeric=is_numeric,
            sample_values=[str(v) for v in sample_values],
            stats=stats
        ))
    
    # Detect coordinate system
    coord_system_info = coordinate_converter.detect_coordinate_system(df)
    coord_system = CoordinateSystemInfo(
        type=coord_system_info.type,
        utm_zone=coord_system_info.utm_zone,
        epsg_code=coord_system_info.epsg_code,
        easting_column=coord_system_info.easting_column,
        northing_column=coord_system_info.northing_column,
        latitude_column=coord_system_info.latitude_column,
        longitude_column=coord_system_info.longitude_column,
        bounds=coord_system_info.bounds
    )
    
    # Get numeric columns
    numeric_columns = excel_parser.get_numeric_columns(df)
    
    # Get preview data (first 10 rows)
    preview_data = excel_parser.get_preview_data(df, rows=10)
    
    return PreviewResponse(
        filename=file.filename,
        sheet_names=sheet_names,
        current_sheet=sheet_name or sheet_names[0] if sheet_names else None,
        row_count=len(df),
        column_count=len(df.columns),
        columns=columns,
        coordinate_system=coord_system,
        numeric_columns=numeric_columns,
        preview_data=preview_data,
        needs_sheet_selection=False
    )


@router.post("/sheets")
async def list_sheets(
    file: UploadFile = File(..., description="Excel file to analyze"),
    user: Optional[dict] = Depends(get_current_user_optional)
) -> dict:
    """
    List all sheets in an Excel file.
    
    Returns a list of sheet names with row and column counts for each.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    filename = file.filename.lower()
    if not (filename.endswith('.xlsx') or filename.endswith('.xls')):
        raise HTTPException(
            status_code=400, 
            detail="Invalid file type. Only .xlsx and .xls files are supported."
        )
    
    # Read file content
    try:
        content = await file.read()
    except Exception as e:
        logger.error(f"Error reading file: {e}")
        raise HTTPException(status_code=400, detail=f"Error reading file: {str(e)}")
    
    # Get sheet names
    try:
        sheet_names = excel_parser.get_sheet_names(content)
    except Exception as e:
        logger.error(f"Error reading sheets: {e}")
        raise HTTPException(status_code=422, detail=f"Error reading sheets: {str(e)}")
    
    # Get info for each sheet
    sheets_info = []
    for sheet in sheet_names:
        try:
            df = excel_parser.parse_file(content, filename=file.filename, sheet_name=sheet)
            sheets_info.append({
                "name": sheet,
                "rows": len(df),
                "columns": len(df.columns)
            })
        except Exception as e:
            logger.warning(f"Error reading sheet {sheet}: {e}")
            sheets_info.append({
                "name": sheet,
                "rows": 0,
                "columns": 0,
                "error": str(e)
            })
    
    return {
        "filename": file.filename,
        "sheets": sheets_info
    }

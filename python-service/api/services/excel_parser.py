"""
Excel parsing service with LlamaParse and pandas fallback.
Handles file parsing, sheet detection, and data extraction.
"""

import os
import io
import base64
import logging
import tempfile
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

# LlamaParse availability check
LLAMAPARSE_AVAILABLE = False
try:
    from llama_parse import LlamaParse
    LLAMAPARSE_AVAILABLE = True
    logger.info("LlamaParse is available")
except ImportError:
    logger.warning("LlamaParse not installed, using pandas fallback")


class ExcelParserService:
    """Service for parsing Excel files with multiple backends."""
    
    def __init__(self):
        self.llama_cloud_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        self.llamaparse_available = LLAMAPARSE_AVAILABLE and bool(self.llama_cloud_api_key)
    
    def parse_file(
        self,
        file_content: bytes,
        filename: str = "uploaded.xlsx",
        use_llamaparse: bool = True,
        sheet_name: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Parse an Excel file and return a DataFrame.
        
        Args:
            file_content: Raw file bytes
            filename: Original filename for extension detection
            use_llamaparse: Whether to try LlamaParse (default True for AI-powered parsing)
            sheet_name: Specific sheet to parse (None for first sheet)
            
        Returns:
            DataFrame with parsed data
        """
        # Get file extension
        ext = filename.lower().split('.')[-1] if '.' in filename else 'xlsx'
        
        # Try LlamaParse first if requested and available
        if use_llamaparse and self.llamaparse_available and ext in ['xlsx', 'xls']:
            try:
                df = self._parse_with_llamaparse(file_content, filename)
                if df is not None and not df.empty:
                    logger.info(f"Successfully parsed with LlamaParse: {len(df)} rows")
                    return df
            except Exception as e:
                logger.warning(f"LlamaParse failed, falling back to pandas: {e}")
        
        # Fallback to pandas
        df = self._parse_with_pandas(file_content, ext, sheet_name)
        logger.info(f"Parsed with pandas: {len(df)} rows, {len(df.columns)} columns")
        
        return df
    
    def _parse_with_llamaparse(
        self,
        file_content: bytes,
        filename: str
    ) -> Optional[pd.DataFrame]:
        """Parse Excel file using LlamaParse.
        
        Note: LlamaParse is disabled by default due to async compatibility issues.
        Use pandas fallback which works reliably.
        """
        # LlamaParse has async compatibility issues with FastAPI
        # The sync load_data method may not exist in newer versions
        # Fallback to pandas is reliable and fast
        return None
    
    def _parse_with_pandas(
        self,
        file_content: bytes,
        ext: str,
        sheet_name: Optional[str] = None
    ) -> pd.DataFrame:
        """Parse Excel file using pandas."""
        try:
            if ext in ['xlsx', 'xls']:
                # Read all sheet names first
                xl_file = pd.ExcelFile(io.BytesIO(file_content))
                # sheet_names is already a list in newer pandas versions
                sheets = xl_file.sheet_names if isinstance(xl_file.sheet_names, list) else xl_file.sheet_names.tolist()
                
                # Read the specified sheet or first sheet
                target_sheet = sheet_name if sheet_name in sheets else sheets[0] if sheets else 0
                df = pd.read_excel(io.BytesIO(file_content), sheet_name=target_sheet)
            elif ext == 'csv':
                df = pd.read_csv(io.BytesIO(file_content))
            else:
                # Try Excel first, then CSV
                try:
                    df = pd.read_excel(io.BytesIO(file_content))
                except:
                    df = pd.read_csv(io.BytesIO(file_content))
            
            # Clean column names
            df.columns = [str(col).strip() for col in df.columns]
            
            # Remove completely empty rows
            df = df.dropna(how='all')
            
            return df
            
        except Exception as e:
            logger.error(f"Pandas parsing failed: {e}")
            raise ValueError(f"Failed to parse file: {str(e)}")
    
    def get_sheet_names(self, file_content: bytes) -> List[str]:
        """Get list of sheet names from an Excel file."""
        try:
            xl_file = pd.ExcelFile(io.BytesIO(file_content))
            # sheet_names is already a list in newer pandas versions
            return xl_file.sheet_names if isinstance(xl_file.sheet_names, list) else xl_file.sheet_names.tolist()
        except Exception as e:
            logger.error(f"Failed to get sheet names: {e}")
            return []
    
    def get_column_stats(self, df: pd.DataFrame, column: str) -> Dict[str, Any]:
        """Get statistics for a numeric column."""
        if column not in df.columns:
            return {}
        
        series = pd.to_numeric(df[column], errors='coerce')
        
        return {
            "min": float(series.min()) if not series.isna().all() else None,
            "max": float(series.max()) if not series.isna().all() else None,
            "mean": float(series.mean()) if not series.isna().all() else None,
            "count": int(series.count()),
            "std": float(series.std()) if not series.isna().all() else None
        }
    
    def get_numeric_columns(self, df: pd.DataFrame) -> List[str]:
        """Get list of numeric columns in DataFrame."""
        numeric_cols = []
        for col in df.columns:
            series = pd.to_numeric(df[col], errors='coerce')
            if series.count() > 0:
                numeric_cols.append(col)
        return numeric_cols
    
    def get_preview_data(self, df: pd.DataFrame, rows: int = 10) -> List[Dict[str, Any]]:
        """Get preview data as list of dictionaries."""
        preview_df = df.head(rows)
        # Replace NaN with None for JSON serialization
        return preview_df.where(pd.notnull(preview_df), None).to_dict('records')


# Global service instance
excel_parser = ExcelParserService()


def parse_excel_file(
    file_content: bytes,
    filename: str = "uploaded.xlsx",
    use_llamaparse: bool = True,
    sheet_name: Optional[str] = None
) -> pd.DataFrame:
    """
    Convenience function to parse Excel files.
    
    Args:
        file_content: Raw file bytes
        filename: Original filename
        use_llamaparse: Whether to try LlamaParse (default True)
        sheet_name: Specific sheet to parse
        
    Returns:
        DataFrame with parsed data
    """
    return excel_parser.parse_file(file_content, filename, use_llamaparse, sheet_name)


def decode_base64_file(base64_content: str) -> bytes:
    """Decode base64 encoded file content."""
    # Handle data URL prefix
    if ',' in base64_content:
        base64_content = base64_content.split(',')[1]
    return base64.b64decode(base64_content)

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
                df = self._parse_with_llamaparse(file_content, filename, sheet_name)
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
        filename: str,
        sheet_name: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """Parse Excel file using LlamaParse - matching Streamlit's approach."""
        if not self.llamaparse_available:
            return None
        
        # Save to temp file for LlamaParse
        ext = filename.lower().split('.')[-1] if '.' in filename else 'xlsx'
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # Use SimpleDirectoryReader with LlamaParse - same as Streamlit
            from llama_index.core import SimpleDirectoryReader
            
            parser = LlamaParse(
                api_key=self.llama_cloud_api_key,
                result_type="markdown",  # Use markdown for better table structure
                verbose=False
            )
            
            # Use file_extractor like Streamlit does
            file_extractor = {".xlsx": parser}
            reader = SimpleDirectoryReader(input_files=[tmp_path], file_extractor=file_extractor)
            documents = reader.load_data()
            
            if not documents:
                return None
            
            # Get the markdown text
            markdown_text = "\n\n".join([doc.text for doc in documents])
            
            # Parse markdown tables - similar to Streamlit's smart_extract_sheet
            df = self._parse_markdown_tables(markdown_text)
            
            if df is not None and not df.empty:
                logger.info(f"LlamaParse successfully parsed: {len(df)} rows, {len(df.columns)} columns")
                return df
            
            return None
            
        except Exception as e:
            logger.warning(f"LlamaParse parsing failed: {e}")
            return None
        finally:
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _parse_markdown_tables(self, markdown_text: str) -> Optional[pd.DataFrame]:
        """
        Parse markdown tables from LlamaParse output - matching Streamlit's approach.
        """
        import re
        
        lines = markdown_text.split('\n')
        tables = []
        
        current_idx = 0
        while current_idx < len(lines):
            # Find next table header (look for | in line)
            header_row_index = -1
            for i in range(current_idx, len(lines)):
                if "|" in lines[i] and not lines[i].startswith('#'):
                    header_row_index = i
                    break
            
            if header_row_index == -1:
                break  # No more tables
            
            # Parse header row
            header_line = lines[header_row_index].strip()
            if header_line.startswith('|'): header_line = header_line[1:]
            if header_line.endswith('|'): header_line = header_line[:-1]
            headers = [c.strip() for c in header_line.split('|')]
            
            # Check for second header row (multi-row headers)
            next_row_idx = header_row_index + 1
            headers_row2 = None
            if next_row_idx < len(lines):
                next_line = lines[next_row_idx].strip()
                if next_line.startswith('|') and '---' not in next_line:
                    if next_line.startswith('|'): next_line = next_line[1:]
                    if next_line.endswith('|'): next_line = next_line[:-1]
                    potential_headers = [c.strip() for c in next_line.split('|')]
                    has_column_names = any(h and h not in ['Units', 'LOR', 'Guideline', ''] and not h.replace('.','').replace('-','').isdigit() for h in potential_headers)
                    if has_column_names:
                        headers_row2 = potential_headers
            
            # Merge headers if multi-row
            if headers_row2:
                merged_headers = []
                for i in range(max(len(headers), len(headers_row2))):
                    h1 = headers[i] if i < len(headers) else ''
                    h2 = headers_row2[i] if i < len(headers_row2) else ''
                    merged_headers.append(h2 if h2 else h1)
                headers = merged_headers
            
            # Remove empty headers
            headers = [h for h in headers if h]
            
            if not headers:
                current_idx = header_row_index + 1
                continue
            
            # Parse data rows
            data = []
            data_start_row = header_row_index + (2 if headers_row2 else 1)
            
            for i in range(data_start_row, len(lines)):
                line = lines[i].strip()
                
                # Stop at new section or non-table content
                if line.startswith('#'): break
                if not line.startswith('|') and len(line) > 5: break
                
                if not line.startswith('|'): continue
                if '---' in line: continue
                
                clean_line = line
                if clean_line.startswith('|'): clean_line = clean_line[1:]
                if clean_line.endswith('|'): clean_line = clean_line[:-1]
                cells = [c.strip() for c in clean_line.split('|')]
                
                if len(cells) > len(headers): cells = cells[:len(headers)]
                elif len(cells) < len(headers): cells += [''] * (len(headers) - len(cells))
                
                row_dict = {}
                has_data = False
                for h, c in zip(headers, cells):
                    row_dict[h] = c
                    if c: has_data = True
                
                if has_data and row_dict.get(headers[0]):
                    val = str(row_dict[headers[0]])
                    if val in ['Units', 'LOR', 'Guideline', 'None', '', 'nan']: continue
                    data.append(row_dict)
            
            if data:
                df_table = pd.DataFrame(data)
                tables.append(df_table)
            
            current_idx = data_start_row + len(data)
        
        if not tables:
            return None
        
        # Return the first/largest table
        return tables[0] if tables else None
    
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

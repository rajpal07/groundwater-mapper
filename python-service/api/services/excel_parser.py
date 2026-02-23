"""
Excel parsing service with LlamaParse - Replicating Streamlit's exact approach.
Uses SimpleDirectoryReader with file_extractor for .xlsx files.
"""

import os
import io
import base64
import logging
import tempfile
import re
import hashlib
from typing import Optional, List, Dict, Any, Tuple

import pandas as pd
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

# LlamaParse availability check
LLAMAPARSE_AVAILABLE = False
SIMPLE_DIRECTORY_READER_AVAILABLE = False

try:
    from llama_parse import LlamaParse
    from llama_index.core import SimpleDirectoryReader
    LLAMAPARSE_AVAILABLE = True
    SIMPLE_DIRECTORY_READER_AVAILABLE = True
    logger.info("LlamaParse and SimpleDirectoryReader are available")
except ImportError as e:
    logger.warning(f"LlamaParse/SimpleDirectoryReader not installed: {e}")
    try:
        from llama_parse import LlamaParse
        LLAMAPARSE_AVAILABLE = True
        logger.info("LlamaParse is available (but SimpleDirectoryReader not)")
    except ImportError:
        logger.warning("LlamaParse not installed, using pandas fallback")


class ExcelParserService:
    """Service for parsing Excel files - replicating Streamlit's SheetAgent approach."""
    
    def __init__(self):
        self.llama_cloud_api_key = os.getenv("LLAMA_CLOUD_API_KEY")
        self.llamaparse_available = LLAMAPARSE_AVAILABLE and bool(self.llama_cloud_api_key)
        self.simple_directory_reader_available = SIMPLE_DIRECTORY_READER_AVAILABLE and self.llamaparse_available
    
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
                # Use the Streamlit approach - create temp file for the sheet and parse
                df = self._parse_with_llamaparse_streamlit_approach(file_content, filename, sheet_name)
                if df is not None and not df.empty:
                    logger.info(f"Successfully parsed with LlamaParse (Streamlit approach): {len(df)} rows")
                    return df
            except Exception as e:
                logger.warning(f"LlamaParse Streamlit approach failed, trying direct: {e}")
                try:
                    # Fallback to direct parsing
                    df = self._parse_with_llamaparse_direct(file_content, filename, sheet_name)
                    if df is not None and not df.empty:
                        logger.info(f"Successfully parsed with LlamaParse (direct): {len(df)} rows")
                        return df
                except Exception as e2:
                    logger.warning(f"LlamaParse direct also failed: {e2}")
        
        # Fallback to pandas
        df = self._parse_with_pandas(file_content, ext, sheet_name)
        logger.info(f"Parsed with pandas: {len(df)} rows, {len(df.columns)} columns")
        
        return df
    
    def _parse_with_llamaparse_streamlit_approach(
        self,
        file_content: bytes,
        filename: str,
        sheet_name: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """
        Parse Excel file using LlamaParse + SimpleDirectoryReader - EXACTLY like Streamlit.
        
        This is the Streamlit approach:
        1. Extract the specific sheet to a temporary Excel file
        2. Use SimpleDirectoryReader with file_extractor for .xlsx
        3. Parse the markdown and extract tables
        """
        if not self.llamaparse_available:
            return None
        
        # Save to temp file first
        ext = filename.lower().split('.')[-1] if '.' in filename else 'xlsx'
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
            tmp.write(file_content)
            original_tmp_path = tmp.name
        
        try:
            # Determine which sheet to parse
            xl_file = pd.ExcelFile(original_tmp_path)
            sheets = xl_file.sheet_names if isinstance(xl_file.sheet_names, list) else xl_file.sheet_names.tolist()
            
            if not sheets:
                return None
            
            # Use the specified sheet or first sheet
            target_sheet = sheet_name if sheet_name in sheets else sheets[0]
            
            # Extract this specific sheet to a NEW temp file (like Streamlit does)
            temp_sheet_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            temp_sheet_path = temp_sheet_file.name
            temp_sheet_file.close()
            
            try:
                # Read only this sheet and write to temp file
                df_temp = pd.read_excel(original_tmp_path, sheet_name=target_sheet)
                df_temp.to_excel(temp_sheet_path, index=False, sheet_name=target_sheet)
                
                # Parse the isolated sheet using SimpleDirectoryReader (EXACTLY like Streamlit)
                markdown_text = self._parse_raw_file_streamlit(temp_sheet_path)
                
                if not markdown_text:
                    logger.warning("No markdown output from LlamaParse")
                    return None
                
                # Extract tables from markdown (Streamlit's smart_extract_sheet logic)
                df = self._smart_extract_sheet_from_markdown(markdown_text)
                
                if df is not None and not df.empty:
                    logger.info(f"Streamlit approach successfully parsed sheet '{target_sheet}': {len(df)} rows")
                    return df
                
                return None
                
            finally:
                # Clean up temp sheet file
                try:
                    os.unlink(temp_sheet_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Streamlit approach failed: {e}")
            return None
        finally:
            # Clean up original temp file
            try:
                os.unlink(original_tmp_path)
            except:
                pass
    
    def _parse_raw_file_streamlit(self, file_path: str) -> str:
        """
        Parse the raw Excel file using LlamaParse + SimpleDirectoryReader.
        EXACT copy of Streamlit's parse_raw_file method.
        """
        if not self.simple_directory_reader_available:
            raise RuntimeError("SimpleDirectoryReader not available")
        
        parser = LlamaParse(
            api_key=self.llama_cloud_api_key,
            result_type="markdown",
            verbose=True,
            language="en"
        )
        
        # Use SimpleDirectoryReader with file_extractor (like Streamlit)
        file_extractor = {".xlsx": parser}
        reader = SimpleDirectoryReader(input_files=[file_path], file_extractor=file_extractor)
        documents = reader.load_data()
        
        # Combine all parts
        full_text = "\n\n".join([doc.text for doc in documents])
        logger.info(f"Parsed file, got {len(documents)} documents")
        return full_text
    
    def _smart_extract_sheet_from_markdown(self, markdown_text: str) -> Optional[pd.DataFrame]:
        """
        Extract data from markdown tables - EXACT copy of Streamlit's smart_extract_sheet logic.
        Looks for "Well ID" in the markdown to find table headers.
        """
        lines = markdown_text.split('\n')
        tables = []
        
        current_idx = 0
        while current_idx < len(lines):
            # Find next table header (look for "Well ID" like Streamlit does)
            header_row_index = -1
            for i in range(current_idx, len(lines)):
                if "Well ID" in lines[i] and "|" in lines[i]:
                    header_row_index = i
                    break
            
            if header_row_index == -1:
                break  # No more tables
            
            logger.info(f"Found Table Header at line {header_row_index}")
            
            # Handle multi-row headers (common in Excel tables)
            header_line = lines[header_row_index].strip()
            if header_line.startswith('|'): header_line = header_line[1:]
            if header_line.endswith('|'): header_line = header_line[:-1]
            headers_row1 = [c.strip() for c in header_line.split('|')]
            
            # Check if next row is a continuation of headers
            next_row_idx = header_row_index + 1
            headers_row2 = None
            
            if next_row_idx < len(lines):
                next_line = lines[next_row_idx].strip()
                if next_line.startswith('|') and '---' not in next_line:
                    if next_line.startswith('|'): next_line = next_line[1:]
                    if next_line.endswith('|'): next_line = next_line[:-1]
                    potential_headers = [c.strip() for c in next_line.split('|')]
                    
                    # If this row has meaningful column names
                    has_column_names = any(h and h not in ['Units', 'LOR', 'Guideline', ''] and 
                                          not h.replace('.','').replace('-','').isdigit() for h in potential_headers)
                    
                    if has_column_names:
                        headers_row2 = potential_headers
                        logger.info(f"Detected multi-row header, merging row {next_row_idx}")
            
            # Merge headers
            if headers_row2:
                headers = []
                for i in range(max(len(headers_row1), len(headers_row2))):
                    h1 = headers_row1[i] if i < len(headers_row1) else ''
                    h2 = headers_row2[i] if i < len(headers_row2) else ''
                    headers.append(h2 if h2 else h1)
                data_start_row = header_row_index + 2
            else:
                headers = headers_row1
                data_start_row = header_row_index + 1
            
            # Remove empty headers
            headers = [h for h in headers if h]
            
            if not headers:
                current_idx = header_row_index + 1
                continue
            
            # Parse data rows
            data = []
            last_row_idx = data_start_row
            
            for i in range(data_start_row, len(lines)):
                line = lines[i].strip()
                last_row_idx = i
                
                # Stop if new Section
                if line.startswith("#"): break
                if not line.startswith("|") and len(line) > 5: break
                
                if not line.startswith("|"): continue
                if "---" in line: continue
                
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
            
            # Move search forward
            current_idx = last_row_idx + 1
        
        if not tables:
            return None
        
        # Return the first/largest table
        return tables[0]
    
    def _parse_with_llamaparse_direct(
        self,
        file_content: bytes,
        filename: str,
        sheet_name: Optional[str] = None
    ) -> Optional[pd.DataFrame]:
        """Fallback: Direct parsing without temp file approach."""
        if not self.llamaparse_available:
            return None
        
        # Save to temp file
        ext = filename.lower().split('.')[-1] if '.' in filename else 'xlsx'
        with tempfile.NamedTemporaryFile(delete=False, suffix=f'.{ext}') as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            parser = LlamaParse(
                api_key=self.llama_cloud_api_key,
                result_type="markdown",
                verbose=False
            )
            
            import asyncio
            import concurrent.futures
            
            async def load_data_async():
                return await parser.aload_data(tmp_path)
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, load_data_async())
                documents = future.result()
            
            if not documents:
                return None
            
            markdown_text = "\n\n".join([doc.text for doc in documents])
            df = self._smart_extract_sheet_from_markdown(markdown_text)
            
            if df is not None and not df.empty:
                logger.info(f"LlamaParse direct parsed: {len(df)} rows")
                return df
            
            return None
            
        except Exception as e:
            logger.warning(f"LlamaParse direct failed: {e}")
            return None
        finally:
            try:
                os.unlink(tmp_path)
            except:
                pass
    
    def _parse_with_pandas(
        self,
        file_content: bytes,
        ext: str,
        sheet_name: Optional[str] = None
    ) -> pd.DataFrame:
        """Parse Excel file using pandas."""
        try:
            if ext in ['xlsx', 'xls']:
                xl_file = pd.ExcelFile(io.BytesIO(file_content))
                sheets = xl_file.sheet_names if isinstance(xl_file.sheet_names, list) else xl_file.sheet_names.tolist()
                
                target_sheet = sheet_name if sheet_name in sheets else sheets[0] if sheets else 0
                df = pd.read_excel(io.BytesIO(file_content), sheet_name=target_sheet)
            elif ext == 'csv':
                df = pd.read_csv(io.BytesIO(file_content))
            else:
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
    if ',' in base64_content:
        base64_content = base64_content.split(',')[1]
    return base64.b64decode(base64_content)

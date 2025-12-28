import os
import pandas as pd
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader
import io
import re

class SheetAgent:
    def __init__(self, api_key):
        self.api_key = api_key
        os.environ["LLAMA_CLOUD_API_KEY"] = api_key

    def parse_raw_file(self, file_path):
        """
        Parses the raw Excel file using LlamaParse to get markdown content.
        """
        print(f"Parsing file: {file_path}...")
        parser = LlamaParse(
            result_type="markdown",
            verbose=True,
            language="en"
        )
        
        # Use SimpleDirectoryReader to load the specific file
        file_extractor = {".xlsx": parser}
        reader = SimpleDirectoryReader(input_files=[file_path], file_extractor=file_extractor)
        documents = reader.load_data()
        
        # Combine all parts (though usually it's one doc per sheet/file)
        full_text = "\n\n".join([doc.text for doc in documents])
        print("Parsing complete.")
        return full_text

    def extract_chemical_data(self, markdown_text):
        """
        Extracts the 'Attachment 3' table (Chemical Data).
        Handles multi-row headers (Main Header + Sub Header).
        """
        print("Extracting table data using robust parsing...")
        
        lines = markdown_text.split('\n')
        
        # 1. Locate Table Start (Dynamic)
        # Strategy: Search for a row containing "Well ID" AND ("Easting" or "Northing")
        # This handles files where "Attachment 3" is missing or on different rows.
        
        start_index = -1
        signature_found = False
        
        for i, line in enumerate(lines):
            # Check for Header Signature
            # Note: LlamaParse tables are pipe-delimited
            if "Well ID" in line and ("Easting" in line or "Northing" in line or "Eassting" in line):
                print(f"DEBUG: Found Header Signature at line {i}: '{line.strip()[:50]}...'")
                start_index = i
                signature_found = True
                break
                
        if start_index == -1:
             print("Warning: Could not find table with 'Well ID' + 'Easting/Northing'. Checking for just 'Well ID'...")
             # Fallback: Just "Well ID" (maybe coordinates are on next row)
             for i, line in enumerate(lines):
                 if "|Well ID|" in line or "| Well ID |" in line:
                     start_index = i
                     signature_found = True
                     print(f"DEBUG: Found potential header at line {i}")
                     break

        if start_index == -1:
             raise ValueError("Could not find Chemical Data Table (looked for 'Well ID').")

        # 2. Find the specific Header Rows
        # Row 1: |Well ID|Sample Date|...|MGA2020...|...
        # Row 2: ||||Eassting|Northing|...
        
        header_row_1 = None
        header_row_2 = None
        data_start_index = -1
        
        # 2. Extract Headers
        # We start looking from start_index.
        
        header_row_1 = None
        header_row_2 = None
        data_start_index = -1
        
        current_idx = start_index
        # Limit search to next 5 lines to find the sub-header
        for offset in range(0, 5): 
            if current_idx + offset >= len(lines): break
            
            line = lines[current_idx + offset].strip()
            
            # Identify Main Header
            if "Well ID" in line:
                # Robust split ensuring we keep empty attributes
                raw_cells = line.strip().split('|')
                # Markdown tables usually start/end with | so first/last split are empty
                if len(raw_cells) > 0 and raw_cells[0].strip() == '': raw_cells.pop(0)
                if len(raw_cells) > 0 and raw_cells[-1].strip() == '': raw_cells.pop(-1)
                header_row_1 = [c.strip() for c in raw_cells]
                
                # Look for Sub-Header (Easting/Northing OR Latitude/Longitude)
                
                # Check next line
                next_offset = 1
                while current_idx + offset + next_offset < len(lines):
                    next_line = lines[current_idx + offset + next_offset].strip()
                    if "---" in next_line: # Skip separator
                        next_offset += 1
                        continue
                        
                    is_sub_header = False
                    if "Easting" in next_line or "Northing" in next_line or "Eassting" in next_line:
                        is_sub_header = True
                    elif "Latitude" in next_line or "Longitude" in next_line:
                        is_sub_header = True
                        
                    if is_sub_header:
                         raw_next = next_line.strip().split('|')
                         if len(raw_next) > 0 and raw_next[0].strip() == '': raw_next.pop(0)
                         if len(raw_next) > 0 and raw_next[-1].strip() == '': raw_next.pop(-1)
                         header_row_2 = [c.strip() for c in raw_next]
                         data_start_index = current_idx + offset + next_offset + 1
                         break
                    else:
                        # Maybe single row header?
                        # If next line is data (starts with pipe but no keywords), stop
                        break
                    next_offset += 1
                
                if not header_row_2:
                    # Assume Single Row Header if E/N/Lat/Lon are in Row 1
                    if any(x in line for x in ["Easting", "Northing", "Latitude", "Longitude"]):
                        header_row_2 = [""] * len(header_row_1) # Dummy
                        data_start_index = current_idx + offset + 1
                        if current_idx + offset + 1 < len(lines) and "---" in lines[current_idx + offset + 1]:
                            data_start_index += 1
                break

        if not header_row_1:
             raise ValueError("Found start but failed to parse Headers.")
        
        # If still no header 2, we might fail later, but let's try proceed
        if not header_row_2:
             header_row_2 = [""] * len(header_row_1)

        print("Headers found. processing columns...")
        
        # 3. Combine Headers
        # If Header 2 has a value, use it (e.g., Easting). If not, use Header 1 (e.g., Well ID).
        # We need to handle column alignment carefully.
        
        # Normalize lengths
        max_len = max(len(header_row_1), len(header_row_2))
        header_row_1 += [''] * (max_len - len(header_row_1))
        header_row_2 += [''] * (max_len - len(header_row_2))
        
        final_headers = []
        for h1, h2 in zip(header_row_1, header_row_2):
            if h2 and h2 not in ['Units', 'LOR']: # Use sub-header if meaningful
                final_headers.append(h2)
            elif h1:
                final_headers.append(h1)
            else:
                final_headers.append("Unknown")
                
        # 4. Extract Data Rows
        # Iterate from data_start_index until we hit a new section or empty block
        data_rows = []
        
        for i in range(data_start_index, len(lines)):
            line = lines[i].strip()
            
            # Stop conditions
            if not line: continue # Skip empty lines inside table? Or stop? Markdown tables usually tight.
            if "Attachment" in line or "Soil" in line or line.startswith("#"): # New section
                 break
            
            if not line.startswith("|"): continue
            if "---" in line: continue # Separator
            if "Units" in line or "LOR" in line: continue # Metadata rows
            if "Assessment Guidelines" in line: continue # Metadata rows
            
            # Check if it's a data row (starts with a Well ID-like string)
            # Use same robust splitting
            clean_line = line
            if clean_line.startswith('|'): clean_line = clean_line[1:]
            if clean_line.endswith('|'): clean_line = clean_line[:-1]
            
            cells = [c.strip() for c in clean_line.split('|')]
            
            # Pad or truncate
            if len(cells) < len(final_headers):
                cells += [''] * (len(final_headers) - len(cells))
            else:
                cells = cells[:len(final_headers)]
            
            # Simple heuristic: First column must not be empty (Well ID)
            # Actually, sometimes LlamaParse puts keys in col 1.
            # Let's just collect everything that looks like a row.
            data_rows.append(cells)

        print(f"Extracted {len(data_rows)} rows.")
        
        df = pd.DataFrame(data_rows, columns=final_headers)
        return df

    def extract_groundwater_data(self, markdown_text):
        """
        Extracts 'Attachment 1' table (Groundwater Levels).
        Target Columns: Well ID, Static Water Level (mAHD)
        """
        print("Extracting Groundwater Levels...")
        lines = markdown_text.split('\n')
        
        start_index = -1
        # Priority 1: Attachment 1
        for i, line in enumerate(lines):
            if "Attachment 1" in line:
                start_index = i
                print("DEBUG: Found 'Attachment 1' for Groundwater.")
                break
        
        # Priority 2: Fallback - Search for "Static Water Level" anywhere
        if start_index == -1:
             print("Warning: Attachment 1 not found. Scanning globally for 'Static Water Level'...")
             for i, line in enumerate(lines):
                  if "Static Water Level" in line and "Well ID" in line:
                      start_index = i - 1 # Assumption: header is near
                      print(f"DEBUG: Found Groundwater Header at line {i}")
                      break

        if start_index == -1:
            print("Warning: Groundwater headers not found in file. Skipping GW data.")
            return pd.DataFrame()

        # Find header row
        # Row with "Static Water Level (mAHD)"
        header_index = -1
        target_col = "Static Water Level (mAHD)"
        well_col = "Well ID"
        
        # Search forward from start_index (limit 20 lines)
        for i in range(start_index, min(len(lines), start_index + 50)):
            if target_col in lines[i] and well_col in lines[i]:
                header_index = i
                break
            # Relaxed match: maybe just 'Water Level' if 'mAHD' is missing? 
            # Sticking to exact match for now as per user instruction "Static Water Level (mAHD)"
        
        if header_index == -1:
             print("Warning: Groundwater headers match failed.")
             return pd.DataFrame()

        # Parse Header
        header_line = lines[header_index].strip()
        if header_line.startswith('|'): header_line = header_line[1:]
        if header_line.endswith('|'): header_line = header_line[:-1]
        headers = [c.strip() for c in header_line.split('|')]
        
        # Identify indices
        try:
            well_idx = next(i for i, h in enumerate(headers) if "Well ID" in h)
            gw_idx = next(i for i, h in enumerate(headers) if "Static Water Level" in h)
        except StopIteration:
            print("Warning: Critical columns missing in Attachment 1.")
            return pd.DataFrame()
            
        # Extract Data
        data = []
        
        for i in range(header_index + 1, len(lines)):
            line = lines[i].strip()
            if not line: continue
            if "Attachment" in line or line.startswith("#"): 
                # If we are far from header, this is likely end of table
                if i > header_index + 5: break 
            
            if not line.startswith("|"): continue
            if "---" in line: continue
            
            # Clean split
            clean_line = line
            if clean_line.startswith('|'): clean_line = clean_line[1:]
            if clean_line.endswith('|'): clean_line = clean_line[:-1]
            cells = [c.strip() for c in clean_line.split('|')]
            
            if len(cells) <= max(well_idx, gw_idx): continue
            
            well_id = cells[well_idx]
            gw_level = cells[gw_idx]
            
            # Simple validation: Well ID shouldn't be empty, GW level should be numeric-ish or empty
            if not well_id or well_id in ['Units', 'LOR']: continue
            
            data.append({'Well ID': well_id, 'Static Water Level (mAHD)': gw_level})

        return pd.DataFrame(data)

    def clean_data(self, df):
        """
        Cleans the DataFrame:
        - Ensures numeric types for coordinates and chemicals.
        - Renames columns if necessary.
        """
        print("Cleaning data...")
        
        # Deduplicate columns first
        if df.columns.duplicated().any():
            print(f"Warning: Duplicate columns found: {df.columns[df.columns.duplicated()].tolist()}. Removing duplicates.")
            df = df.loc[:, ~df.columns.duplicated()]
        
        # 1. Coordinate Cleaning
        # The markdown might have 'Eassting' (typo) or 'Easting'
        # Let's normalize column names
        # STRICT CLEANING: remove anything that isn't alphanumeric, space, or parens
        # This removes \* \ etc that cause JSON escape errors
        def clean_col(col_name):
            # Special case for GW level to ensure exact match if desired, 
            # but usually the regex below keeps () which is good.
            # re.sub(r'[^\w\s\(\)\-\.]', '', col_name) keeps ( and )
            cleaned = re.sub(r'[^\w\s\(\)\-\.]', '', col_name).strip()
            return cleaned

        df.columns = [clean_col(c) for c in df.columns]
        
        # Map common misspellings or variations
        col_map = {
            'Eassting': 'Easting',
            'Northing': 'Northing',
            'Well ID': 'Well ID',
            'Sample Date': 'Date',
            'Latitude': 'Latitude',
            'Longitude': 'Longitude',
            'Static Water Level': 'Static Water Level (mAHD)', # Normalize variations
            'Static Water Level mAHD': 'Static Water Level (mAHD)'
        }
        
        # Apply map if key is found (exact or close?)
        # For now, precise rename
        df = df.rename(columns=col_map)
        
        # Deduplicate columns (Handle rename collisions)
        if df.columns.duplicated().any():
            print(f"Warning: Duplicate columns found after rename: {df.columns[df.columns.duplicated()].tolist()}. Keeping first.")
            df = df.loc[:, ~df.columns.duplicated()]
        
        # 2. Convert Numeric Columns
        # Identify columns that should be numeric (Easting, Northing, Chemicals)
        # We basically want everything except 'Well ID', 'Date', 'Time' to be numeric
        exclude_cols = ['Well ID', 'Date', 'Time', 'MGA2020 / MGA Zone 54']
        
        for col in df.columns:
            if col not in exclude_cols:
                # Force numeric, coerce errors to NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 3. Drop rows where Well ID or Coordinates are missing
        # Check for E/N OR Lat/Lon
        has_coords = False
        if 'Easting' in df.columns and 'Northing' in df.columns:
            df = df.dropna(subset=['Easting', 'Northing'])
            has_coords = True
        elif 'Latitude' in df.columns and 'Longitude' in df.columns:
            df = df.dropna(subset=['Latitude', 'Longitude'])
            has_coords = True
            
        if not has_coords:
             print("Warning: No valid coordinate columns (Easting/Northing or Lat/Lon) found.")
       
        print("Data cleaning complete.")
        return df

    def process(self, file_path):
        """
        Main execution method.
        """
        print(f"Running agent on {file_path}...")
        
        # 1. Parse File
        # Cache based on FILE CONTENT Hash to avoid collision for 'temp_upload.xlsx'
        import hashlib
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            file_hash = hashlib.md5(file_bytes).hexdigest()
            
        cache_file = f"cache_llama_{file_hash}.md"
        
        if not os.path.exists(cache_file):
            print("Parsing file (this may take a moment)...")
            markdown_output = self.parse_raw_file(file_path)
            # Save for debugging/caching
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(markdown_output)
        else:
             print(f"Loading cached markdown ({cache_file})...")
             with open(cache_file, "r", encoding="utf-8") as f:
                markdown_output = f.read()

        # 2. Extract Data
        chem_df = self.extract_chemical_data(markdown_output)
        gw_df = self.extract_groundwater_data(markdown_output)
        
        # 3. Merge
        print("Merging datasets...")
        if not chem_df.empty and not gw_df.empty:
            # Clean Well IDs for merging (strip whitespace)
            chem_df['Well ID'] = chem_df['Well ID'].astype(str).str.strip()
            gw_df['Well ID'] = gw_df['Well ID'].astype(str).str.strip()
            
            # Check if GW column exists in chem_df
            gw_col = 'Static Water Level (mAHD)'
            
            # Normalize column names in both DFs first for consistent checking
            # (We usually do clean_data AFTER merge, but for checking duplicates we need to know)
            # A quick check:
            chem_cols = [c for c in chem_df.columns if "Static Water Level" in c]
            
            if chem_cols:
                print(f"Groundwater data already in Chemical Table (Columns: {chem_cols}). Ignoring separate GW data to prevent duplicates.")
                final_df = chem_df
            else:
                merged_df = pd.merge(chem_df, gw_df, on='Well ID', how='left')
                final_df = merged_df
                
        elif not chem_df.empty:
            final_df = chem_df
            print("Warning: Groundwater data missing (or integrated), using only chemical data.")
        else:
             final_df = pd.DataFrame()
             print("Error: No data extracted.")

        # 4. Clean & Save
        if not final_df.empty:
            cleaned_df = self.clean_data(final_df)
            output_path = "processed_data.xlsx" # Hardcoded output path
            cleaned_df.to_excel(output_path, index=False)
            print(f"Successfully saved processed data to: {output_path}")
            return output_path
        else:
            print("Failed to extract data.")
            return None


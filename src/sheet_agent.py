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
        
        # 1. Locate Attachment 3
        start_index = -1
        for i, line in enumerate(lines):
            if "Attachment 3" in line:
                print(f"DEBUG: Found target section '{line.strip()}' at line {i}")
                start_index = i
                break
        
        if start_index == -1:
            print("Warning: 'Attachment 3' not found using exact string. Searching for similar headers.")
            # Fallback: look for 'Well ID' directly
            for i, line in enumerate(lines):
                if "|Well ID|" in line:
                    start_index = i - 5 # Give some buffer
                    break
        
        if start_index == -1:
             raise ValueError("Could not find Attachment 3 or Well ID table.")

        # 2. Find the specific Header Rows
        # Row 1: |Well ID|Sample Date|...|MGA2020...|...
        # Row 2: ||||Eassting|Northing|...
        
        header_row_1 = None
        header_row_2 = None
        data_start_index = -1
        
        current_idx = start_index
        while current_idx < len(lines):
            line = lines[current_idx].strip()
            if line.startswith("|Well ID"):
                # Use slicing [1:-1] to remove first/last pipe only, preserving internal empty structure
                # Ensure we handle lines that might not strictly end with pipe by checking
                clean_line = line.strip()
                if clean_line.startswith('|'): clean_line = clean_line[1:]
                if clean_line.endswith('|'): clean_line = clean_line[:-1]
                
                header_row_1 = [c.strip() for c in clean_line.split('|')]
                
                # Look ahead for sub-header
                offset = 1
                while current_idx + offset < len(lines):
                    next_line = lines[current_idx + offset].strip()
                    if "Eassting" in next_line or "Easting" in next_line or "Northing" in next_line:
                         clean_next = next_line.strip()
                         if clean_next.startswith('|'): clean_next = clean_next[1:]
                         if clean_next.endswith('|'): clean_next = clean_next[:-1]
                         
                         header_row_2 = [c.strip() for c in clean_next.split('|')]
                         data_start_index = current_idx + offset + 1
                         break
                    offset += 1
                break
            current_idx += 1
            
        if not header_row_1 or not header_row_2:
            raise ValueError("Could not find Multi-Row Headers (Well ID + Coordinates).")

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
        print("Extracting Groundwater Levels from Attachment 1...")
        lines = markdown_text.split('\n')
        
        start_index = -1
        for i, line in enumerate(lines):
            if "Attachment 1" in line:
                start_index = i
                break
        
        if start_index == -1:
            print("Warning: Attachment 1 not found. Skipping groundwater data.")
            return pd.DataFrame()

        # Find header row
        # Row with "Static Water Level (mAHD)"
        header_index = -1
        target_col = "Static Water Level (mAHD)"
        well_col = "Well ID"
        
        for i in range(start_index, len(lines)):
            if target_col in lines[i] and well_col in lines[i]:
                header_index = i
                break
        
        if header_index == -1:
             print("Warning: Groundwater headers not found.")
             return pd.DataFrame()

        # Parse Header
        header_line = lines[header_index].strip()
        if header_line.startswith('|'): header_line = header_line[1:]
        if header_line.endswith('|'): header_line = header_line[:-1]
        headers = [c.strip() for c in header_line.split('|')]
        
        # Identify indices
        try:
            well_idx = next(i for i, h in enumerate(headers) if "Well ID" in h)
            gw_idx = next(i for i, h in enumerate(headers) if "Static Water Level (mAHD)" in h)
        except StopIteration:
            print("Warning: Critical columns missing in Attachment 1.")
            return pd.DataFrame()
            
        # Extract Data
        data = []
        
        for i in range(header_index + 1, len(lines)):
            line = lines[i].strip()
            if not line: continue
            if "Attachment" in line or line.startswith("#"): break # Next section
            
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
        
        # 1. Coordinate Cleaning
        # The markdown might have 'Eassting' (typo) or 'Easting'
        # Let's normalize column names
        # STRICT CLEANING: remove anything that isn't alphanumeric, space, or parens
        # This removes \* \ etc that cause JSON escape errors
        def clean_col(col_name):
            # Keep letters, numbers, spaces, (), -, _
            return re.sub(r'[^\w\s\(\)\-\.]', '', col_name).strip()

        df.columns = [clean_col(c) for c in df.columns]
        
        # Map common misspellings or variations
        col_map = {
            'Eassting': 'Easting',
            'Northing': 'Northing',
            'Well ID': 'Well ID',
            'Sample Date': 'Date'
        }
        
        df = df.rename(columns=col_map)
        
        # 2. Convert Numeric Columns
        # Identify columns that should be numeric (Easting, Northing, Chemicals)
        # We basically want everything except 'Well ID', 'Date', 'Time' to be numeric
        exclude_cols = ['Well ID', 'Date', 'Time', 'MGA2020 / MGA Zone 54']
        
        for col in df.columns:
            if col not in exclude_cols:
                # Force numeric, coerce errors to NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 3. Drop rows where Well ID or Coordinates are missing
        if 'Easting' in df.columns and 'Northing' in df.columns:
            df = df.dropna(subset=['Easting', 'Northing'])
        
        print("Data cleaning complete.")
        return df

    def process(self, file_path):
        """
        Main execution method.
        """
        print(f"Running agent on {file_path}...")
        
        # 1. Parse File
        # Changed parse_excel to parse_raw_file
        if not os.path.exists("llama_parse_output.md"):
            print("Parsing file (this may take a moment)...")
            markdown_output = self.parse_raw_file(file_path)
            # Save for debugging/caching
            with open("llama_parse_output.md", "w", encoding="utf-8") as f:
                f.write(markdown_output)
        else:
             print("Loading cached markdown...")
             with open("llama_parse_output.md", "r", encoding="utf-8") as f:
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
            
            # Merge left on chemical data (primary) or outer?
            # User wants chemical data primarily, but with GW level added.
            # "Attachment 3" is Lab data, "Attachment 1" is Insitu/Levels.
            # We trust Attachment 3 for coordinates.
            
            merged_df = pd.merge(chem_df, gw_df, on='Well ID', how='left')
            final_df = merged_df
        elif not chem_df.empty:
            final_df = chem_df
            print("Warning: Groundwater data missing, using only chemical data.")
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


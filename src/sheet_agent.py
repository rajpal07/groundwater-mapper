import os
import pandas as pd
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader
import io
import re
import hashlib

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
        
        # Use SimpleDirectoryReader
        file_extractor = {".xlsx": parser}
        reader = SimpleDirectoryReader(input_files=[file_path], file_extractor=file_extractor)
        documents = reader.load_data()
        
        # Combine all parts
        full_text = "\n\n".join([doc.text for doc in documents])
        print("Parsing complete.")
        return full_text

    def smart_extract_sheet(self, sheet_name, file_path):
        """
        Extracts data from a specific sheet by:
        1. Extracting that sheet to a temporary Excel file
        2. Parsing it with LlamaParse (guarantees isolation)
        3. Extracting tables from the markdown
        
        This eliminates the need for fuzzy header matching.
        """
        import tempfile
        
        print(f"\n=== Processing Sheet: {sheet_name} ===")
        
        # 1. Extract this specific sheet to a temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
        temp_path = temp_file.name
        temp_file.close()
        
        try:
            # Read only this sheet and write to temp file
            df_temp = pd.read_excel(file_path, sheet_name=sheet_name)
            df_temp.to_excel(temp_path, index=False, sheet_name=sheet_name)
            
            # 2. Parse the isolated sheet
            markdown_text = self.parse_raw_file(temp_path)
            
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
        
        # 3. Extract ALL tables from this markdown (now guaranteed to be only this sheet)
        lines = markdown_text.split('\n')
        tables = []
        
        current_idx = 0
        while current_idx < len(lines):
            # Find next table header
            header_row_index = -1
            for i in range(current_idx, len(lines)):
                if "Well ID" in lines[i] and "|" in lines[i]:
                    header_row_index = i
                    break
            
            if header_row_index == -1:
                break # No more tables
            
            # --- Extract Table ---
            print(f"Found Table Header at line {header_row_index}")
            
            header_line = lines[header_row_index].strip()
            if header_line.startswith('|'): header_line = header_line[1:]
            if header_line.endswith('|'): header_line = header_line[:-1]
            headers = [c.strip() for c in header_line.split('|')]
            headers = [h for h in headers if h] 
            
            data = []
            last_row_idx = header_row_index
            for i in range(header_row_index + 1, len(lines)):
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
            
        # 4. Merge Tables
        if not tables:
            return pd.DataFrame()
            
        final_sheet_df = tables[0]
        for df in tables[1:]:
            # Clean keys
            if 'Well ID' in final_sheet_df.columns: final_sheet_df['Well ID'] = final_sheet_df['Well ID'].astype(str).str.strip()
            if 'Well ID' in df.columns: df['Well ID'] = df['Well ID'].astype(str).str.strip()
            
            # Merge
            final_sheet_df = pd.merge(final_sheet_df, df, on='Well ID', how='outer', suffixes=('', '_dup'))
            
        return final_sheet_df

    def clean_sheet_data(self, df):
        """
        Cleans a single sheet's data. 
        """
        # 1. Normalize Columns
        new_cols = []
        for c in df.columns:
            # Clean special chars (keep parens)
            c_clean = re.sub(r'[^\w\s\(\)\-\.]', '', c).strip()
            
            # Map Common Variations
            if c_clean in ['Eassting', 'Easting_1']: c_clean = 'Easting'
            if c_clean in ['Northing_1']: c_clean = 'Northing'
            if c_clean in ['Waell ID', 'Well_ID']: c_clean = 'Well ID'
            
            # Standardize Groundwater
            if 'Static Water' in c_clean or 'Water Level' in c_clean:
                 # Ensure we keep unit if present, or standardize?
                 # User likes "Static Water Level (mAHD)"
                 if 'mAHD' in c_clean:
                      c_clean = "Static Water Level (mAHD)"
                      
            new_cols.append(c_clean)
            
        df.columns = new_cols
        
        # 2. Ensure Numeric
        # Exclude metadata columns
        exclude_cols = ['Well ID', 'Date', 'Time', 'Sample ID', 'Comments']
        for c in df.columns:
            if c not in exclude_cols:
                df[c] = pd.to_numeric(df[c], errors='coerce')
                
        return df

    def process(self, file_path, output_path=None, selected_sheets=None):
        """
        Main execution method.
        """
        print(f"Running agent on {file_path}...")
        
        # 1. Parse File
        with open(file_path, "rb") as f:
            file_bytes = f.read()
            file_hash = hashlib.md5(file_bytes).hexdigest()
            
        cache_file = f"cache_llama_{file_hash}.md"
        
        if not os.path.exists(cache_file):
            print("Parsing file...")
            try:
                markdown_output = self.parse_raw_file(file_path)
                with open(cache_file, "w", encoding="utf-8") as f:
                    f.write(markdown_output)
            except Exception as e:
                print(f"Parsing failed: {e}")
                return None
        else:
             print(f"Loading cached markdown ({cache_file})...")
             with open(cache_file, "r", encoding="utf-8") as f:
                markdown_output = f.read()

        # 2. Extract Data from Selected Sheets
        dfs = []
        
        if not selected_sheets:
             print("No sheets supplied. Attempting to read all sheets from file.")
             # Read all sheet names from the Excel file
             xls = pd.ExcelFile(file_path)
             selected_sheets = xls.sheet_names
             print(f"Auto-detected sheets: {selected_sheets}")
        
        for sheet in selected_sheets:
            df_sheet = self.smart_extract_sheet(sheet, file_path)
            if not df_sheet.empty:
                cleaned_df = self.clean_sheet_data(df_sheet)
                dfs.append((sheet, cleaned_df))

        if not dfs:
             print("No data extracted from any sheet.")
             return None

        # 3. Merge
        print("Merging extracted sheets...")
        final_df = None
        
        for sheet_name, df in dfs:
            if 'Well ID' not in df.columns: continue
            
            # Normalize Key
            df['Well ID'] = df['Well ID'].astype(str).str.strip()
            
            if final_df is None:
                final_df = df
                # Suffix columns for the FIRST sheet too, if we expect collisions?
                # User Policy: "keep that column for that sheet"
                # If we have Sheet1 (col A) and Sheet2 (col A), we want A(Sheet1) and A(Sheet2).
                # So yes, we should suffix ALL non-key columns always?
                # OR only suffix if collision?
                # User said: "we will have to keep that column for that sheet".
                # To be explicit and avoiding confusion, let's suffix EVERYTHING with sheet name,
                # EXCEPT maybe Easting/Northing which we coalesce?
                # Let's suffix everything. It's safer.
                
                new_cols = {}
                for c in final_df.columns:
                    if c != 'Well ID':
                        new_cols[c] = f"{c} ({sheet_name})"
                final_df = final_df.rename(columns=new_cols)
                
            else:
                # Prepare next DF
                new_cols = {}
                for c in df.columns:
                    if c != 'Well ID':
                        new_cols[c] = f"{c} ({sheet_name})"
                df = df.rename(columns=new_cols)
                
                # Outer Merge
                final_df = pd.merge(final_df, df, on='Well ID', how='outer')
                
        # 4. Final Processing
        if final_df is None or final_df.empty:
            return None
            
        # Coalesce Coordinates for Map
        # We need a single 'Easting' and 'Northing' (or Lat/Lon) for the map to work.
        print("Coalescing Coordinates...")

        def coalesce_columns(df, target_base_names):
            if isinstance(target_base_names, str):
                target_base_names = [target_base_names]
            
            candidates = []
            for base in target_base_names:
                # Find columns starting with base (and optionally having '(', though suffixing ensures this)
                # We check for "(" to ensure we are looking at the suffixed versions we created.
                found = [c for c in df.columns if c.startswith(base) and "(" in c]
                candidates.extend(found)
            
            if not candidates:
                return None
            
            # Start with the first one
            combined = df[candidates[0]]
            for c in candidates[1:]:
                # Fill NAs in 'combined' with values from 'c'
                combined = combined.combine_first(df[c])
            return combined

        # Attempt to create master Coordinate columns
        # Support "Eassting" typo in detection
        easting = coalesce_columns(final_df, ["Easting", "Eassting"])
        northing = coalesce_columns(final_df, "Northing")
        
        if easting is not None: final_df['Easting'] = easting
        if northing is not None: final_df['Northing'] = northing
        
        # Also do Lat/Lon just in case
        lat = coalesce_columns(final_df, "Latitude")
        lon = coalesce_columns(final_df, "Longitude")
        
        if lat is not None: final_df['Latitude'] = lat
        if lon is not None: final_df['Longitude'] = lon

        # Save
        if output_path is None: output_path = "processed_data.xlsx"
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        final_df.to_excel(output_path, index=False)
        print(f"Saved merged data to {output_path}")
        
        return output_path

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

    def smart_extract_sheet(self, sheet_name, markdown_text):
        """
        Generic extractor for ANY sheet.
        Scans the markdown text looking for the specific sheet section.
        Then finds the table within it.
        """
        print(f"--- Extracting Sheet: {sheet_name} ---")
        lines = markdown_text.split('\n')
        
        # 1. Find Start of Sheet
        start_index = -1
        
        # Normalize for search (LlamaParse might produce "Sheet Name" or "SheetName")
        sheet_search = sheet_name.replace('_', ' ').strip()
        
        # Scan for Sheet Header
        # Looking for things like "## <SheetName>" or "### <SheetName>"
        # or even just text that matches strongly.
        for i, line in enumerate(lines):
            if line.strip().startswith("#") and sheet_search.lower() in line.lower():
                start_index = i
                print(f"DEBUG: Found Sheet Header for '{sheet_name}' at line {i}: {line[:50]}...")
                break
        
        # Fallback: If strict header search fails, look for simple text match if the sheet name is unique/long enough
        if start_index == -1 and len(sheet_search) > 5:
             for i, line in enumerate(lines):
                if sheet_search.lower() in line.lower() and (line.startswith("#") or line.startswith("**")):
                    start_index = i
                    print(f"DEBUG: Found Loose Sheet Header for '{sheet_name}' at line {i}")
                    break
        
        # If still -1, and we are looking for a SPECIFIC sheet, maybe we just scan the whole file?
        # But that risks pulling data from other sheets. 
        # However, if the Excel file is simple, maybe it's fine.
        if start_index == -1:
            print(f"Warning: Specific header for '{sheet_name}' not found. scanning from top.")
            start_index = 0
            
        # 2. Find Table Header (Well ID)
        header_row_index = -1
        
        # Look for "Well ID"
        # We limit the search distance if we found a header to avoid bleeding into next sheet
        search_limit = len(lines)
        if start_index > 0:
            # Try to find the NEXT sheet header to stop searching?
            # Hard to guess.
            pass

        for i in range(start_index, search_limit):
            line = lines[i]
            # Check for generic table header
            if "Well ID" in line and "|" in line:
                header_row_index = i
                break
            # Also check if we hit another header which might mean we missed it
            if i > start_index + 100 and line.startswith("# "): 
                # Safety break? No, tables can be long.
                pass
                
        if header_row_index == -1:
             print(f"Skipping Sheet '{sheet_name}': No 'Well ID' header found.")
             return pd.DataFrame()
             
        print(f"Found Table Header at row {header_row_index}")
        
        # 3. Parse Header
        header_line = lines[header_row_index].strip()
        if header_line.startswith('|'): header_line = header_line[1:]
        if header_line.endswith('|'): header_line = header_line[:-1]
        
        headers = [c.strip() for c in header_line.split('|')]
        # Filter empty
        headers = [h for h in headers if h] 
        
        # 4. Extract Rows
        data = []
        for i in range(header_row_index + 1, len(lines)):
            line = lines[i].strip()
            
            # Stop if new Section 
            if line.startswith("#") and i > header_row_index + 2:
                break
     
            if not line.startswith("|"): continue
            if "---" in line: continue
            
            clean_line = line
            if clean_line.startswith('|'): clean_line = clean_line[1:]
            if clean_line.endswith('|'): clean_line = clean_line[:-1]
            
            cells = [c.strip() for c in clean_line.split('|')]
            
            # Align
            if len(cells) > len(headers):
                 cells = cells[:len(headers)]
            elif len(cells) < len(headers):
                 cells += [''] * (len(headers) - len(cells))
                 
            row_dict = {}
            has_data = False
            for h, c in zip(headers, cells):
                row_dict[h] = c
                if c: has_data = True
                
            if has_data and row_dict.get(headers[0]): # Check first col (Well ID)
                 val = row_dict[headers[0]]
                 if val in ['Units', 'LOR', 'Guideline', 'None', '']: continue
                 data.append(row_dict)
                 
        df = pd.DataFrame(data)
        return df

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

        # 2. Extract Data
        dfs = []
        
        # If no sheets selected, try to infer from file? 
        # (This tool runs after App.py reads excel structure, so likely we have sheets)
        if not selected_sheets:
             print("No sheets supplied. Attempting blind extraction (fallback).")
             # Fallback: Treat whole doc as one big search space for "Well ID"
             # This is weak but prevents total failure if called from CLI without args.
             # We create a dummy sheet name "Detected Table"
             df_blind = self.smart_extract_sheet("Detected Table", markdown_output)
             if not df_blind.empty:
                 dfs.append(("Auto", self.clean_sheet_data(df_blind)))
        else:
             for sheet in selected_sheets:
                 df_sheet = self.smart_extract_sheet(sheet, markdown_output)
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
        # We look for ANY "Easting *" and "Northing *" column
        print("Coalescing Coordinates...")
        
        easting_cols = [c for c in final_df.columns if "Easting" in c]
        northing_cols = [c for c in final_df.columns if "Northing" in c]
        
        # Use bfill to get the first available coordinate
        if easting_cols:
             final_df['Easting'] = final_df[easting_cols].bfill(axis=1).iloc[:, 0]
        if northing_cols:
             final_df['Northing'] = final_df[northing_cols].bfill(axis=1).iloc[:, 0]
             
        # Lat/Lon
        lat_cols = [c for c in final_df.columns if "Latitude" in c]
        lon_cols = [c for c in final_df.columns if "Longitude" in c]
        
        if lat_cols: final_df['Latitude'] = final_df[lat_cols].bfill(axis=1).iloc[:, 0]
        if lon_cols: final_df['Longitude'] = final_df[lon_cols].bfill(axis=1).iloc[:, 0]

        # Save
        if output_path is None: output_path = "processed_data.xlsx"
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        final_df.to_excel(output_path, index=False)
        print(f"Saved merged data to {output_path}")
        
        return output_path

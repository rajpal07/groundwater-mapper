import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from aquifer import analyze_aquifer_layers

FILE_PATH = r"d:\anirudh_kahn\adi_version\Fonterra Darnum_OCT_2025_Lab_Data_V1.xlsx"
SHEET_NAME = "2. Darnum_GW_insitu"
HEADER_ROW = 6 # Row 7 (0-indexed 6)

def test_fix():
    print(f"Reading with header={HEADER_ROW}...")
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=HEADER_ROW)
    
    # Strip whitespace from columns
    df.columns = df.columns.astype(str).str.strip()
    
    # Check first row for sub-headers
    first_row = df.iloc[0].astype(str).str.strip()
    
    print("First row values (potential sub-headers):")
    print(first_row.tolist())
    
    # Logic to rename columns based on first row
    new_columns = df.columns.tolist()
    for i, val in enumerate(first_row):
        if val.lower() in ['latitude', 'longitude', 'easting', 'northing']:
            print(f"  Found sub-header '{val}' at index {i}. Renaming column '{new_columns[i]}' -> '{val}'")
            new_columns[i] = val
            
    df.columns = new_columns
    
    # Drop the sub-header row
    df = df.iloc[1:].reset_index(drop=True)
    
    # Convert coordinates to numeric
    for col in ['Latitude', 'Longitude', 'Easting', 'Northing']:
        if col in df.columns:
            print(f"Converting '{col}' to numeric...")
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    print(f"New Columns: {df.columns.tolist()}")
    
    # Now run analysis
    print("\n--- Running src.aquifer.analyze_aquifer_layers with FIX ---")
    try:
        # Pass dummy value column if needed, or ensuring it exists
        val_col = 'Static Water Level (mAHD)'
        if val_col not in df.columns:
             # Try to find it again? Or just warn
             print(f"Warning: {val_col} not found in {df.columns}")
             
        results = analyze_aquifer_layers(df, val_col)
        print("\nAnalysis Results:")
        for k, v in results.items():
            print(f"{k}: {v}")
            
    except Exception as e:
        print(f"Error running analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fix()

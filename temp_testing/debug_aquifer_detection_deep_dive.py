import pandas as pd
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from aquifer import analyze_aquifer_layers, detect_nested_wells

FILE_PATH = r"d:\anirudh_kahn\adi_version\Fonterra Darnum_OCT_2025_Lab_Data_V1.xlsx"
SHEET_NAME = "2. Darnum_GW_insitu"
HEADER_ROW = 5
VALUE_COL = "Static Water Level (mAHD)"

def run_debug():
    print(f"Loading {FILE_PATH}...")
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=HEADER_ROW)
    
    # Strip whitespace from columns
    df.columns = df.columns.str.strip()
    
    print(f"Columns: {df.columns.tolist()}")
    
    # Check for coordinate columns
    x_col = None
    y_col = None
    if 'Easting' in df.columns and 'Northing' in df.columns:
        x_col, y_col = 'Easting', 'Northing'
        print("Found Easting/Northing columns.")
    elif 'Latitude' in df.columns and 'Longitude' in df.columns:
        x_col, y_col = 'Longitude', 'Latitude' # Note: X=Long, Y=Lat
        print("Found Lat/Long columns.")
        
    if x_col and y_col:
        print(f"Using coordinates: {x_col}, {y_col}")
        
        # Check for potential nested wells manually first
        print("\n--- Manual Coordinate Analysis ---")
        coords = df[[x_col, y_col, 'Well ID']].dropna()
        coords['x_rounded'] = coords[x_col].round(0) # Round to nearest meter (if UTM)
        coords['y_rounded'] = coords[y_col].round(0)
        
        # Find duplicates based on rounded coords
        dups = coords[coords.duplicated(subset=['x_rounded', 'y_rounded'], keep=False)]
        
        if not dups.empty:
            print(f"Found {len(dups)} rows with potentially identical locations (rounded to 1m):")
            print(dups.sort_values(by=['x_rounded', 'y_rounded']).to_string())
        else:
            print("No locations found with identical rounded coordinates (1m precision).")
            
            # Try looser precision
            print("\nTrying looser precision (10m)...")
            coords['x_rounded_10'] = (coords[x_col] / 10).round(0) * 10
            coords['y_rounded_10'] = (coords[y_col] / 10).round(0) * 10
            dups_10 = coords[coords.duplicated(subset=['x_rounded_10', 'y_rounded_10'], keep=False)]
            if not dups_10.empty:
                 print(f"Found {len(dups_10)} rows with potentially identical locations (rounded to 10m):")
                 print(dups_10.sort_values(by=['x_rounded_10', 'y_rounded_10']).to_string())
            else:
                print("Still no nested wells found even at 10m precision.")

    print("\n\n--- Running src.aquifer.analyze_aquifer_layers ---")
    try:
        results = analyze_aquifer_layers(df, VALUE_COL)
        print("\nAnalysis Results:")
        for k, v in results.items():
            print(f"{k}: {v}")
            
    except Exception as e:
        print(f"Error running analysis: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_debug()

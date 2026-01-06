import pandas as pd
import utils
import os

def debug_map():
    file_path = "processed_data.xlsx"
    if not os.path.exists(file_path):
        print("processed_data.xlsx not found.")
        return

    df = pd.read_excel(file_path)
    print("Columns:", df.columns.tolist())
    
    # Pick a target column
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    # Handle case where no other numeric cols exist
    available = [c for c in numeric_cols if c not in ['Easting', 'Northing', 'Latitude', 'Longitude', 'Time', 'Well ID']]
    if not available:
        print("No target numeric column found.")
        return
        
    # Prefer explicit known columns for testing
    if 'Static Water Level (mAHD)' in df.columns:
        target_col = 'Static Water Level (mAHD)'
    elif 'Groundwater Elevation mAHD' in df.columns:
         target_col = 'Groundwater Elevation mAHD'
    else:
        target_col = available[0]
        
    print(f"DEBUG: Selected Target Column: '{target_col}'")
    
    try:
        # Run utils logic (mocking streamlit cache/map gen)
        # We need to see what `auto_detect_utm_zone` picks
        
        # Call process_excel_data but capture stdout/print info inside utils
        print("--- Calling utils.process_excel_data ---")
        # FIX: Use keyword argument for value_column
        map_html, bounds, points, geojson  = utils.process_excel_data(df, value_column=target_col)
        
        print("--- Map Generation Successful ---")
        # Bounds are [[min_lat, min_lon], [max_lat, max_lon]]
        print(f"Calculated Image Bounds: {bounds}")
        center_lat = (bounds[0][0] + bounds[1][0]) / 2
        center_lon = (bounds[0][1] + bounds[1][1]) / 2
        print(f"Map Center Est: {center_lat}, {center_lon}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_map()

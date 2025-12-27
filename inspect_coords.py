import pandas as pd

file = "Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
sheet = "Attachment 3 - Cobden_GW_Lab"

try:
    print(f"\nScanning {sheet} for Coordinates...")
    df = pd.read_excel(file, sheet_name=sheet, header=None, nrows=50)
    
    # Search for "Easting" or "Northing" or "Lat" or "Lon" in the first column
    # or anywhere
    
    # Convert to string to search
    df_str = df.astype(str)
    
    mask = df_str.apply(lambda x: x.str.contains(r'East|North|Lat|Lon|Coord', case=False, na=False))
    
    # Get rows where this matches
    rows_with_coords = df[mask.any(axis=1)]
    
    if not rows_with_coords.empty:
        print("Found possible coordinate info:")
        print(rows_with_coords.iloc[:, :5].to_string()) # Show first few cols
    else:
        print("No explicit coordinate rows found in first 50 rows.")

except Exception as e:
    print(f"Error: {e}")

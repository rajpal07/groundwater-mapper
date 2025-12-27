import pandas as pd

file = "Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
sheet = "Attachment 3 - Cobden_GW_Lab"

try:
    print(f"\nScanning {sheet} for Well IDs...")
    # Read rows 0-15
    df = pd.read_excel(file, sheet_name=sheet, header=None, nrows=15)
    
    # Check each row for distinct values
    for index, row in df.iterrows():
        # Get unique string values that are not null
        vals = [str(x) for x in row.values if pd.notna(x)]
        if len(vals) > 0:
            print(f"Row {index}: {vals[:5]}...") # Show first 5 items
            
except Exception as e:
    print(f"Error: {e}")

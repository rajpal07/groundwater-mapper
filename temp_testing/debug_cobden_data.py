
import pandas as pd
import os

FILE_PATH = r"d:\anirudh_kahn\adi_version\Water_Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
HEADER_ROW = 5
PARAM = "Static Water Level (mAHD)"

print(f"Loading {FILE_PATH} with header={HEADER_ROW}...")

try:
    xl = pd.ExcelFile(FILE_PATH)
    print(f"Sheet Names Found: {xl.sheet_names}")
    
    TARGET_SHEET = "1. wwtf_gw_insitu(2)"
    if TARGET_SHEET in xl.sheet_names:
        print(f"\nProcessing sheet: {TARGET_SHEET}")
        df = pd.read_excel(FILE_PATH, sheet_name=TARGET_SHEET, header=HEADER_ROW)
    else:
        print(f"\nTarget sheet '{TARGET_SHEET}' NOT found. Using default/first sheet.")
        df = pd.read_excel(FILE_PATH, header=HEADER_ROW)
    
    # Clean Columns
    df.columns = df.columns.str.strip()
    
    print("\nColumns found:")
    print(df.columns.tolist())
    
    if PARAM not in df.columns:
        print(f"\nCRITICAL: '{PARAM}' not found in columns!")
        # Try finding close match
        closest = [c for c in df.columns if "Water Level" in c]
        print(f"Did you mean? {closest}")
        exit()
        
    # Convert to numeric
    df[PARAM] = pd.to_numeric(df[PARAM], errors='coerce')
    
    # Filter valid
    df_valid = df.dropna(subset=[PARAM])
    
    print(f"\nStats for '{PARAM}':")
    print(f"Count: {len(df_valid)}")
    print(f"Min: {df_valid[PARAM].min()}")
    print(f"Max: {df_valid[PARAM].max()}")
    print("-" * 30)
    
    # Search for M1 and M1A
    # Assuming 'Bore Name' or 'Name' or similar column exists.
    # Let's guess 'Bore Id' or similar based on previous experience or just search all text columns?
    # Usually first column?
    
    name_col = df.columns[0] # Guessing first column is ID
    print(f"assuming ID column is '{name_col}'")
    
    m1_row = df_valid[df_valid[name_col].astype(str).str.contains("M1", case=False, na=False)]
    
    print("\nRows matching 'M1':")
    if not m1_row.empty:
        print(m1_row[[name_col, PARAM]].to_string())
    else:
        print("No rows found for M1")

    # High Value Check
    print(f"\nRows with value > 141.7 (Likely EXCLUDED in GitHub version):")
    high_rows = df_valid[df_valid[PARAM] > 141.7]
    if not high_rows.empty:
        print(high_rows[[name_col, PARAM]].to_string())
    else:
        print("None found.")
        
    # Valid Rows for M1
    print("\nDetailed scan of M1 row (checking for 141.61 in other columns):")
    m1_row = df_valid[df_valid[name_col].astype(str) == "M1"]
    if not m1_row.empty:
        # Print all columns and their values
        row = m1_row.iloc[0]
        for col in df.columns:
            val = row[col]
            print(f"  {col}: {val}")
            
    # Check max of ALL numeric columns
    print("\nChecking Max of all numeric columns to find 141.61:")
    numeric_df = df_valid.select_dtypes(include=['number'])
    for col in numeric_df.columns:
        mx = numeric_df[col].max()
        if 141.4 < mx < 141.8:
            print(f"  MATCH FOUND: Column '{col}' has max {mx}")

    # Check for the GitHub Max
    print(f"\nSearching for value near 141.61:")
    target_row = df_valid[(df_valid[PARAM] > 141.60) & (df_valid[PARAM] < 141.62)]
    if not target_row.empty:
        print(target_row[[name_col, PARAM]].to_string())
    else:
        print("No exact match for 141.61 found.")
        
    # Simulate Filter
    print("\nSimulating 'Remove M1/M1A' filter:")
    filtered_df = df_valid[df_valid[PARAM] < 141.7]
    print(f"New Max: {filtered_df[PARAM].max()}")
    print(f"Count: {len(filtered_df)}")

except Exception as e:
    print(f"Error: {e}")

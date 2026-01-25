import pandas as pd

FILE_PATH = r"d:\anirudh_kahn\adi_version\Water_Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
SHEET = "Attachment 1 - WWTF_GW_insitu"
PARAM = "Static Water Level (mAHD)"

print(f"Loading sheet: {SHEET}\n")

df = pd.read_excel(FILE_PATH, sheet_name=SHEET, header=5)
df.columns = df.columns.str.strip()

print(f"Total rows: {len(df)}")
print(f"\nColumns: {df.columns.tolist()[:10]}")

# Check for the parameter column
if PARAM in df.columns:
    df[PARAM] = pd.to_numeric(df[PARAM], errors='coerce')
    df_valid = df.dropna(subset=[PARAM])
    
    print(f"\nValid {PARAM} rows: {len(df_valid)}")
    print(f"Min: {df_valid[PARAM].min()}")
    print(f"Max: {df_valid[PARAM].max()}")
    
    # Check for coordinate columns
    print(f"\nChecking coordinate columns:")
    for col in df.columns:
        if 'MGA' in col or 'Coord' in col or 'Lat' in col or 'Long' in col:
            print(f"  Found: '{col}'")
            
    # Show first few rows
    print(f"\nFirst 5 rows of key columns:")
    key_cols = ['Well ID', PARAM]
    if 'MGA2020 / MGA Zone 54' in df.columns:
        key_cols.append('MGA2020 / MGA Zone 54')
    print(df[key_cols].head(10).to_string())
else:
    print(f"\nERROR: Column '{PARAM}' not found!")
    print(f"Available columns: {df.columns.tolist()}")

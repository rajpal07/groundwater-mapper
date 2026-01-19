import pandas as pd
import os

input_file = "Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
output_file = "processed_data.xlsx"

print(f"Reading {input_file}...")

# 1. READ WATER DATA (Attachment 1)
sheet_water = 'Attachment 1 - WWTF_GW_insitu'
print(f"Reading Water Data from: {sheet_water}")

# Read first few rows to find header for Attachment 1
df_water_raw = pd.read_excel(input_file, sheet_name=sheet_water, header=None, nrows=20)
header_idx_water = -1
for i, row in df_water_raw.iterrows():
    row_str = row.astype(str).str.cat(sep=' ')
    if "Well ID" in row_str and "Static Water Level" in row_str:
        header_idx_water = i
        break

if header_idx_water == -1:
    print("❌ Could not find header in Attachment 1")
    exit()

print(f"Found Water header at row {header_idx_water}")
df_water = pd.read_excel(input_file, sheet_name=sheet_water, header=header_idx_water)

# Clean Water Columns
df_water.columns = df_water.columns.astype(str).str.strip().str.replace('\n', ' ')
print("Raw Water Columns:", df_water.columns.tolist())

# Rename coordinates if found (Handle merged headers manually if needed)
# Looking for "MGA2020" or similar
renames = {}
cols = df_water.columns.tolist()
for i, col in enumerate(cols):
    if "MGA" in col and "Zone54" in col.replace(" ", ""):
        renames[col] = "Easting"
        # The next column is likely Northing (often unnamed if merged header)
        if i + 1 < len(cols):
            renames[cols[i+1]] = "Northing"

if renames:
    print(f"Renaming coordinate columns: {renames}")
    df_water = df_water.rename(columns=renames)

# Check if we have Easting/Northing now
if 'Easting' not in df_water.columns:
    # Try finding by index if needed, but let's see output first
    print("Warning: Easting column not explicitly identified by name 'Easting' or 'MGA'.")

# Keep relevant columns
keep_cols_water = [c for c in df_water.columns if any(k in c for k in ['Well ID', 'Static Water Level (mAHD)', 'Easting', 'Northing'])]
print("Keeping Water columns:", keep_cols_water)
df_water = df_water[keep_cols_water].dropna(subset=['Well ID'])


# 2. READ CHEMICAL DATA (Attachment 3)
sheet_chem = 'Attachment 3 - Cobden_GW_Lab'
print(f"Reading Chemical Data from: {sheet_chem}")

# Read first few rows to find header for Attachment 3
df_chem_raw = pd.read_excel(input_file, sheet_name=sheet_chem, header=None, nrows=20)
header_idx_chem = -1
for i, row in df_chem_raw.iterrows():
    row_str = row.astype(str).str.cat(sep=' ')
    if "Well ID" in row_str and "Ammonia" in row_str: 
        header_idx_chem = i
        break
    if "Well ID" in row_str: 
         header_idx_chem = i
         break

if header_idx_chem == -1:
    print("❌ Could not find header in Attachment 3")
    header_idx_chem = 0

print(f"Found Chemical header at row {header_idx_chem}")
df_chem = pd.read_excel(input_file, sheet_name=sheet_chem, header=header_idx_chem)
df_chem.columns = df_chem.columns.astype(str).str.strip().str.replace('\n', ' ')

# Drop coordinates from chem 
drop_cols = [c for c in df_chem.columns if "Easting" in c or "Northing" in c or "Coordinates" in c]
df_chem = df_chem.drop(columns=drop_cols, errors='ignore')
df_chem = df_chem.dropna(subset=['Well ID'])

# 3. MERGE DATA
print("Merging datasets on 'Well ID'...")
df_water['Well ID'] = df_water['Well ID'].astype(str).str.strip()
df_chem['Well ID'] = df_chem['Well ID'].astype(str).str.strip()

merged_df = pd.merge(df_water, df_chem, on='Well ID', how='outer')

# 4. SAVE
merged_df.to_excel(output_file, index=False)
print(f"✅ merged data saved to {output_file}")
print("Final Columns:", merged_df.columns.tolist()[:15])

"""
Comprehensive Data Analysis Script for Cobden Attachment 1 Sheet
This script analyzes the data structure, coordinates, and values to understand
why the generated map might have issues.
"""

import pandas as pd
import numpy as np

FILE_PATH = r"d:\anirudh_kahn\adi_version\Water_Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
SHEET = "Attachment 1 - WWTF_GW_insitu"
PARAM = "Static Water Level (mAHD)"

print("="*80)
print("COBDEN ATTACHMENT 1 DATA ANALYSIS")
print("="*80)

# Load data
df = pd.read_excel(FILE_PATH, sheet_name=SHEET, header=5)
df.columns = df.columns.str.strip()

print(f"\n1. BASIC INFO")
print(f"   Total rows: {len(df)}")
print(f"   Columns: {len(df.columns)}")

# Check for parameter column
if PARAM not in df.columns:
    print(f"\n   ERROR: '{PARAM}' column not found!")
    print(f"   Available columns: {df.columns.tolist()}")
    exit()

# Convert to numeric
df[PARAM] = pd.to_numeric(df[PARAM], errors='coerce')
df_valid = df.dropna(subset=[PARAM])

print(f"\n2. PARAMETER: {PARAM}")
print(f"   Valid rows: {len(df_valid)}")
print(f"   Min: {df_valid[PARAM].min():.3f}")
print(f"   Max: {df_valid[PARAM].max():.3f}")
print(f"   Mean: {df_valid[PARAM].mean():.3f}")

# Check coordinates
print(f"\n3. COORDINATE ANALYSIS")
coord_col = None
for col in df.columns:
    if 'MGA' in col or 'Coord' in col:
        coord_col = col
        print(f"   Found coordinate column: '{coord_col}'")
        break

if coord_col:
    # Check if next column exists (should be Northing)
    col_idx = df.columns.get_loc(coord_col)
    if col_idx + 1 < len(df.columns):
        next_col = df.columns[col_idx + 1]
        print(f"   Next column (assumed Northing): '{next_col}'")
        
        # Map to Lat/Lon
        df['Easting'] = pd.to_numeric(df[coord_col], errors='coerce')
        df['Northing'] = pd.to_numeric(df[next_col], errors='coerce')
        
        # Filter valid coordinates
        df_coords = df_valid.dropna(subset=['Easting', 'Northing'])
        
        print(f"\n4. COORDINATE STATISTICS")
        print(f"   Valid coordinate rows: {len(df_coords)}")
        print(f"   Easting range: {df_coords['Easting'].min():.2f} to {df_coords['Easting'].max():.2f}")
        print(f"   Northing range: {df_coords['Northing'].min():.2f} to {df_coords['Northing'].max():.2f}")
        
        # Check for duplicate locations
        print(f"\n5. DUPLICATE LOCATION CHECK")
        duplicates = df_coords.groupby(['Easting', 'Northing']).size()
        dup_locations = duplicates[duplicates > 1]
        if len(dup_locations) > 0:
            print(f"   WARNING: Found {len(dup_locations)} locations with multiple wells:")
            for (e, n), count in dup_locations.items():
                wells = df_coords[(df_coords['Easting'] == e) & (df_coords['Northing'] == n)]['Well ID'].tolist()
                values = df_coords[(df_coords['Easting'] == e) & (df_coords['Northing'] == n)][PARAM].tolist()
                print(f"     Location ({e:.2f}, {n:.2f}): {count} wells")
                for w, v in zip(wells, values):
                    print(f"       - {w}: {v:.3f}")
        else:
            print(f"   No duplicate locations found")
            
        # Show all wells with coordinates
        print(f"\n6. ALL WELLS WITH VALID DATA")
        print(f"   {'Well ID':<10} {'Easting':<12} {'Northing':<12} {PARAM}")
        print(f"   {'-'*10} {'-'*12} {'-'*12} {'-'*25}")
        for idx, row in df_coords.iterrows():
            well_id = str(row['Well ID'])[:10]
            print(f"   {well_id:<10} {row['Easting']:<12.2f} {row['Northing']:<12.2f} {row[PARAM]:.3f}")
            
        # Check for spatial distribution
        print(f"\n7. SPATIAL DISTRIBUTION")
        easting_range = df_coords['Easting'].max() - df_coords['Easting'].min()
        northing_range = df_coords['Northing'].max() - df_coords['Northing'].min()
        print(f"   Easting span: {easting_range:.2f} meters")
        print(f"   Northing span: {northing_range:.2f} meters")
        print(f"   Aspect ratio: {easting_range/northing_range:.2f}")
        
        # Check for potential data issues
        print(f"\n8. DATA QUALITY CHECKS")
        
        # Check if coordinates are reasonable for MGA Zone 54
        if df_coords['Easting'].min() < 100000 or df_coords['Easting'].max() > 900000:
            print(f"   WARNING: Easting values outside typical MGA Zone 54 range")
        else:
            print(f"   ✓ Easting values within typical MGA Zone 54 range")
            
        if df_coords['Northing'].min() < 5000000 or df_coords['Northing'].max() > 7000000:
            print(f"   WARNING: Northing values outside typical MGA Zone 54 range")
        else:
            print(f"   ✓ Northing values within typical MGA Zone 54 range")
            
        # Check for value consistency
        value_range = df_coords[PARAM].max() - df_coords[PARAM].min()
        print(f"   Value range: {value_range:.3f} meters")
        if value_range > 50:
            print(f"   WARNING: Large value range might indicate data issues")
        else:
            print(f"   ✓ Value range seems reasonable")

print(f"\n{'='*80}")
print("ANALYSIS COMPLETE")
print("="*80)

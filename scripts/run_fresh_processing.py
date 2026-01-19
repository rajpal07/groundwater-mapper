"""
Fresh Processing Test - Deletes cache, processes file, shows new cache.
This will show us EXACTLY what LlamaParse is generating for Attachment 3.
"""
import os
import sys
import glob
import pandas as pd
from src.sheet_agent import SheetAgent

# Fix Windows encoding for Unicode output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Configuration
EXCEL_FILE = "Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
SHEET_NAME = "Attachment 3 - Cobden_GW_Lab"

# Try to get API key
try:
    import streamlit as st
    if "LLAMA_CLOUD_API_KEY" in st.secrets:
        API_KEY = st.secrets["LLAMA_CLOUD_API_KEY"]
    else:
        API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
except:
    API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

if not API_KEY:
    print("ERROR: LLAMA_CLOUD_API_KEY not found")
    print("Set it with: $env:LLAMA_CLOUD_API_KEY='your_key'  (PowerShell)")
    print("Or add to .streamlit/secrets.toml")
    sys.exit(1)

if not os.path.exists(EXCEL_FILE):
    print(f"ERROR: File not found: {EXCEL_FILE}")
    print("Update EXCEL_FILE path in this script")
    sys.exit(1)

print("="*100)
print("FRESH CACHE ANALYSIS - ATTACHMENT 3")
print("="*100)

# Step 1: Delete ALL old cache files
print("\n[STEP 1] Deleting all old cache files...")
print("-"*100)
cache_files = glob.glob("cache_llama_*.md")
if cache_files:
    for f in cache_files:
        os.remove(f)
        print(f"   ✓ Deleted: {f}")
    print(f"\n   Total deleted: {len(cache_files)} files")
else:
    print("   No cache files found (already clean)")

# Step 2: Process with AI (this will create fresh cache)
print("\n[STEP 2] Processing with AI Agent (FRESH - will create new cache)...")
print("-"*100)
print(f"   File: {EXCEL_FILE}")
print(f"   Sheet: {SHEET_NAME}")
print("\n   [*] Processing... (this may take 30-60 seconds)")

try:
    agent = SheetAgent(api_key=API_KEY)
    result_path = agent.process(
        EXCEL_FILE, 
        output_path="fresh_test_output.xlsx", 
        selected_sheets=[SHEET_NAME]
    )
    
    if result_path and os.path.exists(result_path):
        print(f"\n   ✓ Processing complete!")
        print(f"   ✓ Output saved to: {result_path}")
    else:
        print("\n   ✗ Processing failed - no output file created")
        sys.exit(1)
        
except Exception as e:
    print(f"\n   ✗ Processing failed with error:")
    print(f"   {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Find and show the NEW cache file
print("\n[STEP 3] Finding FRESH cache file...")
print("-"*100)

cache_files = glob.glob("cache_llama_*.md")
if not cache_files:
    print("   ✗ ERROR: No cache file was created!")
    print("   This means LlamaParse didn't cache the result")
    sys.exit(1)

# Get the newest cache file
newest_cache = max(cache_files, key=os.path.getmtime)
print(f"   ✓ Found fresh cache: {newest_cache}")

with open(newest_cache, 'r', encoding='utf-8') as f:
    cache_content = f.read()

lines = cache_content.split('\n')
print(f"   ✓ Cache size: {len(cache_content)} characters, {len(lines)} lines")

# Step 4: Show cache structure
print("\n[STEP 4] Cache Structure Analysis")
print("-"*100)

# Look for headers
print("\n   [HEADERS] Headers found (lines starting with #):")
header_count = 0
for i, line in enumerate(lines[:50]):
    if line.strip().startswith('#'):
        header_count += 1
        print(f"      Line {i:3d}: {line[:80]}")

if header_count == 0:
    print("      ⚠️  No headers found in first 50 lines")

# Look for Well ID table
print("\n   [TABLE] Searching for 'Well ID' table...")
well_id_line = None
for i, line in enumerate(lines):
    if 'well id' in line.lower() and '|' in line:
        well_id_line = i
        print(f"      ✓ Found 'Well ID' table at line {i}")
        break

if well_id_line is None:
    print("      ✗ No 'Well ID' table found in entire cache!")
else:
    # Show the table header area (5 lines before and 10 lines after)
    print(f"\n   [CONTEXT] Table header context (lines {max(0, well_id_line-5)} to {well_id_line+10}):")
    print("   " + "-"*96)
    for i in range(max(0, well_id_line-5), min(len(lines), well_id_line+11)):
        marker = ">>>" if i == well_id_line else "   "
        print(f"   {marker} {i:3d}: {lines[i][:90]}")
    print("   " + "-"*96)

# Look for coordinate keywords
print("\n   [COORDS] Searching for coordinate keywords...")
coord_keywords = ['easting', 'northing', 'latitude', 'longitude', 'eassting']
coord_lines = []
for i, line in enumerate(lines):
    for kw in coord_keywords:
        if kw in line.lower():
            coord_lines.append((i, kw, line))
            break

if coord_lines:
    print(f"      ✓ Found {len(coord_lines)} lines with coordinate keywords:")
    for line_num, keyword, line_text in coord_lines[:10]:  # Show first 10
        print(f"      Line {line_num:3d} ({keyword}): {line_text[:80]}")
else:
    print("      ✗ NO coordinate keywords found in entire cache!")
    print("      ⚠️  This means LlamaParse is not extracting coordinate columns!")

# Step 5: Check the processed output
print("\n[STEP 5] Processed Output Analysis")
print("-"*100)

df_output = pd.read_excel(result_path)
print(f"   ✓ Output shape: {df_output.shape} (rows, columns)")
print(f"\n   [COLUMNS] All columns in processed output:")
for i, col in enumerate(df_output.columns, 1):
    has_coord = any(kw in col.lower() for kw in coord_keywords)
    marker = "[*] COORDINATE" if has_coord else ""
    print(f"      {i:2d}. {col} {marker}")

# Check for coordinates
coord_cols = [col for col in df_output.columns if any(kw in col.lower() for kw in coord_keywords)]
if coord_cols:
    print(f"\n   ✓ Found {len(coord_cols)} coordinate column(s): {coord_cols}")
    for col in coord_cols:
        non_null = df_output[col].notna().sum()
        samples = df_output[col].dropna().head(3).tolist()
        print(f"      {col}: {non_null} non-null values, samples: {samples}")
else:
    print("\n   ✗ NO coordinate columns in output!")

# Final summary
print("\n" + "="*100)
print("SUMMARY")
print("="*100)
print(f"✓ Cache file created: {newest_cache}")
print(f"✓ Well ID table found: {'YES' if well_id_line is not None else 'NO'}")
print(f"✓ Coordinate keywords in cache: {'YES' if coord_lines else 'NO'}")
print(f"✓ Coordinate columns in output: {'YES' if coord_cols else 'NO'}")

if not coord_cols:
    print("\n[!] PROBLEM IDENTIFIED:")
    if not coord_lines:
        print("   LlamaParse is NOT extracting coordinate column headers from the Excel file.")
        print("   This could be due to:")
        print("   1. Complex multi-row headers that LlamaParse can't parse")
        print("   2. Merged cells in the Excel file")
        print("   3. Non-standard table structure")
    else:
        print("   Coordinates are in the cache but not being extracted by our table parsing logic.")
        print("   Check the table header context above to see the structure.")

print("\n[TIP] Next step: Review the cache file directly:")
print(f"   code {newest_cache}")
print("="*100)

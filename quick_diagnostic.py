"""
Quick diagnostic to show what columns are being extracted.
This version reads API key from streamlit secrets if available.
"""
import os
import sys
import pandas as pd
from src.sheet_agent import SheetAgent
import glob

# Try to get API key from streamlit secrets
try:
    import streamlit as st
    if "LLAMA_CLOUD_API_KEY" in st.secrets:
        API_KEY = st.secrets["LLAMA_CLOUD_API_KEY"]
    else:
        API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")
except:
    API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

if not API_KEY:
    print("ERROR: Set LLAMA_CLOUD_API_KEY environment variable or add to .streamlit/secrets.toml")
    sys.exit(1)

# Configuration - UPDATE THESE
EXCEL_FILE = "@Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
SHEET_NAME = "Attachment 3 - Cobden_GW_Lab"

print("="*80)
print("QUICK COORDINATE DIAGNOSTIC")
print("="*80)

# Clean old cache
print("\n[1] Cleaning cache...")
for f in glob.glob("cache_llama_*.md"):
    os.remove(f)
    print(f"   Removed: {f}")

# Check raw Excel
print("\n[2] Raw Excel columns:")
df_raw = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
print(f"   Total columns: {len(df_raw.columns)}")
for i, col in enumerate(df_raw.columns, 1):
    coord_marker = " ⭐" if any(kw in col.lower() for kw in ['easting', 'northing', 'lat', 'lon']) else ""
    print(f"   {i:2d}. {col}{coord_marker}")

# Process with AI
print("\n[3] Processing with AI (fresh, no cache)...")
agent = SheetAgent(api_key=API_KEY)
result_path = agent.process(EXCEL_FILE, output_path="quick_diagnostic.xlsx", selected_sheets=[SHEET_NAME])

# Check AI output
print("\n[4] AI output columns:")
df_ai = pd.read_excel(result_path)
print(f"   Total columns: {len(df_ai.columns)}")
for i, col in enumerate(df_ai.columns, 1):
    coord_marker = " ⭐" if any(kw in col.lower() for kw in ['easting', 'northing', 'lat', 'lon']) else ""
    print(f"   {i:2d}. {col}{coord_marker}")

# Show latest cache
print("\n[5] Latest markdown cache:")
cache_files = glob.glob("cache_llama_*.md")
if cache_files:
    latest = max(cache_files, key=os.path.getmtime)
    print(f"   File: {latest}")
    with open(latest, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    print(f"   Total lines: {len(lines)}")
    print("\n   First 20 lines:")
    for i, line in enumerate(lines[:20], 1):
        print(f"   {i:3d}: {line.rstrip()[:100]}")

print("\n" + "="*80)
print("DONE - Check if ⭐ coordinates appear in both Raw and AI output")
print("="*80)

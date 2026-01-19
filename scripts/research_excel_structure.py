import pandas as pd
import os

files = [
    "Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx",
    "some1.xlsx",
    "STANHOPE_JAN-25.xlsx"
]

print("--- Excel Structure Research ---\n")

for f in files:
    if not os.path.exists(f):
        print(f"[MISSING] {f}")
        continue
        
    print(f"FILE: {f}")
    try:
        # Load Excel File to get sheet names
        xls = pd.ExcelFile(f)
        sheets = xls.sheet_names
        print(f"  Sheets ({len(sheets)}): {sheets}")
        
        # Analyze each sheet briefly
        for sheet in sheets:
            df = pd.read_excel(f, sheet_name=sheet, nrows=5, header=None)
            print(f"    Sheet '{sheet}': {df.shape} (Rows x Cols)")
            # Check for header-like content in first few rows
            # print(df.astype(str).values[:2]) 
            
    except Exception as e:
        print(f"  ERROR reading file: {e}")
    print("-" * 30)

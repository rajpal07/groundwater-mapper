import pandas as pd
import os

files = [
    "WCT Huntly 12052025.xlsx",
    "Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
]

for file in files:
    if not os.path.exists(file):
        print(f"Skipping {file} (not found)")
        continue
        
    print(f"\n{'='*50}")
    print(f"Inspecting: {file}")
    print(f"{'='*50}")
    
    try:
        xl = pd.ExcelFile(file)
        print(f"Sheet Names: {xl.sheet_names}")
        
        # Check specific sheets based on file type
        for i, sheet in enumerate(xl.sheet_names):
            if file.startswith("Cobden") and ("Attachment 3" in sheet or i == 3):  # Check Attachment 3 explicitly
                print(f"\n--- [TARGET SHEET] Sheet {i}: {sheet} ---")
                df = pd.read_excel(file, sheet_name=sheet, nrows=10)
                print(df.head().to_string())
                print(f"Columns: {list(df.columns)}")
                
            elif file.startswith("WCT") and i == 0:
                 print(f"\n--- Sheet {i}: {sheet} ---")
                 df = pd.read_excel(file, sheet_name=sheet, nrows=5)
                 print(df.head().to_string())
                 print(f"Columns: {list(df.columns)}")

    except Exception as e:
        print(f"Error reading {file}: {e}")

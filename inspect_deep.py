import pandas as pd
import os

file = "Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
sheet = "Attachment 3 - Cobden_GW_Lab"

try:
    print(f"\nScanning {file} - {sheet} rows 10-15...")
    df = pd.read_excel(file, sheet_name=sheet, header=None, skiprows=10, nrows=10)
    print(df.to_string())
except Exception as e:
    print(f"Error: {e}")

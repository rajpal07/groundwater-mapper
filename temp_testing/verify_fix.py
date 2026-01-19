
import pandas as pd
import numpy as np
import sys
import os
import matplotlib.pyplot as plt
from scipy.interpolate import Rbf

# Add src to path
sys.path.append(os.getcwd())

def verify_fix(file_path):
    print(f"Loading {file_path}...")
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()
    target_col = 'Groundwater Elevation mAHD'
    
    # Minimal Cleaning
    df['Easting'] = pd.to_numeric(df['Easting'], errors='coerce')
    df['Northing'] = pd.to_numeric(df['Northing'], errors='coerce')
    df[target_col] = pd.to_numeric(df[target_col], errors='coerce')
    df = df.dropna(subset=['Easting', 'Northing', target_col])
    
    # 1. Verify Interval Logic
    z_min, z_max = df[target_col].min(), df[target_col].max()
    z_range = z_max - z_min
    print(f"\nZ Range: {z_range:.4f} ({z_min:.2f} - {z_max:.2f})")
    
    # New Logic Replication
    if z_range > 10: interval = 1.0
    elif z_range > 5: interval = 0.5
    elif z_range > 2: interval = 0.2
    elif z_range > 0.5: interval = 0.1
    else: interval = 0.05
    
    print(f"Chosen Interval: {interval}")
    
    start = np.floor(z_min / interval) * interval
    end = np.ceil(z_max / interval) * interval + interval
    levels = np.arange(start, end, interval)
    print(f"Number of Levels: {len(levels)}")
    print(f"Levels: {levels}")
    
    if len(levels) < 15:
        print("PASS: Interval selection effectively reduced level count.")
    else:
        print("FAIL: Still too many levels.")

    # 2. Verify Gradient Code (by reading the file content directly)
    # Since I cannot import the modified code dynamically easily without reloading,
    # reading the file is a sure way to check if 'replace_file' worked.
    
    with open("d:/anirudh_kahn/adi_version/src/data.py", "r") as f:
        content = f.read()
        
    if "dz_dy, dz_dx = np.gradient(grid_z)" in content:
        print("\nPASS: Code modification found: 'dz_dy, dz_dx = np.gradient(grid_z)'")
    else:
        print("\nFAIL: Code modification NOT found.")

if __name__ == "__main__":
    verify_fix("d:/anirudh_kahn/adi_version/Shepparton 29.09.2025.xlsx")

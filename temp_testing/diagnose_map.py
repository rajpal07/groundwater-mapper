
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import griddata, Rbf
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

# Mocking data processing from src/data.py to inspect internals
def inspect_logic(file_path):
    print(f"Loading {file_path}...")
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()
    
    target_col = 'Groundwater Elevation mAHD'
    print(f"Target Column: {target_col}")
    
    # Cleaning
    df['Easting'] = pd.to_numeric(df['Easting'], errors='coerce')
    df['Northing'] = pd.to_numeric(df['Northing'], errors='coerce')
    df[target_col] = pd.to_numeric(df[target_col], errors='coerce')
    df = df.dropna(subset=['Easting', 'Northing', target_col])
    
    print(f"Data Rows: {len(df)}")
    print(df[['Easting', 'Northing', target_col]].head())

    x_col, y_col = 'Easting', 'Northing'
    
    # Grid setup
    xi = np.linspace(df[x_col].min(), df[x_col].max(), 200)
    yi = np.linspace(df[y_col].min(), df[y_col].max(), 200)
    grid_x, grid_y = np.meshgrid(xi, yi)
    
    # Interpolation
    # Use simple RBF to match code
    rbf = Rbf(df[x_col], df[y_col], df[target_col], function='linear')
    grid_z = rbf(grid_x, grid_y)
    
    # Gradient Check
    # np.gradient returns [gradient_axis0, gradient_axis1]
    # axis0 is Y (rows), axis1 is X (cols)
    grads = np.gradient(grid_z)
    dz_axis0 = grads[0] # Change w.r.t Y (rows)
    dz_axis1 = grads[1] # Change w.r.t X (cols)
    
    print("\n--- Gradient Diagnosis ---")
    print(f"Shape of grid_z: {grid_z.shape}")
    print(f"Shape of grads[0] (axis0/Y): {dz_axis0.shape}")
    
    # The code does: dz_dx, dz_dy = np.gradient(grid_z)
    # This implies dz_dx = grads[0] (which is Y-gradient!)
    # and dz_dy = grads[1] (which is X-gradient!)
    
    # Let's verify with a simple synthetic case
    print("\n--- Synthetic Test ---")
    # Z = X (gradient should be [1, 0] roughly)
    x_syn = np.linspace(0, 10, 11)
    y_syn = np.linspace(0, 10, 11)
    gx, gy = np.meshgrid(x_syn, y_syn)
    gz = gx # Z increases with X only
    
    syn_grads = np.gradient(gz)
    syn_dz_axis0 = syn_grads[0] # dZ/dRow (Y)
    syn_dz_axis1 = syn_grads[1] # dZ/dCol (X)
    
    print(f"Synthetic Z = X")
    print(f"Check dZ/dRow (Axis 0) [Should be 0]: Mean={np.mean(syn_dz_axis0)}")
    print(f"Check dZ/dCol (Axis 1) [Should be >0]: Mean={np.mean(syn_dz_axis1)}")
    
    if np.abs(np.mean(syn_dz_axis1)) > np.abs(np.mean(syn_dz_axis0)):
        print("CONFIRMED: np.gradient returns [dZ/dy, dZ/dx] (axis0, axis1)")
    else:
        print("Weird numpy behavior?")

    # Current Code Simulation
    code_dz_dx, code_dz_dy = np.gradient(gz)
    print(f"Code 'dz_dx' (assigned from axis0/Y): Mean={np.mean(code_dz_dx)}")
    print(f"Code 'dz_dy' (assigned from axis1/X): Mean={np.mean(code_dz_dy)}")
    
    if np.mean(code_dz_dx) == 0 and np.mean(code_dz_dy) > 0:
         print("BUG VERIFIED: Code assigns dZ/dY to 'dz_dx' and dZ/dX to 'dz_dy'.")
    
    # Levels Check
    print("\n--- Contour Levels Check ---")
    z_min, z_max = df[target_col].min(), df[target_col].max()
    z_range = z_max - z_min
    print(f"Z Min: {z_min}, Z Max: {z_max}, Range: {z_range}")
    
    interval = 1.0 if z_range > 10 else 0.5 if z_range > 5 else 0.2 if z_range > 2 else 0.1 if z_range > 1 else 0.05 if z_range > 0.5 else 0.01
    print(f"Calculated Interval: {interval}")
    
    start = np.floor(z_min / interval) * interval
    end = np.ceil(z_max / interval) * interval + interval
    levels = np.arange(start, end, interval)
    print(f"Generated Levels: {levels}")
    print(f"Number of Levels: {len(levels)}")

if __name__ == "__main__":
    inspect_logic("d:/anirudh_kahn/adi_version/Shepparton 29.09.2025.xlsx")


import numpy as np
import pandas as pd
from scipy.interpolate import griddata
import itertools
import sys

def calculate_epa_exact_direction(points, quiet=False):
    """
    Implements the EPA '3-point' or 'n-point' problem logic using Least Squares Plane Fitting.
    Equation: h = ax + by + c
    Gradient vector = (a, b)
    Flow direction = (-a, -b) (Downhill)
    
    points: list of dicts [{'x': 100, 'y': 200, 'h': 50}, ...]
    """
    if not quiet: print("\n--- Method 1: EPA / Exact Plane Fitting ---")
    
    A_data = []
    h_data = []
    
    for p in points:
        A_data.append([p['x'], p['y'], 1])
        h_data.append(p['h'])
        
    A = np.array(A_data)
    h = np.array(h_data)
    
    try:
        coeffs, residuals, rank, s = np.linalg.lstsq(A, h, rcond=None)
        a, b, c_intercept = coeffs
    except:
        return None, (0,0)

    if not quiet: print(f"Computed Plane Coefficients: a={a:.6f}, b={b:.6f}")
    
    flow_u = -a
    flow_v = -b
    
    math_angle_rad = np.arctan2(flow_v, flow_u)
    math_angle_deg = np.degrees(math_angle_rad)
    azimuth = (90 - math_angle_deg) % 360
    
    if not quiet: print(f"Flow Direction (Azimuth): {azimuth:.2f} degrees")
    return azimuth, (flow_u, flow_v)

def calculate_map_grid_direction(points, grid_res=100, quiet=False):
    """
    Simulates the logic used in the map generation script:
    1. Griddata interpolation (Linear)
    2. np.gradient calculation
    """
    if not quiet: print("\n--- Method 2: Map Script Simulation (Grid + Gradient) ---")
    
    df = pd.DataFrame(points)
    x = df['x'].values
    y = df['y'].values
    z = df['h'].values
    
    # Create grid covering the area
    padding = 10
    xi = np.linspace(x.min() - padding, x.max() + padding, grid_res)
    yi = np.linspace(y.min() - padding, y.max() + padding, grid_res)
    grid_x, grid_y = np.meshgrid(xi, yi)
    
    # 2. Interpolate (Linear / TIN equivalent)
    grid_z = griddata((x, y), z, (grid_x, grid_y), method='linear')
    
    # 3. Calculate Gradient using np.gradient
    dx_step = xi[1] - xi[0]
    dy_step = yi[1] - yi[0]
    
    dz_dy, dz_dx = np.gradient(grid_z, dy_step, dx_step)
    
    # 4. Sample Gradient at the Centroid
    centroid_x = x.mean()
    centroid_y = y.mean()
    
    idx_x = (np.abs(xi - centroid_x)).argmin()
    idx_y = (np.abs(yi - centroid_y)).argmin()
    
    sampled_dz_dx = dz_dx[idx_y, idx_x]
    sampled_dz_dy = dz_dy[idx_y, idx_x]
    
    if np.isnan(sampled_dz_dx) or np.isnan(sampled_dz_dy):
        # Try finding a valid point
        valid_mask = ~np.isnan(dz_dx)
        if valid_mask.any():
            sampled_dz_dx = dz_dx[valid_mask][0]
            sampled_dz_dy = dz_dy[valid_mask][0]
        else:
            return None, None

    if not quiet: print(f"Sampled Gradient at Centroid: dz/dx: {sampled_dz_dx:.6f}, dz/dy: {sampled_dz_dy:.6f}")
    
    flow_u = -sampled_dz_dx
    flow_v = -sampled_dz_dy
    
    math_angle_rad = np.arctan2(flow_v, flow_u)
    math_angle_deg = np.degrees(math_angle_rad)
    azimuth = (90 - math_angle_deg) % 360
    
    if not quiet: print(f"Flow Direction (Azimuth): {azimuth:.2f} degrees")
    return azimuth, (flow_u, flow_v)

def run_verification():
    # Real Data Load
    file_path = r"d:\anirudh_kahn\adi_version\Shepparton 29.09.2025.xlsx"
    print(f"Loading real data from: {file_path}")
    
    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip() 
    
    # Filter for valid data
    required_cols = ['Well ID', 'Easting', 'Northing', 'Groundwater Elevation mAHD']
    df = df.dropna(subset=required_cols)
    
    # Optional: Filter for only 'GWB' wells if needed, but user said 'all combinations'
    # df = df[df['Well ID'].astype(str).str.startswith('GWB')]

    all_wells = []
    for _, row in df.iterrows():
        all_wells.append({
            'x': row['Easting'],
            'y': row['Northing'],
            'h': row['Groundwater Elevation mAHD'],
            'name': str(row['Well ID'])
        })
        
    combos = list(itertools.combinations(all_wells, 3))
    print(f"Found {len(all_wells)} valid wells. Testing {len(combos)} unique 3-well combinations...")
    
    print("-" * 80)
    print(f"{'Combo':<30} | {'EPA (Deg)':<10} | {'Map (Deg)':<10} | {'Diff':<8} | {'Status'}")
    print("-" * 80)

    results = []
    
    for combo in combos:
        points = list(combo)
        names = "+".join([p['name'] for p in points])
        
        # 1. Exact
        az_exact, _ = calculate_epa_exact_direction(points, quiet=True)
        if az_exact is None: continue

        # 2. Grid
        az_grid, _ = calculate_map_grid_direction(points, quiet=True)
        if az_grid is None: continue
        
        diff = abs(az_exact - az_grid)
        if diff > 180: diff = 360 - diff
        
        status = "MATCH" if diff < 1.0 else "FAIL"
        
        # Truncate names for display
        display_names = (names[:27] + '..') if len(names) > 27 else names
        
        print(f"{display_names:<30} | {az_exact:<10.2f} | {az_grid:<10.2f} | {diff:<8.4f} | {status}")
        results.append(diff)

    print("-" * 80)
    if results:
        avg_diff = sum(results) / len(results)
        max_diff = max(results)
        print(f"Summary Statistics:")
        print(f"Total Combinations Tested: {len(results)}")
        print(f"Average Difference: {avg_diff:.4f} degrees")
        print(f"Max Difference:     {max_diff:.4f} degrees")
        
        if max_diff < 1.0:
            print("\nVERDICT: EXCELLENT (Map logic is mathematically identical to EPA logic)")
        else:
            print("\nVERDICT: WARNING (Some combinations show deviation)")
    else:
        print("No valid combinations processed.")

if __name__ == "__main__":
    run_verification()

import pandas as pd
import numpy as np
import io
import base64
import matplotlib.pyplot as plt
from scipy.interpolate import griddata, Rbf
from pyproj import Transformer
from src.geo import auto_detect_utm_zone

def get_point_name(row, idx):
    if 'Well ID' in row: return str(row['Well ID'])
    if 'Name' in row: return str(row['Name'])
    return f"Point {idx}"

def process_excel_data(file, interpolation_method='linear', reference_points=None, value_column='Groundwater Elevation mAHD', generate_contours=True, colormap='viridis'):
    """
    Reads Excel file (or DataFrame), interpolates data, and generates a contour image.
    
    Args:
        file: Excel file path, object, or pandas DataFrame
        interpolation_method: 'linear' or 'cubic'
        reference_points: Optional list of points (e.g. from KMZ) to help with zone detection
        value_column: The specific column to map (default: 'Groundwater Elevation mAHD')
        generate_contours: If True, generates interpolation and overlay. If False, returns None for image.
        
    Returns:
        - image_base64: Base64 encoded PNG image of the contour (or None).
        - bounds: [[min_lat, min_lon], [max_lat, max_lon]] for the image overlay (or None).
        - target_points: List of dictionaries for target points (lat, lon, id).
        - bbox_geojson: GeoJSON of the bounding box.
    """
    if isinstance(file, pd.DataFrame):
        df = file.copy()
    else:
        df = pd.read_excel(file)
        
    df.columns = df.columns.str.strip()

    # Filter data (same logic as original)
    if 'Name' in df.columns and df['Name'].astype(str).str.contains('TOC1', na=False).any():
        df = df[df['Name'].str.contains('TOC1', na=False)].copy()

    target_col = value_column
    if target_col not in df.columns:
        raise ValueError(f"Column '{target_col}' not found in data.")

    df = df[df[target_col].notna()]
    df = df[df[target_col].notna()]
    df = df[df[target_col] != '-']

    # --- Coordinate Mapping for separate formats ---
    if 'Geographical Coordinates (GDA2020)' in df.columns:
        print("Detected 'Geographical Coordinates (GDA2020)' - Mapping to Lat/Lon...")
        try:
            col_idx = df.columns.get_loc('Geographical Coordinates (GDA2020)')
            # Assuming adjacent column is Longitude (Lat, Lon convention in this file)
            lat_col = df.columns[col_idx]
            lon_col = df.columns[col_idx + 1] 
            df['Latitude'] = df[lat_col]
            df['Longitude'] = df[lon_col]
        except Exception as e:
            print(f"Error mapping specific coordinates: {e}")
    # -----------------------------------------------

    df['Easting'] = pd.to_numeric(df.get('Easting'), errors='coerce')
    df['Northing'] = pd.to_numeric(df.get('Northing'), errors='coerce')
    df['Latitude'] = pd.to_numeric(df.get('Latitude'), errors='coerce')
    df['Longitude'] = pd.to_numeric(df.get('Longitude'), errors='coerce')
    
    df[target_col] = pd.to_numeric(df[target_col], errors='coerce')
    
    # Check if we have Easting/Northing OR Lat/Lon
    use_utm = False
    if df['Easting'].notna().any() and df['Northing'].notna().any():
        df = df.dropna(subset=['Easting', 'Northing', target_col])
        use_utm = True
    elif df['Latitude'].notna().any() and df['Longitude'].notna().any():
        df = df.dropna(subset=['Latitude', 'Longitude', target_col])
        use_utm = False
    else:
        raise ValueError("No valid coordinates (Easting/Northing or Latitude/Longitude) found.")

    if df.empty:
        raise ValueError("No valid data found in Excel file.")

    # Auto-detect UTM zone using enhanced algorithm
    transformer = None
    if use_utm:
        selected_epsg, confidence, zone_info = auto_detect_utm_zone(df, reference_points)
        transformer = Transformer.from_crs(selected_epsg, "EPSG:4326", always_xy=True)
    else:
        print("Using existing Latitude/Longitude coordinates.")
        # Create a dummy transformer that just passes through? No, handle logic below.
        pass

    # -------------------------------------------------------------
    # ALWAYS Generate Interpolation & Colored Visualization
    # Conditionally add contour lines and streamplot arrows
    # -------------------------------------------------------------
    
    # Interpolation grid
    if use_utm:
        x_col, y_col = 'Easting', 'Northing'
    else:
        x_col, y_col = 'Longitude', 'Latitude'

    xi = np.linspace(df[x_col].min(), df[x_col].max(), 200)
    yi = np.linspace(df[y_col].min(), df[y_col].max(), 200)
    grid_x, grid_y = np.meshgrid(xi, yi)
    
    # Reproject grid corners to get lat/lon bounds for the IMAGE
    min_x, max_x = grid_x.min(), grid_x.max()
    min_y, max_y = grid_y.min(), grid_y.max()
    
    if use_utm:
        # Transform corners from UTM to Lat/Lon
        min_lon, min_lat = transformer.transform(min_x, min_y)
        max_lon, max_lat = transformer.transform(max_x, max_y)
    else:
        # Already Lat/Lon
        min_lon, min_lat = min_x, min_y
        max_lon, max_lat = max_x, max_y
    
    # Folium expects [[lat_min, lon_min], [lat_max, lon_max]]
    image_bounds = [[min_lat, min_lon], [max_lat, max_lon]]

    # Interpolation (Switch to RBF for extrapolation/filling gaps)
    # griddata defaults to 'linear' and leaves NaNs outside convex hull.
    # Rbf (Radial Basis Function) smoothly extrapolates to fill the grid.
    
    # (Optional but robust)

    # Interpolation Strategy
    # 'hybrid': Cubic for contour lines (smooth), Linear for arrows/colors (accurate).
    # 'linear': Linear for everything (strict engineering accuracy).
    
    # 1. Base Grid (Linear/TIN) - Used for Physics (Arrows) and Colors
    grid_z_linear = griddata((df[x_col], df[y_col]), df[target_col], (grid_x, grid_y), method='linear')
    grid_z = grid_z_linear # Default grid

    # 2. Smooth Grid (Cubic) - Used ONLY for Contour Lines in Hybrid mode
    grid_z_smooth = None
    if interpolation_method == 'hybrid':
        grid_z_smooth = griddata((df[x_col], df[y_col]), df[target_col], (grid_x, grid_y), method='cubic')
        # Fill NaNs in smooth grid with linear values
        if np.isnan(grid_z_smooth).any():
            mask = np.isnan(grid_z_smooth)
            grid_z_smooth[mask] = grid_z_linear[mask]

    # Generate Contour Image
    z_min, z_max = df[target_col].min(), df[target_col].max()
    z_range = z_max - z_min
    
    # Smart Levels (Fixed Intervals)
    if z_range > 10: interval = 1.0
    elif z_range > 5: interval = 0.5
    elif z_range > 2: interval = 0.2
    elif z_range > 0.5: interval = 0.05
    else: interval = 0.05
    
    # Ensure nice numbers
    levels = np.arange(np.floor(z_min/interval)*interval, np.ceil(z_max/interval)*interval + interval, interval)
    
    # Plot
    fig, ax = plt.subplots(figsize=(10, 10))
    # CRITICAL: Force equal aspect ratio to prevent distortion of arrows and geometry
    ax.set_aspect('equal')
    
    # Filled contours (Visuals) - Always uses Linear Grid for accuracy of colors vs arrows
    contour_filled = ax.contourf(grid_x, grid_y, grid_z, levels=levels, cmap=colormap, alpha=0.7)
    
    # Contour lines and Arrows - Only for groundwater/elevation
    if generate_contours:
        # Determine which grid to use for Lines
        grid_for_lines = grid_z_smooth if interpolation_method == 'hybrid' else grid_z
        
        # Plot Contour Lines
        contour_lines = ax.contour(grid_x, grid_y, grid_for_lines, levels=levels, colors='black', linewidths=0.8, alpha=0.8)
        # Add labels to contour lines for clarity
        ax.clabel(contour_lines, inline=True, fontsize=8, fmt='%.2f')
        
        # Quiver for flow direction (Arrows at points) - Uses Linear Grid (Physics)
        
        # Quiver for flow direction (Arrows at points)
        # Calculate step sizes for correct gradient scaling (fix for aspect ratio distortion)
        dx_step = xi[1] - xi[0]
        dy_step = yi[1] - yi[0]
        
        # Pass step sizes: axis0=y (dy_step), axis1=x (dx_step)
        dz_dy, dz_dx = np.gradient(grid_z, dy_step, dx_step) 
        
        # Normalize vectors for consistent arrow size
        magnitude = np.sqrt(dz_dx**2 + dz_dy**2)
        # Avoid division by zero
        u = -dz_dx / (magnitude + 1e-10)
        v = -dz_dy / (magnitude + 1e-10)
        
        # Plot Arrows (Quiver)
        # angles='xy' is CRITICAL: it ensures arrows point effectively from (x,y) to (x+u, y+v) in DATA coordinates.
        # Combined with set_aspect('equal'), this guarantees correct direction.
        
        # Reduced density: step=15 (was 19) to increase count further
        step = 15
        
        # Shorter arrows: scale=0.12 (was 0.08). Reduce length significantly.
        ax.quiver(grid_x[::step, ::step], grid_y[::step, ::step], u[::step, ::step], v[::step, ::step], 
                  color='red', angles='xy', scale_units='xy', scale=0.12/dx_step, width=0.003, headwidth=4, headlength=5, alpha=0.9)

    ax.axis('off')
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    
    buf = io.BytesIO()
    # High DPI for HD output (prevents pixelation)
    plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0, dpi=300)
    plt.close()
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')

    # Target Points (Lat/Lon) with Borewell Names
    if use_utm:
        target_lons, target_lats = transformer.transform(df['Easting'].values, df['Northing'].values)
    else:
        target_lons = df['Longitude'].values
        target_lats = df['Latitude'].values
    
    target_points = [
        {
            "lat": lat, 
            "lon": lon, 
            "id": i,
            "name": get_point_name(df.iloc[i], i),
            "value": df.iloc[i][target_col]
        } 
        for i, (lat, lon) in enumerate(zip(target_lats, target_lons))
    ]

    # Bounding Box GeoJSON
    bbox_geojson = {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [min_lon, min_lat],
                [max_lon, min_lat],
                [max_lon, max_lat],
                [min_lon, max_lat],
                [min_lon, min_lat]
            ]]
        },
        "properties": {}
    }
    # print(f"DEBUG: BBox Coordinates: {bbox_geojson['geometry']['coordinates']}")

    return image_base64, image_bounds, target_points, bbox_geojson

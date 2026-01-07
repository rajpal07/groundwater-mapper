import os
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from scipy.interpolate import griddata
from pyproj import Transformer
from zipfile import ZipFile
from pykml import parser
from shapely.geometry import Point, box, mapping
import geopandas as gpd
import ee
import streamlit as st
from google.oauth2.service_account import Credentials
print("DEBUG: Loading utils.py - Version FixImports_v1")
import geemap.foliumap as geemap_folium # Validated: Use Folium backend explicitly
import geemap.coreutils 
import folium
from folium.raster_layers import ImageOverlay
import io
import base64

# === Earth Engine Setup ===
GEE_PROJECT_ID = 'geekahn'

def init_earth_engine():
    """Initialize Google Earth Engine."""
    try:
        # Try to use Streamlit Secrets for Service Account (Cloud Deployment)
        if "EARTHENGINE_TOKEN" in st.secrets:
            print("Using Service Account from Streamlit Secrets...")
            # Parse the JSON string from secrets
            # strict=False allows control characters (like newlines) inside strings, 
            # which fixes common copy-paste errors in the private key.
            token_str = st.secrets["EARTHENGINE_TOKEN"]
            service_account_info = json.loads(token_str, strict=False)
            
            # CRITICAL: Remove the token from environment variables.
            # 'geemap' automatically tries to read this env var and often crashes if the format isn't perfect.
            # Since we are handling authentication manually below, we hide it from geemap.
            if "EARTHENGINE_TOKEN" in os.environ:
                os.environ.pop("EARTHENGINE_TOKEN")
            
            # Create credentials with correct EE Scope
            scopes = ['https://www.googleapis.com/auth/earthengine']
            credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
            
            # Initialize with credentials
            ee.Initialize(credentials=credentials, project=GEE_PROJECT_ID)
            print("Google Earth Engine initialized successfully (Service Account)!")
            return True
            
        # Fallback to local authentication (Development)
        else:
            print("No Service Account token found. Trying default authentication...")
            ee.Initialize(project=GEE_PROJECT_ID)
            print("Google Earth Engine initialized successfully (Local)!")
            return True
            
    except Exception as e:
        print(f"Warning: Could not initialize Earth Engine: {e}")
        print("For cloud deployment, please ensure 'EARTHENGINE_TOKEN' is set in Streamlit Secrets.")
        print("For local development, run 'earthengine authenticate' in your terminal.")
        return False

# Initialize GEE on import
init_earth_engine()

# === UTM Zone Detection Functions ===

# === UTM Zone Detection Functions ===

def calculate_utm_zone_from_lonlat(longitude, latitude):
    """
    Calculate UTM zone number from longitude and latitude.
    
    Args:
        longitude: Longitude in degrees
        latitude: Latitude in degrees
    
    Returns:
        UTM zone number (1-60)
    """
    # Standard UTM zone formula
    zone = int((longitude + 180) / 6) + 1
    return zone


def get_australian_utm_zones():
    """
    Returns a dictionary of Australian UTM zones with their coverage.
    
    Returns:
        dict: {zone_number: {'epsg': str, 'lon_min': float, 'lon_max': float, 'description': str}}
    """
    return {
        49: {'epsg': 'EPSG:32749', 'lon_min': 108, 'lon_max': 114, 'description': 'Western Australia'},
        50: {'epsg': 'EPSG:32750', 'lon_min': 114, 'lon_max': 120, 'description': 'Western Australia'},
        51: {'epsg': 'EPSG:32751', 'lon_min': 120, 'lon_max': 126, 'description': 'WA/NT'},
        52: {'epsg': 'EPSG:32752', 'lon_min': 126, 'lon_max': 132, 'description': 'NT/SA'},
        53: {'epsg': 'EPSG:32753', 'lon_min': 132, 'lon_max': 138, 'description': 'South Australia'},
        54: {'epsg': 'EPSG:32754', 'lon_min': 138, 'lon_max': 144, 'description': 'SA/VIC'},
        55: {'epsg': 'EPSG:32755', 'lon_min': 144, 'lon_max': 150, 'description': 'VIC/NSW/TAS'},
        56: {'epsg': 'EPSG:32756', 'lon_min': 150, 'lon_max': 156, 'description': 'NSW/QLD'}
    }



# Try to import global-land-mask for robust detection
try:
    from global_land_mask import globe
    HAS_LAND_MASK = True
except ImportError:
    HAS_LAND_MASK = False
    print("Warning: global-land-mask not installed. Land/Water check disabled.")

def auto_detect_utm_zone(df, reference_points=None):
    """
    Auto-detect the correct UTM zone for Australian coordinates.
    Uses mathematical calculation and Land/Water check.
    
    Args:
        df: DataFrame with 'Easting' and 'Northing' columns
        reference_points: Optional list of dicts/objects with 'lat', 'lon' (e.g. from KMZ)
                          Used as ground truth to resolve zone ambiguity.
    
    Returns:
        tuple: (epsg_code, confidence, zone_info)
            - epsg_code: str like "EPSG:32754"
            - confidence: str like "high", "medium", "low"
            - zone_info: dict with detection details
    """
    avg_easting = df['Easting'].mean()
    avg_northing = df['Northing'].mean()
    
    australian_zones = get_australian_utm_zones()
    zones_to_test = []
    
    # Strategy 0: Use Reference Points (Ground Truth)
    if reference_points:
        try:
            # Calculate centroid of reference points
            if isinstance(reference_points[0], (dict)):
                 ref_lons = [p['lon'] for p in reference_points]
                 ref_lats = [p['lat'] for p in reference_points]
            else:
                 # Assume objects with x/y or lon/lat attributes
                 if hasattr(reference_points[0], 'x'):
                     ref_lons = [p.x for p in reference_points]
                     ref_lats = [p.y for p in reference_points]
                 else:
                     ref_lons = []
                     ref_lats = []
            
            if ref_lons:
                avg_ref_lon = sum(ref_lons) / len(ref_lons)
                avg_ref_lat = sum(ref_lats) / len(ref_lats)
                
                expected_zone = calculate_utm_zone_from_lonlat(avg_ref_lon, avg_ref_lat)
                print(f"📌 KMZ Reference Hint: Lon {avg_ref_lon:.4f}°, Lat {avg_ref_lat:.4f}° -> Zone {expected_zone}S")
                zones_to_test.append(expected_zone)
        except Exception as e:
            print(f"Warning: Could not use reference points for zone hint: {e}")

    # Strategy 1: Estimate zone from Easting value
    if 200000 <= avg_easting <= 800000:
        candidates = [55, 54, 56, 53, 52, 51, 50, 49] # Prioritize 55/54 for Victoria
    else:
        candidates = list(australian_zones.keys())
    
    # Add candidates to test list (preserving order)
    for c in candidates:
        if c not in zones_to_test:
            zones_to_test.append(c)
            
    # Strategy 2: Transform and Check (Validity + Land Mask)
    best_match = None
    best_confidence = "low" # low, medium, high, very_high (land)
    
    print(f"DEBUG: Testing Zones: {zones_to_test}")
    
    for zone_num in zones_to_test:
        if zone_num not in australian_zones: continue 
        
        zone_data = australian_zones[zone_num]
        epsg_code = zone_data['epsg']
        
        try:
            # Transform to lat/lon
            transformer = Transformer.from_crs(epsg_code, "EPSG:4326", always_xy=True)
            test_lon, test_lat = transformer.transform(avg_easting, avg_northing)
            
            # 1. Geographic Bounds Check (Is it in/near Australia?)
            if not (112 <= test_lon <= 155 and -45 <= test_lat <= -10):
                continue
            
            calculated_zone = calculate_utm_zone_from_lonlat(test_lon, test_lat)
            is_zone_match = (calculated_zone == zone_num)
            
            # 2. Land Check (The "Robust" Check)
            is_on_land = False
            if HAS_LAND_MASK:
                try:
                    is_on_land = globe.is_land(test_lat, test_lon)
                except:
                    pass # Globe might fail on edge cases
            
            # Scoring Logic
            current_confidence = "low"
            if is_on_land:
                current_confidence = "very_high"
            elif is_zone_match:
                current_confidence = "high"
            elif abs(calculated_zone - zone_num) <= 1:
                current_confidence = "medium"
            
            print(f"  Testing Zone {zone_num}S: Lon {test_lon:.2f}, Lat {test_lat:.2f} | Match? {is_zone_match} | Land? {is_on_land} -> {current_confidence.upper()}")
            
            # Acceptance Logic:
            # If we find "very_high" (Land), we take it immediately (unless we had a specific reference hint earlier?)
            # Actually, reference hint is reliable. Land is next most reliable.
            
            if current_confidence == "very_high":
                best_match = {
                    'epsg': epsg_code, 'zone': zone_num, 'lon': test_lon, 'lat': test_lat, 'description': zone_data['description']
                }
                best_confidence = "very_high"
                break # Found land! Stop searching.
                
            if current_confidence == "high":
                # High (Math match) but maybe water? Keep looking for Land, but store this as backup.
                if best_confidence not in ["very_high", "high"]: # Don't downgrade
                    best_match = {
                         'epsg': epsg_code, 'zone': zone_num, 'lon': test_lon, 'lat': test_lat, 'description': zone_data['description']
                    }
                    best_confidence = "high"
            
            elif current_confidence == "medium":
                 if best_confidence == "low":
                    best_match = {
                         'epsg': epsg_code, 'zone': zone_num, 'lon': test_lon, 'lat': test_lat, 'description': zone_data['description']
                    }
                    best_confidence = "medium"
            
            elif best_confidence == "low" and best_match is None:
                 best_match = {
                        'epsg': epsg_code, 'zone': zone_num, 'lon': test_lon, 'lat': test_lat, 'description': zone_data['description']
                   }
                
        except Exception as e:
            print(f"Error testing zone {zone_num}: {e}")
            continue
    
    # Fallback
    if best_match is None:
        print("⚠ Warning: Could not auto-detect UTM zone. Defaulting to 55S.")
        best_match = {'epsg': 'EPSG:32755', 'zone': 55, 'lon': None, 'lat': None, 'description': 'Default'}
        best_confidence = "low"

    print(f"✓ Selected Zone {best_match['zone']}S ({best_match['epsg']}) with {best_confidence} confidence.")
    return best_match['epsg'], best_confidence, best_match



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
    df = df[df[target_col] != '-']

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
    from scipy.interpolate import Rbf
    
    # Add a small amount of noise to coordinates to prevent singular matrix if points are duplicate/collinear
    # (Optional but robust)
    
    # Interpolation Strategy:
    # 1. Use RBF for smooth internal interpolation (or Linear as fallback).
    # 2. STRICTLY MASK to the Convex Hull of the data points to avoid misleading extrapolation.
    #    (Groundwater data should not be inferred far beyond monitoring wells).
    
    # Create a mask using 'linear' interpolation which intrinsically returns NaNs outside the convex hull
    mask_z = griddata((df[x_col], df[y_col]), df[target_col], (grid_x, grid_y), method='linear')
    is_outside_hull = np.isnan(mask_z)

    try:
        # Try RBF for smoothness
        from scipy.interpolate import Rbf
        # 'linear' radial basis function is good for groundwater
        rbf = Rbf(df[x_col], df[y_col], df[target_col], function='linear')
        grid_z = rbf(grid_x, grid_y)
        
        # Apply Hull Mask
        grid_z[is_outside_hull] = np.nan
        
    except Exception as e:
        print(f"RBF Interpolation failed: {e}. Fallback to linear.")
        # Linear already computed as mask_z (valid info inside hull)
        grid_z = mask_z
        # No 'nearest' fill anymore - we WANT NaNs outside.

    # Generate Contour Image
    z_min, z_max = df[target_col].min(), df[target_col].max()
    z_range = z_max - z_min
    
    # Dynamic Interval Logic (Restored from Backup)
    interval = 1.0 if z_range > 10 else 0.5 if z_range > 5 else 0.2 if z_range > 2 else 0.1 if z_range > 1 else 0.05 if z_range > 0.5 else 0.01
    
    # Ensure range isn't zero
    if z_range == 0:
        levels = np.linspace(z_min, z_max, 20)
    else:
        start = np.floor(z_min / interval) * interval
        end = np.ceil(z_max / interval) * interval + interval
        levels = np.arange(start, end, interval)

    # Plot
    fig, ax = plt.subplots(figsize=(10, 10))
    # Filled contours (Visuals) - Always show colored gradient
    # colormap is passed via argument (default 'viridis')
    contour_filled = ax.contourf(grid_x, grid_y, grid_z, levels=levels, cmap=colormap, alpha=0.6)
    
    # Contour lines and Arrows - Only for groundwater/elevation
    if generate_contours:
        # Contour lines (Structure) - Made darker and slightly thicker for visibility
        contour_lines = ax.contour(grid_x, grid_y, grid_z, levels=levels, colors='black', linewidths=0.8, alpha=0.8)
        
        # Quiver for flow direction (Arrows at points)
        dz_dx, dz_dy = np.gradient(grid_z)
        
        # Normalize vectors for consistent arrow size (Restored)
        magnitude = np.sqrt(dz_dx**2 + dz_dy**2)
        # Avoid division by zero
        u = -dz_dx / (magnitude + 1e-10)
        v = -dz_dy / (magnitude + 1e-10)
        
        # Plot Arrows (Quiver)
        # HD Settings: Higher density (lower step), optimized width/scale for 300 DPI
        step = 10 
        # width scale interacts with figsize and dpi. 0.002 is relative to plot width.
        ax.quiver(grid_x[::step, ::step], grid_y[::step, ::step], u[::step, ::step], v[::step, ::step], 
                  color='red', scale=25, width=0.0025, headwidth=3, headlength=4, alpha=0.9)

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
    
    # helper to safely get name
    def get_point_name(row, idx):
        if 'Well ID' in row: return str(row['Well ID'])
        if 'Name' in row: return str(row['Name'])
        return f"Point {idx}"
        
    target_points = [
        {
            "lat": lat, 
            "lon": lon, 
            "id": i,
            "name": get_point_name(df.iloc[i], i)
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

def extract_kmz_points(kmz_file):
    """
    Extracts points from a KMZ file.
    Returns:
        - points: List of shapely Points (lon, lat)
    """
    # KMZ is a zip
    with ZipFile(kmz_file, 'r') as kmz:
        # Find KML
        kml_filename = next((f for f in kmz.namelist() if f.endswith('.kml')), None)
        if not kml_filename:
            raise ValueError("No .kml file found in KMZ")
        
        with kmz.open(kml_filename, 'r') as f:
            root = parser.parse(f).getroot()

    ns = {'kml': 'http://www.opengis.net/kml/2.2'}
    placemarks = root.xpath('.//kml:Placemark[kml:Point]', namespaces=ns)
    
    points = []
    for pm in placemarks:
        coords = pm.Point.coordinates.text.strip()
        lon, lat, *_ = map(float, coords.split(','))
        points.append(Point(lon, lat))
        
    return points

def create_map(image_base64, image_bounds, target_points, kmz_points=None, bbox_geojson=None, legend_label="Groundwater Elevation (mAHD)"):
    """
    Creates an interactive GEE-based map with contour overlay.
    Points are added via JavaScript injection for full interactivity.
    """
    # Calculate center from target points
    if target_points:
        center_lat = sum(p['lat'] for p in target_points) / len(target_points)
        center_lon = sum(p['lon'] for p in target_points) / len(target_points)
    else:
        center_lat, center_lon = 0, 0

    # Create GEE map with satellite basemap - Controls disabled
    
    # --- Production Environment Configuration ---
    # We manually initialized Earth Engine with Service Account credentials above.
    # We now override geemap's default initialization to prevent it from attempting 
    # redundant OAuth flows (which cause 'client_secret' errors in cloud environments).
    try:
        # Check if EE is alive
        ee.Image(0).getInfo()
        # If alive, configure geemap to use existing session
        print("Earth Engine active. Configuring geemap to use existing session.")
        
        # Patch coreutils (imported at top level now)
        geemap.coreutils.ee_initialize = lambda *args, **kwargs: None
        
        # Patch the module we interact with directly
        geemap_folium.ee_initialize = lambda *args, **kwargs: None
        
    except Exception as e:
        print(f"Earth Engine not active, attempting default initialization: {e}")

    m = geemap_folium.Map(center=[center_lat, center_lon], zoom=16, basemap='SATELLITE', max_zoom=19, zoom_control=False, attributionControl=False)
    print(f"DEBUG: Map Type: {type(m)}")
    # print(f"DEBUG: Map Attributes: {dir(m)[:10]}...") # Inspect first few attributes


    # Add contour overlay
    img_url = f"data:image/png;base64,{image_base64}"
    ImageOverlay(
        image=img_url,
        bounds=image_bounds,
        opacity=0.7,
        interactive=False,
        cross_origin=True,
        zindex=1,
        name="Groundwater Contour"
    ).add_to(m)

    # Add bounding box if provided
    if bbox_geojson:
        folium.GeoJson(
            bbox_geojson,
            name='Bounding Box',
            style_function=lambda x: {
                "color": "red",
                "weight": 5,
                "dashArray": "5, 5",
                "fillOpacity": 0.0
            }
        ).add_to(m)

    # Add layer control at the end to ensure all layers are initialized
    # folium.LayerControl().add_to(m) # Disabled as per request

    # Note: Target points are added via JavaScript
    # in inject_controls_to_html() for full interactivity and geemap compatibility
    
    return m


def get_colormap_info(cmap_name):
    """
    Returns hex codes and descriptive labels for a given colormap.
    Returns: (low_hex, mid_hex, high_hex, high_label_desc, low_label_desc)
    """
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    
    try:
        cmap = plt.get_cmap(cmap_name)
    except:
        cmap = plt.get_cmap('viridis')
        
    # Get colors at 0.0 (Low), 0.5 (Mid), 1.0 (High)
    low_rgb = cmap(0.0)[:3]
    mid_rgb = cmap(0.5)[:3]
    high_rgb = cmap(1.0)[:3]
    
    low_hex = mcolors.to_hex(low_rgb)
    mid_hex = mcolors.to_hex(mid_rgb)
    high_hex = mcolors.to_hex(high_rgb)
    
    # Heuristic labels for common maps users might pick
    # This helps the "High (Yellow)" text be accurate
    labels = {
        'viridis': ('Yellow', 'Purple'),
        'plasma': ('Yellow', 'Blue'),
        'inferno': ('Yellow', 'Black'),
        'magma': ('Light Pink', 'Black'),
        'cividis': ('Yellow', 'Blue'),
        'RdYlBu': ('Blue', 'Red'), # Note: Matplotlib RdYlBu has Red at 0 (low) and Blue at 1 (high)? No, Red is Low index? Wait.
                                     # RdYlBu: Red (0) -> Yellow -> Blue (1). IF used as is.
                                     # Often used as '_r' for Red=High.
        'RdYlBu_r': ('Red', 'Blue'), # Red (1) -> Blue (0)
        'Spectral': ('Red', 'Purple'), # 0=Red, 1=Purple/Blue? Spectral is Red->Yellow->Blue/Purple
        'Spectral_r': ('Red', 'Blue'), 
        'coolwarm': ('Red', 'Blue'),
        'bwr': ('Red', 'Blue'),
        'seismic': ('Red', 'Blue')
    }
    
    # Generic fallback
    high_desc, low_desc = labels.get(cmap_name, ('High Color', 'Low Color'))
    
    # Adjust for inverted maps automatically-ish if possible, otherwise rely on manual list
    if cmap_name.endswith('_r') and cmap_name not in labels:
         # simple swap approximation
         base = cmap_name[:-2]
         if base in labels:
             low_desc, high_desc = labels[base]
             
    return low_hex, mid_hex, high_hex, high_desc, low_desc
    

def inject_controls_to_html(html_file, image_bounds, target_points, kmz_points=None, legend_label="Elevation", colormap="viridis", project_details=None):
    """
    Injects JavaScript into HTML. Now supports dynamic legend label.
    """
    # Shorten label for legend if too long
    legend_label_short = legend_label
    if len(legend_label) > 15:
        # e.g. "Nitrate as N" -> "Nitrate..." if extremely long, but "Nitrate as N" is fine.
        # "Groundwater Elevation mAHD" -> "GW Elev..."
        if "Elevation" in legend_label: legend_label_short = "Elevation"
        else: legend_label_short = legend_label.split(' ')[0]

    # Get dynamic colors for legend
    low_hex, mid_hex, high_hex, high_desc, low_desc = get_colormap_info(colormap)

    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Calculate initial center from target points
    if target_points:
        center_lat = sum(p['lat'] for p in target_points) / len(target_points)
        center_lon = sum(p['lon'] for p in target_points) / len(target_points)
        initial_center = [center_lat, center_lon]
    else:
        initial_center = [0, 0]

    # Default Project Details
    if project_details is None:
        project_details = {}
    
    pd_safe = {
        "attachment_title": project_details.get("attachment_title", "Attachment 1, Figure 1 – Site Location Plan"),
        "general_notes": project_details.get("general_notes", "General Notes:"),
        "drawn_by": project_details.get("drawn_by", "LC"),
        "project": project_details.get("project", "Project Project"), # Placeholder
        "address": project_details.get("address", "Address Location"),
        "drawing_title": project_details.get("drawing_title", "SITE MAP"),
        "authorised_by": project_details.get("authorised_by", "Authorised By"),
        "date": project_details.get("date", "24-02-2023"),
        "client": project_details.get("client", "Client Name"),
        "job_no": project_details.get("job_no", "#773")
    }

    target_points_json = json.dumps(target_points)
    kmz_points_json = json.dumps([{"lat": p.y, "lon": p.x} for p in kmz_points] if kmz_points else [])
    image_bounds_json = json.dumps(image_bounds)
    initial_center_json = json.dumps(initial_center)

    js_code = f"""
<!-- Force Hide Leaflet Controls -->
<style>
/* Hide Zoom Control */
.leaflet-control-zoom {{
    display: none !important;
}}
/* Hide Layer Control */
.leaflet-control-layers {{
    display: none !important;
}}
/* Hide Attribution */
.leaflet-control-attribution {{
    display: none !important;
}}
/* Hide Draw Toolbar if present */
.leaflet-draw {{
    display: none !important;
}}
/* Borewell ID Labels */
/* Borewell ID Labels */
.borewell-label {{
    background: #FFFFFF !important;
    border: 1px solid #000000 !important;
    border-radius: 0px !important;
    padding: 1px 4px !important;
    font-weight: bold !important;
    font-family: Arial, sans-serif !important;
    font-size: 11px !important;
    color: #000000 !important;
    box-shadow: none !important;
}}
</style>

<style>
/* Footer Strip Styles */
#snapshot-footer {{
    display: none; /* Hidden by default, shown during snapshot composite */
    width: 100%;
    background: white;
    border-top: 2px solid #333;
    font-family: Arial, sans-serif;
    color: #333;
    box-sizing: border-box;
    padding: 0;
    margin: 0;
}}

.footer-container {{
    display: flex;
    flex-direction: column;
    width: 100%;
}}

.footer-top {{
    padding: 5px 10px;
    border-bottom: 2px solid #333;
    font-weight: bold;
    font-size: 14px;
}}

.footer-main {{
    display: flex;
    width: 100%;
    height: 120px; /* Fixed height for consistency */
}}

.footer-notes {{
    flex: 1;
    padding: 10px;
    border-right: 2px solid #333;
    font-size: 12px;
}}

.footer-details {{
    flex: 1;
    display: grid;
    grid-template-columns: 100px 1fr;
    grid-gap: 4px;
    padding: 10px;
    font-size: 11px;
    align-content: start;
}}

.footer-label {{
    font-weight: bold;
    text-align: right;
    padding-right: 5px;
}}

.footer-value {{
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
</style>

<!-- html-to-image for snapshot -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/html-to-image/1.11.11/html-to-image.js"></script>

<!-- Compass UI - Realistic and Draggable -->
<div id="compass" style="position:absolute; top:80px; left:10px; z-index:9999; width:80px; height:80px; cursor:move; touch-action: none; -webkit-user-select: none; user-select: none;" title="Drag to reposition | Click to reset rotation">
    <div id="compassInner" style="position:relative; width:100%; height:100%; background:radial-gradient(circle, rgba(255,255,255,0.95) 0%, rgba(240,240,240,0.95) 100%); border-radius:50%; border:4px solid #2c3e50; transition: transform 0.3s ease;">
        <!-- Outer ring with degree marks -->
        <div style="position:absolute; top:50%; left:50%; width:90%; height:90%; transform:translate(-50%, -50%);">
            <!-- Cardinal direction markers -->
            <div style="position:absolute; top:2px; left:50%; transform:translateX(-50%); color:#c0392b; font-weight:bold; font-size:18px;">N</div>
            <div style="position:absolute; bottom:2px; left:50%; transform:translateX(-50%); color:#34495e; font-weight:bold; font-size:14px;">S</div>
            <div style="position:absolute; top:50%; right:2px; transform:translateY(-50%); color:#34495e; font-weight:bold; font-size:14px;">E</div>
            <div style="position:absolute; top:50%; left:2px; transform:translateY(-50%); color:#34495e; font-weight:bold; font-size:14px;">W</div>
        </div>
        
        <!-- Center circle -->
        <div style="position:absolute; top:50%; left:50%; width:12px; height:12px; transform:translate(-50%, -50%); background:#2c3e50; border-radius:50%; border:2px solid #ecf0f1;"></div>
        
        <!-- North arrow (red) -->
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);">
            <div style="position:absolute; bottom:6px; left:50%; transform:translateX(-50%); width:0; height:0; border-left:8px solid transparent; border-right:8px solid transparent; border-bottom:35px solid #c0392b;"></div>
        </div>
        
        <!-- South arrow (white) -->
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);">
            <div style="position:absolute; top:6px; left:50%; transform:translateX(-50%); width:0; height:0; border-left:8px solid transparent; border-right:8px solid transparent; border-top:35px solid #ecf0f1;"></div>
        </div>
        
        <!-- Decorative tick marks -->
        <div style="position:absolute; top:8px; left:50%; width:2px; height:8px; background:#95a5a6; transform:translateX(-50%);"></div>
        <div style="position:absolute; bottom:8px; left:50%; width:2px; height:8px; background:#95a5a6; transform:translateX(-50%);"></div>
        <div style="position:absolute; top:50%; right:8px; width:8px; height:2px; background:#95a5a6; transform:translateY(-50%);"></div>
        <div style="position:absolute; top:50%; left:8px; width:8px; height:2px; background:#95a5a6; transform:translateY(-50%);"></div>
    </div>
</div>

<!-- Controls UI -->
<div style="position:absolute; top:10px; right:10px; z-index:9999; background:rgba(255,255,255,0.95); padding:10px; border-radius:6px; font-family:Arial,Helvetica,sans-serif;">
  <div style="margin-bottom:8px;">
    <label>Move Scale: </label>
    <input type="number" id="moveScale" value="0.01" step="0.01" min="0.01" style="width:60px;">
    <br>
    <button onclick="moveImage('up')" style="margin:2px;">⬆️</button>
    <button onclick="moveImage('down')" style="margin:2px;">⬇️</button>
    <button onclick="moveImage('left')" style="margin:2px;">⬅️</button>
    <button onclick="moveImage('right')" style="margin:2px;">➡️</button>
  </div>

  <div style="margin-bottom:8px;">
    <label>Scale Factor: </label>
    <input type="number" id="scaleAmount" value="1.1" step="0.1" min="0.1" style="width:60px;">
    <br>
    <button onclick="scaleImage('expand')" style="margin:2px;">🔍 Expand</button>
    <button onclick="scaleImage('contract')" style="margin:2px;">🔎 Contract</button>
  </div>

  <div style="margin-bottom:8px;">
    <label>Rotation (deg): </label>
    <input type="number" id="rotationDegrees" value="15" step="1" style="width:60px;">
    <br>
    <button onclick="rotateImage('left')" style="margin:2px;">↺</button>
    <button onclick="rotateImage('right')" style="margin:2px;">↻</button>
  </div>

  <div>
    <button onclick="resetImageBounds()" style="background:#ff6b6b; color:white; margin-bottom:5px;">🔁 Reset</button>
    <br>
    <button id="btn-snapshot" onclick="takeSnapshot()" disabled style="background:#4CAF50; color:white; padding: 5px 10px; cursor:not-allowed; opacity:0.6;">⏳ Loading...</button>
  </div>
</div>

<!-- Legend -->
<div id="map-legend" style="position:absolute; bottom:10px; right:10px; z-index:9999; background:rgba(255,255,255,0.95); padding:10px; border-radius:6px; font-family:Arial,Helvetica,sans-serif; font-size:12px; box-shadow:0 0 5px rgba(0,0,0,0.2); cursor:move;">
  <div style="font-weight:bold; margin-bottom:8px; border-bottom:1px solid #ddd; padding-bottom:4px;">Legend</div>
  
  <!-- Points -->
  <div style="display:flex; align-items:center; margin-bottom:10px;">
    <div style="width:12px; height:12px; background:#FF6B35; border-radius:50%; border:2px solid white; margin-right:8px;"></div>
    <span>Monitoring Bore</span>
  </div>

  <!-- Contour Guide -->
  <div style="font-weight:bold; margin-bottom:6px; margin-top:8px; border-top:1px solid #ddd; padding-top:6px;">How to Read Contour</div>
  
  <!-- High Gradient -->
  <div style="display:flex; align-items:center; margin-bottom:4px;">
    <div style="width:20px; height:10px; background:linear-gradient(to right, {mid_hex}, {high_hex}); margin-right:8px; border:1px solid #999;"></div>
    <span>High {legend_label_short} ({high_desc})</span>
  </div>
  
  <!-- Low Gradient -->
  <div style="display:flex; align-items:center; margin-bottom:4px;">
    <div style="width:20px; height:10px; background:linear-gradient(to right, {low_hex}, {mid_hex}); margin-right:8px; border:1px solid #999;"></div>
    <span>Low {legend_label_short} ({low_desc})</span>
  </div>
  
  <div style="display:flex; align-items:center;">
    <div style="font-size:16px; color:red; font-weight:bold; margin-right:8px; line-height:10px;">&rarr;</div>
    <span>Flow Direction</span>
  </div>
</div>

<!-- Hidden Footer Template -->
<div id="snapshot-footer">
    <div class="footer-container">
        <div class="footer-top">
             <span id="footer-attachment-title">{pd_safe['attachment_title']}</span>
        </div>
        <div class="footer-main">
            <div class="footer-notes">
                <strong>{pd_safe['general_notes']}</strong><br>
                <br>
                <!-- Space for notes -->
            </div>
            
            <!-- Logo Section substitute -->
            <div style="width: 150px; border-right: 2px solid #333; display: flex; align-items: center; justify-content: center; flex-direction: column;">
                <div style="font-size: 24px; font-weight: bold; color: #4DA6FF;">ee</div>
                <div style="font-size: 10px; color: #4DA6FF;">edwards<br>environmental</div>
            </div>

            <div class="footer-details">
                <!-- Client Info -->
                <div class="footer-label">Client:</div>
                <div class="footer-value">{pd_safe['client']}</div>

                 <div class="footer-label">Project:</div>
                <div class="footer-value">{pd_safe['project']}</div>
                
                <div class="footer-label">Location:</div>
                <div class="footer-value">{pd_safe['address']}</div>
                
            </div>
            
            <div class="footer-details" style="border-left: 1px solid #ccc;">
                 <div class="footer-label">Drawing Title:</div>
                <div class="footer-value"><strong>{pd_safe['drawing_title']}</strong></div>

                <div class="footer-label">Drawn:</div>
                <div class="footer-value">{pd_safe['drawn_by']}</div>
                
                <div class="footer-label">Project No:</div>
                <div class="footer-value">{pd_safe['job_no']}</div>
                
                 <div class="footer-label">Date:</div>
                <div class="footer-value">{pd_safe['date']}</div>
                
                <div class="footer-label">Figure No:</div>
                <div class="footer-value">1 Rev. A</div>
            </div>
        </div>
    </div>
</div>

<!-- Optional: Input for Attachment Title in Controls -->
<div id="footer-controls" style="position: absolute; top: 350px; right: 10px; z-index: 9999; background: rgba(255,255,255,0.9); padding: 5px; border-radius: 4px; font-size: 11px; width: 200px;">
    <strong>Footer Settings</strong><br>
    <label>Figure Title:</label>
    <input type="text" id="input-attachment-title" value="{pd_safe['attachment_title']}" style="width: 100%; margin-top:2px;" oninput="document.getElementById('footer-attachment-title').innerText = this.value">
</div>

<!-- Debug Status -->
<div id="js-status" style="position:fixed; top:50%; left:50%; transform:translate(-50%, -50%); background:red; color:white; padding:20px; z-index:10000; font-size:24px; font-weight:bold; border: 4px solid white; pointer-events:none; opacity: 0.8;">
  JS: Waiting for Map...
</div>

<script>
(() => {{
  let map = null;
  let overlay = null;
  let originalBounds = null;
  let currentRotation = 0;
  
  const bluePoints = {kmz_points_json};
  const orangePoints = {target_points_json};
  const overlayBounds = {image_bounds_json};
  const initialCenter = {initial_center_json};

  // --- Update Compass Rotation ---
  function updateCompass() {{
    const compassInner = document.getElementById('compassInner');
    if (compassInner) {{
      compassInner.style.transform = `rotate(${{-currentRotation}}deg)`;
    }}
  }}

  // --- Generic Draggable Logic ---
  function makeDraggable(element, options = {{}}) {{
    if (!element) return;
    
    let isDragging = false;
    let hasMoved = false;
    let startX, startY, initialLeft, initialTop;
    
    function getEventCoords(e) {{
      if (e.touches && e.touches.length > 0) {{
        return {{ x: e.touches[0].clientX, y: e.touches[0].clientY }};
      }}
      return {{ x: e.clientX, y: e.clientY }};
    }}
    
    function handleStart(e) {{
      isDragging = true;
      hasMoved = false;
      
      const coords = getEventCoords(e);
      startX = coords.x;
      startY = coords.y;
      
      const rect = element.getBoundingClientRect();
      
      // Calculate offset relative to parent for correct absolute positioning
      const parent = element.offsetParent || document.body;
      const parentRect = parent.getBoundingClientRect();
      
      initialLeft = rect.left - parentRect.left;
      initialTop = rect.top - parentRect.top;
      
      element.style.cursor = 'grabbing';
      
      const m = findMap();
      if (m) m.dragging.disable();
      
      e.preventDefault();
      e.stopPropagation();
    }}
    
    function handleMove(e) {{
      if (!isDragging) return;
      
      const coords = getEventCoords(e);
      const deltaX = coords.x - startX;
      const deltaY = coords.y - startY;
      
      if (Math.abs(deltaX) > 5 || Math.abs(deltaY) > 5) hasMoved = true;
      
      if (hasMoved) {{
        const newLeft = initialLeft + deltaX;
        const newTop = initialTop + deltaY;
        
        element.style.position = 'absolute';
        element.style.left = newLeft + 'px';
        element.style.top = newTop + 'px';
        element.style.bottom = 'auto';
        element.style.right = 'auto';
        
        e.preventDefault();
        e.stopPropagation();
      }}
    }}
    
    function handleEnd(e) {{
      if (isDragging) {{
        isDragging = false;
        element.style.cursor = 'move';
        
        const m = findMap();
        if (m) m.dragging.enable();
        
        if (!hasMoved && options.onClick) {{
          options.onClick(e);
        }}
        
        if (hasMoved) {{
          e.preventDefault();
          e.stopPropagation();
        }}
      }}
    }}
    
    element.addEventListener('mousedown', handleStart);
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleEnd);
    
    element.addEventListener('touchstart', handleStart, {{ passive: false }});
    document.addEventListener('touchmove', handleMove, {{ passive: false }});
    document.addEventListener('touchend', handleEnd);
    document.addEventListener('touchcancel', handleEnd);
  }}

  // Initialize Compass Dragging
  makeDraggable(document.getElementById('compass'), {{
      onClick: function() {{
          currentRotation = 0;
          resetImageBounds();
      }}
  }});

  // --- Helper: find the Leaflet Map instance on the page ---
  function findMap() {{
    if (map && map instanceof L.Map) return map;
    for (const k in window) {{
      try {{
        const v = window[k];
        if (v && v instanceof L.Map) {{ map = v; break; }}
      }} catch(e) {{ /* ignore cross-origin / exotic props */ }}
    }}
    return map;
  }}

  // --- Helper: find the first ImageOverlay (or choose filter here) ---
  function findOverlay() {{
    if (overlay && overlay instanceof L.ImageOverlay) return overlay;
    const m = findMap();
    if (!m) return null;
    let found = null;
    m.eachLayer(layer => {{
      if (!found && layer instanceof L.ImageOverlay) found = layer;
    }});
    if (found) overlay = found;
    return overlay;
  }}

  // --- Apply rotation to a given img element by composing with Leaflet's transform ---
  function applyRotationTo(img) {{
    if (!img) return;
    try {{
      if (img.__setting) return;
      img.__setting = true;

      img.style.transformOrigin = "center center";

      let inline = (img.style && img.style.transform) ? img.style.transform : '';
      inline = inline.replace(/rotate\\([^)]*\\)/g, '').trim();

      if (!inline) {{
        const cs = window.getComputedStyle(img);
        if (cs) inline = (cs.transform && cs.transform !== 'none') ? cs.transform : '';
      }}

      const rotationStr = ` rotate(${{currentRotation}}deg)`;
      img.style.transform = (inline ? inline + rotationStr : rotationStr);

      img.dataset.__desiredRotation = String(currentRotation);

      requestAnimationFrame(() => {{ img.__setting = false; }});
    }} catch (e) {{
      console.warn("applyRotationTo error:", e);
      if (img) img.__setting = false;
    }}
  }}

  // --- Attach observers to handle style changes and element replacement ---
  function attachImageObservers(img) {{
    if (!img) return;

    if (img.__obsAttached) {{
      applyRotationTo(img);
      return;
    }}
    img.__obsAttached = true;

    const attrObs = new MutationObserver(mutations => {{
      for (const m of mutations) {{
        if (m.type === 'attributes' && m.attributeName === 'style') {{
          if (img.__setting) continue;
          applyRotationTo(img);
        }}
        if (m.type === 'attributes' && m.attributeName === 'src') {{
          applyRotationTo(img);
        }}
      }}
    }});
    attrObs.observe(img, {{ attributes: true, attributeFilter: ['style', 'src'] }});
    img.__attrObserver = attrObs;

    const parent = img.parentNode;
    if (parent && !parent.__childObserver) {{
      const childObs = new MutationObserver(changes => {{
        for (const c of changes) {{
          if (c.type === 'childList') {{
            for (const node of c.addedNodes) {{
              if (node && node.tagName && node.tagName.toLowerCase() === 'img') {{
                attachImageObservers(node);
                applyRotationTo(node);
              }}
            }}
          }}
        }}
      }});
      childObs.observe(parent, {{ childList: true }});
      parent.__childObserver = childObs;
    }}

    applyRotationTo(img);
  }}

  // --- Snapshot Button State ---
  function enableSnapshotBtn() {{
      const btn = document.getElementById('btn-snapshot');
      if (btn) {{
          btn.disabled = false;
          btn.innerHTML = '📸 Snapshot';
          btn.style.cursor = 'pointer';
          btn.style.opacity = '1.0';
      }}
  }}

  // --- Reapply to current overlay image (safe wrapper) ---
  function reapplyToOverlayImage() {{
    const ov = findOverlay();
    if (!ov) return;
    const img = (typeof ov.getElement === 'function') ? ov.getElement() : ov._image || null;
    if (img) attachImageObservers(img);
  }}

  // --- Controls (move / scale / rotate / reset) ---
  window.moveImage = function(direction) {{
    const ov = findOverlay(); if (!ov) return;
    const moveScale = parseFloat(document.getElementById('moveScale').value) || 0.1;
    const b = ov.getBounds();
    const sw = b.getSouthWest(), ne = b.getNorthEast();
    const latSpan = ne.lat - sw.lat, lngSpan = ne.lng - sw.lng;
    let dLat = 0, dLng = 0;
    if (direction === 'up') dLat =  latSpan * moveScale;
    if (direction === 'down') dLat = -latSpan * moveScale;
    if (direction === 'left') dLng = -lngSpan * moveScale;
    if (direction === 'right') dLng =  lngSpan * moveScale;
    const newB = L.latLngBounds([sw.lat + dLat, sw.lng + dLng],[ne.lat + dLat, ne.lng + dLng]);
    ov.setBounds(newB);
    requestAnimationFrame(reapplyToOverlayImage);
  }};

  window.scaleImage = function(action) {{
    const ov = findOverlay(); if (!ov) return;
    const scaleAmount = parseFloat(document.getElementById('scaleAmount').value) || 1.1;
    const b = ov.getBounds();
    const sw = b.getSouthWest(), ne = b.getNorthEast();
    const cLat = (sw.lat + ne.lat) / 2, cLng = (sw.lng + ne.lng) / 2;
    const factor = (action === 'expand') ? scaleAmount : (1 / scaleAmount);
    const halfLat = (ne.lat - sw.lat) * factor / 2;
    const halfLng = (ne.lng - sw.lng) * factor / 2;
    const newB = L.latLngBounds([cLat - halfLat, cLng - halfLng],[cLat + halfLat, cLng + halfLng]);
    ov.setBounds(newB);
    requestAnimationFrame(reapplyToOverlayImage);
  }};

  window.rotateImage = function(direction) {{
    const step = parseFloat(document.getElementById('rotationDegrees').value) || 15;
    currentRotation = (currentRotation + (direction === 'left' ? -step : step)) % 360;
    updateCompass();
    reapplyToOverlayImage();
  }};

  window.resetImageBounds = function() {{
    const ov = findOverlay(); if (!ov || !originalBounds) return;
    ov.setBounds(originalBounds);
    currentRotation = 0;
    updateCompass();
    
    // Recenter map and fit to overlay bounds
    const m = findMap();
    if (m) {{
        m.fitBounds(overlayBounds);
    }}
    
    requestAnimationFrame(reapplyToOverlayImage);
  }};
  
  // --- Snapshot Logic ---
  // --- Snapshot Logic ---
  // --- Snapshot Logic ---
  // --- Snapshot Logic ---
  window.takeSnapshot = function() {{
      const m = findMap();
      if (!m) return;
      
      const btn = document.getElementById('btn-snapshot');
      const leafletControls = document.querySelector('.leaflet-control-container');
      const customControls = Array.from(document.querySelectorAll('div[style*="z-index:9999"]'));
      const footerStrip = document.getElementById('snapshot-footer');
      const hiddenControls = document.getElementById('footer-controls'); // Hide this input box
      
      // Helper: Restore UI
      const restoreUI = () => {{
          if (leafletControls) leafletControls.style.display = 'block';
          
          customControls.forEach(ctrl => {{
              if (ctrl.id !== 'footer-controls') ctrl.style.display = 'block'; 
              else ctrl.style.display = 'block';
          }});
          
          if (btn) {{
            btn.disabled = false;
            btn.innerText = '📸 Snapshot';
            btn.style.opacity = '1';
          }}
          
          // Clean up composition container
          const comp = document.getElementById('composition-container');
          if (comp) comp.remove();
      }};

      // Safety Timeout
      const safetyTimeout = setTimeout(() => {{
          console.warn('Snapshot process timed out (Safety Trigger)');
          alert('Snapshot timed out. Please try again.');
          restoreUI();
      }}, 20000);
      
      if (btn) {{
        btn.disabled = true;
        btn.innerText = 'Capturing...';
        btn.style.opacity = '0.7';
      }}

      // Hide standard Leaflet controls
      if (leafletControls) leafletControls.style.display = 'none';

      // Hide custom controls (excluding compass and legend)
      customControls.forEach(ctrl => {{
          if (ctrl.id !== 'compass' && ctrl.id !== 'map-legend') {{
              ctrl.style.display = 'none';
          }}
      }});
      if (hiddenControls) hiddenControls.style.display = 'none';
      
      const mapContainer = m.getContainer();

      // Detect mobile device
      const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
      
      // Options for html-to-image
      const options = {{
           width: mapContainer.offsetWidth,
           height: mapContainer.offsetHeight,
           useCORS: true,
           backgroundColor: '#ffffff',
           cacheBust: false,
           pixelRatio: isMobile ? 3 : 4,
           filter: (node) => {{
               if (node.tagName === 'IMG') return true; 
               return true;
           }}
       }};

      // Force Map Layout Refresh
      if (m && typeof m.invalidateSize === 'function') {{
          m.invalidateSize();
      }}

      console.log('Starting Composite Snapshot...');

      // PHASE 1: Capture Map Only
      setTimeout(() => {{
          htmlToImage.toPng(mapContainer, options)
             .then((mapDataUrl) => {{
                 console.log('Map Captured. Composing with Footer...');
                 
                 // PHASE 2: Composition
                 // Create a container that exactly matches the map width
                 const container = document.createElement('div');
                 container.id = 'composition-container';
                 container.style.position = 'absolute';
                 container.style.top = '0';
                 container.style.left = '0';
                 container.style.zIndex = '99999';
                 container.style.background = 'white';
                 container.style.width = mapContainer.offsetWidth + 'px';
                 
                 // 1. Map Image
                 const mapImg = document.createElement('img');
                 mapImg.src = mapDataUrl;
                 mapImg.style.width = '100%';
                 mapImg.style.display = 'block';
                 container.appendChild(mapImg);
                 
                 // 2. Footer clone
                 const footerClone = footerStrip.cloneNode(true);
                 footerClone.style.display = 'block'; // Make visible
                 footerClone.id = 'footer-clone';
                 container.appendChild(footerClone);
                 
                 document.body.appendChild(container);
                 
                 // Wait a moment for the DOM to settle with the new image
                 setTimeout(() => {{
                     // Capture the Composite
                     htmlToImage.toPng(container, {{
                         width: container.offsetWidth,
                         // Height is auto
                         useCORS: true,
                         pixelRatio: options.pixelRatio
                     }})
                     .then((finalDataUrl) => {{
                          const link = document.createElement('a');
                          link.download = 'map_snapshot_with_footer.png';
                          link.href = finalDataUrl;
                          link.click();
                          
                          clearTimeout(safetyTimeout);
                          restoreUI();
                     }})
                     .catch((err) => {{
                         console.error('Composite Snapshot failed:', err);
                         alert('Composite Snapshot failed.');
                         clearTimeout(safetyTimeout);
                         restoreUI();
                     }});
                 }}, 500);
                 
             }})
             .catch((err) => {{
                 console.error('Map Snapshot failed:', err);
                 alert('Snapshot failed.');
                 clearTimeout(safetyTimeout);
                 restoreUI();
             }});
          
      }}, 500); 
  }};

  // --- Interactive Dots Logic ---
  function initDots() {{
      const m = findMap();
      if (!m) return;
      
      // 1. Add KMZ Points (Blue - Fixed/Non-draggable)
      bluePoints.forEach((pt, idx) => {{
          L.circleMarker([pt.lat, pt.lon], {{
              radius: 6,
              color: 'white',
              weight: 2,
              fillColor: '#4A90E2',
              fillOpacity: 1.0,
              fill: true
          }}).addTo(m).bindPopup(`<b>KMZ Point (Fixed)</b><br>Index: ${{idx}}`);
      }});
      
      // 2. Add Excel Points (Orange - Draggable/Moveable) with Borewell IDs
      orangePoints.forEach(pt => {{
          const marker = L.circleMarker([pt.lat, pt.lon], {{
              radius: 6,
              color: 'white',
              weight: 2,
              fillColor: '#FF6B35',
              fillOpacity: 1.0,
              fill: true,
              draggable: true
          }}).addTo(m);
          
          // Extract short ID (e.g., "WB-01" from "WB-01 TOC1")
          const shortId = pt.name ? pt.name.split(' ')[0] : `Point ${{pt.id}}`;
          const fullName = pt.name || 'Excel Point';
          
          // Popup with full details
          marker.bindPopup(`<b>${{fullName}}</b><br>ID: ${{pt.id}}<br>Lat: ${{pt.lat.toFixed(6)}}<br>Lon: ${{pt.lon.toFixed(6)}}`);
          
          // Permanent label with short ID
          marker.bindTooltip(shortId, {{
              permanent: true,
              direction: 'right',
              className: 'borewell-label',
              offset: [10, 0]
          }});
          
          // Update popup on drag
          marker.on('drag', function(e) {{
              const latlng = e.target.getLatLng();
              marker.setPopupContent(`<b>${{fullName}} (Dragging...)</b><br>ID: ${{pt.id}}<br>Lat: ${{latlng.lat.toFixed(6)}}<br>Lon: ${{latlng.lng.toFixed(6)}}`);
          }});
          
          marker.on('dragend', function(e) {{
              const latlng = e.target.getLatLng();
              marker.setPopupContent(`<b>${{fullName}}</b><br>ID: ${{pt.id}}<br>Lat: ${{latlng.lat.toFixed(6)}}<br>Lon: ${{latlng.lng.toFixed(6)}}`);
              console.log(`Borewell ${{shortId}} moved to: [${{latlng.lat}}, ${{latlng.lng}}]`);
          }});
      }});
  }}

  // --- Initialization: find overlay + hooks to reapply on map/overlay events ---
  function init() {{
    const m = findMap();
    if (!m) {{
        setTimeout(init, 200); // Retry if map not ready
        return;
    }}

    // Initialize Dots
    initDots();

    // Move Controls into Map Container for Snapshot
    const compass = document.getElementById('compass');
    const legend = document.getElementById('map-legend');
    if (m) {{
        const container = m.getContainer();
        if (compass && container) container.appendChild(compass);
        if (legend && container) {{
            container.appendChild(legend);
            makeDraggable(legend);
        }}
        
        // Add dynamic scale control (like Google Maps)
        const scaleCtrl = L.control.scale({{
            position: 'bottomleft', // Initial, we move it later
            metric: true,
            imperial: false,
            maxWidth: 250
        }}).addTo(m);
        
        // Make scale control draggable
        const scaleContainer = scaleCtrl.getContainer();
        scaleContainer.id = 'draggable-scale';
        scaleContainer.style.cursor = 'move';
        scaleContainer.title = "Drag to move";
        scaleContainer.style.pointerEvents = 'auto'; // Ensure clickable
        scaleContainer.style.zIndex = '9999'; // Ensure on top of everything
        
        // CRITICAL: Move it out of Leaflet's corner container to map root
        // This allows free movement without being clipped or constrained
        const mapRoot = m.getContainer();
        mapRoot.appendChild(scaleContainer);
        
        // Reset/Set positioning
        scaleContainer.style.position = 'absolute';
        scaleContainer.style.bottom = '25px';
        scaleContainer.style.left = '10px';
        scaleContainer.style.marginBottom = '0';
        scaleContainer.style.marginLeft = '0';
        
        makeDraggable(scaleContainer);
    }}

    // Initialize Overlay Observers
    const ov = findOverlay();
    if (ov) {{
        originalBounds = ov.getBounds();
        reapplyToOverlayImage();
        
        // Update Status
        const statusEl = document.getElementById('js-status');
        if (statusEl) {{
            statusEl.style.background = 'green';
            statusEl.innerHTML = 'JS: Active & Map Found';
            setTimeout(() => {{ statusEl.style.display = 'none'; }}, 3000);
        }}
        
        // Overlay Events
        ov.on('load', () => {{
            setTimeout(reapplyToOverlayImage, 0);
            enableSnapshotBtn();
        }});
        ov.on('update', () => setTimeout(reapplyToOverlayImage, 0));

        // Check if already loaded
        const img = (typeof ov.getElement === 'function') ? ov.getElement() : ov._image;
        if (img && img.complete) {{
            enableSnapshotBtn();
        }}
    }}

    // Map Events
    m.on('zoomend', () => setTimeout(reapplyToOverlayImage, 0));
    m.on('moveend', () => setTimeout(reapplyToOverlayImage, 0));
  }}

  // start
  init();
}})();
</script>
"""

    # Inject the script - try </body> first, then </html>, then just append
    print(f"DEBUG: Reading file {html_file}, size: {len(html)}")
    print(f"DEBUG: js_code size: {len(js_code)}")
    
    if "</body>" in html:
        print("DEBUG: Found </body>, replacing...")
        html = html.replace("</body>", js_code + "\n</body>")
    elif "</html>" in html:
        print("DEBUG: Found </html>, replacing...")
        html = html.replace("</html>", js_code + "\n</html>")
    else:
        print("DEBUG: No closing tags found, appending...")
        # Just append to end if no closing tags found
        html = html + js_code
    
    print(f"DEBUG: New content size: {len(html)}")
    
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Controls injected into: {html_file}")

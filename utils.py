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
print("DEBUG: Loading utils.py - Version ScaleFix_v3")
import geemap.foliumap as geemap
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
            
            # Create credentials
            credentials = Credentials.from_service_account_info(service_account_info)
            
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


def auto_detect_utm_zone(df, reference_points=None):
    """
    Auto-detect the correct UTM zone for Australian coordinates.
    Uses mathematical calculation instead of trial-and-error.
    
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
    # If we have KMZ points, we KNOW where the project is.
    if reference_points:
        try:
            # Calculate centroid of reference points
            if isinstance(reference_points[0], (dict)):
                 ref_lons = [p['lon'] for p in reference_points]
                 ref_lats = [p['lat'] for p in reference_points]
            else:
                 # Assume objects with x/y or lon/lat attributes (like shapely points or custom objs)
                 # Handle shapely points (x=lon, y=lat)
                 if hasattr(reference_points[0], 'x'):
                     ref_lons = [p.x for p in reference_points]
                     ref_lats = [p.y for p in reference_points]
                 else:
                     # Fallback
                     ref_lons = []
                     ref_lats = []
            
            if ref_lons:
                avg_ref_lon = sum(ref_lons) / len(ref_lons)
                avg_ref_lat = sum(ref_lats) / len(ref_lats)
                
                expected_zone = calculate_utm_zone_from_lonlat(avg_ref_lon, avg_ref_lat)
                print(f"📌 KMZ Reference Hint: Lon {avg_ref_lon:.4f}°, Lat {avg_ref_lat:.4f}° -> Zone {expected_zone}S")
                
                # Test THIS zone first!
                zones_to_test.append(expected_zone)
        except Exception as e:
            print(f"Warning: Could not use reference points for zone hint: {e}")

    # Strategy 1: Estimate zone from Easting value
    # Appending other logical candidates
    if 200000 <= avg_easting <= 800000:
        # Standard common zones
        candidates = [54, 55, 56, 53, 52, 51, 50, 49]
    else:
        # All zones
        candidates = list(australian_zones.keys())
    
    # Add candidates to test list (preserving order, avoid duplicates)
    for c in candidates:
        if c not in zones_to_test:
            zones_to_test.append(c)
            
    # Strategy 2: Transform using each candidate zone and check validity
    best_match = None
    best_confidence = "low"
    
    for zone_num in zones_to_test:
        if zone_num not in australian_zones: continue 
        
        zone_data = australian_zones[zone_num]
        epsg_code = zone_data['epsg']
        
        try:
            # Transform to lat/lon
            transformer = Transformer.from_crs(epsg_code, "EPSG:4326", always_xy=True)
            test_lon, test_lat = transformer.transform(avg_easting, avg_northing)
            
            # Check if coordinates are in Australia
            if not (112 <= test_lon <= 160 and -45 <= test_lat <= -10):
                continue
            
            # Calculate what zone this longitude should be in
            calculated_zone = calculate_utm_zone_from_lonlat(test_lon, test_lat)
            
            # Check if the calculated zone matches the zone we're testing
            if calculated_zone == zone_num:
                # Perfect match!
                best_match = {
                    'epsg': epsg_code,
                    'zone': zone_num,
                    'lon': test_lon,
                    'lat': test_lat,
                    'description': zone_data['description']
                }
                best_confidence = "high"
                print(f"✓ Auto-detected UTM Zone {zone_num}S ({epsg_code}) - {zone_data['description']}")
                print(f"  Coordinates: Lon {test_lon:.4f}°, Lat {test_lat:.4f}°")
                print(f"  Confidence: HIGH")
                
                # If this matches our reference hint, STOP IMMEDIATELY - We found it!
                if reference_points and zones_to_test[0] == zone_num:
                     print("  (Confirmed by KMZ Reference)")
                     break
                
                # Otherwise, continue checking just in case (unless we trust this 100%)
                # Actually, if we hit a valid HIGH confidence match, we should probably take it
                # But wait - in the ambiguity case, Zone 54 IS a valid high confidence match mathematically!
                # So we rely on the ORDER of 'zones_to_test' to prioritize the KMZ hint.
                break
            
            # Check if we're near a zone boundary (within 1 zone)
            elif abs(calculated_zone - zone_num) == 1:
                # Near boundary - this could still be valid
                if best_match is None or best_confidence == "low":
                    best_match = {
                        'epsg': epsg_code,
                        'zone': zone_num,
                        'lon': test_lon,
                        'lat': test_lat,
                        'description': zone_data['description']
                    }
                    best_confidence = "medium"
            
            # If no perfect match yet, keep the first valid Australian coordinate
            elif best_match is None:
                best_match = {
                    'epsg': epsg_code,
                    'zone': zone_num,
                    'lon': test_lon,
                    'lat': test_lat,
                    'description': zone_data['description']
                }
                best_confidence = "low"
                
        except Exception as e:
            # Transformation failed for this zone
            print(f"Error testing zone {zone_num}: {e}")
            continue
    
    # Strategy 3: Fallback if no match found
    if best_match is None:
        print("⚠ Warning: Could not auto-detect UTM zone reliably")
        print(f"  Using default Zone 54S (EPSG:32754) - most common for Victoria/NSW")
        best_match = {
            'epsg': 'EPSG:32754',
            'zone': 54,
            'lon': None,
            'lat': None,
            'description': 'Default fallback'
        }
        best_confidence = "low"
    elif best_confidence == "medium":
        print(f"⚠ Auto-detected UTM Zone {best_match['zone']}S ({best_match['epsg']}) - {best_match['description']}")
        print(f"  Coordinates: Lon {best_match['lon']:.4f}°, Lat {best_match['lat']:.4f}°")
        print(f"  Confidence: MEDIUM (near zone boundary)")
    elif best_confidence == "low":
        print(f"⚠ Auto-detected UTM Zone {best_match['zone']}S ({best_match['epsg']}) - {best_match['description']}")
        print(f"  Coordinates: Lon {best_match['lon']:.4f}°, Lat {best_match['lat']:.4f}°")
        print(f"  Confidence: LOW (unusual coordinates)")
    
    return best_match['epsg'], best_confidence, best_match


def process_excel_data(file, interpolation_method='linear', reference_points=None):
    """
    Reads Excel file, interpolates groundwater data, and generates a contour image.
    
    Args:
        file: Excel file path or object
        interpolation_method: 'linear' or 'cubic'
        reference_points: Optional list of points (e.g. from KMZ) to help with zone detection
        
    Returns:
        - image_base64: Base64 encoded PNG image of the contour.
        - bounds: [[min_lat, min_lon], [max_lat, max_lon]] for the image overlay.
        - target_points: List of dictionaries for target points (lat, lon, id).
        - bbox_geojson: GeoJSON of the bounding box.
    """
    df = pd.read_excel(file)
    df.columns = df.columns.str.strip()

    # Filter data (same logic as original)
    if 'Name' in df.columns and df['Name'].astype(str).str.contains('TOC1', na=False).any():
        df = df[df['Name'].str.contains('TOC1', na=False)].copy()

    if 'Groundwater Elevation mAHD' in df.columns:
        df = df[df['Groundwater Elevation mAHD'].notna()]
        df = df[df['Groundwater Elevation mAHD'] != '-']

    df['Easting'] = pd.to_numeric(df['Easting'], errors='coerce')
    df['Northing'] = pd.to_numeric(df['Northing'], errors='coerce')
    df['Groundwater Elevation mAHD'] = pd.to_numeric(df['Groundwater Elevation mAHD'], errors='coerce')
    df = df.dropna(subset=['Easting', 'Northing', 'Groundwater Elevation mAHD'])

    if df.empty:
        raise ValueError("No valid data found in Excel file.")

    # Interpolation grid
    # Increase density for smoother contours
    grid_x, grid_y = np.mgrid[
        df['Easting'].min():df['Easting'].max():200j,
        df['Northing'].min():df['Northing'].max():200j
    ]

    # Auto-detect UTM zone using enhanced algorithm
    # Supports all Australian zones (49S-56S) with mathematical calculation
    # Uses reference_points (if provided) to resolve zone ambiguity
    selected_epsg, confidence, zone_info = auto_detect_utm_zone(df, reference_points)
    
    # Reproject grid corners to get lat/lon bounds for the IMAGE
    transformer = Transformer.from_crs(selected_epsg, "EPSG:4326", always_xy=True)
    min_easting, max_easting = grid_x.min(), grid_x.max()
    min_northing, max_northing = grid_y.min(), grid_y.max()
    
    # Transform corners
    min_lon, min_lat = transformer.transform(min_easting, min_northing)
    max_lon, max_lat = transformer.transform(max_easting, max_northing)
    
    # Folium expects [[lat_min, lon_min], [lat_max, lon_max]]
    # BUT check order: usually [[south, west], [north, east]]
    image_bounds = [[min_lat, min_lon], [max_lat, max_lon]]

    # Interpolation
    grid_z = griddata(
        points=(df['Easting'], df['Northing']),
        values=df['Groundwater Elevation mAHD'],
        xi=(grid_x, grid_y),
        method=interpolation_method
    )

    # Fill NaNs - COMMENTED OUT AS PER REQUEST (Breaking/Incorrect results)
    # mask_nan = np.isnan(grid_z)
    # if np.any(mask_nan):
    #     grid_z_nearest = griddata(
    #         points=(df['Easting'], df['Northing']),
    #         values=df['Groundwater Elevation mAHD'],
    #         xi=(grid_x, grid_y),
    #         method='nearest'
    #     )
    #     grid_z[mask_nan] = grid_z_nearest[mask_nan]

    # Generate Contour Image
    dz_dx, dz_dy = np.gradient(grid_z)
    magnitude = np.sqrt(dz_dx**2 + dz_dy**2)
    u = -dz_dx / (magnitude + 1e-10)
    v = -dz_dy / (magnitude + 1e-10)

    z_min, z_max = df['Groundwater Elevation mAHD'].min(), df['Groundwater Elevation mAHD'].max()
    z_range = z_max - z_min
    interval = 1.0 if z_range > 10 else 0.5 if z_range > 5 else 0.2 if z_range > 2 else 0.1 if z_range > 1 else 0.05 if z_range > 0.5 else 0.01

    contour_levels = np.arange(
        np.floor(z_min / interval) * interval,
        np.ceil(z_max / interval) * interval + interval,
        interval
    )

    fig, ax = plt.subplots(figsize=(12, 8), facecolor='none', dpi=300)
    ax.patch.set_alpha(0)
    
    # Draw filled contours (colors) first
    ax.contourf(grid_x, grid_y, grid_z, levels=contour_levels, cmap='viridis', alpha=0.6)
    
    # Draw contour lines on top (black lines with labels)
    contours = ax.contour(grid_x, grid_y, grid_z, levels=contour_levels, colors='black', linewidths=1.5, alpha=0.8)
    ax.clabel(contours, inline=True, fontsize=8, fmt='%1.1f')  # Add labels to contour lines
    
    ax.scatter(df['Easting'], df['Northing'], color='black', edgecolor='black', linewidth=0.8, s=40)
    
    step = 18  # Show ~30% of arrows
    ax.quiver(grid_x[::step, ::step], grid_y[::step, ::step], u[::step, ::step], v[::step, ::step], color='red', scale=25, width=0.005, headwidth=4)

    # Bounding box (visual only for the image)
    bbox_x = df['Easting'].min()
    bbox_y = df['Northing'].min()
    bbox_width = df['Easting'].max() - bbox_x
    bbox_height = df['Northing'].max() - bbox_y
    bbox_rect = Rectangle((bbox_x, bbox_y), bbox_width, bbox_height, linewidth=2, edgecolor='blue', facecolor='none', linestyle='--')
    ax.add_patch(bbox_rect)

    ax.axis('off')
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=300, bbox_inches='tight', pad_inches=0, transparent=True)
    plt.close()
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')

    # Target Points (Lat/Lon) with Borewell Names
    target_lons, target_lats = transformer.transform(df['Easting'].values, df['Northing'].values)
    target_points = [
        {
            "lat": lat, 
            "lon": lon, 
            "id": i,
            "name": df.iloc[i]['Name'] if 'Name' in df.columns else f"Point {i}"
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
    print(f"DEBUG: BBox Coordinates: {bbox_geojson['geometry']['coordinates']}")

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

def create_map(image_base64, image_bounds, target_points, kmz_points=None, bbox_geojson=None):
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
    m = geemap.Map(center=[center_lat, center_lon], zoom=16, basemap='SATELLITE', max_zoom=19, zoom_control=False, attributionControl=False)
    
    # Add layer control moved to end


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


def inject_controls_to_html(html_file, image_bounds, target_points, kmz_points=None):
    """
    Injects JavaScript controls into an already-saved HTML file.
    This must be called AFTER the map is saved to guarantee the JS is included.
    """
    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Calculate initial center from target points
    if target_points:
        center_lat = sum(p['lat'] for p in target_points) / len(target_points)
        center_lon = sum(p['lon'] for p in target_points) / len(target_points)
        initial_center = [center_lat, center_lon]
    else:
        initial_center = [0, 0]

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
.borewell-label {{
    background: rgba(255, 255, 255, 0.95) !important;
    border: 2px solid #FF6B35 !important;
    border-radius: 4px !important;
    padding: 2px 6px !important;
    font-weight: bold !important;
    font-size: 12px !important;
    color: #333 !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
}}
</style>

<!-- html-to-image for snapshot -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/html-to-image/1.11.11/html-to-image.js"></script>

<!-- Compass UI - Realistic and Draggable -->
<div id="compass" style="position:absolute; top:80px; left:10px; z-index:9999; width:80px; height:80px; cursor:move; touch-action: none; -webkit-user-select: none; user-select: none;" title="Drag to reposition | Click to reset rotation">
    <div id="compassInner" style="position:relative; width:100%; height:100%; background:radial-gradient(circle, rgba(255,255,255,0.95) 0%, rgba(240,240,240,0.95) 100%); border-radius:50%; border:4px solid #2c3e50; box-shadow:0 4px 12px rgba(0,0,0,0.4), inset 0 2px 4px rgba(255,255,255,0.5); transition: transform 0.3s ease;">
        <!-- Outer ring with degree marks -->
        <div style="position:absolute; top:50%; left:50%; width:90%; height:90%; transform:translate(-50%, -50%);">
            <!-- Cardinal direction markers -->
            <div style="position:absolute; top:2px; left:50%; transform:translateX(-50%); color:#c0392b; font-weight:bold; font-size:18px; text-shadow:1px 1px 2px rgba(0,0,0,0.3);">N</div>
            <div style="position:absolute; bottom:2px; left:50%; transform:translateX(-50%); color:#34495e; font-weight:bold; font-size:14px; text-shadow:1px 1px 2px rgba(0,0,0,0.2);">S</div>
            <div style="position:absolute; top:50%; right:2px; transform:translateY(-50%); color:#34495e; font-weight:bold; font-size:14px; text-shadow:1px 1px 2px rgba(0,0,0,0.2);">E</div>
            <div style="position:absolute; top:50%; left:2px; transform:translateY(-50%); color:#34495e; font-weight:bold; font-size:14px; text-shadow:1px 1px 2px rgba(0,0,0,0.2);">W</div>
        </div>
        
        <!-- Center circle -->
        <div style="position:absolute; top:50%; left:50%; width:12px; height:12px; transform:translate(-50%, -50%); background:#2c3e50; border-radius:50%; border:2px solid #ecf0f1; box-shadow:0 1px 3px rgba(0,0,0,0.3);"></div>
        
        <!-- North arrow (red) -->
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);">
            <div style="position:absolute; bottom:6px; left:50%; transform:translateX(-50%); width:0; height:0; border-left:8px solid transparent; border-right:8px solid transparent; border-bottom:35px solid #c0392b; filter:drop-shadow(0 2px 3px rgba(0,0,0,0.3));"></div>
        </div>
        
        <!-- South arrow (white) -->
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);">
            <div style="position:absolute; top:6px; left:50%; transform:translateX(-50%); width:0; height:0; border-left:8px solid transparent; border-right:8px solid transparent; border-top:35px solid #ecf0f1; filter:drop-shadow(0 2px 3px rgba(0,0,0,0.2));"></div>
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
<div id="map-legend" style="position:absolute; bottom:10px; right:10px; z-index:9999; background:rgba(255,255,255,0.95); padding:10px; border-radius:6px; font-family:Arial,Helvetica,sans-serif; font-size:12px; box-shadow:0 0 5px rgba(0,0,0,0.2);">
  <div style="font-weight:bold; margin-bottom:8px; border-bottom:1px solid #ddd; padding-bottom:4px;">Legend</div>
  
  <!-- Points -->
  <div style="display:flex; align-items:center; margin-bottom:10px;">
    <div style="width:12px; height:12px; background:#FF6B35; border-radius:50%; border:2px solid white; margin-right:8px; box-shadow:0 0 2px rgba(0,0,0,0.5);"></div>
    <span>Borewell Points</span>
  </div>

  <!-- Contour Guide -->
  <div style="font-weight:bold; margin-bottom:6px; margin-top:8px; border-top:1px solid #ddd; padding-top:6px;">How to Read Contour</div>
  <div style="display:flex; align-items:center; margin-bottom:4px;">
    <div style="width:20px; height:10px; background:linear-gradient(to right, #fde725, #5ec962); margin-right:8px; border:1px solid #999;"></div>
    <span>High Elevation (Yellow)</span>
  </div>
  <div style="display:flex; align-items:center; margin-bottom:4px;">
    <div style="width:20px; height:10px; background:linear-gradient(to right, #3b528b, #440154); margin-right:8px; border:1px solid #999;"></div>
    <span>Low Elevation (Purple)</span>
  </div>
  <div style="display:flex; align-items:center;">
    <div style="font-size:16px; color:red; font-weight:bold; margin-right:8px; line-height:10px;">&rarr;</div>
    <span>Flow Direction</span>
  </div>
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
  window.takeSnapshot = function() {{
      const m = findMap();
      if (!m) return;
      
      const btn = document.getElementById('btn-snapshot');
      if (btn) {{
          btn.disabled = true;
          btn.innerHTML = '📸 Processing...';
          btn.style.opacity = '0.7';
      }}

      // Hide standard Leaflet controls (Zoom, Layers, etc.)
      const leafletControls = document.querySelector('.leaflet-control-container');
      if (leafletControls) leafletControls.style.display = 'none';

      // Hide custom controls (excluding compass and legend)
      const controls = document.querySelectorAll('div[style*="z-index:9999"]');
      controls.forEach(ctrl => {{
          if (ctrl.id !== 'compass' && ctrl.id !== 'map-legend') {{
              ctrl.style.display = 'none';
          }}
      }});
      
      const mapContainer = m.getContainer();
      
      // Helper: Wait for overlay image to be fully loaded
      const waitForOverlayImage = () => {{
          return new Promise((resolve) => {{
              const ov = findOverlay();
              if (!ov) {{
                  console.warn('No overlay found, proceeding anyway');
                  resolve();
                  return;
              }}
              
              const img = (typeof ov.getElement === 'function') ? ov.getElement() : ov._image;
              if (!img) {{
                  console.warn('No overlay image found, proceeding anyway');
                  resolve();
                  return;
              }}
              
              if (img.complete && img.naturalHeight !== 0) {{
                  console.log('Overlay image already loaded');
                  resolve();
              }} else {{
                  console.log('Waiting for overlay image to load...');
                  img.onload = () => {{
                      console.log('Overlay image loaded');
                      resolve();
                  }};
                  img.onerror = () => {{
                      console.warn('Overlay image failed to load, proceeding anyway');
                      resolve();
                  }};
                  // Timeout after 3 seconds
                  setTimeout(() => {{
                      console.warn('Overlay image load timeout, proceeding anyway');
                      resolve();
                  }}, 3000);
              }}
          }});
      }};
      
      // Options for html-to-image
      const options = {{
          width: mapContainer.offsetWidth,
          height: mapContainer.offsetHeight,
          useCORS: true,
          backgroundColor: '#ffffff',
          cacheBust: true,
          pixelRatio: 4, // Increased to 4x for Ultra High Resolution 
          filter: (node) => true
      }};

      // Helper: Restore UI
      const restoreUI = () => {{
          if (leafletControls) leafletControls.style.display = 'block';
          controls.forEach(ctrl => {{
              ctrl.style.display = 'block';
          }});
          if (btn) {{
            btn.disabled = false;
            btn.innerHTML = '📸 Snapshot';
            btn.style.opacity = '1.0';
          }}
      }};

      // STRATEGY: Wait for overlay + Double Snapshot
      // 0. Wait for overlay image to load
      // 1. First "Warm-up" Snapshot (Often blank/incomplete on mobile)
      // 2. Wait
      // 3. Second "Real" Snapshot
      
      // Detect mobile device
      const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
      const initialDelay = isMobile ? 3000 : 1000;  // 3s for mobile, 1s for desktop
      const betweenDelay = isMobile ? 4000 : 2000;  // 4s for mobile, 2s for desktop
      
      console.log('Device type:', isMobile ? 'Mobile' : 'Desktop');
      console.log('Using delays:', initialDelay, 'ms initial,', betweenDelay, 'ms between');
      
      // First, ensure overlay image is loaded
      waitForOverlayImage().then(() => {{
          console.log('Overlay ready, starting snapshot process...');
          
          // Force map to invalidate size and redraw (helps with rendering)
          if (m && typeof m.invalidateSize === 'function') {{
              m.invalidateSize();
              console.log('Map invalidated for fresh render');
          }}
          
          setTimeout(() => {{
              // 1. Warm-up (Discard result)
              console.log("Starting Warm-up Snapshot...");
              htmlToImage.toPng(mapContainer, options)
              .then(() => {{
                  console.log("Warm-up complete. Waiting...");
                  
                  // 2. Wait for cache/rasterization (longer delay for mobile)
                  setTimeout(() => {{
                      
                      // 3. Real Snapshot
                      console.log("Taking Real Snapshot...");
                      htmlToImage.toPng(mapContainer, options)
                      .then(function (dataUrl) {{
                          const link = document.createElement('a');
                          link.download = 'map_snapshot.png';
                          link.href = dataUrl;
                          link.click();
                          restoreUI();
                      }})
                      .catch(function (error) {{
                          console.error('Real Snapshot failed:', error);
                          alert('Snapshot failed. See console.');
                          restoreUI();
                      }});
                      
                  }}, betweenDelay);
              }})
              .catch(function (error) {{
                  // Even if warm-up fails, try the real one? 
                  // Usually if warm-up fails, it might be a partial render. 
                  // Let's log and try proceeding carefully or just alert.
                  console.warn('Warm-up Snapshot failed:', error);
                  
                  setTimeout(() => {{
                       htmlToImage.toPng(mapContainer, options)
                       .then(function (dataUrl) {{
                          const link = document.createElement('a');
                          link.download = 'map_snapshot.png';
                          link.href = dataUrl;
                          link.click();
                          restoreUI();
                       }})
                       .catch(err => {{
                           console.error('Fallback Snapshot failed:', err);
                           alert('Snapshot failed.');
                           restoreUI();
                       }});
                  }}, betweenDelay);
              }});
          }}, initialDelay);
      }});
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
        if (legend && container) container.appendChild(legend);
        
        // Add dynamic scale control (like Google Maps)
        const scaleCtrl = L.control.scale({{
            position: 'bottomleft', // Initial, we move it later
            metric: true,
            imperial: true,
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

import os
import json
import ee
import streamlit as st

import os
import json
import ee
import streamlit as st

# --- HACK: Fix for geemap import error on newer IPython versions ---
# geemap < 0.36 import 'display' from 'IPython.core.display' which is missing in modern IPython.
# We manually inject it if missing.
try:
    import IPython.core.display
    if not hasattr(IPython.core.display, 'display'):
        from IPython.display import display, HTML
        IPython.core.display.display = display
        IPython.core.display.HTML = HTML
except (ImportError, AttributeError):
    pass
# -----------------------------------------------------------------

import geemap.foliumap as geemap_folium 
import geemap.coreutils 
import folium
from folium.raster_layers import ImageOverlay

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
            
            # Get service account email
            service_account_email = service_account_info.get('client_email')
            
            # Use EE's native ServiceAccountCredentials instead of google.oauth2
            # This avoids the '_credentials' attribute error
            credentials = ee.ServiceAccountCredentials(
                service_account_email, 
                key_data=json.dumps(service_account_info)
            )
            
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

    # Use direct Folium map instead of geemap to avoid BoxKeyError with basemaps
    # This provides better compatibility across different library versions
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=16,
        max_zoom=19,
        zoom_control=False,
        attribution_control=False,
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite'
    )
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

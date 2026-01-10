import numpy as np
import pandas as pd
from pyproj import Transformer
from zipfile import ZipFile
# from pykml import parser  # KMZ functionality disabled
from shapely.geometry import Point

# Try to import global-land-mask for robust detection
try:
    from global_land_mask import globe
    HAS_LAND_MASK = True
except ImportError:
    HAS_LAND_MASK = False
    print("Warning: global-land-mask not installed. Land/Water check disabled.")

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

import geopandas as gpd
from shapely.geometry import Point
from pyproj import Transformer
import warnings
warnings.filterwarnings('ignore')

def test_land_check():
    print("Testing Geopandas Land Check...")
    
    try:
        # Load low resolution world
        print("Loading naturaleath_lowres...")
        world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))
        australia = world[world.name == 'Australia']
        
        if australia.empty:
             print("Error: Australia not found in dataset.")
             return

        australia_geom = australia.geometry.iloc[0]
        
        # Test Points
        # 1. Stanhope (Approx Zone 55 location) -> Should be ON LAND
        # Lat: -36.45, Lon: 144.95
        pt_expected_land = Point(144.95, -36.45)
        
        # 2. The "Bad" Zone 54 location 
        # Using the actual coordinates we used before which mapped to Zone 54S
        # Easting 319828, Northing 5959890
        # If in Zone 54 (EPSG:32754)
        transformer = Transformer.from_crs("EPSG:32754", "EPSG:4326", always_xy=True)
        lon_bad, lat_bad = transformer.transform(319828, 5959890)
        pt_expected_water = Point(lon_bad, lat_bad)
        
        print(f"Checking Point 1 (Land Candidate): {pt_expected_land}")
        is_land_1 = australia_geom.contains(pt_expected_land)
        print(f" -> Is on land? {is_land_1}")

        print(f"Checking Point 2 (Water Candidate): {pt_expected_water}")
        is_land_2 = australia_geom.contains(pt_expected_water)
        print(f" -> Is on land? {is_land_2}")
        
        if is_land_1 and not is_land_2:
            print("SUCCESS: Geopandas correctly distinguished land from water.")
        else:
            print("FAILURE: Could not distinguish (or both on land/water).")
            # Maybe the resolution is too low?
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_land_check()

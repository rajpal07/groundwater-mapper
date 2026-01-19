from global_land_mask import globe
from pyproj import Transformer

def test_land_check():
    print("Testing global-land-mask...")
    
    # Test Points
    # 1. Stanhope (Approx Zone 55 location) -> Should be ON LAND
    lat_land, lon_land = -36.45, 144.95
    
    # 2. The "Bad" Zone 54 location 
    # Easting 319828, Northing 5959890
    transformer = Transformer.from_crs("EPSG:32754", "EPSG:4326", always_xy=True)
    lon_bad, lat_bad = transformer.transform(319828, 5959890)
    
    print(f"Checking Point 1 (Land Candidate): Lat {lat_land}, Lon {lon_land}")
    is_land_1 = globe.is_land(lat_land, lon_land)
    print(f" -> Is on land? {is_land_1}")

    print(f"Checking Point 2 (Water Candidate): Lat {lat_bad:.4f}, Lon {lon_bad:.4f}")
    is_land_2 = globe.is_land(lat_bad, lon_bad)
    print(f" -> Is on land? {is_land_2}")
    
    if is_land_1 and not is_land_2:
        print("SUCCESS: global-land-mask correctly distinguished land from water.")
    else:
        print("FAILURE: Could not distinguish.")

if __name__ == "__main__":
    test_land_check()

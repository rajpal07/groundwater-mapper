import utils
import os
import pandas as pd

def check_kmz_and_resolve_zone():
    kmz_path = "Western Composting Technology Bendigo (1).kmz"
    excel_path = "WCT Huntly 12052025.xlsx"
    
    print("="*60)
    print("CHECKING KMZ COORDINATES")
    print("="*60)
    
    # 1. Extract KMZ points (Ground Truth)
    kmz_points = utils.extract_kmz_points(kmz_path)
    if kmz_points:
        print(f"Found {len(kmz_points)} points in KMZ")
        lons = [p.x for p in kmz_points]
        lats = [p.y for p in kmz_points]
        avg_lon = sum(lons) / len(lons)
        avg_lat = sum(lats) / len(lats)
        print(f"Average KMZ Location: Lon {avg_lon:.4f}°, Lat {avg_lat:.4f}°")
        
        # Calculate expected zone
        expected_zone = utils.calculate_utm_zone_from_lonlat(avg_lon, avg_lat)
        print(f"EXPECTED UTM ZONE: {expected_zone}S")
    else:
        print("No points found in KMZ")
        return

    print("\n" + "="*60)
    print("CHECKING EXCEL ZONES")
    print("="*60)
    
    df = pd.read_excel(excel_path)
    df.columns = df.columns.str.strip()
    df['Easting'] = pd.to_numeric(df['Easting'], errors='coerce')
    df['Northing'] = pd.to_numeric(df['Northing'], errors='coerce')
    df = df.dropna(subset=['Easting', 'Northing'])
    
    print("Testing auto-detection vs Expected...")
    
    # Call auto-detect
    detected_epsg, conf, info = utils.auto_detect_utm_zone(df)
    print(f"Currently Auto-Detected: {info['zone']}S ({detected_epsg})")
    
    if info['zone'] != expected_zone:
        print(f"\n⚠ MISMATCH DETECTED!")
        print(f"  Auto-detect picked Zone {info['zone']}S")
        print(f"  KMZ indicates Zone {expected_zone}S")
        print("  This confirms the ambiguity issue.")
    else:
        print("\nMatch! (Wait, then why did the map fail?)")

if __name__ == "__main__":
    check_kmz_and_resolve_zone()

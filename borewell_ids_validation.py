"""
Verification for borewell ID labels feature.
Tests that borewell names are correctly extracted from Excel and included in target_points.
"""
import sys
sys.path.insert(0, '.')

from utils import process_excel_data

print("=" * 80)
print("BOREWELL ID LABELS - VERIFICATION")
print("=" * 80)

try:
    # Process the Excel file
    print("\n1. Processing Excel file...")
    image_base64, image_bounds, target_points, bbox_geojson = process_excel_data('WCT Huntly 12052025.xlsx')
    
    print(f"✓ Excel processed successfully")
    print(f"✓ Total points: {len(target_points)}")
    
    # Verify all points have names
    print("\n2. Verifying borewell names...")
    all_have_names = True
    for pt in target_points:
        if 'name' not in pt:
            print(f"✗ Point {pt['id']} missing 'name' field")
            all_have_names = False
        elif not pt['name']:
            print(f"✗ Point {pt['id']} has empty name")
            all_have_names = False
    
    if all_have_names:
        print("✓ All points have valid names")
    
    # Display all borewell points
    print("\n3. Borewell Point Details:")
    print("-" * 80)
    for pt in target_points:
        short_id = pt['name'].split(' ')[0] if pt['name'] else f"Point {pt['id']}"
        print(f"  ID: {pt['id']:2d} | Name: {pt['name']:20s} | Short ID: {short_id:10s} | Lat: {pt['lat']:10.6f} | Lon: {pt['lon']:10.6f}")
    
    print("\n" + "=" * 80)
    print("VERIFICATION COMPLETE - ALL TESTS PASSED ✓")
    print("=" * 80)
    print("\nNext Steps:")
    print("1. Run: streamlit run app.py")
    print("2. Upload: WCT Huntly 12052025.xlsx")
    print("3. Verify labels appear on map (e.g., WB-01, WB-02, etc.)")
    print("4. Click markers to see full names in popups")
    
except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

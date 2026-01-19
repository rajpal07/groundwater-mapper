import utils
import os

def test_generation():
    # Paths to sample files in local directory
    excel_path = "some1.xlsx"
    kmz_path = "some1.kmz"
    
    if not os.path.exists(excel_path):
        print(f"Error: {excel_path} not found.")
        return
    
    print("Processing KMZ first (to resolve UTM Zone)...")
    kmz_points = None
    if os.path.exists(kmz_path):
        try:
            kmz_points = utils.extract_kmz_points(kmz_path)
            print(f"Success! Extracted {len(kmz_points)} points from KMZ.")
        except Exception as e:
            print(f"Failed to process KMZ: {e}")
    else:
        print("KMZ file not found, skipping.")
    
    print("Processing Excel...")
    try:
        # Pass kmz_points as reference to ensure correct zone detection
        image_base64, image_bounds, target_points, bbox_geojson = utils.process_excel_data(
            excel_path, 
            reference_points=kmz_points
        )
        print(f"Success! Image bounds: {image_bounds}")
        print(f"Number of target points: {len(target_points)}")
    except Exception as e:
        print(f"Failed to process Excel: {e}")
        return

    print("Creating Map...")
    try:
        m = utils.create_map(image_base64, image_bounds, target_points, kmz_points, bbox_geojson)
        output_file = "test_map.html"
        m.save(output_file)
        print(f"Map saved to {output_file}")
    except Exception as e:
        print(f"Failed to create map: {e}")

if __name__ == "__main__":
    test_generation()

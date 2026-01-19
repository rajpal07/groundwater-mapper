
import pandas as pd
import sys
import os
import uuid

# Add src to path
sys.path.append(os.getcwd())

import src.data as data
import src.visualization as viz
import src.templates as templates

# Define inputs
FILE_PATH = "d:/anirudh_kahn/adi_version/Water_Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
OUTPUT_HTML = "d:/anirudh_kahn/adi_version/Cobden_Map_Generated_Water.html"
COLORMAP = "viridis"
PARAM = "Static Water Level (mAHD)"

def generate():
    print(f"Processing {FILE_PATH}...")
    try:
        # Note: Header appears to be at row index 5 for this file based on inspection
        df = pd.read_excel(FILE_PATH, header=5)
        # Process Data
        print("Generating Contour Data...")
        image_base64, image_bounds, target_points, bbox_geojson = data.process_excel_data(
            df, 
            value_column=PARAM,
            generate_contours=True,
            colormap=COLORMAP
        )
        
        # Create Map
        print("Creating Folium Map...")
        m = viz.create_map(
            image_base64, 
            image_bounds, 
            target_points, 
            kmz_points=None, 
            bbox_geojson=bbox_geojson,
            legend_label=PARAM
        )
        
        # Save initial HTML
        m.save(OUTPUT_HTML)
        
        # Inject Controls
        print("Injecting Controls...")
        project_details = {
             "project": "Shepparton Groundwater Assessment",
             "date": "29.09.2025"
        }
        
        templates.inject_controls_to_html(
            OUTPUT_HTML, 
            image_bounds, 
            target_points, 
            kmz_points=None, 
            legend_label=PARAM, 
            colormap=COLORMAP, 
            project_details=project_details
        )
        
        print(f"Map successfully generated at: {OUTPUT_HTML}")
        
    except Exception as e:
        print(f"Error generating map: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    generate()

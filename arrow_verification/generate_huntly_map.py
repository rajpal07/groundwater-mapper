
import pandas as pd
import sys
import os

# Add parent dir to sys.path to find src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.data import process_excel_data
import src.visualization as viz
import src.templates as templates

FILE_PATH = r"d:\anirudh_kahn\adi_version\WCT Huntly 12052025.xlsx"
# Note: The column has a trailing space based on previous inspection
PARAM = "Groundwater Elevation mAHD" 

def generate_huntly_map():
    print(f"Loading {FILE_PATH}...")
    df = pd.read_excel(FILE_PATH)
    
    # Clean columns to remove trailing spaces
    df.columns = df.columns.str.strip()
    
    print(f"Columns: {df.columns.tolist()}")
    
    if PARAM not in df.columns:
        print(f"Error: Parameter '{PARAM}' not found.")
        return

    print("Generating Hybrid Map...")
    image_base64, image_bounds, target_points, bbox_geojson = process_excel_data(
        df, 
        interpolation_method='hybrid', 
        value_column=PARAM,
        generate_contours=True,
        colormap='viridis'
    )
    
    output_filename = r"d:\anirudh_kahn\adi_version\Huntly_Map_Hybrid.html"
    
    m = viz.create_map(
        image_base64, 
        image_bounds, 
        target_points, 
        kmz_points=None, 
        bbox_geojson=bbox_geojson, 
        legend_label=PARAM
    )
    
    m.save(output_filename)
        
    # Calculate min/max for controls
    min_val = df[PARAM].min()
    max_val = df[PARAM].max()
    
    PROJECT_DETAILS = {
        "project": "Huntly Groundwater",
        "date": "10.01.2026"
    }

    templates.inject_controls_to_html(
        output_filename, 
        image_bounds, 
        target_points, 
        kmz_points=None, 
        legend_label=PARAM, 
        colormap='viridis', 
        project_details=PROJECT_DETAILS,
        min_val=min_val,
        max_val=max_val
    )
    
    print(f"Map generated at: {output_filename}")
    import webbrowser
    webbrowser.open('file://' + output_filename)

if __name__ == "__main__":
    generate_huntly_map()

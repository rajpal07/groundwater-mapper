
import pandas as pd
import folium
import os
import sys
from src.data import process_excel_data
import src.visualization as viz
import src.templates as templates

# Project Inputs
FILE_PATH = r"d:\anirudh_kahn\adi_version\Water_Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
PARAM = "Static Water Level (mAHD)" 
PROJECT_DETAILS = {
     "project": "Cobden Static Water Level",
     "date": "10.01.2026"
}

def generate_map(interpolation_mode, output_filename):
    print(f"\nProcessing {interpolation_mode.upper()} map for {FILE_PATH}...")

    # Load Data (Standard header=0 for Shepparton, header=5 for Cobden)
    try:
        if "Cobden" in FILE_PATH:
            # User request: using sheet "Attachment 1 - WWTF_GW_insitu" (GitHub version)
            # This sheet has headers at row 5 (same as other sheet)
            df = pd.read_excel(FILE_PATH, sheet_name="Attachment 1 - WWTF_GW_insitu", header=5)
        else:
            df = pd.read_excel(FILE_PATH)
            
        print("Excel loaded successfully.")
    except Exception as e:
        print(f"Error loading excel: {e}")
        return

    # Process Data
    # Process Data
    try:
        # Pass interpolation_mode ('linear' or 'hybrid')
        # auto_split_layers=True is now default in process_excel_data
        result = process_excel_data(
            df, 
            interpolation_method=interpolation_mode,
            value_column=PARAM,
            generate_contours=True,
            colormap='viridis',
            auto_split_layers=True 
        )
        print("Contour data generated.")
    except Exception as e:
        print(f"Error in processing: {e}")
        import traceback
        traceback.print_exc()
        return

    # Handle Result (List or Tuple)
    if isinstance(result, list):
        results_list = result
    else:
        # Backward compatibility wrapper
        image_base64, image_bounds, target_points, bbox_geojson = result
        results_list = [{
            'layer_name': 'All Data',
            'image_base64': image_base64,
            'image_bounds': image_bounds,
            'target_points': target_points,
            'bbox_geojson': bbox_geojson
        }]

    # Create Map for EACH result
    for res in results_list:
        layer_name = res['layer_name']
        image_base64 = res['image_base64']
        image_bounds = res['image_bounds']
        target_points = res['target_points']
        bbox_geojson = res['bbox_geojson']
        
        # Modify Filename for Layers
        if layer_name != "All Data":
            base, ext = os.path.splitext(output_filename)
            final_filename = f"{base}_{layer_name.replace(' ', '_')}{ext}"
        else:
            final_filename = output_filename
            
        print(f"Generating Map for: {layer_name} -> {final_filename}")

        # Create Map
        try:
            m = viz.create_map(
                image_base64, 
                image_bounds, 
                target_points, 
                kmz_points=None, 
                bbox_geojson=bbox_geojson, 
                legend_label=f"{PARAM} ({layer_name})"
            )
            
            # Save Base HTML
            m.save(final_filename)
            print(f"Base map saved to {final_filename}")
        
            # Calculate Min/Max for Legend key (Per Layer could be better, but Global is safer for comparison? 
            # Actually, per layer effectively because we filter df? 
            # The 'target_points' has the specific values. Let's use that.
            
            min_val = None
            max_val = None
            
            # Extract values from target_points for this layer
            values = [p['value'] for p in target_points if isinstance(p['value'], (int, float))]
            if values:
                min_val = min(values)
                max_val = max(values)
                print(f"Data Range for {layer_name}: {min_val} to {max_val}")
            
            # Inject Controls
            templates.inject_controls_to_html(
                final_filename, 
                image_bounds, 
                target_points, 
                kmz_points=None, 
                legend_label=f"{PARAM} ({layer_name})", 
                colormap='viridis', 
                project_details=PROJECT_DETAILS,
                min_val=min_val,
                max_val=max_val
            )
            print(f"Controls injected. Final map ready: {final_filename}")
            
        except Exception as e:
            print(f"Error creating/saving map for {layer_name}: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    # Earth Engine is already initialized by src.visualization import
    
    # 1. Generate Map
    generate_map('linear', r"d:\anirudh_kahn\adi_version\Cobden_Map_Attachment1.html")
    
    print("\n✓ Map generation complete.")

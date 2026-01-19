
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
            df = pd.read_excel(FILE_PATH, header=5)
        else:
            df = pd.read_excel(FILE_PATH)
            
        print("Excel loaded successfully.")
    except Exception as e:
        print(f"Error loading excel: {e}")
        return

    # Process Data
    try:
        # Pass interpolation_mode ('linear' or 'hybrid')
        image_base64, image_bounds, target_points, bbox_geojson = process_excel_data(
            df, 
            interpolation_method=interpolation_mode,
            value_column=PARAM,
            generate_contours=True,
            colormap='viridis'
        )
        print("Contour data generated.")
    except Exception as e:
        print(f"Error in processing: {e}")
        import traceback
        traceback.print_exc()
        return

    # Create Map
    try:
        m = viz.create_map(
            image_base64, 
            image_bounds, 
            target_points, 
            kmz_points=None, 
            bbox_geojson=bbox_geojson, 
            legend_label=PARAM
        )
        
        # Save Base HTML
        m.save(output_filename)
        print(f"Base map saved to {output_filename}")
        
        # Calculate Min/Max for Legend key
        min_val = None
        max_val = None
        try:
            # Clean columns
            df.columns = df.columns.str.strip()
            
            if PARAM in df.columns:
                # Filter for valid numeric data just like process_excel_data does
                valid_df = df.copy()
                valid_df[PARAM] = pd.to_numeric(valid_df[PARAM], errors='coerce')
                valid_df = valid_df.dropna(subset=[PARAM])
                
                if not valid_df.empty:
                    min_val = valid_df[PARAM].min()
                    max_val = valid_df[PARAM].max()
                    print(f"Data Range for Legend: {min_val} to {max_val}")
                else:
                    print("Warning: No valid numeric data found for legend range.")
            else:
                print(f"Warning: Column '{PARAM}' not found in dataframe columns: {df.columns.tolist()}")
                
        except Exception as e:
            print(f"Error calculating legend range: {e}")
            min_val = None
            max_val = None

        # Inject Controls
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
        print(f"Controls injected. Final map ready: {output_filename}")
        
    except Exception as e:
        print(f"Error creating/saving map: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import ee
    try:
        ee.Initialize()
        print("Earth Engine initialized.")
    except:
        # Fallback if using service account logic from main app, but for script we might need to rely on existing auth
        print("Earth Engine init failed (might need service account). Trying to proceed if geemap handles it...")
    
    # 1. Generate TIN Map
    generate_map('linear', r"d:\anirudh_kahn\adi_version\Cobden_Map_TIN.html")
    
    print("\n✓ TIN Map generation complete.")

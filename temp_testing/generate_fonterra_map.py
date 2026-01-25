
import pandas as pd
import folium
import os
import sys
from src.data import process_excel_data
import src.visualization as viz
import src.templates as templates

# Fonterra Inputs
FILE_PATH = r"d:\anirudh_kahn\adi_version\Fonterra Darnum_OCT_2025_Lab_Data_V1.xlsx"
SHEET = "2. Darnum_GW_insitu"
PARAM = "Static Water Level (mAHD)" 
PROJECT_DETAILS = {
     "project": "Fonterra Darnum Static Water Level",
     "date": "25.01.2026"
}

def generate_fonterra_map(output_filename):
    print(f"\nProcessing Fonterra map for {FILE_PATH}...")

    # Load Data with header=6
    try:
        df = pd.read_excel(FILE_PATH, sheet_name=SHEET, header=6)
        print("Excel loaded successfully.")
    except Exception as e:
        print(f"Error loading excel: {e}")
        return
        
    # Process data
    try:
        result = process_excel_data(
            df,
            value_column=PARAM,
            reference_points=None
        )
        
        # Handle both single-layer (tuple) and multi-layer (list) outputs
        if isinstance(result, list):
            # Multi-layer output
            layers = result
            print(f"Generated {len(layers)} aquifer layer(s)")
        elif isinstance(result, tuple):
            # Single-layer output (backward compatibility)
            image_base64, image_bounds, target_points, bbox_geojson = result
            layers = [{
                'layer_name': 'All Data',
                'image_base64': image_base64,
                'image_bounds': image_bounds,
                'target_points': target_points,
                'bbox_geojson': bbox_geojson
            }]
        else:
            # Single-layer dict output
            layers = [result]
        
        # Generate map for EACH layer
        generated_maps = []
        for i, layer in enumerate(layers):
            layer_name = layer['layer_name']
            print(f"\nCreating map {i+1}/{len(layers)}: {layer_name}")
            
            # Create layer-specific filename
            if len(layers) > 1:
                # Multi-layer: Fonterra_Layer_A.html, Fonterra_Layer_B.html
                safe_layer_name = layer_name.replace(' ', '_')
                layer_filename = output_filename.replace('.html', f'_{safe_layer_name}.html')
            else:
                # Single layer: use original filename
                layer_filename = output_filename
            
            # Create map
            m = viz.create_map(
                layer['image_base64'],
                layer['image_bounds'],
                layer['target_points'],
                bbox_geojson=layer['bbox_geojson']
            )
            
            # Save map
            m.save(layer_filename)
            print(f"  Map saved to: {layer_filename}")
            
            # Inject controls
            templates.inject_controls_to_html(
                layer_filename,
                layer['image_bounds'],
                layer['target_points'],
                project_details=PROJECT_DETAILS
            )
            print(f"  Controls injected. Map ready!")
            generated_maps.append(layer_filename)
        
        print(f"\n✓ Generated {len(generated_maps)} map(s):")
        for map_file in generated_maps:
            print(f"  - {map_file}")
        
    except Exception as e:
        print(f"Error in processing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Earth Engine is already initialized by src.visualization import
    
    # Generate Map
    generate_fonterra_map(r"d:\anirudh_kahn\adi_version\Fonterra_Darnum_Map.html")
    
    print("\n✓ Map generation complete.")

import pandas as pd
import utils
import os

def generate_ammonia_map():
    input_file = "processed_data.xlsx"
    output_html = "local_test_map_ammonia.html"
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    print(f"Loading {input_file}...")
    df = pd.read_excel(input_file)
    
    target_col = 'Ammonia as N'
    if target_col not in df.columns:
        print(f"Error: Column '{target_col}' not found. Available: {df.columns.tolist()}")
        return
    
    print(f"Generating map for: {target_col}")
    
    # Process
    try:
        # utils.process_excel_data returns: image_base64, image_bounds, target_points, bbox_geojson
        image_base64, image_bounds, target_points, bbox_geojson = utils.process_excel_data(
            df, 
            value_column=target_col,
            generate_contours=True,
            colormap='viridis' # Default logic
        )
        
        # Create Map
        m = utils.create_map(image_base64, image_bounds, target_points, bbox_geojson=bbox_geojson, legend_label=target_col)
        
        # Save
        m.save(output_html)
        print(f"Base map saved to {output_html}")
        
        # Inject Controls
        utils.inject_controls_to_html(
            output_html, 
            image_bounds, 
            target_points, 
            legend_label=target_col,
            colormap='viridis'
        )
        print("Controls injected successfully.")
        
    except Exception as e:
        print(f"Error generating map: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    generate_ammonia_map()

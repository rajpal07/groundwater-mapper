import pandas as pd
import utils
import os

def generate_ph_map():
    input_file = "processed_data.xlsx"
    output_html = "local_test_map_ph.html"
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    print(f"Loading {input_file}...")
    df = pd.read_excel(input_file)
    
    # Identify pH column
    # The agent output said 'pH value'
    target_col = 'pH value'
    if target_col not in df.columns:
        print(f"Error: Column '{target_col}' not found. Available: {df.columns.tolist()}")
        # Fuzzy search?
        for c in df.columns:
            if 'pH' in c:
                target_col = c
                print(f"Found alternative pH column: {target_col}")
                break
    
    print(f"Generating map for: {target_col}")
    
    # Process
    try:
        # utils.process_excel_data returns: image_base64, image_bounds, target_points, bbox_geojson
        image_base64, image_bounds, target_points, bbox_geojson = utils.process_excel_data(
            df, 
            value_column=target_col,
            generate_contours=True,
            colormap='viridis' # or 'Spectral_r' which is common for pH? Let's stick to default or viridis for now.
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
    generate_ph_map()

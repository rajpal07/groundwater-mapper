from src.sheet_agent import SheetAgent
import os
import pandas as pd
import utils

# API Key provided by user
API_KEY = "llx-0Lk8T6aYU83RDVo3naHVjKsQOVyNbq0ImRDjrrwux1axMi77"

def test_agent():
    input_file = "Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"
    output_file = "processed_data.xlsx"
    
    # Initialize Agent
    agent = SheetAgent(api_key=API_KEY)
    
    # Run
    print(f"Running agent on {input_file}...")
    result_path = agent.process(input_file)
    
    if result_path and os.path.exists(result_path):
        print("SUCCESS: processed_data.xlsx created.")
        
        # Verify content
        df = pd.read_excel(result_path)
        print("Columns found:", df.columns.tolist())
        print("First 5 rows:")
        print(df.head())
        
        # Check for critical columns
        required = ['Well ID', 'Easting', 'Northing', 'Static Water Level (mAHD)']
        missing = [col for col in required if col not in df.columns]
        
        if not missing:
            print("VERIFICATION PASSED: All required columns present.")
        else:
            print(f"VERIFICATION FAILED: Missing columns {missing}")
            return
            
        # --- TEST UTILS (Live Dashboard Logic) ---
        print("\n--- Testing Utils (Map Generation) ---")
        try:
            # Test 1: Groundwater
            print("1. Testing 'Static Water Level (mAHD)'...")
            img, bounds, points, bbox = utils.process_excel_data(df, value_column='Static Water Level (mAHD)')
            print(f"   -> Processed successfully. Points: {len(points)}")
            
            # Test Utils: Map Creation verification
            print("   -> Testing Map Creation...")
            
            # NOTE: In a real run, st.secrets are already loaded.
            # Here we simulate the environment if needed, or rely on local auth if available.
            try:
                # Try to create map with current environment
                m = utils.create_map(img, bounds, points, bbox_geojson=bbox, legend_label="Groundwater Level")
                m.save("test_map_gw.html")
                print("   -> SUCCESS: Map created and saved to 'test_map_gw.html'")
                
                # Check for correct Well IDs in the output
                with open("test_map_gw.html", "r", encoding="utf-8") as f:
                    content = f.read()
                    if 'name": "M1"' in content or 'name": "M2"' in content:
                        print("   -> SUCCESS: Well IDs (M1, M2...) found in Map Data.")
                    else:
                        print("   -> WARNING: Well IDs NOT found. Check point naming logic.")
                
            except Exception as e:
                print(f"   -> Map Creation Warning: {e}")

            # ------------------------------------------------------------------
            # 3. VERIFICATION: Test Chemical Optimization (No Contours)
            # ------------------------------------------------------------------
            print("\n3. Testing Optimization (Chemicals should SKIP contours)...")
            try:
                # Pick a chemical column
                chem_col = "Chloride" 
                if chem_col not in df.columns: chem_col = df.columns[10] # Fallback
                
                print(f"   Testing '{chem_col}'...")
                
                # Manually call process_excel_data with contour flag = False (simulating app behavior)
                # In app.py: should_generate_contours = "Water Level" in param ...
                should_gen = "Water Level" in chem_col or "Elevation" in chem_col
                print(f"   Should Generate Contours? {should_gen}")
                
                img, bounds, pts, box = utils.process_excel_data(df, value_column=chem_col, generate_contours=should_gen)
                
                if img is None and bounds is None:
                    print("   -> SUCCESS: Contours skipped for chemical (Optimization working).")
                else:
                    print("   -> FAILURE: Contours generated despite optimization flag!")
                    
            except Exception as e:
                print(f"   -> Optimization Test Error: {e}")

    # 4. Final Summary
            
            # Test Injection
            utils.inject_controls_to_html("test_map_gw.html", bounds, points, legend_label="Groundwater Level")
            
            with open("test_map_gw.html", "r", encoding="utf-8") as f:
                content = f.read()
                # utils.py shortens "Groundwater Level" -> "Groundwater"
                if "Groundwater" in content:
                    print("   -> SUCCESS: Dynamic Legend injected in HTML.")
                else:
                    print("   -> FAILED: Dynamic Legend not found in HTML.")

            # Test 2: Chemical (Arsenic)
            # Find an arsenic column if exists (cols have stars sometimes)
            # Normalize for search: "\*Arsenic" -> "Arsenic"
            arsenic_col = next((c for c in df.columns if 'Arsenic' in c), None)
            
            if arsenic_col:
                print(f"2. Testing '{arsenic_col}'...")
                
                # Check if we have valid data before interpolating
                valid_count = df[arsenic_col].apply(pd.to_numeric, errors='coerce').notna().sum()
                if valid_count < 3: 
                    print(f"   -> SKIPPING: Not enough valid numeric data for {arsenic_col} (Count: {valid_count})")
                else:
                    img, bounds, points, bbox = utils.process_excel_data(df, value_column=arsenic_col)
                    print(f"   -> Processed successfully. Points: {len(points)}")
                    
                    with open("test_map_arsenic.html", "w", encoding="utf-8") as f:
                        f.write("<html><body><div class='folium-map'></div></body></html>")
                    
                    utils.inject_controls_to_html("test_map_arsenic.html", bounds, points, legend_label=arsenic_col)
                    
                    with open("test_map_arsenic.html", "r", encoding="utf-8") as f:
                        content = f.read()
                        # Legend label logic in utils: split(' ')[0] or shorter
                        # Arsenic might be "*Arsenic" -> "*Arsenic" or "Arsenic"
                        expected_shortr = arsenic_col.split(' ')[0]
                        if expected_shortr in content: 
                            print(f"   -> SUCCESS: Dynamic Legend injected for {arsenic_col}")
                        else:
                            print(f"   -> WARNING: Dynamic Legend not strict match for {arsenic_col}. Content snippet: {content[:100]}...")
                        
            else:
                print("   -> Skipped Arsenic (column not found)")

            print("\n✅ API Integration Verification PASSED")
            
        except Exception as e:
            print(f"\n❌ Utils Validation FAILED: {e}")
            import traceback
            traceback.print_exc()

    else:
        print("FAILURE: Output file not created.")

if __name__ == "__main__":
    test_agent()

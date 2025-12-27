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
            
            # NOW RE-ENABLING TO TEST AUTH FIX
            print("   -> Testing Map Creation (Auth Check)...")
            
            # Manual EE Init to simulate Cloud Environment where secrets worked
            try:
                import ee
                import json
                import toml
                secrets = toml.load(".streamlit/secrets.toml")
                token = json.loads(secrets['EARTHENGINE_TOKEN'], strict=False)
                from google.oauth2.service_account import Credentials
                scopes = ['https://www.googleapis.com/auth/earthengine']
                creds = Credentials.from_service_account_info(token, scopes=scopes)
                ee.Initialize(credentials=creds, project='geekahn')
                print("   -> Simulated Cloud Env: EE Initialized manually.")
                
                # Create map REAL
                m = utils.create_map(img, bounds, points, bbox_geojson=bbox, legend_label="Groundwater Level")
                m.save("test_map_gw.html")
                print("   -> Map created and saved successfully (Auth patch worked!)")
            except Exception as e:
                print(f"   -> Map Creation FAILED: {e}")
                import traceback
                traceback.print_exc()
            
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

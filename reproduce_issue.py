
import pandas as pd
import utils
import json
import traceback

def reproduce():
    print("--- Attempting to reproduce Invalid \escape error ---")
    
    # 1. Create Mock Data with "Dirty" Column Name
    # Simulating what SheetAgent MIGHT have output if cleaning failed
    bad_col = r"\*Arsenic" # Literal \*Arsenic
    
    data = {
        "Well ID": ["W1", "W2", "W3"],
        "Easting": [677291, 677292, 678016],
        "Northing": [5754000, 5754010, 5754020],
        bad_col: [0.001, 0.002, 0.005]
    }
    df = pd.DataFrame(data)
    print(f"Created DataFrame with column: {bad_col}")
    
    try:
        # 2. Call Utils
        print(f"Calling utils.process_excel_data with '{bad_col}'...")
        img, bounds, points, bbox = utils.process_excel_data(df, value_column=bad_col)
        print("Utils processed successfully.")
        
        # 3. Call Create Map
        print(f"Calling utils.create_map with legend_label='{bad_col}'...")
        # Note: mocking geemap behavior if needed, but let's see if utils fails before that
        # create_map calls geemap.Map()... which requires auth.
        # If the error is in json.loads inside utils or geemap, it might trigger here.
        # However, without auth, geemap might just fail on Init.
        
        # Check if we can trigger it just by simple JSON dump of the string?
        # The error "Invalid \escape" is characteristic of json.loads(bad_string)
        
        # Let's try to simulate what passing this string to a JSON construct does
        test_json = f'{{"label": "{bad_col}"}}'
        print(f"Testing JSON load of: {test_json}")
        try:
             json.loads(test_json)
             print("JSON load success.")
        except json.JSONDecodeError as e:
             print(f"CAUGHT EXPECTED ERROR in raw JSON: {e}")

        # If utils does something similar
    except Exception as e:
        print("Caught Exception in Utils:")
        traceback.print_exc()

if __name__ == "__main__":
    reproduce()

from src.sheet_agent import SheetAgent
import os
import pandas as pd
import utils

# API Key provided by user
API_KEY = "llx-0Lk8T6aYU83RDVo3naHVjKsQOVyNbq0ImRDjrrwux1axMi77"

import argparse

def test_agent():
    parser = argparse.ArgumentParser(description="Run SheetAgent on an Excel file.")
    parser.add_argument("input_file", nargs='?', default="Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx", help="Path to input Excel file")
    args = parser.parse_args()
    
    input_file = args.input_file
    output_file = "processed_data.xlsx"
    
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found.")
        return

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
        has_coords = False
        if 'Easting' in df.columns and 'Northing' in df.columns:
            has_coords = True
        elif 'Latitude' in df.columns and 'Longitude' in df.columns:
            has_coords = True

        if 'Well ID' in df.columns and has_coords:
            print("VERIFICATION PASSED: Well ID and Coordinates present.")
        else:
            print(f"VERIFICATION FAILED: Missing columns. Columns: {df.columns.tolist()}")
            return

if __name__ == "__main__":
    test_agent()

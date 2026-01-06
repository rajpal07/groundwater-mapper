import os
import shutil
import time
from src.sheet_agent import SheetAgent
import pandas as pd

# Mock API Key (not needed for this test if we mock parse or use existing cache)
TEST_FILE = "Cobden_Processed.xlsx" # Existing file in dir

def test_isolation():
    print("Testing Job Isolation...")
    
    # Setup runs dir
    if os.path.exists("runs_test"):
        shutil.rmtree("runs_test")
    os.makedirs("runs_test")
    
    job_id_1 = "job_1"
    job_id_2 = "job_2"
    
    path_1 = os.path.join("runs_test", job_id_1, "output.xlsx")
    path_2 = os.path.join("runs_test", job_id_2, "output.xlsx")
    
    agent = SheetAgent(api_key="dummy")
    
    # Mock parse_raw_file to avoid API calls
    agent.parse_raw_file = lambda x: """
    | Well ID | Easting | Northing | Static Water Level (mAHD) |
    |---|---|---|---|
    | W001 | 100 | 200 | 10.5 |
    | W002 | 110 | 210 | 11.2 |
    """
    
    print(f"Job 1 -> {path_1}")
    result_1 = agent.process(TEST_FILE, output_path=path_1)
    
    print(f"Job 2 -> {path_2}")
    result_2 = agent.process(TEST_FILE, output_path=path_2)
    
    # Verification
    if os.path.exists(path_1) and os.path.exists(path_2):
        print("SUCCESS: Both job files exist.")
        if path_1 != path_2:
             print("SUCCESS: Paths are different.")
        else:
             print("FAIL: Paths are identical.")
    else:
        print("FAIL: Files not created.")
        if not os.path.exists(path_1): print(f"Missing: {path_1}")
        if not os.path.exists(path_2): print(f"Missing: {path_2}")
    
    # Clean up
    if os.path.exists("runs_test"):
        shutil.rmtree("runs_test")

if __name__ == "__main__":
    if not os.path.exists(TEST_FILE):
        # Create dummy excel if needed
        pd.DataFrame({'A': [1]}).to_excel(TEST_FILE)
        
    test_isolation()

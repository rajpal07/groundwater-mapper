import sys
import os
import unittest.mock
from unittest.mock import MagicMock, patch

# Mock LlamaParse and SimpleDirectoryReader BEFORE importing src.sheet_agent
sys.modules['llama_parse'] = MagicMock()
sys.modules['llama_index.core'] = MagicMock()

# Now import the class
from src.sheet_agent import SheetAgent

def test_cache_logic():
    print("Testing SheetAgent Cache Logic...")
    
    # Mock dependencies
    agent = SheetAgent(api_key="fake")
    
    # Mock 'parse_raw_file' to return "MOCKED MARKDOWN" and print a message
    original_parse = agent.parse_raw_file
    agent.parse_raw_file = MagicMock(return_value="MOCKED MARKDOWN")
    
    # Create a dummy excel file
    import pandas as pd
    df = pd.DataFrame({'a': [1, 2], 'Well ID': ['W1', 'W2']})
    df.to_excel("dummy_test.xlsx", index=False)
    
    # Run process twice
    print("\n--- Run 1 ---")
    with patch('pandas.read_excel', return_value=df):
       # We need to mock smart_extract_sheet's specific pd.read_excel if it's called
       # But actually smart_extract_sheet does: pd.read_excel(file_path, sheet_name=sheet_name)
       # Let's just mock the whole smart_extract_sheet to see if it's called
       
       # Wait, I want to see if parse_raw_file is called multiple times.
       
       # If I mock smart_extract_sheet, I miss the bug because the bug is INSIDE smart_extract_sheet calling parse_raw_file.
       # So I must NOT mock smart_extract_sheet.
       
       # I need to mock pd.read_excel to just return valid DF so the temp file creation works.
       pass

    try:
        # Run 1
        agent.process("dummy_test.xlsx", output_path="out1.xlsx", selected_sheets=["Sheet1"])
        
        # Run 2
        print("\n--- Run 2 ---")
        agent.process("dummy_test.xlsx", output_path="out2.xlsx", selected_sheets=["Sheet1"])
        
        # Check call count
        print(f"\nTotal calls to parse_raw_file: {agent.parse_raw_file.call_count}")
        
        # We expect:
        # Run 1: 
        #   - process calls parse_raw_file (to cache the whole file? No, line 231 checks cache)
        #   - smart_extract_sheet calls parse_raw_file (on temp file)
        # Run 2:
        #   - process sees cache for whole file, SKIP parse_raw_file
        #   - smart_extract_sheet calls parse_raw_file (on temp file) -> DOES NOT CHECK CACHE
        
        # If cache was working for smart_extract, we'd expect fewer calls.
        # But 'process' logic (lines 231-240) only caches the "whole file" scan which is seemingly UNUSED?
        # Because 'process' doesn't pass the cached markdown to 'smart_extract_sheet'.
        
        if agent.parse_raw_file.call_count >= 2:
             print("FAIL: parse_raw_file called multiple times, proving smart_extract_sheet bypasses cache.")
        else:
             print("PASS: parse_raw_file called minimally.")

    finally:
        if os.path.exists("dummy_test.xlsx"): os.remove("dummy_test.xlsx")
        if os.path.exists("out1.xlsx"): os.remove("out1.xlsx")
        # cleanup cache files
        import glob
        for f in glob.glob("cache_llama_*.md"):
            os.remove(f)

if __name__ == "__main__":
    test_cache_logic()

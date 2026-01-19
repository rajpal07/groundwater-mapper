"""
Diagnostic script to trace coordinate extraction through the entire pipeline.
Run this to see exactly what the AI is extracting and why coordinates might be missing.

Usage:
    python diagnose_coordinates.py <excel_file> <sheet_name>
    
Example:
    python diagnose_coordinates.py "Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx" "Attachment 3 - Cobden_GW_Lab"
"""
import os
import sys
import pandas as pd
from src.sheet_agent import SheetAgent
import glob

def cleanup_cache():
    """Remove old cache files to force fresh parsing"""
    cache_files = glob.glob("cache_llama_*.md")
    for f in cache_files:
        try:
            os.remove(f)
            print(f"✓ Removed old cache: {f}")
        except:
            pass

def main():
    if len(sys.argv) < 3:
        print("Usage: python diagnose_coordinates.py <excel_file> <sheet_name>")
        print('Example: python diagnose_coordinates.py "data.xlsx" "Sheet1"')
        sys.exit(1)
    
    EXCEL_FILE = sys.argv[1]
    SHEET_NAME = sys.argv[2]
    API_KEY = os.getenv("LLAMA_CLOUD_API_KEY")

    if not API_KEY:
        print("ERROR: LLAMA_CLOUD_API_KEY not set in environment")
        print("Set it with: export LLAMA_CLOUD_API_KEY=your_key")
        sys.exit(1)

    if not os.path.exists(EXCEL_FILE):
        print(f"ERROR: File not found: {EXCEL_FILE}")
        sys.exit(1)

    print("="*80)
    print("COORDINATE EXTRACTION DIAGNOSTIC")
    print("="*80)
    print(f"File: {EXCEL_FILE}")
    print(f"Sheet: {SHEET_NAME}")
    print()

    # Clean cache to force fresh processing
    print("[0] CLEANING CACHE")
    print("-"*80)
    cleanup_cache()
    print()

    # Step 1: Check raw Excel
    print("[1] RAW EXCEL FILE INSPECTION")
    print("-"*80)
    try:
        df_raw = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME)
        print(f"✓ Successfully read sheet: {SHEET_NAME}")
        print(f"✓ Shape: {df_raw.shape} (rows, columns)")
        print(f"\n✓ All column names in raw Excel:")
        for i, col in enumerate(df_raw.columns, 1):
            print(f"   {i:2d}. '{col}'")
        
        # Check for coordinate columns
        coord_keywords = ['easting', 'northing', 'latitude', 'longitude', 'eassting']
        found_coords = [col for col in df_raw.columns if any(kw in col.lower() for kw in coord_keywords)]
        
        if found_coords:
            print(f"\n✓ Found potential coordinate columns: {found_coords}")
            for col in found_coords:
                non_null = df_raw[col].notna().sum()
                sample_vals = df_raw[col].dropna().head(3).tolist()
                print(f"   {col}: {non_null} non-null values")
                print(f"      Samples: {sample_vals}")
        else:
            print("\n✗ NO coordinate columns found in raw Excel!")
            print("   This means the Excel file itself doesn't have coordinate data.")
            
    except Exception as e:
        print(f"✗ Failed to read Excel: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Step 2: Process with AI
    print("\n[2] AI AGENT PROCESSING (FRESH - NO CACHE)")
    print("-"*80)
    try:
        agent = SheetAgent(api_key=API_KEY)
        output_path = "diagnostic_output.xlsx"
        
        print(f"Processing sheet '{SHEET_NAME}' with AI...")
        print("(This will take a moment as it's parsing fresh...)")
        
        result_path = agent.process(EXCEL_FILE, output_path=output_path, selected_sheets=[SHEET_NAME])
        
        if not result_path or not os.path.exists(result_path):
            print("✗ AI Agent failed to produce output file")
            sys.exit(1)
        
        print(f"✓ AI processing complete: {result_path}")
        
    except Exception as e:
        print(f"✗ AI processing failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Step 3: Inspect AI output
    print("\n[3] AI OUTPUT INSPECTION")
    print("-"*80)
    try:
        df_processed = pd.read_excel(result_path)
        print(f"✓ Shape: {df_processed.shape} (rows, columns)")
        print(f"\n✓ All column names in AI output:")
        for i, col in enumerate(df_processed.columns, 1):
            print(f"   {i:2d}. '{col}'")
        
        # Check for coordinate columns
        found_coords = [col for col in df_processed.columns if any(kw in col.lower() for kw in coord_keywords)]
        
        if found_coords:
            print(f"\n✓ Found coordinate columns in AI output: {found_coords}")
            for col in found_coords:
                non_null = df_processed[col].notna().sum()
                sample_vals = df_processed[col].dropna().head(3).tolist()
                print(f"   {col}: {non_null} non-null values")
                print(f"      Samples: {sample_vals}")
        else:
            print("\n✗ NO coordinate columns in AI output!")
            print("   ⚠️  THIS IS THE PROBLEM!")
            print("   The AI extraction is not capturing coordinate columns.")
        
        # Check Well ID
        if 'Well ID' in df_processed.columns:
            print(f"\n✓ 'Well ID' column present: {df_processed['Well ID'].nunique()} unique wells")
            print(f"   Sample Well IDs: {df_processed['Well ID'].head(3).tolist()}")
        else:
            print("\n✗ 'Well ID' column missing!")
        
        # Show sample data
        print("\n✓ First 3 rows of processed data:")
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        print(df_processed.head(3).to_string())
        
    except Exception as e:
        print(f"✗ Failed to inspect AI output: {e}")
        import traceback
        traceback.print_exc()

    # Step 4: Inspect markdown cache
    print("\n[4] MARKDOWN CACHE INSPECTION")
    print("-"*80)
    cache_files = glob.glob("cache_llama_*.md")
    
    if cache_files:
        print(f"✓ Found {len(cache_files)} cache file(s)")
        latest_cache = max(cache_files, key=os.path.getmtime)
        print(f"✓ Latest cache: {latest_cache}")
        
        with open(latest_cache, 'r', encoding='utf-8') as f:
            md_content = f.read()
        
        print(f"✓ Cache size: {len(md_content)} characters")
        
        # Search for coordinate references
        lines = md_content.split('\n')
        print("\n✓ Searching for coordinate references in markdown...")
        found_any = False
        for i, line in enumerate(lines[:100]):  # Check first 100 lines
            if any(kw in line.lower() for kw in coord_keywords):
                found_any = True
                print(f"   Line {i}: {line[:120]}")
        
        if not found_any:
            print("   ✗ No coordinate keywords found in first 100 lines")
            
        # Look for Well ID table
        print("\n✓ Searching for 'Well ID' table headers...")
        for i, line in enumerate(lines[:100]):
            if 'well id' in line.lower() and '|' in line:
                print(f"   Found at line {i}: {line[:120]}")
                # Show next few lines
                for j in range(i+1, min(i+5, len(lines))):
                    print(f"   Line {j}: {lines[j][:120]}")
                break
    else:
        print("✗ No cache files found")

    print("\n" + "="*80)
    print("DIAGNOSTIC COMPLETE")
    print("="*80)
    print("\n📊 SUMMARY:")
    print(f"   Raw Excel has coordinates: {'YES' if found_coords else 'NO'}")
    print(f"   AI output has coordinates: {'YES' if found_coords else 'NO'}")
    print("\n💡 NEXT STEPS:")
    if found_coords:
        print("   ✓ Coordinates are being extracted correctly!")
    else:
        print("   ✗ Check the markdown cache to see if LlamaParse is capturing the headers")
        print("   ✗ The issue is likely in the table extraction logic (multi-row headers)")

if __name__ == "__main__":
    main()

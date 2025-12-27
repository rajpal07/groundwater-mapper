import nest_asyncio
nest_asyncio.apply()

from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader
import os

# Set API Key provided by user
os.environ["LLAMA_CLOUD_API_KEY"] = "llx-0Lk8T6aYU83RDVo3naHVjKsQOVyNbq0ImRDjrrwux1axMi77"

file_path = "Cobden_JUNE_2025_Lab_and_Insitu_Data_V1 (1).xlsx"

print(f"initializing LlamaParse for {file_path}...")

try:
    # Initialize parser
    # premium_mode=True is default for LlamaParse but good to be explicit if available, 
    # though valid options are usually just result_type="markdown"
    parser = LlamaParse(
        result_type="markdown",  # "markdown" and "text" are available
        verbose=True,
        language="en"
    )

    # Use SimpleDirectoryReader to load the file using the parser
    file_extractor = {".xlsx": parser}
    
    print("Parsing file... this may take a moment (cloud processing)...")
    documents = SimpleDirectoryReader(input_files=[file_path], file_extractor=file_extractor).load_data()
    
    print(f"Parsing complete. Loaded {len(documents)} documents (or split pages).")
    
    # In Markdown mode, tables usually come out as markdown tables.
    # Let's inspect the content to see if 'Attachment 3' was clearly separated.
    
    full_text = "\n\n".join([doc.text for doc in documents])
    
    # Save raw output to inspect
    with open("llama_parse_output.md", "w", encoding="utf-8") as f:
        f.write(full_text)
        
    print("Saved output to 'llama_parse_output.md'.")
    
    # Look for our target keywords
    if "Attachment 3" in full_text:
        print("SUCCESS: Found 'Attachment 3' in the parsed output.")
        
        # Print a snippet around "Attachment 3"
        start_idx = full_text.find("Attachment 3")
        snippet = full_text[start_idx:start_idx+1000]
        print("\n--- SNIPPET ---")
        print(snippet)
        print("---------------\n")
    else:
        print("WARNING: 'Attachment 3' keywords not found in parsed text.")
        
except Exception as e:
    print(f"Error running LlamaParse: {e}")

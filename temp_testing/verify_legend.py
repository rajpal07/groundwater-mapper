import re

file_path = r"d:\anirudh_kahn\adi_version\Cobden_Map_TIN.html"

try:
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
        
    if "Legend with Resize Handles" in content:
        print("Found Legend section.")
    else:
        print("Legend section NOT found.")
        
    # Search for the gradient scale numbers
    # We expect something like <span>104.50</span> (example value)
    # Let's search for the structure
    
    match = re.search(r'<span>Min</span>\s*<span>Max</span>', content)
    if match:
        print("Found Min/Max labels.")
    else:
        print("Min/Max labels NOT found.")

    match = re.search(r'<span>([\d\.]+|Low)</span>\s*<span>([\d\.]+|High)</span>', content)
    if match:
        print(f"Found Scale Values: Min={match.group(1)}, Max={match.group(2)}")
    else:
        print("Scale values not found or format mismatch.")
        
except Exception as e:
    print(f"Error reading file: {e}")

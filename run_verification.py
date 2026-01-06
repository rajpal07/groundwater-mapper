import utils
import os

# Create a dummy HTML file
dummy_html = "test_map_verify.html"
with open(dummy_html, "w", encoding="utf-8") as f:
    f.write("<html><body><div id='map'></div></body></html>")

try:
    # Test injection
    print("Injecting controls...")
    utils.inject_controls_to_html(
        dummy_html, 
        image_bounds=[[-38, 145], [-37, 146]], 
        target_points=[{'lat': -37.5, 'lon': 145.5, 'id': 'MW1', 'name': 'MW1'}],
        legend_label="Test"
    )
    
    # Read back to verify CSS present
    with open(dummy_html, "r", encoding="utf-8") as f:
        content = f.read()
        
    if ".borewell-label {" in content and "border: 1px solid #000000" in content:
        print("SUCCESS: CSS styling injected correctly.")
    else:
        print("FAILURE: CSS styling not found or incorrect.")
        print("Found content snippet:", content[680:750] if len(content)>750 else content)
        
except Exception as e:
    print(f"Error: {e}")
finally:
    # Cleanup
    if os.path.exists(dummy_html):
        os.remove(dummy_html)

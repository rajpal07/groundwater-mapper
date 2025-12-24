import streamlit as st
import utils
import os
import webbrowser

st.set_page_config(layout="wide", page_title="Groundwater Mapper")

st.title("Groundwater Elevation Mapper")
st.markdown("""
Upload your Excel data and KMZ file to generate an interactive groundwater contour map.
""")

# Output path for the generated map - use absolute path
# Output path - use relative path for cloud compatibility
OUTPUT_MAP_PATH = "generated_map.html"

with st.sidebar:
    st.header("Data Upload")
    excel_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx", "xls"])
    kmz_file = st.file_uploader("Upload KMZ File (.kmz)", type=["kmz", "zip"], help="On mobile, you may need to rename .kmz to .zip or select 'All Files' if supported.")
    
    generate_btn = st.button("Generate Map", type="primary")

if generate_btn:
    if not excel_file:
        st.error("Please upload an Excel file.")
    else:
        with st.spinner("Processing data and generating contours..."):
            try:
                st.write("📊 Processing data...")
                
                # 1. Process KMZ first (if provided) to get reference points
                # This helps resolve UTM zone ambiguities using ground truth
                kmz_points = None
                if kmz_file:
                    st.write("📍 Processing KMZ file...")
                    try:
                        kmz_points = utils.extract_kmz_points(kmz_file)
                        st.write(f"✅ KMZ processed: {len(kmz_points)} points found")
                    except Exception as e:
                        st.error(f"Error processing KMZ: {e}")
                        # Continue without KMZ points
                
                # 2. Process Excel using KMZ points as reference
                st.write("📊 Processing Excel file...")
                # Reset file pointer if needed (though Streamlit handles this usually)
                excel_file.seek(0)
                
                # Pass kmz_points as reference_points to help with correct UTM zone detection
                image_base64, image_bounds, target_points, bbox_geojson = utils.process_excel_data(
                    excel_file, 
                    reference_points=kmz_points
                )
                
                st.write(f"✅ Excel processed: {len(target_points)} target points found")
                # st.write(f"📍 Image bounds: {image_bounds}")
                
                st.write("🗺️ Creating map...")
                # Create Map
                m = utils.create_map(image_base64, image_bounds, target_points, kmz_points, bbox_geojson)
                
                # Save map to file
                m.save(OUTPUT_MAP_PATH)
                st.write(f"💾 Map saved")
                
                # Inject controls AFTER saving (this is required for geemap compatibility)
                utils.inject_controls_to_html(OUTPUT_MAP_PATH, image_bounds, target_points, kmz_points)
                st.write("✅ Controls and points injected successfully")
                
                st.success("Map generated successfully!")
                
                # --- Display Map in Streamlit ---
                # Read the HTML file
                with open(OUTPUT_MAP_PATH, 'r', encoding='utf-8') as f:
                    map_html = f.read()

                # Display download button
                st.download_button(
                    label="📥 Download Map (HTML)",
                    data=map_html,
                    file_name="groundwater_map.html",
                    mime="text/html"
                )

                # Embed the map
                st.components.v1.html(map_html, height=800, scrolling=True)
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.exception(e)
                
            except Exception as e:
                st.error(f"An error occurred: {e}")
                st.exception(e)
else:
    st.info("Upload files and click 'Generate Map' to start.")





import streamlit as st
import sys
import os

# Add the current directory to sys.path to ensure 'src' module can be found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import src.geo as geo
import src.data as data
import src.visualization as viz
import src.templates as templates
import os
import pandas as pd
from src.sheet_agent import SheetAgent
import uuid

st.set_page_config(layout="wide", page_title="Groundwater Mapper")

st.title("Groundwater Elevation Mapper")
st.markdown("""
Upload your Excel data and KMZ file to generate an interactive groundwater contour map.
""")

st.page_link("pages/Smart_Excel_Tool.py", label="Go to Smart Excel Tool", icon="📊", use_container_width=True)


# Output path
OUTPUT_MAP_PATH = "generated_map.html"

# Initialize Session State for Processed Data
if 'processed_data' not in st.session_state:
    st.session_state['processed_data'] = None
if 'processed_source' not in st.session_state:
    st.session_state['processed_source'] = None
if 'current_job_id' not in st.session_state:
    st.session_state['current_job_id'] = None

# --- Sidebar Definition ---
with st.sidebar:
    st.header("1. Data Upload")
    # API Key Handling
    api_key = None
    if "LLAMA_CLOUD_API_KEY" in st.secrets:
        api_key = st.secrets["LLAMA_CLOUD_API_KEY"]
    else:
        api_key = st.text_input("Llama Cloud API Key", type="password")
    
    excel_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx", "xls"])
    kmz_file = st.file_uploader("Upload KMZ File (.kmz)", type=["kmz", "zip"], help="On mobile, use .zip")
    
    # Validation Warning in Sidebar if Key missing
    if not api_key:
        st.warning("Please provide Llama Cloud API Key in Sidebar or Secrets.")

# --- Main Layout Logic ---
# Check if file was removed (user clicked the cross button)
if not excel_file and st.session_state['processed_data'] is not None:
    st.session_state['processed_data'] = None
    st.session_state['current_job_id'] = None
    st.session_state['success_msg'] = None
    st.session_state['processed_source'] = None
    st.rerun()

if excel_file and api_key:
    st.header("2. AI Processing")
    
    # Checking for file change to reset state
    if st.session_state['processed_source'] != excel_file.name:
        if st.session_state['processed_data'] is not None:
            st.info("New file detected. Resetting previous data.")
            st.session_state['processed_data'] = None
            st.session_state['current_job_id'] = None
            st.session_state['success_msg'] = None
            st.session_state['processed_source'] = None
            st.rerun()

    # Pre-process: Detect Sheets
    try:
        excel_file.seek(0) # IMPORTANT: Reset cursor before reading
        xls = pd.ExcelFile(excel_file)
        sheet_names = xls.sheet_names
        
        selected_sheets = []
        if len(sheet_names) > 1:
            st.info(f"File contains {len(sheet_names)} sheets. Select which ones to analyze:")
            # Default: Select ONLY the first sheet (usually the relevant one)
            st.multiselect("Select Sheets", sheet_names, default=sheet_names[0:1], key="sheet_selector")
        else:
            # One sheet: Auto select without UI
            # We must still populate the widget/variable even if hidden
            # But here we just use logic
            pass # We use sheet_names directly in logic below if selector not used

        # Button in Main Area
        if st.button("Start AI Processing", type="primary"):
            # Get selection
            selected_sheets = st.session_state.get("sheet_selector", sheet_names)
            
            if not selected_sheets:
                st.warning("Please select at least one sheet.")
            else:
                with st.spinner("AI Agent is reading the Excel file..."):
                    try:
                        # Job ID for caching
                        job_id = str(uuid.uuid4())[:8]
                        
                        # Save temp file
                        input_path = f"temp_input_{job_id}.xlsx"
                        output_path = f"processed_{job_id}.xlsx"
                        
                        with open(input_path, "wb") as f:
                            excel_file.seek(0)
                            f.write(excel_file.read())
                        
                        # Init Agent
                        agent = SheetAgent(api_key=api_key)
                        
                        # NEW: Pass selected_sheets
                        result_path = agent.process(input_path, output_path=output_path, selected_sheets=selected_sheets)
                        
                        if result_path and os.path.exists(result_path):
                            # Load into Session State
                            df = pd.read_excel(result_path)
                            st.session_state['processed_data'] = df
                            st.session_state['processed_source'] = excel_file.name
                            st.session_state['current_job_id'] = job_id
                            st.session_state['success_msg'] = f"Processed {len(df)} rows from sheets: {selected_sheets} (Job ID: {job_id})"
                            st.rerun() # Force refresh to show map settings
                        else:
                            st.error("Agent failed to extract data.")
                            
                    except Exception as e:
                        st.error(f"AI Processing failed: {e}")
    except Exception as e:
        st.warning(f"Error reading Excel structure: {e}")

elif not api_key:
    st.info("👈 Please provide your API Key in the sidebar to begin.")
elif not excel_file:
    st.info("👈 Upload an Excel file and click 'Start AI Processing' to begin.")

if st.session_state['processed_data'] is not None:
    df = st.session_state['processed_data']
    
    # Show Success Message if just processed
    if 'success_msg' in st.session_state and st.session_state['success_msg']:
        st.success(st.session_state['success_msg'])
        # Clear it so it doesn't stay forever (actually, maybe keep it?)
        # Let's keep it until new file upload clears session state.

    # Display Job ID explicitly
    if st.session_state.get('current_job_id'):
        st.caption(f"Active Job ID: {st.session_state['current_job_id']}")
    
    # Unified Dropdown
    st.header("3. Map Settings")
    
    # Filter columns to only numeric/interesting ones
    # Exclude metadata
    exclude = ['Well ID', 'Date', 'Time', 'Easting', 'Northing', 'MGA2020 / MGA Zone 54', 'Unknown']
    available_cols = [c for c in df.columns if c not in exclude]
    
    # Default to Groundwater if available
    default_idx = 0
    if "Static Water Level (mAHD)" in available_cols:
        default_idx = available_cols.index("Static Water Level (mAHD)")
    elif "Groundwater Elevation mAHD" in available_cols:
        default_idx = available_cols.index("Groundwater Elevation mAHD")
        
    selected_param = st.selectbox("Select Parameter to Visualize", available_cols, index=default_idx)
    
    # Dynamic Colormap Selector
    colormap_options = ['viridis', 'plasma', 'inferno', 'magma', 'cividis', 'RdYlBu_r', 'Spectral_r', 'coolwarm']
    
    # Smart default: Use 'RdYlBu_r' (Red=High) for pH/Chemicals if selected, else 'viridis' seems fine.
    # Actually, user complained about opacity/darkness. 'plasma' or 'inferno' are very bright.
    # 'RdYlBu_r' is good for divergence. 
    default_cmap_idx = 0
    if "pH" in selected_param or "Salinity" in selected_param or "TDS" in selected_param:
         if 'RdYlBu_r' in colormap_options: default_cmap_idx = colormap_options.index('RdYlBu_r')
         
    selected_cmap = st.selectbox("Color Scheme", colormap_options, index=default_cmap_idx)
    
    if st.button("Generate Map", type="primary"):
        with st.spinner(f"Generating map for {selected_param}..."):
            try:
                # 1. Process KMZ
                kmz_points = None
                if kmz_file:
                    try:
                        kmz_points = geo.extract_kmz_points(kmz_file)
                        st.write(f"✅ KMZ processed: {len(kmz_points)} ref points")
                    except Exception as e:
                        st.warning(f"KMZ Error: {e}")

                # 2. Process Data for Map
                # Pass DataFrame directly to utils
                # OPTIMIZATION: Only generate contours for Groundwater/Elevation
                should_generate_contours = any(x in selected_param for x in ["Water Level", "Elevation", "SWL", "mAHD"])
                
                image_base64, image_bounds, target_points, bbox_geojson = data.process_excel_data(
                    df, 
                    reference_points=kmz_points,
                    value_column=selected_param,
                    generate_contours=should_generate_contours,
                    colormap=selected_cmap
                )
                
                # 3. Create Map
                m = viz.create_map(
                    image_base64, 
                    image_bounds, 
                    target_points, 
                    kmz_points, 
                    bbox_geojson,
                    legend_label=selected_param # Dynamic Legend
                )
                
                # Save & Inject
                # Use a unique filename to prevent caching issues
                unique_id = str(uuid.uuid4())[:8]
                OUTPUT_MAP_PATH_UNIQUE = f"generated_map_{unique_id}.html"
                
                m.save(OUTPUT_MAP_PATH_UNIQUE)
                # Default Project Details (Configurable)
                project_details = {
                    "attachment_title": "Attachment 1, Figure 1 – Site Location Plan",
                    "general_notes": "The aerial map is provided for illustrative purpose and may not reflect current site conditions.\\nBoundaries, dimensions and area shown on this plan are approximate only and subject to survey.",
                    "drawn_by": "LC",
                    "project": "BENDIGO LIVESTOCK\\nEXCHANGE - WALLENJOE ROAD\\nHUNTLY VICTORIA",
                    "address": "11 MATCHETT DRIVE STRATHDALE, VICTORIA, 3550.\\nPH: (03) 5406 0522 admin@edwardsenvironmental.com.au",
                    "drawing_title": "SITE MAP",
                    "authorised_by": "DE",
                    "date": "24-02-2023",
                    "client": "CITY OF GREATER BENDIGO",
                    "job_no": "#773-01"
                }
                
                templates.inject_controls_to_html(OUTPUT_MAP_PATH_UNIQUE, image_bounds, target_points, kmz_points, legend_label=selected_param, colormap=selected_cmap, project_details=project_details)
                
                # Render
                with open(OUTPUT_MAP_PATH_UNIQUE, 'r', encoding='utf-8') as f:
                    map_html = f.read()
                    
                st.download_button("📥 Download Map", map_html, f"groundwater_map_{selected_param}.html", "text/html")
                
                # Append unique ID to HTML to satisfy Streamlit's diffing (Forces refresh as content changed)
                map_html_with_id = map_html + f"\n<!-- Job ID: {unique_id} -->"
                
                # Render (removed key arg which caused error)
                st.components.v1.html(map_html_with_id, height=800, scrolling=True)
                
                # Clean up (Optional, but good practice to avoid clutter)
                # try:
                #    os.remove(OUTPUT_MAP_PATH_UNIQUE)
                # except:
                #    pass
                
            except Exception as e:
                st.error(f"Map Generation Error: {e}")







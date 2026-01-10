import streamlit as st
import pandas as pd
import sys
import os

# Add project root to path to import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import from the verification script
verification_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'arrow_verification'))
if verification_path not in sys.path:
    sys.path.append(verification_path)

try:
    import verify_with_epa_site as verifier
except ImportError as e:
    # This might happen if relative imports fail, try absolute
    try:
        from arrow_verification import verify_with_epa_site as verifier
    except Exception as e2:
        st.error(f"Failed to import verification logic: {e}, {e2}")
        st.stop()

def render():
    st.header("🧭 Groundwater Arrow Verification")
    st.markdown("""
    This tool uses **AI to automatically process your Excel file** and verify the Groundwater Flow Direction arrow calculation 
    against the official [EPA On-site Method](https://www3.epa.gov/ceampubl/learn2model/part-two/onsite/gradient4plus-ns.html).
    """)

    # API Key Handling
    api_key = None
    if "LLAMA_CLOUD_API_KEY" in st.secrets:
        api_key = st.secrets["LLAMA_CLOUD_API_KEY"]
    else:
        api_key = st.text_input("Llama Cloud API Key", type="password", key="verify_api_key")
    
    if not api_key:
        st.warning("👈 Please provide Llama Cloud API Key to use AI processing.")
        return

    # 1. File Upload
    uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx", "xls"], key="verify_uploader")

    # Initialize session state for verification
    if 'verify_processed_data' not in st.session_state:
        st.session_state['verify_processed_data'] = None
    if 'verify_processed_source' not in st.session_state:
        st.session_state['verify_processed_source'] = None

    # Check if file was removed
    if not uploaded_file and st.session_state['verify_processed_data'] is not None:
        st.session_state['verify_processed_data'] = None
        st.session_state['verify_processed_source'] = None
        st.rerun()

    if uploaded_file:
        # Check for file change
        if st.session_state['verify_processed_source'] != uploaded_file.name:
            if st.session_state['verify_processed_data'] is not None:
                st.info("New file detected. Resetting previous data.")
                st.session_state['verify_processed_data'] = None
                st.session_state['verify_processed_source'] = None
                st.rerun()

        # Detect sheets
        try:
            uploaded_file.seek(0)
            xls = pd.ExcelFile(uploaded_file)
            sheet_names = xls.sheet_names
            
            selected_sheets = []
            if len(sheet_names) > 1:
                st.info(f"File contains {len(sheet_names)} sheets. Select which ones to analyze:")
                st.multiselect("Select Sheets", sheet_names, default=sheet_names[0:1], key="verify_sheet_selector")
            
            # AI Processing Button
            if st.button("🤖 Start AI Processing", type="primary", key="verify_ai_btn"):
                selected_sheets = st.session_state.get("verify_sheet_selector", sheet_names)
                
                if not selected_sheets:
                    st.warning("Please select at least one sheet.")
                else:
                    with st.spinner("AI Agent is reading the Excel file..."):
                        try:
                            import uuid
                            from src.sheet_agent import SheetAgent
                            
                            # Job ID for caching
                            job_id = str(uuid.uuid4())[:8]
                            
                            # Save temp file
                            input_path = f"temp_verify_{job_id}.xlsx"
                            output_path = f"processed_verify_{job_id}.xlsx"
                            
                            with open(input_path, "wb") as f:
                                uploaded_file.seek(0)
                                f.write(uploaded_file.read())
                            
                            # Init Agent
                            agent = SheetAgent(api_key=api_key)
                            
                            # Process
                            result_path = agent.process(input_path, output_path=output_path, selected_sheets=selected_sheets)
                            
                            if result_path and os.path.exists(result_path):
                                # Load into Session State
                                df = pd.read_excel(result_path)
                                st.session_state['verify_processed_data'] = df
                                st.session_state['verify_processed_source'] = uploaded_file.name
                                st.success(f"✅ AI Processing Complete! Extracted {len(df)} rows.")
                                st.rerun()
                            else:
                                st.error("Agent failed to extract data.")
                                
                            # Cleanup temp files
                            try:
                                os.remove(input_path)
                                if os.path.exists(output_path):
                                    os.remove(output_path)
                            except:
                                pass
                                
                        except Exception as e:
                            st.error(f"AI Processing failed: {e}")
                            import traceback
                            st.code(traceback.format_exc())
        except Exception as e:
            st.warning(f"Error reading Excel structure: {e}")
    
    # Display processed data and verification interface
    if st.session_state['verify_processed_data'] is not None:
        df = st.session_state['verify_processed_data']
        
        # Post-process: Normalize column names
        # The AI might extract elevation with different names, standardize them
        elevation_variations = [
            'Static Water Level (mAHD)',
            'Static Water Level',
            'SWL (mAHD)',
            'SWL',
            'Corrected Level (mAHD)',
            'Corrected Level',
            'Water Level (mAHD)',
            'GW Elevation'
        ]
        
        if 'Groundwater Elevation mAHD' not in df.columns:
            # Use substring matching to handle sheet-suffixed columns like "Static Water Level (mAHD) (Sheet1)"
            found_col = None
            for var in elevation_variations:
                # Find any column that starts with this variation
                matching_cols = [col for col in df.columns if col.startswith(var)]
                if matching_cols:
                    found_col = matching_cols[0]  # Take the first match
                    st.toast(f"✅ Found '{found_col}' - renaming to 'Groundwater Elevation mAHD'", icon="🔄")
                    df = df.rename(columns={found_col: 'Groundwater Elevation mAHD'})
                    st.session_state['verify_processed_data'] = df  # Update session state
                    st.rerun()  # Force refresh to show updated data
                    break
        
        st.success(f"📊 Data loaded: {len(df)} wells found")
        
        # Show preview
        with st.expander("Preview Processed Data"):
            st.dataframe(df.head(10))
        
        # Check for required columns - accept either coordinate system
        has_well_id = 'Well ID' in df.columns
        has_elevation = 'Groundwater Elevation mAHD' in df.columns
        has_utm = 'Easting' in df.columns and 'Northing' in df.columns
        has_latlon = 'Latitude' in df.columns and 'Longitude' in df.columns
        
        missing_issues = []
        if not has_well_id:
            missing_issues.append("Well ID")
        if not has_elevation:
            missing_issues.append("Groundwater Elevation mAHD")
        if not has_utm and not has_latlon:
            missing_issues.append("Coordinates (need either Easting & Northing OR Latitude & Longitude)")
        
        if missing_issues:
            st.error(f"⚠️ AI extraction incomplete. Missing: {', '.join(missing_issues)}")
            st.info("The AI should have extracted these columns. Please check your Excel file format.")
            st.write("**Available columns:**", ", ".join(df.columns.tolist()))
        else:
            # If we have Lat/Lon but not UTM, convert
            if has_latlon and not has_utm:
                st.info("Converting Latitude/Longitude to Easting/Northing (UTM)...")
                try:
                    from pyproj import Transformer
                    
                    # Determine UTM zone from first valid coordinate
                    sample_lon = df['Longitude'].dropna().iloc[0]
                    utm_zone = int((sample_lon + 180) / 6) + 1
                    
                    # Create transformer (WGS84 to UTM)
                    # Assuming southern hemisphere (Australia) - use negative for south
                    transformer = Transformer.from_crs(
                        "EPSG:4326",  # WGS84
                        f"EPSG:326{utm_zone:02d}" if df['Latitude'].dropna().iloc[0] > 0 else f"EPSG:327{utm_zone:02d}",  # UTM
                        always_xy=True
                    )
                    
                    # Convert coordinates
                    eastings = []
                    northings = []
                    
                    for idx, row in df.iterrows():
                        if pd.notna(row['Latitude']) and pd.notna(row['Longitude']):
                            easting, northing = transformer.transform(row['Longitude'], row['Latitude'])
                            eastings.append(easting)
                            northings.append(northing)
                        else:
                            eastings.append(None)
                            northings.append(None)
                    
                    df['Easting'] = eastings
                    df['Northing'] = northings
                    st.session_state['verify_processed_data'] = df  # Update session state
                    
                    st.success(f"✅ Converted to UTM Zone {utm_zone}")
                    
                except ImportError:
                    st.error("pyproj library required for coordinate conversion. Please install: pip install pyproj")
                    st.stop()
                except Exception as e:
                    st.error(f"Coordinate conversion failed: {e}")
                    st.stop()
            # 2. Well Selection
            all_wells = df['Well ID'].unique().tolist()
            selected_wells = st.multiselect(
                "Select exactly 3 wells for verification:",
                options=all_wells,
                max_selections=3,
                key="verify_multiselect"
            )
            
            if len(selected_wells) == 3:
                st.info(f"✓ Ready to verify: {', '.join(selected_wells)}")
                
                # 3. Run Verification
                if st.button("🚀 Run Verification", type="primary", key="verify_btn"):
                    
                    # Filter data
                    subset = df[df['Well ID'].isin(selected_wells)].copy()
                    
                    # Prepare points data structure
                    points = []
                    for _, row in subset.iterrows():
                        points.append({
                            'name': row['Well ID'],
                            'x': row['Easting'],
                            'y': row['Northing'],
                            'h': row['Groundwater Elevation mAHD']
                        })
                    
                    with st.status("Performing Verification...", expanded=True) as status:
                        # Local Calculation
                        st.write("📐 Performing local 3-point calculation...")
                        local_az, u_vec, v_vec = verifier.calculate_exact_local(points)
                        st.write(f"✅ Local Result: **{local_az:.2f}°**")
                        
                        # Web Verification
                        st.write("🌐 Connecting to EPA website (automating form)...")
                        epa_result = None
                        try:
                            epa_result = verifier.get_epa_web_result(points, headless=True)
                            if epa_result is not None:
                                web_az = epa_result['azimuth']
                                st.write(f"✅ EPA Website Result: **{web_az:.2f}°**")
                            else:
                                web_az = None
                                st.error("❌ Failed to get result from EPA website.")
                        except Exception as e:
                            web_az = None
                            st.error(f"⚠️ EPA automation unavailable: {e}")
                            st.info("💡 **Note:** EPA automation works on Streamlit Cloud deployment. Local calculation is still accurate!")
                            status.update(label="Verification Completed with Warning", state="error", expanded=True)
                        else:
                            if web_az is None:
                                status.update(label="Verification Failed (EPA Site Error)", state="error", expanded=True)
                            else:
                                status.update(label="Verification Complete!", state="complete", expanded=False)
                    
                    # --- Display Screenshots (Always Visible) ---
                    if epa_result is not None and 'screenshot_form' in epa_result:
                        st.divider()
                        st.subheader("📸 EPA Automation Evidence")
                        col1, col2 = st.columns(2)
                        with col1:
                            st.image(epa_result['screenshot_form'], caption="1. Form Filled Automatically", use_container_width=True)
                        with col2:
                            st.image(epa_result['screenshot_result'], caption="2. EPA Calculation Results", use_container_width=True)

                    # Generate Report HTML
                    html_report = verifier.generate_html_report(
                        points, local_az, web_az, u_vec, v_vec, return_html_string=True
                    )
                    
                    # Display Report
                    st.divider()
                    st.subheader("📋 Verification Report")
                    st.components.v1.html(html_report, height=800, scrolling=True)
                    
            elif len(selected_wells) > 0:
                st.warning(f"Please select exactly 3 wells (currently {len(selected_wells)}).")

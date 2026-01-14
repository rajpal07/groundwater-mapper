import json
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

def get_colormap_info(cmap_name):
    """
    Returns hex codes and descriptive labels for a given colormap.
    Returns: (low_hex, mid_hex, high_hex, high_label_desc, low_label_desc)
    """
    try:
        cmap = plt.get_cmap(cmap_name)
    except:
        cmap = plt.get_cmap('viridis')
        
    # Get colors at 0.0 (Low), 0.5 (Mid), 1.0 (High)
    low_rgb = cmap(0.0)[:3]
    mid_rgb = cmap(0.5)[:3]
    high_rgb = cmap(1.0)[:3]
    
    low_hex = mcolors.to_hex(low_rgb)
    mid_hex = mcolors.to_hex(mid_rgb)
    high_hex = mcolors.to_hex(high_rgb)
    
    # Heuristic labels for common maps users might pick
    # This helps the "High (Yellow)" text be accurate
    labels = {
        'viridis': ('Yellow', 'Purple'),
        'plasma': ('Yellow', 'Blue'),
        'inferno': ('Yellow', 'Black'),
        'magma': ('Light Pink', 'Black'),
        'cividis': ('Yellow', 'Blue'),
        'RdYlBu': ('Blue', 'Red'), # Note: Matplotlib RdYlBu has Red at 0 (low) and Blue at 1 (high)? No, Red is Low index? Wait.
                                     # RdYlBu: Red (0) -> Yellow -> Blue (1). IF used as is.
                                     # Often used as '_r' for Red=High.
        'RdYlBu_r': ('Red', 'Blue'), # Red (1) -> Blue (0)
        'Spectral': ('Red', 'Purple'), # 0=Red, 1=Purple/Blue? Spectral is Red->Yellow->Blue/Purple
        'Spectral_r': ('Red', 'Blue'), 
        'coolwarm': ('Red', 'Blue'),
        'bwr': ('Red', 'Blue'),
        'seismic': ('Red', 'Blue')
    }
    
    # Generic fallback
    high_desc, low_desc = labels.get(cmap_name, ('High Color', 'Low Color'))
    
    # Adjust for inverted maps automatically-ish if possible, otherwise rely on manual list
    if cmap_name.endswith('_r') and cmap_name not in labels:
         # simple swap approximation
         base = cmap_name[:-2]
         if base in labels:
             low_desc, high_desc = labels[base]
             
    return low_hex, mid_hex, high_hex, high_desc, low_desc

def inject_controls_to_html(html_file, image_bounds, target_points, kmz_points=None, legend_label="Elevation", colormap="viridis", project_details=None, min_val=None, max_val=None):
    """
    Injects JavaScript into HTML. Now supports dynamic legend label.
    """
    # Shorten label for legend if too long
    legend_label_short = legend_label
    if len(legend_label) > 15:
        # e.g. "Nitrate as N" -> "Nitrate..." if extremely long, but "Nitrate as N" is fine.
        # "Groundwater Elevation mAHD" -> "GW Elev..."
        if "Elevation" in legend_label: legend_label_short = "Elevation"
        else: legend_label_short = legend_label.split(' ')[0]

    # Get dynamic colors for legend
    low_hex, mid_hex, high_hex, high_desc, low_desc = get_colormap_info(colormap)

    with open(html_file, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Calculate initial center from target points
    if target_points:
        center_lat = sum(p['lat'] for p in target_points) / len(target_points)
        center_lon = sum(p['lon'] for p in target_points) / len(target_points)
        initial_center = [center_lat, center_lon]
    else:
        initial_center = [0, 0]

    # Default Project Details
    if project_details is None:
        project_details = {}
    
    pd_safe = {
        "attachment_title": project_details.get("attachment_title", "Attachment 1, Figure 1 – Site Location Plan"),
        "general_notes": project_details.get("general_notes", "General Notes:"),
        "drawn_by": project_details.get("drawn_by", "LC"),
        "project": project_details.get("project", "Project Project"), # Placeholder
        "address": project_details.get("address", "Address Location"),
        "drawing_title": project_details.get("drawing_title", "SITE MAP"),
        "authorised_by": project_details.get("authorised_by", "Authorised By"),
        "date": project_details.get("date", "24-02-2023"),
        "client": project_details.get("client", "Client Name"),
        "job_no": project_details.get("job_no", "#773")
    }

    target_points_json = json.dumps(target_points)
    kmz_points_json = json.dumps([{"lat": p.y, "lon": p.x} for p in kmz_points] if kmz_points else [])
    image_bounds_json = json.dumps(image_bounds)
    initial_center_json = json.dumps(initial_center)

    # Format min/max for display if provided
    min_str = f"{min_val:.2f}" if isinstance(min_val, (int, float)) else "Low"
    max_str = f"{max_val:.2f}" if isinstance(max_val, (int, float)) else "High"

    controls_html = f"""
<!-- Force Hide Leaflet Controls -->
<style>
/* Hide Zoom Control */
.leaflet-control-zoom {{
    display: none !important;
}}
/* Hide Layer Control */
.leaflet-control-layers {{
    display: none !important;
}}
/* Hide Attribution */
.leaflet-control-attribution {{
    display: none !important;
}}
/* Hide Draw Toolbar if present */
.leaflet-draw {{
    display: none !important;
}}
/* Borewell ID Labels */
/* Borewell ID Labels */
.borewell-label {{
    background: #FFFFFF !important;
    border: 1px solid #000000 !important;
    border-radius: 0px !important;
    padding: 1px 4px !important;
    font-weight: bold !important;
    font-family: Arial, sans-serif !important;
    font-size: 11px !important;
    color: #000000 !important;
    box-shadow: none !important;
}}
</style>

<style>
/* Footer Strip Styles */
#snapshot-footer {{
    display: none; /* Hidden by default, shown during snapshot composite */
    width: 100%;
    background: white;
    border-top: 2px solid #333;
    font-family: Arial, sans-serif;
    color: #333;
    box-sizing: border-box;
    padding: 0;
    margin: 0;
}}

.footer-container {{
    display: grid;
    /* Grid Columns: Notes | Logo | Details */
    grid-template-columns: 2fr 1.2fr 2fr;
    width: 100%;
    height: 120px; /* Fixed height for consistency */
}}

.footer-cell {{
    border-right: 2px solid #333;
    padding: 5px;
    box-sizing: border-box;
    overflow: hidden;
    position: relative;
}}

.footer-cell:last-child {{
    border-right: none;
}}

/* CELL 1: NOTES */
.cell-notes {{
    font-size: 11px;
    padding: 8px;
    display: flex;
    flex-direction: column;
}}

/* CELL 2: LOGO */
.cell-logo {{
    display: flex;
    align-items: center;
    justify-content: center;
    flex-direction: column;
    padding: 2px;
}}

.logo-img {{
    max-width: 95%;
    max-height: 90%;
    object-fit: contain;
}}

/* CELL 3: DETAILS */
.cell-details {{
    display: grid;
    grid-template-columns: 85px 1fr; /* Label Value */
    grid-gap: 2px;
    font-size: 10px;
    align-content: start;
    padding: 6px;
}}

.footer-label {{
    font-weight: bold;
    text-align: right;
    padding-right: 5px;
}}

.footer-value {{
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

/* Revision box style at bottom of details? Or just list items. */

</style>

<!-- html-to-image for snapshot -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/html-to-image/1.11.11/html-to-image.js"></script>

<!-- Compass UI - Realistic and Draggable -->
<!-- Compass UI - Two-Ring Minimalist -->
<div id="compass" style="position:fixed; top:80px; left:10px; z-index:100000 !important; width:80px; height:80px; cursor:move; touch-action: none; -webkit-user-select: none; user-select: none;" title="Drag to reposition | Click to reset rotation">
    <!-- Main Housing (Outer Ring) -->
    <div id="compassInner" style="position:relative; width:100%; height:100%; background:#1a1a1a; border-radius:50%; border:2px solid #555; transition: transform 0.3s ease; box-shadow: 0 5px 15px rgba(0,0,0,0.5);">
        
        <!-- N Label - Positioned in the outer ring area -->
        <div style="position:absolute; top:2px; left:50%; transform:translateX(-50%); color:#fff; font-family: 'Arial', sans-serif; font-weight:bold; font-size:14px; pointer-events:none; text-shadow:0 0 2px rgba(0,0,0,0.8); z-index: 2;">N</div>

        <!-- Inner Circle (Needle Container) -->
        <!-- Inset by 12px on all sides to create the ring effect -->
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); width:65%; height:65%; background:radial-gradient(circle at 30% 30%, #2a2a2a, #000); border-radius:50%; border:1px solid #444; box-shadow: inset 0 2px 5px rgba(0,0,0,0.8);">
            
            <!-- Needle (Centered in Inner Circle) -->
            <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%); width:0; height:0;">
                 <!-- North (Red Tapered) -->
                 <!-- Size tuned to fit in the 65% inner circle (approx 52px diam) -->
                <div style="position:absolute; bottom:0; left:-4px; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-bottom: 20px solid #ff3333; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.4));"></div>
                 <!-- South (Dark Grey Tapered) -->
                <div style="position:absolute; top:0; left:-4px; width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 20px solid #444; filter: drop-shadow(0 2px 2px rgba(0,0,0,0.4));"></div>
            </div>
            
             <!-- Center Pin -->
            <div style="position:absolute; top:50%; left:50%; width:6px; height:6px; transform:translate(-50%, -50%); background:#e0e0e0; border-radius:50%; border:1px solid #000; z-index:10; box-shadow: 0 1px 2px rgba(0,0,0,0.5);"></div>
        </div>
    </div>
</div>

<!-- Controls UI -->
<div id="map-controls" style="position:fixed; top:10px; right:10px; z-index:100000 !important; background:rgba(255,255,255,0.95); padding:10px; border-radius:6px; font-family:Arial,Helvetica,sans-serif; pointer-events:auto; box-shadow: 0 0 5px rgba(0,0,0,0.2);">
  <div style="margin-bottom:10px;">
    <label style="font-size:11px; font-weight:bold; display:block; margin-bottom:3px; color:#333;">Figure Title:</label>
    <input type="text" id="input-attachment-title" value="{pd_safe['attachment_title']}" style="width: 130px; padding:3px; font-size:11px; border:1px solid #ccc; border-radius:3px;" oninput="document.getElementById('footer-attachment-title').innerText = this.value">
  </div>

  <div style="display:flex; flex-direction:column; gap:5px;">
    <button onclick="resetImageBounds()" style="background:#ff6b6b; color:white; border:none; padding:6px 10px; border-radius:4px; cursor:pointer; font-size:12px; font-weight:bold;">🔁 Reset View</button>
    <button id="btn-snapshot" onclick="takeSnapshot()" disabled style="background:#4CAF50; color:white; border:none; padding:6px 10px; border-radius:4px; cursor:not-allowed; opacity:0.6; font-size:12px; font-weight:bold;">⏳ Snapshot</button>
  </div>
</div>

<!-- Legend with Resize Handles -->
<style>
/* Resize handles for legend */
.resize-handle {{
  position: absolute;
  background: rgba(0, 0, 0, 0.1);
  transition: background 0.2s;
}}
.resize-handle:hover {{
  background: rgba(0, 120, 215, 0.5);
}}
/* Corner handles */
.resize-nw {{ top: 0; left: 0; width: 10px; height: 10px; cursor: nw-resize; }}
.resize-ne {{ top: 0; right: 0; width: 10px; height: 10px; cursor: ne-resize; }}
.resize-sw {{ bottom: 0; left: 0; width: 10px; height: 10px; cursor: sw-resize; }}
.resize-se {{ bottom: 0; right: 0; width: 10px; height: 10px; cursor: se-resize; }}
/* Edge handles */
.resize-n {{ top: 0; left: 10px; right: 10px; height: 5px; cursor: n-resize; }}
.resize-s {{ bottom: 0; left: 10px; right: 10px; height: 5px; cursor: s-resize; }}
.resize-w {{ left: 0; top: 10px; bottom: 10px; width: 5px; cursor: w-resize; }}
.resize-e {{ right: 0; top: 10px; bottom: 10px; width: 5px; cursor: e-resize; }}
</style>

<div id="map-legend" style="position:fixed; bottom:10px; right:10px; z-index:100000 !important; background:rgba(255,255,255,0.95); padding:10px; border-radius:6px; font-family:Arial,Helvetica,sans-serif; font-size:12px; box-shadow:0 0 5px rgba(0,0,0,0.2); cursor:move; min-width:150px; min-height:100px; box-sizing:border-box;">
  <!-- Resize Handles -->
  <div class="resize-handle resize-nw"></div>
  <div class="resize-handle resize-ne"></div>
  <div class="resize-handle resize-sw"></div>
  <div class="resize-handle resize-se"></div>
  <div class="resize-handle resize-n"></div>
  <div class="resize-handle resize-s"></div>
  <div class="resize-handle resize-w"></div>
  <div class="resize-handle resize-e"></div>
  
  <div id="legend-content" style="width:100%; height:100%; overflow:auto; box-sizing:border-box; padding-right:5px;">
    <div style="font-weight:bold; margin-bottom:8px; border-bottom:1px solid #ddd; padding-bottom:4px; word-wrap:break-word;">Legend</div>
    
    <!-- Points -->
    <div style="display:flex; align-items:center; margin-bottom:10px; flex-wrap:wrap;">
      <div style="width:12px; height:12px; background:#FF6B35; border-radius:50%; border:2px solid white; margin-right:8px; flex-shrink:0;"></div>
      <span style="word-wrap:break-word; overflow-wrap:break-word;">Monitoring Bore</span>
    </div>

    <!-- Contour Guide -->
    <div style="font-weight:bold; margin-bottom:6px; margin-top:8px; border-top:1px solid #ddd; padding-top:6px; word-wrap:break-word;">How to Read Contour</div>
    
    <!-- Gradient Scale -->
    <div style="margin-top:8px; margin-bottom:8px;">
        <div style="display:flex; justify-content:space-between; font-size:10px; color:#555; margin-bottom:0px;">
            <span>Low</span>
            <span>High</span>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:11px; font-weight:bold; margin-bottom:2px;">
            <span>{min_str}</span>
            <span>{max_str}</span>
        </div>
        <div style="width:100%; height:15px; background:linear-gradient(to right, {low_hex}, {mid_hex}, {high_hex}); border:1px solid #999; border-radius:3px;"></div>
        <div style="display:flex; justify-content:space-between; font-size:9px; color:#555; margin-top:2px;">
           <span>{low_desc}</span>
           <span>{high_desc}</span>
        </div>
        <div style="text-align:center; font-size:10px; margin-top:2px; font-weight:bold; color:#333;">
            {legend_label_short}
        </div>
    </div>
    
    <div style="display:flex; align-items:center; flex-wrap:wrap;">
      <div style="font-size:16px; color:red; font-weight:bold; margin-right:8px; line-height:10px; flex-shrink:0;">&rarr;</div>
      <span style="word-wrap:break-word; overflow-wrap:break-word;">Flow Direction</span>
    </div>
  </div>
</div>
"""

    # Load static logo from assets directory
    import base64
    import os
    
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'cts_logo.png')
    print(f"DEBUG: Looking for logo at: {logo_path}")
    
    logo_html_str = ""
    if os.path.exists(logo_path):
        print("DEBUG: Logo file found!")
        with open(logo_path, 'rb') as f:
            logo_base64 = base64.b64encode(f.read()).decode('utf-8')
        logo_html_str = f'<img src="data:image/png;base64,{logo_base64}" class="logo-img" alt="Project Logo">'
    else:
        print("DEBUG: Logo file NOT found!")
        # Try finding any jpeg in assets as fallback?
        # Listing dir to debug
        assets_dir = os.path.dirname(logo_path)
        if os.path.exists(assets_dir):
            print(f"DEBUG: Assets dir content: {os.listdir(assets_dir)}")
        
        logo_html_str = '<div style="text-align:center; color:#ccc;"><div style="font-size:12px;">(Logo Missing)</div></div>'


    footer_html = f'''
<!-- Force Hide Leaflet Controls -->
<style>
/* ... (Leaflet styles same as before) ... */
<div id="snapshot-footer">
    <div class="footer-container">
        <!-- CELL 1: GENERAL NOTES -->
        <div class="footer-cell cell-notes">
            <div style="font-weight:bold; margin-bottom:4px; text-decoration: underline;">GENERAL NOTES:</div>
            <div>{{pd_safe["general_notes"]}}</div>
             <div style="position: absolute; bottom: 5px; left: 8px; font-size: 10px; color: #555;">
               SOURCE: NEARMAP {{pd_safe["date"]}} <!-- Placeholder source -->
            </div>
        </div>
        
        
        <!-- CELL 2: LOGO -->
        <div class="footer-cell cell-logo">
             {logo_html_str}
        </div>
        
        <!-- CELL 3: DETAILS -->
        <div class="footer-cell cell-details">
            <!-- Row 1 -->
            <div class="footer-label">Client:</div>
            <div class="footer-value"><strong>{{pd_safe["client"]}}</strong></div>
            
            <!-- Row 2 -->
            <div class="footer-label">Project:</div>
            <div class="footer-value">{{pd_safe["project"]}}</div>
            
            <!-- Row 3 -->
            <div class="footer-label">Location:</div>
            <div class="footer-value">{{pd_safe["address"]}}</div>
            
            <!-- Row 4 -->
            <div class="footer-label">Drawing Title:</div>
            <div class="footer-value" style="font-size:11px; font-weight:bold;">{{pd_safe["drawing_title"]}}</div>
            
             <!-- Row 5 (Split grid for Drawn/ProjectNo) -->
             <!-- Making it simple rows for reliability -->
            <div class="footer-label">Drawn:</div>
            <div class="footer-value">{{pd_safe["drawn_by"]}}</div>
            
            <div class="footer-label">Project No:</div>
            <div class="footer-value">{{pd_safe["job_no"]}}</div>
            
            <div class="footer-label">Date:</div>
            <div class="footer-value">{{pd_safe["date"]}}</div>
            
            <div class="footer-label">Figure No:</div>
            <div class="footer-value">1 Rev. A</div>
        </div>
    </div>
</div>
'''

    js_code = f'''
{footer_html}
<!-- Force Hide Leaflet Controls -->
<style>
/* Hide Zoom Control */
.leaflet-control-zoom {{
    display: none !important;
}}
.leaflet-control-layers {{
    display: none !important;
}}
.leaflet-control-attribution {{
    display: none !important;
}}
.leaflet-draw {{
    display: none !important;
}}
.borewell-label {{
    background: #FFFFFF !important;
    border: 1px solid #000000 !important;
    border-radius: 0px !important;
    padding: 1px 4px !important;
    font-weight: bold !important;
    font-family: Arial, sans-serif !important;
    font-size: 11px !important;
    color: #000000 !important;
    box-shadow: none !important;
}}
</style>

<style>
/* Footer Strip Styles (GRID) */
#snapshot-footer {{
    display: none; /* Hidden by default, shown during snapshot composite */
    width: 100%;
    background: white;
    border-top: 2px solid #333;
    font-family: Arial, sans-serif;
    color: #333;
    box-sizing: border-box;
    padding: 0;
    margin: 0;
    border-left: 2px solid #333; /* Outer Frame */
    border-right: 2px solid #333;
    border-bottom: 2px solid #333;
}}

.footer-container {{
    display: grid;
    /* Grid Columns: Notes (2fr) | Logo (1.2fr) | Details (2fr) */
    grid-template-columns: 2fr 1.2fr 2fr;
    width: 100%;
    height: 125px; /* Fixed height matches typical title block */
}}

.footer-cell {{
    border-right: 2px solid #333;
    padding: 5px;
    box-sizing: border-box;
    overflow: hidden;
    position: relative;
    display: flex;
    flex-direction: column;
}}

.footer-cell:last-child {{
    border-right: none;
}}

/* CELL 1: NOTES */
.cell-notes {{
    font-size: 10px;
    padding: 8px;
    line-height: 1.3;
}}

/* CELL 2: LOGO */
.cell-logo {{
    align-items: center;
    justify-content: center;
    padding: 4px;
}}

.logo-img {{
    max-width: 98%;
    max-height: 95%;
    object-fit: contain;
}}

/* CELL 3: DETAILS */
.cell-details {{
    display: grid;
    grid-template-columns: 80px 1fr; /* Label Value */
    grid-gap: 2px 8px; /* row-gap col-gap */
    font-size: 10px;
    align-content: start;
    padding: 6px 10px;
}}

.footer-label {{
    font-weight: bold;
    text-align: right;
}}

.footer-value {{
    text-align: left;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: 'Arial Narrow', Arial, sans-serif;
}}
</style>

<!-- html-to-image for snapshot -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/html-to-image/1.11.11/html-to-image.js"></script>

{controls_html}

<!-- Hidden Footer Template -->
<div id="snapshot-footer">
    <div class="footer-container">
        <!-- CELL 1: GENERAL NOTES -->
        <div class="footer-cell cell-notes">
            <div style="font-weight:bold; margin-bottom:4px; text-decoration: underline; font-size: 11px;">GENERAL NOTES:</div>
            <div style="white-space: pre-wrap;">{{pd_safe['general_notes']}}</div>
            
             <div style="margin-top: auto; font-weight: bold; font-size: 11px;">
               SOURCE: NEARMAP {{pd_safe['date']}}
            </div>
        </div>
        
        <!-- CELL 2: LOGO -->
        <div class="footer-cell cell-logo">
             {logo_html_str}
        </div>
        
        <!-- CELL 3: DETAILS -->
        <div class="footer-cell cell-details">
            <!-- Row 1 -->
            <div class="footer-label">Client:</div>
            <div class="footer-value" style="font-weight:bold;">{{pd_safe['client']}}</div>
            
            <!-- Row 2 -->
            <div class="footer-label">Project:</div>
            <div class="footer-value">{{pd_safe['project']}}</div>
            
            <!-- Row 3 -->
            <div class="footer-label">Location:</div>
            <div class="footer-value">{{pd_safe['address']}}</div>
            
            <!-- Row 4 -->
            <div class="footer-label">Drawing Title:</div>
            <div class="footer-value" style="font-size:12px; font-weight:bold;">{{pd_safe['drawing_title']}}</div>
            
            <!-- Row 5 -->
            <div class="footer-label">Drawn:</div>
            <div class="footer-value">{{pd_safe['drawn_by']}}</div>
            
            <!-- Row 6 -->
            <div class="footer-label">Project No:</div>
            <div class="footer-value">{{pd_safe['job_no']}}</div>
            
            <!-- Row 7 -->
            <div class="footer-label">Date:</div>
            <div class="footer-value">{{pd_safe['date']}}</div>
            
            <!-- Row 8 -->
            <div class="footer-label">Figure No:</div>
            <div class="footer-value" style="font-weight:bold;">1 Rev. A</div>
        </div>
    </div>
</div>




<!-- Debug Status -->
<div id="js-status" style="position:fixed; top:50%; left:50%; transform:translate(-50%, -50%); background:red; color:white; padding:20px; z-index:10000; font-size:24px; font-weight:bold; border: 4px solid white; pointer-events:none; opacity: 0.8;">
  JS: Waiting for Map...
</div>

<script>
(() => {{
  let map = null;
  let overlay = null;
  let originalBounds = null;
  let currentRotation = 0;
  
  const bluePoints = {kmz_points_json};
  const orangePoints = {target_points_json};
  const overlayBounds = {image_bounds_json};
  const initialCenter = {initial_center_json};
  const paramLabel = "{legend_label}";

  // --- Update Compass Rotation ---
  function updateCompass() {{
    const compassInner = document.getElementById('compassInner');
    if (compassInner) {{
      compassInner.style.transform = `rotate(${{-currentRotation}}deg)`;
    }}
  }}

  // --- Generic Draggable Logic ---
  function makeDraggable(element, options = {{}}) {{
    if (!element) return;
    
    let isDragging = false;
    let hasMoved = false;
    let startX, startY, initialLeft, initialTop;
    
    function getEventCoords(e) {{
      if (e.touches && e.touches.length > 0) {{
        return {{ x: e.touches[0].clientX, y: e.touches[0].clientY }};
      }}
      return {{ x: e.clientX, y: e.clientY }};
    }}
    
    function handleStart(e) {{
      // Don't start dragging if clicking on a resize handle
      if (e.target && e.target.classList && e.target.classList.contains('resize-handle')) {{
        return;
      }}
      
      isDragging = true;
      hasMoved = false;
      
      const coords = getEventCoords(e);
      startX = coords.x;
      startY = coords.y;
      
      const rect = element.getBoundingClientRect();
      
      // Calculate offset relative to parent for correct absolute positioning
      const parent = element.offsetParent || document.body;
      const parentRect = parent.getBoundingClientRect();
      
      initialLeft = rect.left - parentRect.left;
      initialTop = rect.top - parentRect.top;
      
      element.style.cursor = 'grabbing';
      
      const m = findMap();
      if (m) m.dragging.disable();
      
      e.preventDefault();
      e.stopPropagation();
    }}
    
    function handleMove(e) {{
      if (!isDragging) return;
      
      const coords = getEventCoords(e);
      const deltaX = coords.x - startX;
      const deltaY = coords.y - startY;
      
      if (Math.abs(deltaX) > 5 || Math.abs(deltaY) > 5) hasMoved = true;
      
      if (hasMoved) {{
        const newLeft = initialLeft + deltaX;
        const newTop = initialTop + deltaY;
        
        element.style.position = 'absolute';
        element.style.left = newLeft + 'px';
        element.style.top = newTop + 'px';
        element.style.bottom = 'auto';
        element.style.right = 'auto';
        
        e.preventDefault();
        e.stopPropagation();
      }}
    }}
    
    function handleEnd(e) {{
      if (isDragging) {{
        isDragging = false;
        element.style.cursor = 'move';
        
        const m = findMap();
        if (m) m.dragging.enable();
        
        if (!hasMoved && options.onClick) {{
          options.onClick(e);
        }}
        
        if (hasMoved) {{
          e.preventDefault();
          e.stopPropagation();
        }}
      }}
    }}
    
    element.addEventListener('mousedown', handleStart);
    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleEnd);
    
    element.addEventListener('touchstart', handleStart, {{ passive: false }});
    document.addEventListener('touchmove', handleMove, {{ passive: false }});
    document.addEventListener('touchend', handleEnd);
    document.addEventListener('touchcancel', handleEnd);
  }}

  // --- Generic Resizable Logic with Proportional Scaling ---
  function makeResizable(element) {{
    if (!element) return;
    
    const handles = element.querySelectorAll('.resize-handle');
    if (!handles || handles.length === 0) return;
    
    let isResizing = false;
    let currentHandle = null;
    let startX, startY, startWidth, startHeight, startLeft, startTop;
    let aspectRatio = 1;
    
    function getEventCoords(e) {{
      if (e.touches && e.touches.length > 0) {{
        return {{ x: e.touches[0].clientX, y: e.touches[0].clientY }};
      }}
      return {{ x: e.clientX, y: e.clientY }};
    }}
    
    function handleResizeStart(e, handle) {{
      isResizing = true;
      currentHandle = handle;
      
      const coords = getEventCoords(e);
      startX = coords.x;
      startY = coords.y;
      
      const rect = element.getBoundingClientRect();
      startWidth = rect.width;
      startHeight = rect.height;
      startLeft = rect.left;
      startTop = rect.top;
      
      // Calculate aspect ratio for proportional resizing
      aspectRatio = startWidth / startHeight;
      
      const m = findMap();
      if (m) m.dragging.disable();
      
      e.preventDefault();
      e.stopPropagation();
    }}
    
    function handleResizeMove(e) {{
      if (!isResizing || !currentHandle) return;
      
      const coords = getEventCoords(e);
      const deltaX = coords.x - startX;
      const deltaY = coords.y - startY;
      
      let newWidth = startWidth;
      let newHeight = startHeight;
      let newLeft = startLeft;
      let newTop = startTop;
      
      const handleClass = currentHandle.className;
      
      // Calculate new dimensions based on handle type
      if (handleClass.includes('resize-se')) {{
        // Southeast corner - expand from top-left
        const maxDelta = Math.max(deltaX, deltaY / aspectRatio);
        newWidth = startWidth + maxDelta;
        newHeight = newWidth / aspectRatio;
      }} else if (handleClass.includes('resize-sw')) {{
        // Southwest corner - expand from top-right
        const maxDelta = Math.max(-deltaX, deltaY / aspectRatio);
        newWidth = startWidth + maxDelta;
        newHeight = newWidth / aspectRatio;
        newLeft = startLeft - maxDelta;
      }} else if (handleClass.includes('resize-ne')) {{
        // Northeast corner - expand from bottom-left
        const maxDelta = Math.max(deltaX, -deltaY / aspectRatio);
        newWidth = startWidth + maxDelta;
        newHeight = newWidth / aspectRatio;
        newTop = startTop - (newHeight - startHeight);
      }} else if (handleClass.includes('resize-nw')) {{
        // Northwest corner - expand from bottom-right
        const maxDelta = Math.max(-deltaX, -deltaY / aspectRatio);
        newWidth = startWidth + maxDelta;
        newHeight = newWidth / aspectRatio;
        newLeft = startLeft - maxDelta;
        newTop = startTop - (newHeight - startHeight);
      }} else if (handleClass.includes('resize-e')) {{
        // East edge
        newWidth = startWidth + deltaX;
        newHeight = newWidth / aspectRatio;
        newTop = startTop - (newHeight - startHeight) / 2;
      }} else if (handleClass.includes('resize-w')) {{
        // West edge
        newWidth = startWidth - deltaX;
        newHeight = newWidth / aspectRatio;
        newLeft = startLeft + deltaX;
        newTop = startTop - (newHeight - startHeight) / 2;
      }} else if (handleClass.includes('resize-s')) {{
        // South edge
        newHeight = startHeight + deltaY;
        newWidth = newHeight * aspectRatio;
        newLeft = startLeft - (newWidth - startWidth) / 2;
      }} else if (handleClass.includes('resize-n')) {{
        // North edge
        newHeight = startHeight - deltaY;
        newWidth = newHeight * aspectRatio;
        newLeft = startLeft - (newWidth - startWidth) / 2;
        newTop = startTop + deltaY;
      }}
      
      // Apply minimum size constraints
      const minWidth = parseFloat(element.style.minWidth) || 150;
      const minHeight = parseFloat(element.style.minHeight) || 100;
      
      if (newWidth >= minWidth && newHeight >= minHeight) {{
        element.style.width = newWidth + 'px';
        element.style.height = newHeight + 'px';
        element.style.position = 'absolute';
        element.style.left = newLeft + 'px';
        element.style.top = newTop + 'px';
        element.style.bottom = 'auto';
        element.style.right = 'auto';
      }}
      
      e.preventDefault();
      e.stopPropagation();
    }}
    
    function handleResizeEnd(e) {{
      if (isResizing) {{
        isResizing = false;
        currentHandle = null;
        
        const m = findMap();
        if (m) m.dragging.enable();
        
        e.preventDefault();
        e.stopPropagation();
      }}
    }}
    
    // Attach event listeners to all resize handles
    handles.forEach(handle => {{
      handle.addEventListener('mousedown', (e) => handleResizeStart(e, handle));
      handle.addEventListener('touchstart', (e) => handleResizeStart(e, handle), {{ passive: false }});
    }});
    
    document.addEventListener('mousemove', handleResizeMove);
    document.addEventListener('mouseup', handleResizeEnd);
    document.addEventListener('touchmove', handleResizeMove, {{ passive: false }});
    document.addEventListener('touchend', handleResizeEnd);
    document.addEventListener('touchcancel', handleResizeEnd);
  }}

  // Initialize Compass Dragging
  makeDraggable(document.getElementById('compass'), {{
      onClick: function() {{
          currentRotation = 0;
          resetImageBounds();
      }}
  }});

  // --- Helper: find the Leaflet Map instance on the page ---
  function findMap() {{
    if (map && map instanceof L.Map) return map;
    for (const k in window) {{
      try {{
        const v = window[k];
        if (v && v instanceof L.Map) {{ map = v; break; }}
      }} catch(e) {{ /* ignore cross-origin / exotic props */ }}
    }}
    return map;
  }}

  // --- Helper: find the first ImageOverlay (or choose filter here) ---
  function findOverlay() {{
    if (overlay && overlay instanceof L.ImageOverlay) return overlay;
    const m = findMap();
    if (!m) return null;
    let found = null;
    m.eachLayer(layer => {{
      if (!found && layer instanceof L.ImageOverlay) found = layer;
    }});
    if (found) overlay = found;
    return overlay;
  }}

  // --- Apply rotation to a given img element by composing with Leaflet's transform ---
  function applyRotationTo(img) {{
    if (!img) return;
    try {{
      if (img.__setting) return;
      img.__setting = true;

      img.style.transformOrigin = "center center";

      let inline = (img.style && img.style.transform) ? img.style.transform : '';
      inline = inline.replace(/rotate\\([^)]*\\)/g, '').trim();

      if (!inline) {{
        const cs = window.getComputedStyle(img);
        if (cs) inline = (cs.transform && cs.transform !== 'none') ? cs.transform : '';
      }}

      const rotationStr = ` rotate(${{currentRotation}}deg)`;
      img.style.transform = (inline ? inline + rotationStr : rotationStr);

      img.dataset.__desiredRotation = String(currentRotation);

      requestAnimationFrame(() => {{ img.__setting = false; }});
    }} catch (e) {{
      console.warn("applyRotationTo error:", e);
      if (img) img.__setting = false;
    }}
  }}

  // --- Attach observers to handle style changes and element replacement ---
  function attachImageObservers(img) {{
    if (!img) return;

    if (img.__obsAttached) {{
      applyRotationTo(img);
      return;
    }}
    img.__obsAttached = true;

    const attrObs = new MutationObserver(mutations => {{
      for (const m of mutations) {{
        if (m.type === 'attributes' && m.attributeName === 'style') {{
          if (img.__setting) continue;
          applyRotationTo(img);
        }}
        if (m.type === 'attributes' && m.attributeName === 'src') {{
          applyRotationTo(img);
        }}
      }}
    }});
    attrObs.observe(img, {{ attributes: true, attributeFilter: ['style', 'src'] }});
    img.__attrObserver = attrObs;

    const parent = img.parentNode;
    if (parent && !parent.__childObserver) {{
      const childObs = new MutationObserver(changes => {{
        for (const c of changes) {{
          if (c.type === 'childList') {{
            for (const node of c.addedNodes) {{
              if (node && node.tagName && node.tagName.toLowerCase() === 'img') {{
                attachImageObservers(node);
                applyRotationTo(node);
              }}
            }}
          }}
        }}
      }});
      childObs.observe(parent, {{ childList: true }});
      parent.__childObserver = childObs;
    }}

    applyRotationTo(img);
  }}

  // --- Snapshot Button State ---
  function enableSnapshotBtn() {{
      const btn = document.getElementById('btn-snapshot');
      if (btn) {{
          btn.disabled = false;
          btn.innerHTML = '📸 Snapshot';
          btn.style.cursor = 'pointer';
          btn.style.opacity = '1.0';
      }}
  }}

  // --- Reapply to current overlay image (safe wrapper) ---
  function reapplyToOverlayImage() {{
    const ov = findOverlay();
    if (!ov) return;
    const img = (typeof ov.getElement === 'function') ? ov.getElement() : ov._image || null;
    if (img) attachImageObservers(img);
  }}

  // --- Controls (move / scale / rotate / reset) ---
  window.moveImage = function(direction) {{
    const ov = findOverlay(); if (!ov) return;
    const moveScale = parseFloat(document.getElementById('moveScale').value) || 0.1;
    const b = ov.getBounds();
    const sw = b.getSouthWest(), ne = b.getNorthEast();
    const latSpan = ne.lat - sw.lat, lngSpan = ne.lng - sw.lng;
    let dLat = 0, dLng = 0;
    if (direction === 'up') dLat =  latSpan * moveScale;
    if (direction === 'down') dLat = -latSpan * moveScale;
    if (direction === 'left') dLng = -lngSpan * moveScale;
    if (direction === 'right') dLng =  lngSpan * moveScale;
    const newB = L.latLngBounds([sw.lat + dLat, sw.lng + dLng],[ne.lat + dLat, ne.lng + dLng]);
    ov.setBounds(newB);
    requestAnimationFrame(reapplyToOverlayImage);
  }};

  window.scaleImage = function(action) {{
    const ov = findOverlay(); if (!ov) return;
    const scaleAmount = parseFloat(document.getElementById('scaleAmount').value) || 1.1;
    const b = ov.getBounds();
    const sw = b.getSouthWest(), ne = b.getNorthEast();
    const cLat = (sw.lat + ne.lat) / 2, cLng = (sw.lng + ne.lng) / 2;
    const factor = (action === 'expand') ? scaleAmount : (1 / scaleAmount);
    const halfLat = (ne.lat - sw.lat) * factor / 2;
    const halfLng = (ne.lng - sw.lng) * factor / 2;
    const newB = L.latLngBounds([cLat - halfLat, cLng - halfLng],[cLat + halfLat, cLng + halfLng]);
    ov.setBounds(newB);
    requestAnimationFrame(reapplyToOverlayImage);
  }};

  window.rotateImage = function(direction) {{
    const step = parseFloat(document.getElementById('rotationDegrees').value) || 15;
    currentRotation = (currentRotation + (direction === 'left' ? -step : step)) % 360;
    updateCompass();
    reapplyToOverlayImage();
  }};

  window.resetImageBounds = function() {{
    const ov = findOverlay(); if (!ov || !originalBounds) return;
    ov.setBounds(originalBounds);
    currentRotation = 0;
    updateCompass();
    
    // Recenter map and fit to overlay bounds
    const m = findMap();
    if (m) {{
        m.fitBounds(overlayBounds);
    }}
    
    requestAnimationFrame(reapplyToOverlayImage);
  }};
  
  // --- Snapshot Logic ---
  // --- Snapshot Logic ---
  // --- Snapshot Logic ---
  // --- Snapshot Logic ---
  window.takeSnapshot = function() {{
      const m = findMap();
      if (!m) return;
      
      const btn = document.getElementById('btn-snapshot');
      const leafletControls = document.querySelector('.leaflet-control-container');
      const customControls = ['compass', 'map-controls', 'map-legend', 'footer-controls'].map(id => document.getElementById(id)).filter(el => el);
      const footerStrip = document.getElementById('snapshot-footer');
      const hiddenControls = document.getElementById('footer-controls'); // Hide this input box
      
      // Helper: Restore UI
      const restoreUI = () => {{
          if (leafletControls) leafletControls.style.display = 'block';
          
          customControls.forEach(ctrl => {{
              if (ctrl.id !== 'footer-controls') ctrl.style.display = 'block'; 
              else ctrl.style.display = 'block';
          }});
          
          if (btn) {{
            btn.disabled = false;
            btn.innerText = '📸 Snapshot';
            btn.style.opacity = '1';
          }}
          
          // Clean up composition container
          const comp = document.getElementById('composition-container');
          if (comp) comp.remove();
      }};

      // Safety Timeout
      const safetyTimeout = setTimeout(() => {{
          console.warn('Snapshot process timed out (Safety Trigger)');
          alert('Snapshot timed out. Please try again.');
          restoreUI();
      }}, 20000);
      
      if (btn) {{
        btn.disabled = true;
        btn.innerText = 'Capturing...';
        btn.style.opacity = '0.7';
      }}

      // Hide standard Leaflet controls
      if (leafletControls) leafletControls.style.display = 'none';

      // Hide custom controls (excluding compass and legend)
      customControls.forEach(ctrl => {{
          if (ctrl.id !== 'compass' && ctrl.id !== 'map-legend') {{
              ctrl.style.display = 'none';
          }}
      }});
      if (hiddenControls) hiddenControls.style.display = 'none';
      
      const mapContainer = m.getContainer();

      // Detect mobile device
      const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
      
      // Options for html-to-image
      const options = {{
           width: mapContainer.offsetWidth,
           height: mapContainer.offsetHeight,
           useCORS: true,
           backgroundColor: '#ffffff',
           cacheBust: false,
           pixelRatio: isMobile ? 3 : 4,
           filter: (node) => {{
               if (node.tagName === 'IMG') return true; 
               return true;
           }}
       }};

      // Force Map Layout Refresh
      if (m && typeof m.invalidateSize === 'function') {{
          m.invalidateSize();
      }}

      console.log('Starting Composite Snapshot...');

      // PHASE 1: Capture Map Only
      setTimeout(() => {{
          htmlToImage.toPng(mapContainer, options)
             .then((mapDataUrl) => {{
                 console.log('Map Captured. Composing with Footer...');
                 
                 // PHASE 2: Composition
                 // Create a container that exactly matches the map width
                 const container = document.createElement('div');
                 container.id = 'composition-container';
                 container.style.position = 'absolute';
                 container.style.top = '0';
                 container.style.left = '0';
                 container.style.zIndex = '99999';
                 container.style.background = 'white';
                 container.style.width = mapContainer.offsetWidth + 'px';
                 
                 // 1. Map Image
                 const mapImg = document.createElement('img');
                 mapImg.src = mapDataUrl;
                 mapImg.style.width = '100%';
                 mapImg.style.display = 'block';
                 container.appendChild(mapImg);
                 
                 // 2. Footer clone
                 const footerClone = footerStrip.cloneNode(true);
                 footerClone.style.display = 'block'; // Make visible
                 footerClone.id = 'footer-clone';
                 container.appendChild(footerClone);
                 
                 document.body.appendChild(container);
                 
                 // Wait a moment for the DOM to settle with the new image
                 setTimeout(() => {{
                     // Capture the Composite
                     htmlToImage.toPng(container, {{
                         width: container.offsetWidth,
                         // Height is auto
                         useCORS: true,
                         pixelRatio: options.pixelRatio
                     }})
                     .then((finalDataUrl) => {{
                          const link = document.createElement('a');
                          link.download = 'map_snapshot_with_footer.png';
                          link.href = finalDataUrl;
                          link.click();
                          
                          clearTimeout(safetyTimeout);
                          restoreUI();
                     }})
                     .catch((err) => {{
                         console.error('Composite Snapshot failed:', err);
                         alert('Composite Snapshot failed.');
                         clearTimeout(safetyTimeout);
                         restoreUI();
                     }});
                 }}, 500);
                 
             }})
             .catch((err) => {{
                 console.error('Map Snapshot failed:', err);
                 alert('Snapshot failed.');
                 clearTimeout(safetyTimeout);
                 restoreUI();
             }});
          
      }}, 500); 
  }};

  // --- Label Solver (Force Directed) ---
  class LabelSolver {{
    constructor(map) {{
        this.map = map;
        this.nodes = [];
        this.isBusy = false;
        
        // Container for lines (SVG)
        this.svgContainer = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        this.svgContainer.style.position = 'absolute';
        this.svgContainer.style.top = '0';
        this.svgContainer.style.left = '0';
        this.svgContainer.style.width = '100%';
        this.svgContainer.style.height = '100%';
        this.svgContainer.style.pointerEvents = 'none';
        this.svgContainer.style.zIndex = '400'; 
        this.map.getContainer().appendChild(this.svgContainer);
    }}

    add(labelEl, marker) {{
        // Create Halo Line (White Background - Thick)
        const lineBg = document.createElementNS("http://www.w3.org/2000/svg", "line");
        lineBg.setAttribute("stroke", "white");
        lineBg.setAttribute("stroke-width", "4");
        lineBg.setAttribute("stroke-opacity", "0.8");
        lineBg.setAttribute("stroke-linecap", "round");
        this.svgContainer.appendChild(lineBg);

        // Create Main Line (Black/Dark Foreground - Thin)
        const lineFg = document.createElementNS("http://www.w3.org/2000/svg", "line");
        lineFg.setAttribute("stroke", "black");
        lineFg.setAttribute("stroke-width", "1.5");
        lineFg.setAttribute("stroke-opacity", "0.9");
        this.svgContainer.appendChild(lineFg);

        this.nodes.push({{
            label: labelEl,
            marker: marker,
            lineBg: lineBg,
            lineFg: lineFg,
            x: 0,
            y: 0,
            width: 0,
            height: 0,
            fx: 0,
            fy: 0
        }});
    }}
    
    // Main loop
    update() {{
        if (this.isBusy) return;
        this.isBusy = true;
        
        const padding = 5; // Increased padding used in collision
        const force_iterations = 60; // High iterations to solve dense clusters

        // 1. Update targets (where they WANT to be) & Dimensions
        this.nodes.forEach(node => {{
            const pt = this.map.latLngToContainerPoint(node.marker.getLatLng());
            node.targetX = pt.x + 14; 
            node.targetY = pt.y;
            node.anchorX = pt.x;
            node.anchorY = pt.y;

            if (!node.width) {{
                node.width = node.label.offsetWidth;
                node.height = node.label.offsetHeight;
            }}
            
            // Initial reset if way off
            if (!node.x || Math.abs(node.x - node.targetX) > 1000) {{
                node.x = node.targetX;
                node.y = node.targetY;
            }}
        }});

        // 2. Physics Loop
        for (let k = 0; k < force_iterations; k++) {{
            this.nodes.forEach(a => {{
                a.fx = 0;
                a.fy = 0;

                // A. Gravity: Weak Attraction to target (Allows drifting to find space)
                const dx = a.targetX - a.x;
                const dy = a.targetY - a.y;
                a.fx += dx * 0.05; // Weak spring (was 0.3)
                a.fy += dy * 0.05;
                
                // B. Obstacles: Repulsion from ALL Markers (Prevent covering ANY dot)
                const safeR = 12; // Marker radius buffer
                this.nodes.forEach(m => {{
                    const mx = m.anchorX;
                    const my = m.anchorY;

                    // Label 'a' geometry
                    const lx1 = a.x;
                    const lx2 = a.x + a.width;
                    const ly1 = a.y - a.height/2;
                    const ly2 = a.y + a.height/2;
                    
                    // Box collision check
                    if (lx1 < mx + safeR && lx2 > mx - safeR && 
                        ly1 < my + safeR && ly2 > my - safeR) {{
                         
                        // Push away from marker center
                        const cx = a.x + a.width/2;
                        const cy = a.y;
                        let vx = cx - mx;
                        let vy = cy - my;
                        
                        // Jitter if perfectly centered
                        if (Math.abs(vx) < 1 && Math.abs(vy) < 1) {{
                            vx = 10; vy = (Math.random()-0.5)*10;
                        }}
                        
                        const len = Math.sqrt(vx*vx + vy*vy) || 1;
                        const push = 2.0; // Hard push
                        a.fx += (vx/len) * push;
                        a.fy += (vy/len) * push;
                    }}
                }});

                // C. Collision: Repulsion from other Labels
                this.nodes.forEach(b => {{
                    if (a === b) return;
                    
                    const ax1 = a.x, ax2 = a.x + a.width;
                    const ay1 = a.y - a.height/2, ay2 = a.y + a.height/2;
                    
                    const bx1 = b.x, bx2 = b.x + b.width;
                    const by1 = b.y - b.height/2, by2 = b.y + b.height/2;

                    if (ax1 < bx2 + padding && ax2 > bx1 - padding && 
                        ay1 < by2 + padding && ay2 > by1 - padding) {{
                        
                        const acx = a.x + a.width/2;
                        const acy = a.y;
                        const bcx = b.x + b.width/2;
                        const bcy = b.y;
                        
                        let vx = acx - bcx;
                        let vy = acy - bcy;
                        
                        if (Math.abs(vx) < 0.1 && Math.abs(vy) < 0.1) {{
                             vx = (Math.random() - 0.5);
                             vy = (Math.random() - 0.5);
                        }}
                        
                        const dist = Math.sqrt(vx*vx + vy*vy) || 1;
                        const push = 5.0; // Strong push (was 3.0)
                        a.fx += (vx / dist) * push;
                        a.fy += (vy / dist) * push;
                    }}
                }});
            }});

            // Apply forces
            this.nodes.forEach(node => {{
                node.x += node.fx;
                node.y += node.fy;
            }});
        }}

        // 3. Render
        this.nodes.forEach(node => {{
            node.label.style.transform = `translate3d(${{node.x}}px, ${{node.y - node.height/2}}px, 0)`;
            
            // ALWAYS Draw Lines (Universal Halo)
            const distSq = (node.x - node.anchorX)**2 + (node.y - node.anchorY)**2;
            
            if (distSq > 4) {{ 
                // Background (Halo)
                node.lineBg.setAttribute("x1", node.anchorX);
                node.lineBg.setAttribute("y1", node.anchorY);
                node.lineBg.setAttribute("x2", node.x); 
                node.lineBg.setAttribute("y2", node.y); 
                node.lineBg.style.display = 'block';

                // Foreground
                node.lineFg.setAttribute("x1", node.anchorX);
                node.lineFg.setAttribute("y1", node.anchorY);
                node.lineFg.setAttribute("x2", node.x); 
                node.lineFg.setAttribute("y2", node.y);
                node.lineFg.style.display = 'block';
            }} else {{
                node.lineBg.style.display = 'none';
                node.lineFg.style.display = 'none';
            }}
        }});

        this.isBusy = false;
    }}

  }}

  // --- Interactive Dots Logic ---
  let solver = null;

  function initDots() {{
      const m = findMap();
      if (!m) return;
      
      // Init Solver
      if (!solver) solver = new LabelSolver(m);

      // Create Label Container (if not exists)
      let labelLayer = document.getElementById('label-layer');
      if (!labelLayer) {{
          labelLayer = document.createElement('div');
          labelLayer.id = 'label-layer';
          labelLayer.style.position = 'absolute';
          labelLayer.style.top = '0';
          labelLayer.style.left = '0';
          labelLayer.style.pointerEvents = 'none'; // Let clicks pass through to map
          labelLayer.style.zIndex = '450';
          m.getContainer().appendChild(labelLayer);
      }}
      
      // 1. Add KMZ Points (Blue - Fixed/Non-draggable)
      bluePoints.forEach((pt, idx) => {{
          L.circleMarker([pt.lat, pt.lon], {{
              radius: 6,
              color: 'white',
              weight: 2,
              fillColor: '#4A90E2',
              fillOpacity: 1.0,
              fill: true
          }}).addTo(m).bindPopup(`<b>KMZ Point (Fixed)</b><br>Index: ${{idx}}`);
      }});
      
      // 2. Add Excel Points (Orange - Draggable/Moveable) with Borewell IDs
      orangePoints.forEach(pt => {{
          const marker = L.circleMarker([pt.lat, pt.lon], {{
              radius: 6,
              color: 'white',
              weight: 2,
              fillColor: '#FF6B35',
              fillOpacity: 1.0,
              fill: true,
              draggable: true
          }}).addTo(m);
          
          // Extract short ID (e.g., "WB-01" from "WB-01 TOC1")
          const shortId = pt.name ? pt.name.split(' ')[0] : `Point ${{pt.id}}`;
          const fullName = pt.name || 'Excel Point';
          
          // Popup with full details
          const valDisplay = pt.value !== undefined && pt.value !== null ? Number(pt.value).toFixed(2) : 'N/A';
          const popupContent = `<b>${{fullName}}</b><br>ID: ${{pt.id}}<br>Lat: ${{pt.lat.toFixed(6)}}<br>Lon: ${{pt.lon.toFixed(6)}}<br><b>${{paramLabel}}</b>: ${{valDisplay}}`;
          
          marker.bindPopup(popupContent);
          
          // --- NEW: Dynamic Label (Div) instead of Tooltip ---
          const labelEl = document.createElement('div');
          labelEl.className = 'borewell-label'; // Reuse existing style
          labelEl.innerText = shortId;
          labelEl.style.position = 'absolute';
          labelEl.style.whiteSpace = 'nowrap';
          labelEl.style.willChange = 'transform';
          // Ensure styles are set for calculation
          labelEl.style.background = '#FFFFFF';
          labelEl.style.border = '1px solid #000000';
          labelEl.style.borderLeft = '5px solid #FF6B35'; // Visual Link to Orange Marker
          labelEl.style.padding = '1px 4px';
          labelEl.style.fontWeight = 'bold';
          labelEl.style.fontSize = '11px';
          labelEl.style.fontFamily = 'Arial, sans-serif';
          labelEl.style.top = '0';
          labelEl.style.left = '0';
          
          labelLayer.appendChild(labelEl);
          
          // Add to solver
          solver.add(labelEl, marker);
          
          // Update popup on drag
          marker.on('drag', function(e) {{
              const latlng = e.target.getLatLng();
              marker.setPopupContent(`<b>${{fullName}} (Dragging...)</b><br>ID: ${{pt.id}}<br>Lat: ${{latlng.lat.toFixed(6)}}<br>Lon: ${{latlng.lng.toFixed(6)}}<br><b>${{paramLabel}}</b>: ${{valDisplay}}`);
              // Trigger solver update
              requestAnimationFrame(() => solver.update());
          }});
          
          marker.on('dragend', function(e) {{
              const latlng = e.target.getLatLng();
              marker.setPopupContent(`<b>${{fullName}}</b><br>ID: ${{pt.id}}<br>Lat: ${{latlng.lat.toFixed(6)}}<br>Lon: ${{latlng.lng.toFixed(6)}}<br><b>${{paramLabel}}</b>: ${{valDisplay}}`);
              console.log(`Borewell ${{shortId}} moved to: [${{latlng.lat}}, ${{latlng.lng}}]`);
              solver.update();
          }});
      }});
      
      // Hook up Solver to Map Events
      m.on('zoom', () => requestAnimationFrame(() => solver.update()));
      m.on('zoomend', () => requestAnimationFrame(() => solver.update()));
      m.on('move', () => requestAnimationFrame(() => solver.update()));
      m.on('moveend', () => requestAnimationFrame(() => solver.update()));
      
      // Initial Solve
      setTimeout(() => {{
          // Run a few times to settle
          for(let i=0; i<5; i++) solver.update();
      }}, 500);
  }}

  // --- Initialization: find overlay + hooks to reapply on map/overlay events ---
  function init() {{
    const m = findMap();
    if (!m) {{
        setTimeout(init, 200); // Retry if map not ready
        return;
    }}

    // Initialize Dots
    initDots();

    // Move Controls into Map Container for Snapshot
    const compass = document.getElementById('compass');
    const legend = document.getElementById('map-legend');
    if (m) {{
        const container = m.getContainer();
        if (compass && container) container.appendChild(compass);
        if (legend && container) {{
            container.appendChild(legend);
            makeDraggable(legend);
            makeResizable(legend);
        }}
        
        // Add dynamic scale control (like Google Maps)
        const scaleCtrl = L.control.scale({{
            position: 'bottomleft', // Initial, we move it later
            metric: true,
            imperial: false,
            maxWidth: 250
        }}).addTo(m);
        
        // Make scale control draggable
        const scaleContainer = scaleCtrl.getContainer();
        scaleContainer.id = 'draggable-scale';
        scaleContainer.style.cursor = 'move';
        scaleContainer.title = "Drag to move";
        scaleContainer.style.pointerEvents = 'auto'; // Ensure clickable
        scaleContainer.style.zIndex = '9999'; // Ensure on top of everything
        
        // CRITICAL: Move it out of Leaflet's corner container to map root
        // This allows free movement without being clipped or constrained
        const mapRoot = m.getContainer();
        mapRoot.appendChild(scaleContainer);
        
        // Reset/Set positioning
        scaleContainer.style.position = 'absolute';
        scaleContainer.style.bottom = '25px';
        scaleContainer.style.left = '10px';
        scaleContainer.style.marginBottom = '0';
        scaleContainer.style.marginLeft = '0';
        
        makeDraggable(scaleContainer);
    }}

    // Initialize Overlay Observers
    const ov = findOverlay();
    if (ov) {{
        originalBounds = ov.getBounds();
        reapplyToOverlayImage();
        
        // Update Status
        const statusEl = document.getElementById('js-status');
        if (statusEl) {{
            statusEl.style.background = 'green';
            statusEl.innerHTML = 'JS: Active & Map Found';
            setTimeout(() => {{ statusEl.style.display = 'none'; }}, 3000);
        }}
        
        // Overlay Events
        ov.on('load', () => {{
            setTimeout(reapplyToOverlayImage, 0);
            enableSnapshotBtn();
        }});
        ov.on('update', () => setTimeout(reapplyToOverlayImage, 0));

        // Check if already loaded
        const img = (typeof ov.getElement === 'function') ? ov.getElement() : ov._image;
        if (img && img.complete) {{
            enableSnapshotBtn();
        }}
    }}

    // Map Events
    m.on('zoomend', () => setTimeout(reapplyToOverlayImage, 0));
    m.on('moveend', () => setTimeout(reapplyToOverlayImage, 0));
  }}

  // start
  init();
}})();
</script>
'''

    # Inject the script - try </body> first, then </html>, then just append
    print(f"DEBUG: Reading file {html_file}, size: {len(html)}")
    print(f"DEBUG: js_code size: {len(js_code)}")
    
    if "</body>" in html:
        print("DEBUG: Found </body>, replacing...")
        html = html.replace("</body>", js_code + "\n</body>")
    elif "</html>" in html:
        print("DEBUG: Found </html>, replacing...")
        html = html.replace("</html>", js_code + "\n</html>")
    else:
        print("DEBUG: No closing tags found, appending...")
        # Just append to end if no closing tags found
        html = html + js_code
    
    print(f"DEBUG: New content size: {len(html)}")
    
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Controls injected into: {html_file}")

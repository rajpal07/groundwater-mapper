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

def inject_controls_to_html(html_file, image_bounds, target_points, kmz_points=None, legend_label="Elevation", colormap="viridis", project_details=None):
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
<div id="compass" style="position:fixed; top:80px; left:10px; z-index:100000 !important; width:80px; height:80px; cursor:move; touch-action: none; -webkit-user-select: none; user-select: none;" title="Drag to reposition | Click to reset rotation">
    <div id="compassInner" style="position:relative; width:100%; height:100%; background:radial-gradient(circle, rgba(255,255,255,0.95) 0%, rgba(240,240,240,0.95) 100%); border-radius:50%; border:4px solid #2c3e50; transition: transform 0.3s ease;">
        <!-- Outer ring with degree marks -->
        <div style="position:absolute; top:50%; left:50%; width:90%; height:90%; transform:translate(-50%, -50%);">
            <!-- Cardinal direction markers -->
            <div style="position:absolute; top:2px; left:50%; transform:translateX(-50%); color:#c0392b; font-weight:bold; font-size:18px;">N</div>
            <div style="position:absolute; bottom:2px; left:50%; transform:translateX(-50%); color:#34495e; font-weight:bold; font-size:14px;">S</div>
            <div style="position:absolute; top:50%; right:2px; transform:translateY(-50%); color:#34495e; font-weight:bold; font-size:14px;">E</div>
            <div style="position:absolute; top:50%; left:2px; transform:translateY(-50%); color:#34495e; font-weight:bold; font-size:14px;">W</div>
        </div>
        
        <!-- Center circle -->
        <div style="position:absolute; top:50%; left:50%; width:12px; height:12px; transform:translate(-50%, -50%); background:#2c3e50; border-radius:50%; border:2px solid #ecf0f1;"></div>
        
        <!-- North arrow (red) -->
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);">
            <div style="position:absolute; bottom:6px; left:50%; transform:translateX(-50%); width:0; height:0; border-left:8px solid transparent; border-right:8px solid transparent; border-bottom:35px solid #c0392b;"></div>
        </div>
        
        <!-- South arrow (white) -->
        <div style="position:absolute; top:50%; left:50%; transform:translate(-50%, -50%);">
            <div style="position:absolute; top:6px; left:50%; transform:translateX(-50%); width:0; height:0; border-left:8px solid transparent; border-right:8px solid transparent; border-top:35px solid #ecf0f1;"></div>
        </div>
        
        <!-- Decorative tick marks -->
        <div style="position:absolute; top:8px; left:50%; width:2px; height:8px; background:#95a5a6; transform:translateX(-50%);"></div>
        <div style="position:absolute; bottom:8px; left:50%; width:2px; height:8px; background:#95a5a6; transform:translateX(-50%);"></div>
        <div style="position:absolute; top:50%; right:8px; width:8px; height:2px; background:#95a5a6; transform:translateY(-50%);"></div>
        <div style="position:absolute; top:50%; left:8px; width:8px; height:2px; background:#95a5a6; transform:translateY(-50%);"></div>
    </div>
</div>

<!-- Controls UI -->
<div id="map-controls" style="position:fixed; top:10px; right:10px; z-index:100000 !important; background:rgba(255,255,255,0.95); padding:10px; border-radius:6px; font-family:Arial,Helvetica,sans-serif; pointer-events:auto;">
  <div style="margin-bottom:8px;">
    <label>Move Scale: </label>
    <input type="number" id="moveScale" value="0.01" step="0.01" min="0.01" style="width:60px;">
    <br>
    <button onclick="moveImage('up')" style="margin:2px;">⬆️</button>
    <button onclick="moveImage('down')" style="margin:2px;">⬇️</button>
    <button onclick="moveImage('left')" style="margin:2px;">⬅️</button>
    <button onclick="moveImage('right')" style="margin:2px;">➡️</button>
  </div>

  <div style="margin-bottom:8px;">
    <label>Scale Factor: </label>
    <input type="number" id="scaleAmount" value="1.1" step="0.1" min="0.1" style="width:60px;">
    <br>
    <button onclick="scaleImage('expand')" style="margin:2px;">🔍 Expand</button>
    <button onclick="scaleImage('contract')" style="margin:2px;">🔎 Contract</button>
  </div>

  <div style="margin-bottom:8px;">
    <label>Rotation (deg): </label>
    <input type="number" id="rotationDegrees" value="15" step="1" style="width:60px;">
    <br>
    <button onclick="rotateImage('left')" style="margin:2px;">↺</button>
    <button onclick="rotateImage('right')" style="margin:2px;">↻</button>
  </div>

  <div>
    <button onclick="resetImageBounds()" style="background:#ff6b6b; color:white; margin-bottom:5px;">🔁 Reset</button>
    <br>
    <button id="btn-snapshot" onclick="takeSnapshot()" disabled style="background:#4CAF50; color:white; padding: 5px 10px; cursor:not-allowed; opacity:0.6;">⏳ Loading...</button>
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
    
    <!-- High Gradient -->
    <div style="display:flex; align-items:center; margin-bottom:4px; flex-wrap:wrap;">
      <div style="width:20px; height:10px; background:linear-gradient(to right, {mid_hex}, {high_hex}); margin-right:8px; border:1px solid #999; flex-shrink:0;"></div>
      <span style="word-wrap:break-word; overflow-wrap:break-word; flex:1; min-width:0;">High {legend_label_short} ({high_desc})</span>
    </div>
    
    <!-- Low Gradient -->
    <div style="display:flex; align-items:center; margin-bottom:4px; flex-wrap:wrap;">
      <div style="width:20px; height:10px; background:linear-gradient(to right, {low_hex}, {mid_hex}); margin-right:8px; border:1px solid #999; flex-shrink:0;"></div>
      <span style="word-wrap:break-word; overflow-wrap:break-word; flex:1; min-width:0;">Low {legend_label_short} ({low_desc})</span>
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
    
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'logo.png')
    logo_html_str = ""
    if os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            logo_base64 = base64.b64encode(f.read()).decode('utf-8')
        logo_html_str = f'<img src="data:image/png;base64,{logo_base64}" class="logo-img" alt="Project Logo">'
    else:
        # Placeholder if logo file not found
        logo_html_str = '<div style="text-align:center; color:#ccc;"><div style="font-size:12px;">(Logo Space)</div></div>'

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


<!-- Optional: Input for Attachment Title in Controls -->
<div id="footer-controls" style="position: absolute; top: 350px; right: 10px; z-index: 9999; background: rgba(255,255,255,0.9); padding: 5px; border-radius: 4px; font-size: 11px; width: 200px;">
    <strong>Footer Settings</strong><br>
    <label>Figure Title:</label>
    <input type="text" id="input-attachment-title" value="{pd_safe['attachment_title']}" style="width: 100%; margin-top:2px;" oninput="document.getElementById('footer-attachment-title').innerText = this.value">
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

  // --- Interactive Dots Logic ---
  function initDots() {{
      const m = findMap();
      if (!m) return;
      
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
          marker.bindPopup(`<b>${{fullName}}</b><br>ID: ${{pt.id}}<br>Lat: ${{pt.lat.toFixed(6)}}<br>Lon: ${{pt.lon.toFixed(6)}}`);
          
          // Permanent label with short ID
          marker.bindTooltip(shortId, {{
              permanent: true,
              direction: 'right',
              className: 'borewell-label',
              offset: [10, 0]
          }});
          
          // Update popup on drag
          marker.on('drag', function(e) {{
              const latlng = e.target.getLatLng();
              marker.setPopupContent(`<b>${{fullName}} (Dragging...)</b><br>ID: ${{pt.id}}<br>Lat: ${{latlng.lat.toFixed(6)}}<br>Lon: ${{latlng.lng.toFixed(6)}}`);
          }});
          
          marker.on('dragend', function(e) {{
              const latlng = e.target.getLatLng();
              marker.setPopupContent(`<b>${{fullName}}</b><br>ID: ${{pt.id}}<br>Lat: ${{latlng.lat.toFixed(6)}}<br>Lon: ${{latlng.lng.toFixed(6)}}`);
              console.log(`Borewell ${{shortId}} moved to: [${{latlng.lat}}, ${{latlng.lng}}]`);
          }});
      }});
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


import os
import sys
import pandas as pd
import numpy as np
import time
import webbrowser

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Error: 'playwright' library is not installed.")
    print("Please install it running: pip install playwright")
    print("Then install browsers: playwright install")
    sys.exit(1)

EPA_URL = "https://www3.epa.gov/ceampubl/learn2model/part-two/onsite/gradient4plus-ns.html"

def calculate_exact_local(points):
    """
    Calculates flow direction using 3-point plane fitting (Exact Method).
    Returns: (azimuth_degrees, vector_u, vector_v)
    """
    A_data = []
    h_data = []
    
    for p in points:
        A_data.append([p['x'], p['y'], 1])
        h_data.append(p['h'])
        
    A = np.array(A_data)
    h = np.array(h_data)
    
    try:
        # Solve h = ax + by + c
        coeffs, _, _, _ = np.linalg.lstsq(A, h, rcond=None)
        a, b, _ = coeffs
        
        # Flow vector (downhill)
        u, v = -a, -b
        
        # Azimuth
        math_angle = np.degrees(np.arctan2(v, u))
        azimuth = (90 - math_angle) % 360
        
        return azimuth, u, v
    except Exception as e:
        print(f"Local calc failed: {e}")
        return None, 0, 0

def get_epa_web_result(points, headless=False):
    """
    Uses Playwright to enter data into EPA website and retrieve result.
    points: list of 3 dicts with x, y, h, id.
    """
    print(f"\n[Browser] Launching {'Headless' if headless else 'Visible'} Browser...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        
        print(f"[Browser] Navigating to {EPA_URL}...")
        page.goto(EPA_URL)
        
        # Fill Site Name
        page.fill('input[name="site"]', "Automated Verification")
        
        # Fill Data Rows
        # The form uses names like id1, x1, y1, h1 for row 1
        for i, point in enumerate(points):
            row_idx = i + 1
            print(f"[Browser] Filling Row {row_idx}: {point['name']}...")
            
            page.fill(f'input[name="id{row_idx}"]', str(point['name']))
            page.fill(f'input[name="x{row_idx}"]', str(point['x']))
            page.fill(f'input[name="y{row_idx}"]', str(point['y']))
            page.fill(f'input[name="h{row_idx}"]', str(point['h']))
        
        # Create unique filenames for screenshots (avoid conflicts between users)
        import tempfile
        import uuid
        session_id = str(uuid.uuid4())[:8]
        temp_dir = tempfile.gettempdir()
        screenshot_form = os.path.join(temp_dir, f"epa_form_{session_id}.png")
        screenshot_result = os.path.join(temp_dir, f"epa_result_{session_id}.png")
        
        # Take screenshot after filling form
        print("[Browser] Taking screenshot of filled form...")
        page.screenshot(path=screenshot_form)
        
        # Click Calculate
        print("[Browser] Clicking 'Calculate'...")
        # The button is an input with value="Calculate"
        page.click('input[value="Calculate"]')
        
        # Wait for result to populate 
        print("[Browser] Waiting for results...")
        page.wait_for_timeout(1000) 
        
        # Take screenshot of results
        print("[Browser] Taking screenshot of results...")
        page.screenshot(path=screenshot_result)
        
        # Extract Result
        result_deg = page.input_value('input[name="degrees"]')
        
        print(f"[Browser] Scraped Result: {result_deg} degrees")
            
        browser.close()
        
        try:
            result_value = float(result_deg)
            # Return both the result and screenshot paths
            return {
                'azimuth': result_value,
                'screenshot_form': screenshot_form,
                'screenshot_result': screenshot_result
            }
        except:
            return None

def get_cardinal_direction(azimuth):
    dirs = ['North', 'North-East', 'East', 'South-East', 'South', 'South-West', 'West', 'North-West']
    idx = round(azimuth / 45) % 8
    return dirs[idx]


def create_map_base64(points, u, v):
    """
    Creates a matplotlib plot of the wells and flow arrow, returns base64 string.
    """
    import matplotlib
    matplotlib.use('Agg') # Force non-interactive backend
    import matplotlib.pyplot as plt
    try:
        import io
        import base64
    except ImportError:
        return ""
    try:
        import io
        import base64
    except ImportError:
        return ""

    # Extract data
    xs = [p['x'] for p in points]
    ys = [p['y'] for p in points]
    names = [p['name'] for p in points]
    
    # Setup plot
    plt.figure(figsize=(6, 5), dpi=100)
    plt.style.use('dark_background') # Match the report theme
    
    # Plot wells
    plt.scatter(xs, ys, c='#3b82f6', s=100, zorder=5, label='Wells')
    
    # Annotate wells
    for x, y, name in zip(xs, ys, names):
        plt.annotate(name, (x, y), xytext=(5, 5), textcoords='offset points', 
                     color='white', fontsize=9, fontweight='bold')

    # Calculate centroid for arrow origin
    cx, cy = np.mean(xs), np.mean(ys)
    
    # Arrow length (approx 20% of span)
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    span = max(span_x, span_y) if len(xs) > 1 else 100
    length = span * 0.4
    
    # Normalize u,v and scale
    mag = np.sqrt(u**2 + v**2)
    if mag == 0: mag = 1
    u_norm, v_norm = u/mag, v/mag
    
    # Plot Arrow
    plt.arrow(cx, cy, u_norm * length, v_norm * length, 
              head_width=length*0.3, head_length=length*0.3, 
              fc='#10b981', ec='#10b981', width=length*0.05, zorder=4, label='Flow Dir')

    # Formatting
    plt.title("Spatial Well Layout & Flow", color='white', pad=20)
    plt.xlabel("Easting (m)")
    plt.ylabel("Northing (m)")
    plt.grid(True, linestyle='--', alpha=0.3)
    plt.axis('equal') # Crucial for correct angle perception
    
    # Save to Bytes
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, bbox_inches='tight')
    plt.close()
    
    # Encode
    buf.seek(0)
    b64_str = base64.b64encode(buf.read()).decode('utf-8')
    return b64_str

def generate_html_report(points, local_az, web_az, u_vec, v_vec, return_html_string=False):
    """
    Generates a standalone HTML file with Framer-like animations to visualize the result.
    If return_html_string is True, returns the HTML content as a string instead of writing to file.
    """
    # Determine verdict
    diff = abs(local_az - web_az) if web_az is not None else 0
    verdict = "MATCH" if diff < 1.0 else "FAIL"
    verdict_color = "#10b981" if verdict == "MATCH" else "#ef4444"
    
    # Generate Map
    map_b64 = create_map_base64(points, u_vec, v_vec)
    
    # Format data for JS
    wells_html = ""
    for p in points:
        wells_html += f"""
        <div class="well-card">
            <div class="well-id">{p['name']}</div>
            <div class="well-coords">E: {p['x']}<br>N: {p['y']}</div>
            <div class="well-head">{p['h']} m</div>
        </div>
        """
        
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Groundwater Verification Report</title>
    <style>
        :root {{
            --bg: #0f172a;
            --surface: #1e293b;
            --primary: #3b82f6;
            --text: #f8fafc;
            --text-muted: #94a3b8;
            --success: {verdict_color};
        }}
        
        body {{
            font-family: 'Inter', system-ui, sans-serif;
            background-color: var(--bg);
            color: var(--text);
            margin: 0;
            padding: 40px;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
        }}
        
        .container {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 40px;
            max-width: 1400px;
            width: 100%;
        }}
        
        .card {{
            background: var(--surface);
            border-radius: 24px;
            padding: 32px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            border: 1px solid rgba(255, 255, 255, 0.1);
            display: flex;
            flex-direction: column;
        }}
        
        h1 {{ margin: 0 0 24px 0; font-size: 24px; font-weight: 600; }}
        h2 {{ margin: 0 0 16px 0; font-size: 18px; color: var(--text-muted); font-weight: 500; }}
        
        /* Compass Animation */
        .compass-container {{
            position: relative;
            width: 250px;
            height: 250px;
            margin: 20px auto;
            border-radius: 50%;
            background: conic-gradient(from 0deg, #1e293b, #334155, #1e293b);
            box-shadow: 
                inset 0 0 20px rgba(0,0,0,0.5),
                0 0 0 10px var(--surface),
                0 0 0 12px rgba(255,255,255,0.1);
            display: flex;
            justify-content: center;
            align-items: center;
            flex-shrink: 0;
        }}
        
        .compass-label {{
            position: absolute;
            color: var(--text-muted);
            font-weight: 700;
            font-size: 12px;
        }}
        .n {{ top: 15px; color: var(--primary); }}
        .e {{ right: 15px; }}
        .s {{ bottom: 15px; }}
        .w {{ left: 15px; }}
        
        .arrow-wrapper {{
            width: 100%;
            height: 100%;
            position: absolute;
            transition: transform 2.5s cubic-bezier(0.34, 1.56, 0.64, 1);
            transform: rotate(0deg);
        }}
        
        .arrow {{
            width: 4px;
            height: 110px;
            background: var(--primary);
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -40px);
            border-radius: 4px;
            box-shadow: 0 0 20px var(--primary);
        }}
        
        .arrow::after {{
            content: '';
            position: absolute;
            top: -15px;
            left: 50%;
            transform: translateX(-50%);
            border-left: 10px solid transparent;
            border-right: 10px solid transparent;
            border-bottom: 20px solid var(--primary);
        }}
        
        .degree-badge {{
            position: absolute;
            bottom: -50px;
            background: rgba(59, 130, 246, 0.1);
            color: var(--primary);
            padding: 6px 12px;
            border-radius: 20px;
            font-family: monospace;
            font-size: 14px;
            border: 1px solid rgba(59, 130, 246, 0.3);
            white-space: nowrap;
        }}

        /* Map Image */
        .map-container {{
            width: 100%;
            border-radius: 12px;
            overflow: hidden;
            margin-top: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .map-container img {{
            width: 100%;
            display: block;
        }}

        /* Data Side */
        .well-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
            margin-bottom: 24px;
        }}
        
        .well-card {{
            background: rgba(255,255,255,0.03);
            padding: 12px 16px;
            border-radius: 12px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .well-id {{ font-weight: 600; color: var(--text); min-width: 80px; }}
        .well-coords {{ font-size: 11px; color: var(--text-muted); line-height: 1.4; }}
        .well-head {{ font-family: monospace; color: var(--primary); font-weight: bold; }}
        
        .verdict-box {{
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid var(--success);
            padding: 20px;
            border-radius: 16px;
            text-align: center;
            margin-top: auto;
        }}
        .verdict-value {{ color: var(--success); font-size: 28px; font-weight: 800; margin: 8px 0; }}
        
        .verdict-sub {{ color: var(--text-muted); font-size: 14px; }}
        
        .educational-text {{
            margin-top: 24px;
            padding: 16px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            font-size: 13px;
            line-height: 1.6;
            color: var(--text-muted);
            border-left: 4px solid var(--primary);
        }}
        
    </style>
</head>
<body>

    <div class="container">
        <!-- Visual Side -->
        <div class="card">
            <h1>Flow Direction Visualization</h1>
            
            <div style="display:flex; gap:20px; align-items:flex-start;">
                <!-- Compass -->
                <div style="flex:1; text-align:center;">
                    <h2>Compass Azimuth</h2>
                    <div class="compass-container">
                        <div class="compass-label n">N (0&deg;)</div>
                        <div class="compass-label e">E (90&deg;)</div>
                        <div class="compass-label s">S (180&deg;)</div>
                        <div class="compass-label w">W (270&deg;)</div>
                        
                        <div class="arrow-wrapper" id="arrow">
                            <div class="arrow"></div>
                        </div>
                        
                        <div class="degree-badge" id="degree-text">0.00&deg;</div>
                    </div>
                </div>
            </div>

            <!-- Map -->
            <h2>Spatial Verification</h2>
            <div class="map-container">
                <img src="data:image/png;base64,{map_b64}" alt="Well Map">
            </div>
            
            <div class="educational-text">
                <strong>Analysis:</strong><br>
                The map above shows the actual positions of your wells. The Green Arrow represents 
                the downhill gradient calculated from the head values. 
                <br><br>
                Direction: <strong>{local_az:.2f}&deg; ({get_cardinal_direction(local_az)})</strong>
            </div>
        </div>
        
        <!-- Data Side -->
        <div class="card">
            <h1>Verification Data</h1>
            
            <h2>Input Wells (3-Point Problem)</h2>
            <div class="well-list">
                {wells_html}
            </div>
            
            <h2>Results Comparison</h2>
            <div class="well-list">
                <div class="well-card" style="border-left: 4px solid var(--primary);">
                    <div>Local Script Result</div>
                    <div class="well-head">{local_az:.4f}&deg;</div>
                </div>
                <div class="well-card" style="border-left: 4px solid #f59e0b;">
                    <div>EPA Website Result</div>
                    <div class="well-head">{web_az if web_az else 'N/A'}&deg;</div>
                </div>
            </div>
            
            <div class="verdict-box">
                <div class="verdict-title">Automated Verification Verdict</div>
                <div class="verdict-value">{verdict}</div>
                <div class="verdict-sub">Difference: {diff:.4f}&deg;</div>
            </div>
        </div>
    </div>

    <script>
        // Framer-style animation trigger on load
        setTimeout(() => {{
            const azimuth = {local_az};
            
            // Rotate Arrow
            document.getElementById('arrow').style.transform = `rotate(${{azimuth}}deg)`;
            
            // Animate Text Counter
            const counterElement = document.getElementById('degree-text');
            const duration = 2500; // ms
            const start = 0;
            const startTime = performance.now();
            
            function update(currentTime) {{
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                
                // Ease out cubic
                const ease = 1 - Math.pow(1 - progress, 3);
                
                const currentVal = start + (azimuth - start) * ease;
                counterElement.textContent = currentVal.toFixed(2) + '&deg;';
                
                if (progress < 1) {{
                    requestAnimationFrame(update);
                }}
            }}
            
            requestAnimationFrame(update);
            
        }}, 500); // Small delay for effect
    </script>
</body>
</html>
    """
    
    if return_html_string:
        return html_content
        
    output_file = "verification_report.html"
    with open(output_file, "w", encoding='utf-8') as f:
        f.write(html_content)
        
    print(f"\n[Report] Generated: {output_file}")
    print("[Report] Opening in browser...")
    webbrowser.open('file://' + os.path.realpath(output_file))



def main():
    import argparse
    parser = argparse.ArgumentParser(description='Verify Groundwater Flow with EPA Site')
    parser.add_argument('file_path', nargs='?', default=r"d:\anirudh_kahn\adi_version\Shepparton 29.09.2025.xlsx", help='Path to Excel file')
    parser.add_argument('--subset', type=str, help='Comma-separated list of well names/substrings to include (e.g., "WB-01,WB-02,WB-05")')
    
    args = parser.parse_args()
    file_path = args.file_path
    
    print(f"Reading data from: {file_path}")
    
    try:
        df = pd.read_excel(file_path)
    except Exception as e:
        print(f"Error reading file: {e}")
        return

    # Clean columns
    df.columns = df.columns.str.strip()
    
    # Standardize 'Name' to 'Well ID'
    if 'Name' in df.columns and 'Well ID' not in df.columns:
        print("Note: mapping 'Name' column to 'Well ID'")
        df = df.rename(columns={'Name': 'Well ID'})

    required = ['Well ID', 'Easting', 'Northing', 'Groundwater Elevation mAHD']
    
    if not all(col in df.columns for col in required):
        print(f"Error: Missing columns. Valid columns: {df.columns.tolist()}")
        print(f"Required: {required}")
        return
        
    df = df.dropna(subset=required)
    
    # Filter subset if requested
    if args.subset:
        targets = [t.strip().lower() for t in args.subset.split(',')]
        print(f"Filtering for wells matching: {targets}")
        
        # Helper to check if any target is in the well ID
        def is_match(well_id):
            wid = str(well_id).lower()
            return any(t in wid for t in targets)
            
        df = df[df['Well ID'].apply(is_match)]
        
        if len(df) < 3:
            print(f"Error: Only found {len(df)} wells matching filter. Need at least 3.")
            print(f"Found: {df['Well ID'].tolist()}")
            return
            
    if len(df) < 3:
        print("Error: Need at least 3 valid data points.")
        return
        
    # Take top 3 if more than 3, or use all if exactly 3
    # If user provided a subset, we typically want exactly those. 
    # If more than 3 matched, warn or just take first 3.
    subset = df.head(3)
    
    points = []
    for _, row in subset.iterrows():
        points.append({
            'name': row['Well ID'],
            'x': row['Easting'],
            'y': row['Northing'],
            'h': row['Groundwater Elevation mAHD']
        })
        
    print(f"Selected Wells: {[p['name'] for p in points]}")
    
    # 1. Local Calculation
    print("\n--- Running Local Calculation ---")
    local_az, u_vec, v_vec = calculate_exact_local(points)
    print(f"Local Result: {local_az:.4f} degrees")
    print(f"Vector: u={u_vec:.4f}, v={v_vec:.4f}")
    
    # 2. Web Verification
    print("\n--- Running EPA Web Verification ---")
    web_az = get_epa_web_result(points, headless=False)
    
    # 3. Report
    generate_html_report(points, local_az, web_az, u_vec, v_vec)

if __name__ == "__main__":
    main()

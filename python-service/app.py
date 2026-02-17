"""
Groundwater Mapper Python Microservice
Wraps the Streamlit functionality for Next.js integration
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import io
import base64
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
from pyproj import Transformer
import json
import os
import warnings

warnings.filterwarnings("ignore")

app = Flask(__name__)
CORS(app)

# Try to import optional libraries
try:
    from llama_parse import LlamaParse
    HAS_LLAMA_PARSE = True
except ImportError:
    HAS_LLAMA_PARSE = False
    print("Warning: LlamaParse not installed. Using basic Excel parsing.")

try:
    import ee
    HAS_GEE = True
except ImportError:
    HAS_GEE = False
    print("Warning: Google Earth Engine not installed.")


# Australian UTM zones
def get_australian_utm_zones():
    return {
        49: {'epsg': 'EPSG:32749', 'lon_min': 108, 'lon_max': 114},
        50: {'epsg': 'EPSG:32750', 'lon_min': 114, 'lon_max': 120},
        51: {'epsg': 'EPSG:32751', 'lon_min': 120, 'lon_max': 126},
        52: {'epsg': 'EPSG:32752', 'lon_min': 126, 'lon_max': 132},
        53: {'epsg': 'EPSG:32753', 'lon_min': 132, 'lon_max': 138},
        54: {'epsg': 'EPSG:32754', 'lon_min': 138, 'lon_max': 144},
        55: {'epsg': 'EPSG:32755', 'lon_min': 144, 'lon_max': 150},
        56: {'epsg': 'EPSG:32756', 'lon_min': 150, 'lon_max': 156}
    }


def calculate_utm_zone(lon, lat):
    return int((lon + 180) / 6) + 1


def auto_detect_utm_zone(df):
    """Auto-detect UTM zone from Easting/Northing data."""
    if 'Easting' not in df.columns or 'Northing' not in df.columns:
        return None
    
    avg_easting = df['Easting'].mean()
    avg_northing = df['Northing'].mean()
    
    # Estimate zone from Easting value for Australia
    if 200000 <= avg_easting <= 800000:
        candidates = [55, 54, 56, 53, 52, 51, 50, 49]
    else:
        candidates = list(get_australian_utm_zones().keys())
    
    australian_zones = get_australian_utm_zones()
    
    for zone_num in candidates:
        if zone_num not in australian_zones:
            continue
        epsg = australian_zones[zone_num]['epsg']
        try:
            transformer = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
            test_lon, test_lat = transformer.transform(avg_easting, avg_northing)
            
            # Check if in Australia
            if 112 <= test_lon <= 155 and -45 <= test_lat <= -10:
                calculated_zone = calculate_utm_zone(test_lon, test_lat)
                if abs(calculated_zone - zone_num) <= 1:
                    return epsg, zone_num
        except:
            continue
    
    # Default to zone 55 (Victoria)
    return 'EPSG:32755', 55


def load_excel_data(file_bytes, sheet_name=0):
    """Load Excel file from bytes."""
    df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)
    df.columns = df.columns.astype(str).str.strip()
    return df


def process_excel_with_llamaparse(file_bytes, api_key, selected_sheets=None):
    """Use LlamaParse to process Excel file intelligently."""
    if not HAS_LLAMA_PARSE:
        return load_excel_data(file_bytes)
    
    os.environ["LLAMA_CLOUD_API_KEY"] = api_key
    
    # Save temp file
    temp_input = "temp_input.xlsx"
    temp_output = "processed_output.xlsx"
    
    with open(temp_input, "wb") as f:
        f.write(file_bytes)
    
    try:
        parser = LlamaParse(result_type="markdown", verbose=True)
        
        # Parse each selected sheet
        all_data = []
        xls = pd.ExcelFile(temp_input)
        sheets = selected_sheets if selected_sheets else xls.sheet_names
        
        for sheet in sheets:
            df = pd.read_excel(temp_input, sheet_name=sheet)
            all_data.append(df)
        
        # Merge on Well ID if multiple sheets
        if len(all_data) > 1:
            final_df = all_data[0]
            for df in all_data[1:]:
                if 'Well ID' in final_df.columns and 'Well ID' in df.columns:
                    final_df = pd.merge(final_df, df, on='Well ID', how='outer', suffixes=('', '_dup'))
            return final_df
        return all_data[0] if all_data else pd.DataFrame()
    
    finally:
        # Cleanup temp files
        if os.path.exists(temp_input):
            os.remove(temp_input)
        if os.path.exists(temp_output):
            os.remove(temp_output)


def generate_contour_image(df, value_column, colormap='viridis'):
    """Generate contour image from data points."""
    
    # Determine coordinate columns
    has_utm = 'Easting' in df.columns and 'Northing' in df.columns
    has_latlon = 'Latitude' in df.columns and 'Longitude' in df.columns
    
    if has_utm:
        x_col, y_col = 'Easting', 'Northing'
        use_utm = True
    elif has_latlon:
        x_col, y_col = 'Longitude', 'Latitude'
        use_utm = False
    else:
        return None, None, None
    
    # Convert to numeric
    df[x_col] = pd.to_numeric(df[x_col], errors='coerce')
    df[y_col] = pd.to_numeric(df[y_col], errors='coerce')
    df[value_column] = pd.to_numeric(df[value_column], errors='coerce')
    
    # Drop NaN
    df = df.dropna(subset=[x_col, y_col, value_column])
    
    if len(df) < 3:
        return None, None, None
    
    # Auto-detect UTM zone if needed
    transformer = None
    if use_utm:
        epsg, zone = auto_detect_utm_zone(df)
        if epsg:
            transformer = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
    
    # Create interpolation grid
    xi = np.linspace(df[x_col].min(), df[x_col].max(), 200)
    yi = np.linspace(df[y_col].min(), df[y_col].max(), 200)
    grid_x, grid_y = np.meshgrid(xi, yi)
    
    # Interpolate
    grid_z = griddata((df[x_col], df[y_col]), df[value_column], (grid_x, grid_y), method='linear')
    
    # Calculate bounds
    min_x, max_x = grid_x.min(), grid_x.max()
    min_y, max_y = grid_y.min(), grid_y.max()
    
    if use_utm and transformer:
        min_lon, min_lat = transformer.transform(min_x, min_y)
        max_lon, max_lat = transformer.transform(max_x, max_y)
    else:
        min_lon, min_lat = min_x, min_y
        max_lon, max_lat = max_x, max_y
    
    image_bounds = [[min_lat, min_lon], [max_lat, max_lon]]
    
    # Smart contour levels
    z_min, z_max = df[value_column].min(), df[value_column].max()
    z_range = z_max - z_min
    
    if z_range > 10:
        interval = 1.0
    elif z_range > 5:
        interval = 0.5
    elif z_range > 2:
        interval = 0.2
    else:
        interval = 0.05
    
    levels = np.arange(np.floor(z_min/interval)*interval, np.ceil(z_max/interval)*interval + interval, interval)
    
    # Generate image
    fig, ax = plt.subplots(figsize=(10, 10))
    ax.set_aspect('equal')
    
    contour_filled = ax.contourf(grid_x, grid_y, grid_z, levels=levels, cmap=colormap, alpha=0.7)
    contour_lines = ax.contour(grid_x, grid_y, grid_z, levels=levels, colors='black', linewidths=0.8, alpha=0.8)
    ax.clabel(contour_lines, inline=True, fontsize=8, fmt='%.2f')
    
    ax.axis('off')
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', transparent=True, bbox_inches='tight', pad_inches=0, dpi=300)
    plt.close()
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    
    # Get target points (lat/lon)
    if use_utm and transformer:
        target_lons, target_lats = transformer.transform(df['Easting'].values, df['Northing'].values)
    else:
        target_lons = df['Longitude'].values
        target_lats = df['Latitude'].values
    
    # Get names
    if 'Well ID' in df.columns:
        names = df['Well ID'].astype(str).tolist()
    elif 'Name' in df.columns:
        names = df['Name'].astype(str).tolist()
    else:
        names = [f"Point {i}" for i in range(len(df))]
    
    values = df[value_column].tolist()
    
    target_points = [
        {"lat": lat, "lon": lon, "id": i, "name": names[i], "value": values[i]}
        for i, (lat, lon) in enumerate(zip(target_lats, target_lons))
    ]
    
    return image_base64, image_bounds, target_points


# Columns to exclude from parameter selection
EXCLUDE_KEYWORDS = [
    'sample date', 'time', 'date', 'easting', 'northing',
    'lati', 'longi', 'comments', 'well id', 'mga2020',
    'unknown', 'unit', 'lor', 'guideline', 'trigger'
]


def get_available_parameters(df):
    """Get available numeric columns for parameter selection."""
    available = []
    for col in df.columns:
        col_lower = col.lower()
        
        # Skip excluded keywords
        if any(kw in col_lower for kw in EXCLUDE_KEYWORDS):
            continue
        
        # Check if numeric
        values = df[col].head(20)
        valid_numbers = values.apply(lambda v: not pd.isna(v) and str(v).strip() != '' and 
                                     not pd.isna(pd.to_numeric(str(v), errors='coerce'))).sum()
        
        if valid_numbers / len(values) > 0.3:
            available.append(col)
    
    return available


@app.route('/preview', methods=['POST'])
def preview_file():
    """Preview Excel file and return available parameters."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    file_bytes = file.read()
    
    try:
        # Load workbook to get sheet names
        xls = pd.ExcelFile(io.BytesIO(file_bytes))
        sheet_names = xls.sheet_names
        
        # Load first sheet for preview
        df = load_excel_data(file_bytes, sheet_name=0)
        
        # Get available parameters
        available_params = get_available_parameters(df)
        
        # Detect coordinate columns
        lat_cols = [c for c in df.columns if 'lat' in c.lower()]
        lon_cols = [c for c in df.columns if 'lon' in c.lower() or 'long' in c.lower()]
        
        return jsonify({
            'success': True,
            'sheetNames': sheet_names,
            'columns': list(df.columns),
            'availableParameters': available_params,
            'latColumns': lat_cols,
            'lonColumns': lon_cols,
            'rowCount': len(df),
            'sampleData': df.head(3).to_dict('records')
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/process', methods=['POST'])
def process_file():
    """Process Excel file and generate map."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    parameter = request.form.get('parameter', '')
    colormap = request.form.get('colormap', 'viridis')
    use_ai = request.form.get('useAI', 'false').lower() == 'true'
    api_key = request.form.get('apiKey', '')
    sheet_name = request.form.get('sheetName', '0')
    
    file_bytes = file.read()
    
    try:
        # Process with or without AI
        if use_ai and HAS_LLAMA_PARSE and api_key:
            df = process_excel_with_llamaparse(file_bytes, api_key, [sheet_name])
        else:
            df = load_excel_data(file_bytes, sheet_name=int(sheet_name) if sheet_name.isdigit() else sheet_name)
        
        # Generate contour image
        image_base64, bounds, points = generate_contour_image(df, parameter, colormap)
        
        if not image_base64:
            return jsonify({'error': 'Failed to generate contour. Check your data.'}), 400
        
        return jsonify({
            'success': True,
            'imageBase64': image_base64,
            'bounds': bounds,
            'points': points,
            'parameter': parameter,
            'colormap': colormap
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'llamaparse': HAS_LLAMA_PARSE,
        'gee': HAS_GEE
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

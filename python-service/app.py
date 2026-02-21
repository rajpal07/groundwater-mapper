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
from datetime import datetime, date, time

warnings.filterwarnings("ignore")


def make_json_serializable(obj):
    """Convert non-JSON-serializable objects to serializable types."""
    if obj is None or pd.isna(obj):
        return None
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, time):
        return obj.strftime('%H:%M:%S')
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    elif isinstance(obj, bytes):
        return obj.decode('utf-8', errors='replace')
    else:
        return obj


def convert_df_for_json(df):
    """Convert a DataFrame to a JSON-serializable format."""
    result = []
    for record in df.to_dict(orient='records'):
        converted_record = {}
        for key, value in record.items():
            converted_record[key] = make_json_serializable(value)
        result.append(converted_record)
    return result

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
    from google.oauth2 import service_account
    # Initialize Google Earth Engine - use google-auth library
    HAS_GEE = False
    
    # Define the required scope for Earth Engine - use cloud-platform scope
    EE_SCOPE = 'https://www.googleapis.com/auth/cloud-platform'
    
    # Method 1: Try to read from secret file (recommended for Render)
    secret_file = os.environ.get('GEE_SECRET_FILE', '/etc/secrets/gee-service-account.json')
    if os.path.exists(secret_file):
        try:
            credentials = service_account.Credentials.from_service_account_file(
                secret_file,
                scopes=[EE_SCOPE]
            )
            ee.Initialize(credentials=credentials)
            HAS_GEE = True
            print("Google Earth Engine initialized from secret file!")
        except Exception as e:
            print(f"Warning: Failed to init GEE from secret file: {e}")
    
    # Auto-detect JSON files in /etc/secrets/
    if not HAS_GEE:
        try:
            secrets_dir = '/etc/secrets'
            if os.path.exists(secrets_dir):
                for filename in os.listdir(secrets_dir):
                    if filename.endswith('.json'):
                        secret_path = os.path.join(secrets_dir, filename)
                        print(f"Trying secret file: {secret_path}")
                        try:
                            credentials = service_account.Credentials.from_service_account_file(
                                secret_path,
                                scopes=[EE_SCOPE]
                            )
                            ee.Initialize(credentials=credentials)
                            HAS_GEE = True
                            print(f"Google Earth Engine initialized from {filename}!")
                            break
                        except Exception as e:
                            print(f"Warning: Failed to init GEE from {filename}: {e}")
        except Exception as e:
            print(f"Warning: Error scanning secrets directory: {e}")
    
    # Method 2: Try GOOGLE_APPLICATION_CREDENTIALS env var
    if not HAS_GEE:
        gac = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
        if gac and os.path.exists(gac):
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    gac,
                    scopes=[EE_SCOPE]
                )
                ee.Initialize(credentials=credentials)
                HAS_GEE = True
                print("Google Earth Engine initialized from GOOGLE_APPLICATION_CREDENTIALS!")
            except Exception as e:
                print(f"Warning: Failed to init GEE from GOOGLE_APPLICATION_CREDENTIALS: {e}")
    
    if not HAS_GEE:
        print("GEE initialization skipped - continuing without it")
except ImportError as e:
    HAS_GEE = False
    print(f"Warning: Google Earth Engine not installed or import error: {e}")
except Exception as e:
    HAS_GEE = False
    print(f"Warning: Google Earth Engine initialization failed: {e}")


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
                return zone_num
        except:
            continue
    
    return None


def detect_coordinates_system(df):
    """Detect whether data is in Lat/Lon or UTM."""
    has_lat = 'Latitude' in df.columns or 'latitude' in df.columns
    has_lon = 'Longitude' in df.columns or 'longitude' in df.columns
    has_easting = 'Easting' in df.columns
    has_northing = 'Northing' in df.columns
    
    if has_lat and has_lon:
        return 'latlon'
    elif has_easting and has_northing:
        return 'utm'
    elif 'x' in df.columns and 'y' in df.columns:
        # Check if values look like lat/lon or UTM
        sample_x = df['x'].mean()
        if -180 <= sample_x <= 180:
            return 'latlon'
        elif 100000 <= sample_x <= 1000000:
            return 'utm'
    
    return None


def convert_to_latlon(df, coord_system):
    """Convert coordinates to Lat/Lon for mapping."""
    df = df.copy()
    
    if coord_system == 'latlon':
        if 'Latitude' in df.columns:
            df['lat'] = df['Latitude']
        elif 'latitude' in df.columns:
            df['lat'] = df['latitude']
            
        if 'Longitude' in df.columns:
            df['lon'] = df['Longitude']
        elif 'longitude' in df.columns:
            df['lon'] = df['longitude']
    elif coord_system == 'utm':
        # Auto-detect UTM zone
        zone = auto_detect_utm_zone(df)
        
        if zone is None:
            # Default to zone 55 (Sydney/NSW)
            zone = 55
        
        epsg = f'EPSG:327{zone}'
        
        try:
            transformer = Transformer.from_crs(epsg, "EPSG:4326", always_xy=True)
            df['lon'], df['lat'] = transformer.transform(
                df['Easting'].values, 
                df['Northing'].values
            )
        except Exception as e:
            print(f"Error converting coordinates: {e}")
            return None
    
    return df


def interpolate_contours(df, parameter, resolution=100):
    """Create interpolated grid for contour generation."""
    # Get coordinates
    lat_col = 'Latitude' if 'Latitude' in df.columns else 'latitude'
    lon_col = 'Longitude' if 'Longitude' in df.columns else 'longitude'
    
    lats = df[lat_col].values
    lons = df[lon_col].values
    values = df[parameter].values
    
    # Create grid
    lon_min, lon_max = lons.min(), lons.max()
    lat_min, lat_max = lats.min(), lats.max()
    
    # Add buffer
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min
    
    grid_lon = np.linspace(lon_min - lon_range*0.1, lon_max + lon_range*0.1, resolution)
    grid_lat = np.linspace(lat_min - lat_range*0.1, lat_max + lat_range*0.1, resolution)
    grid_lon_mesh, grid_lat_mesh = np.meshgrid(grid_lon, grid_lat)
    
    # Interpolate
    try:
        grid_values = griddata(
            (lons, lats), 
            values, 
            (grid_lon_mesh, grid_lat_mesh), 
            method='linear'
        )
        return grid_lon_mesh, grid_lat_mesh, grid_values
    except Exception as e:
        print(f"Interpolation error: {e}")
        return None, None, None


def generate_contour_plot(df, parameter, title=None, colormap='viridis', 
                          show_contours=True, show_scatter=True):
    """Generate contour plot from well data."""
    import matplotlib
    matplotlib.use('Agg')
    
    # Detect coordinate system and convert
    coord_system = detect_coordinates_system(df)
    
    if coord_system is None:
        return None, "Could not detect coordinate system"
    
    df = convert_to_latlon(df, coord_system)
    
    if df is None or 'lat' not in df.columns or 'lon' not in df.columns:
        return None, "Could not convert coordinates"
    
    # Interpolate
    grid_lon, grid_lat, grid_values = interpolate_contours(df, parameter)
    
    if grid_values is None:
        return None, "Interpolation failed"
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Contour plot
    if show_contours:
        contour = ax.contourf(grid_lon, grid_lat, grid_values, 
                             levels=20, cmap=colormap)
        plt.colorbar(contour, ax=ax, label=parameter)
        
        # Contour lines
        ax.contour(grid_lon, grid_lat, grid_values, 
                  levels=10, colors='black', linewidths=0.5, alpha=0.5)
    
    # Scatter points
    if show_scatter:
        ax.scatter(df['lon'], df['lat'], c=df[parameter], 
                 cmap=colormap, edgecolors='black', linewidth=0.5, s=50)
    
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title(title or f'{parameter} Distribution')
    ax.set_aspect('equal')
    
    # Save to buffer
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    
    return buf, None


@app.route('/debug', methods=['GET'])
def debug():
    """Debug endpoint to check GEE initialization status"""
    # Note: 'ee' may not be in dir() because it's imported inside a try block
    # The HAS_GEE variable is the authoritative source
    debug_info = {
        'gee_available': HAS_GEE,  # Check the HAS_GEE flag instead
        'gee_initialized': HAS_GEE,
    }
    
    return jsonify(debug_info)


@app.route('/', methods=['GET', 'HEAD'])
def index():
    return jsonify({
        'message': 'Groundwater Mapper API',
        'endpoints': ['/health', '/debug', '/preview', '/process']
    })


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'llamaparse': HAS_LLAMA_PARSE,
        'gee': HAS_GEE
    })


def parse_excel_file(file_content, use_llamaparse=True):
    """Parse Excel file using LlamaParse or pandas."""
    df = None
    parse_method = 'basic'
    
    if use_llamaparse and HAS_LLAMA_PARSE:
        try:
            from llama_parse import LlamaParse
            parsing_instruction = "Extract all data from this Excel file. Return all rows and columns with their exact values."
            parser = LlamaParse(parsing_instruction=parsing_instruction, result_type="markdown")
            
            # Save to temp file
            with open('/tmp/temp_excel.xlsx', 'wb') as f:
                f.write(file_content)
            
            # Parse
            results = parser.load_data('/tmp/temp_excel.xlsx')
            
            if results and len(results) > 0:
                # Get markdown table
                markdown_data = results[0].text
                parse_method = 'llamaparse'
                
                # Convert markdown table to dataframe
                import re
                lines = markdown_data.strip().split('\n')
                header_row = None
                data_rows = []
                
                for line in lines:
                    if '|' in line:
                        cols = [c.strip() for c in line.split('|') if c.strip()]
                        if not cols:
                            continue
                        # Check if it's a separator line
                        if all(set(c.replace('-', '').replace('.', '')) <= {' '} for c in cols if c):
                            continue
                        if header_row is None:
                            header_row = cols
                        else:
                            if len(cols) == len(header_row):
                                data_rows.append(cols)
                
                if header_row and data_rows:
                    df = pd.DataFrame(data_rows, columns=header_row)
                    
                    # Convert numeric columns
                    for col in df.columns:
                        try:
                            df[col] = pd.to_numeric(df[col])
                        except:
                            pass
        except Exception as e:
            print(f"LlamaParse error: {e}")
    
    # Fallback to pandas
    if df is None:
        try:
            df = pd.read_excel(io.BytesIO(file_content))
            parse_method = 'pandas'
        except Exception as e:
            return None, str(e)
    
    return df, parse_method


@app.route('/preview', methods=['POST'])
def preview():
    """Preview uploaded Excel file - returns data summary."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            return jsonify({'error': 'Only Excel files supported'}), 400
        
        # Read file content
        file_content = file.read()
        
        # Parse
        use_llamaparse = request.form.get('use_llamaparse', 'true').lower() == 'true'
        df, parse_method = parse_excel_file(file_content, use_llamaparse)
        
        if df is None:
            return jsonify({'error': parse_method}), 400
        
        # Get summary
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        all_cols = df.columns.tolist()
        
        # Get first few rows - convert to JSON-serializable format
        preview_data = convert_df_for_json(df.head(10))
        
        # Sample stats for numeric columns
        stats = {}
        for col in numeric_cols:
            stats[col] = {
                'min': float(df[col].min()) if not pd.isna(df[col].min()) else None,
                'max': float(df[col].max()) if not pd.isna(df[col].max()) else None,
                'mean': float(df[col].mean()) if not pd.isna(df[col].mean()) else None
            }
        
        return jsonify({
            'columns': all_cols,
            'numeric_columns': numeric_cols,
            'row_count': len(df),
            'preview': preview_data,
            'stats': stats,
            'parse_method': parse_method
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/process', methods=['POST'])
def process():
    """Process Excel file and generate map."""
    try:
        # Support both FormData (from frontend) and JSON (from API)
        if request.files and 'file' in request.files:
            # FormData upload (from frontend direct upload)
            file = request.files['file']
            file_content = file.read()
            parameter = request.form.get('parameter', '')
            colormap = request.form.get('colormap', 'viridis')
            show_contours = request.form.get('show_contours', 'true').lower() == 'true'
            show_scatter = request.form.get('show_scatter', 'true').lower() == 'true'
            use_llamaparse = request.form.get('use_llamaparse', 'true').lower() == 'true'
        else:
            # JSON upload (from API)
            data = request.get_json()
            
            if 'file_content' not in data:
                return jsonify({'error': 'No file content provided'}), 400
            
            if 'parameter' not in data:
                return jsonify({'error': 'No parameter specified'}), 400
            
            # Decode base64 file content
            try:
                file_content = base64.b64decode(data['file_content'])
            except Exception as e:
                return jsonify({'error': f'Invalid file content: {e}'}), 400
            
            parameter = data['parameter']
            colormap = data.get('colormap', 'viridis')
            show_contours = data.get('show_contours', True)
            show_scatter = data.get('show_scatter', True)
            use_llamaparse = data.get('use_llamaparse', True)
        
        if not parameter:
            return jsonify({'error': 'No parameter specified'}), 400
        
        # Parse Excel
        df, parse_method = parse_excel_file(file_content, use_llamaparse)
        
        if df is None:
            return jsonify({'error': parse_method}), 400
        
        # Check if parameter exists
        if parameter not in df.columns:
            available = df.columns.tolist()
            return jsonify({
                'error': f'Parameter {parameter} not found in data',
                'available_parameters': available
            }), 400
        
        # Check if coordinates exist
        coord_system = detect_coordinates_system(df)
        if coord_system is None:
            return jsonify({
                'error': 'Could not detect coordinate system',
                'hint': 'Ensure data has Latitude/Longitude or Easting/Northing columns'
            }), 400
        
        # Convert to lat/lon
        df = convert_to_latlon(df, coord_system)
        
        if df is None or 'lat' not in df.columns or 'lon' not in df.columns:
            return jsonify({'error': 'Could not convert coordinates to lat/lon'}), 400
        
        # Generate contour plot
        plot_buf, error = generate_contour_plot(
            df, parameter, 
            title=f'{parameter} Distribution',
            colormap=colormap,
            show_contours=show_contours,
            show_scatter=show_scatter
        )
        
        if error:
            return jsonify({'error': error}), 400
        
        # Convert to base64
        plot_base64 = base64.b64encode(plot_buf.getvalue()).decode('utf-8')
        
        # Return result
        result = {
            'image': plot_base64,
            'parameter': parameter,
            'colormap': colormap,
            'parse_method': parse_method,
            'coord_system': coord_system,
            'row_count': len(df)
        }
        
        # If GEE is available, add satellite imagery
        if HAS_GEE:
            try:
                # Get bounds
                bounds = {
                    'north': float(df['lat'].max()),
                    'south': float(df['lat'].min()),
                    'east': float(df['lon'].max()),
                    'west': float(df['lon'].min())
                }
                result['gee_available'] = True
                result['bounds'] = bounds
            except Exception as e:
                print(f"GEE bounds error: {e}")
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

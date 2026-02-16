#!/usr/bin/env python3
"""
Groundwater Mapper Processing Script
This script handles Excel data processing, interpolation, and map generation.
It replicates the functionality from the original Streamlit app.
"""

import argparse
import json
import sys
import pandas as pd
import numpy as np
from scipy.interpolate import griddata
from scipy.spatial import ConvexHull
import warnings
warnings.filterwarnings('ignore')

# Try to import visualization libraries
try:
    import folium
    from folium import plugins
    HAS_FOLIUM = True
except ImportError:
    HAS_FOLIUM = False

try:
    import matplotlib.pyplot as plt
    import matplotlib.colors as mcolors
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


def detect_utm_zone(lon, lat):
    """Detect UTM zone from longitude and latitude."""
    zone_number = int((lon + 180) / 6) + 1
    if lat >= 0:
        return zone_number, 'N'
    else:
        return zone_number, 'S'


def detect_aquifer_stratification(df, x_col, y_col, value_col):
    """
    Detect aquifer stratification using depth-to-water values.
    Returns various aquifer parameters.
    """
    try:
        x = df[x_col].values
        y = df[y_col].values
        values = df[value_col].values
        
        # Calculate statistics
        mean_val = np.nanmean(values)
        std_val = np.nanstd(values)
        min_val = np.nanmin(values)
        max_val = np.nanmax(values)
        
        # Detect stratification based on value distribution
        values_sorted = np.sort(values[~np.isnan(values)])
        if len(values_sorted) >= 3:
            # Use percentile-based stratification
            p25 = np.percentile(values_sorted, 25)
            p50 = np.percentile(values_sorted, 50)
            p75 = np.percentile(values_sorted, 75)
            
            stratification = {
                'shallow': {'min': min_val, 'max': p25},
                'intermediate': {'min': p25, 'max': p50},
                'deep': {'min': p50, 'max': p75},
                'very_deep': {'min': p75, 'max': max_val}
            }
        else:
            stratification = {
                'shallow': {'min': min_val, 'max': mean_val - std_val/2},
                'intermediate': {'min': mean_val - std_val/2, 'max': mean_val + std_val/2},
                'deep': {'min': mean_val + std_val/2, 'max': max_val}
            }
        
        return {
            'mean': float(mean_val),
            'std': float(std_val),
            'min': float(min_val),
            'max': float(max_val),
            'stratification': stratification
        }
    except Exception as e:
        return {'error': str(e)}


def interpolate_data(df, x_col, y_col, value_col, method='cubic', num_points=100):
    """
    Interpolate scattered data to a regular grid.
    """
    try:
        x = df[x_col].values
        y = df[y_col].values
        values = df[value_col].values
        
        # Remove NaN values
        valid_mask = ~np.isnan(values) & ~np.isnan(x) & ~np.isnan(y)
        x = x[valid_mask]
        y = y[valid_mask]
        values = values[valid_mask]
        
        if len(x) < 3:
            return {'error': 'Insufficient valid data points for interpolation'}
        
        # Create bounding box
        x_min, x_max = x.min(), x.max()
        y_min, y_max = y.min(), y.max()
        
        # Add small padding
        x_pad = (x_max - x_min) * 0.1
        y_pad = (y_max - y_min) * 0.1
        
        # Create grid
        xi = np.linspace(x_min - x_pad, x_max + x_pad, num_points)
        yi = np.linspace(y_min - y_pad, y_max + y_pad, num_points)
        Xi, Yi = np.meshgrid(xi, yi)
        
        # Interpolate
        if method == 'cubic' and len(x) < 4:
            method = 'linear'
        
        Zi = griddata((x, y), values, (Xi, Yi), method=method)
        
        return {
            'x': xi.tolist(),
            'y': yi.tolist(),
            'z': Zi.tolist(),
            'values': values.tolist(),
            'points': [[float(x[i]), float(y[i]), float(values[i])] for i in range(len(x))],
            'bounds': {
                'min_x': float(x_min - x_pad),
                'max_x': float(x_max + x_pad),
                'min_y': float(y_min - y_pad),
                'max_y': float(y_max + y_pad)
            },
            'statistics': {
                'mean': float(np.nanmean(values)),
                'std': float(np.nanstd(values)),
                'min': float(np.nanmin(values)),
                'max': float(np.nanmax(values)),
                'count': int(len(values))
            }
        }
    except Exception as e:
        return {'error': str(e)}


def generate_folium_map(interp_result, colormap='viridis', parameter='GW Level'):
    """
    Generate an interactive Folium map with the interpolated data.
    """
    if not HAS_FOLIUM:
        return {'error': 'Folium library not available'}
    
    try:
        x = interp_result['x']
        y = interp_result['y']
        z = np.array(interp_result['z'])
        bounds = interp_result['bounds']
        points = interp_result['points']
        
        # Calculate center
        center_lat = (bounds['min_y'] + bounds['max_y']) / 2
        center_lon = (bounds['min_x'] + bounds['max_x']) / 2
        
        # Create base map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=12,
            tiles='CartoDB positron'
        )
        
        # Normalize values for colormap
        z_min = np.nanmin(z)
        z_max = np.nanmax(z)
        
        if z_max == z_min:
            z_normalized = np.zeros_like(z)
        else:
            z_normalized = (z - z_min) / (z_max - z_min)
        
        # Get colormap colors
        cmap = plt.cm.get_cmap(colormap) if HAS_MATPLOTLIB else None
        
        # Create image overlay
        import base64
        from io import BytesIO
        
        if HAS_MATPLOTLIB:
            fig, ax = plt.subplots(figsize=(10, 8))
            im = ax.imshow(z_normalized, extent=[bounds['min_x'], bounds['max_x'], 
                                                bounds['min_y'], bounds['max_y']],
                          origin='lower', cmap=colormap, alpha=0.7)
            ax.scatter([p[0] for p in points], [p[1] for p in points], 
                      c='red', s=50, edgecolors='black', linewidth=1, zorder=5)
            plt.colorbar(im, label=parameter)
            ax.set_xlabel('Easting (m)')
            ax.set_ylabel('Northing (m)')
            ax.set_title(f'{parameter} Map')
            
            # Save to buffer
            buf = BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close(fig)
            
            # Add image overlay
            img_url = f'data:image/png;base64,{img_base64}'
            folium.raster_layers.ImageOverlay(
                image=img_url,
                bounds=[[bounds['min_y'], bounds['min_x']], 
                        [bounds['max_y'], bounds['max_x']]]
            ).add_to(m)
        
        # Add marker cluster for original points
        marker_cluster = plugins.MarkerCluster().add_to(m)
        
        for point in points:
            folium.CircleMarker(
                location=[point[1], point[0]],
                radius=8,
                popup=f'<b>{parameter}</b>: {point[2]:.2f}',
                color='red',
                fill=True,
                fillColor='red',
                fillOpacity=0.7
            ).add_to(marker_cluster)
        
        # Fit bounds
        m.fit_bounds([[bounds['min_y'], bounds['min_x']], 
                     [bounds['max_y'], bounds['max_x']]])
        
        # Get HTML
        map_html = m._repr_html_()
        
        return {
            'map_html': map_html,
            'center': [center_lat, center_lon],
            'bounds': bounds
        }
        
    except Exception as e:
        return {'error': str(e)}


def process_excel_file(file_path, parameter_col, x_col='Easting', y_col='Northing'):
    """
    Main processing function for Excel file.
    """
    try:
        # Read Excel file
        df = pd.read_excel(file_path)
        
        # Clean column names
        df.columns = df.columns.str.strip()
        
        # Find relevant columns
        available_cols = df.columns.tolist()
        
        # Auto-detect column types if not specified
        if x_col not in available_cols:
            # Try to find easting/x columns
            for col in available_cols:
                if 'east' in col.lower() or col.lower() in ['x', 'e']:
                    x_col = col
                    break
        
        if y_col not in available_cols:
            # Try to find northing/y columns
            for col in available_cols:
                if 'north' in col.lower() or col.lower() in ['y', 'n']:
                    y_col = col
                    break
        
        if x_col not in available_cols or y_col not in available_cols:
            return {'error': f'Could not find coordinate columns. Available: {available_cols}'}
        
        # Validate data
        if x_col not in df.columns or y_col not in df.columns or parameter_col not in df.columns:
            return {'error': f'Missing required columns. Available: {available_cols}'}
        
        # Convert to numeric
        df[x_col] = pd.to_numeric(df[x_col], errors='coerce')
        df[y_col] = pd.to_numeric(df[y_col], errors='coerce')
        df[parameter_col] = pd.to_numeric(df[parameter_col], errors='coerce')
        
        # Interpolate data
        interp_result = interpolate_data(df, x_col, y_col, parameter_col)
        
        if 'error' in interp_result:
            return interp_result
        
        # Detect aquifer stratification
        aquifer_data = detect_aquifer_stratification(df, x_col, y_col, parameter_col)
        
        return {
            'success': True,
            'interpolation': interp_result,
            'aquifer': aquifer_data,
            'columns': {
                'x': x_col,
                'y': y_col,
                'parameter': parameter_col
            },
            'data_points': len(df)
        }
        
    except Exception as e:
        return {'error': str(e)}


def main():
    parser = argparse.ArgumentParser(description='Groundwater Mapper Processing')
    parser.add_argument('--input', required=True, help='Input Excel file path')
    parser.add_argument('--parameter', required=True, help='Parameter column name')
    parser.add_argument('--colormap', default='viridis', help='Colormap name')
    parser.add_argument('--x-col', default='Easting', help='X coordinate column')
    parser.add_argument('--y-col', default='Northing', help='Y coordinate column')
    parser.add_argument('--output', help='Output JSON file path')
    
    args = parser.parse_args()
    
    # Process the file
    result = process_excel_file(args.input, args.parameter, args.x_col, args.y_col)
    
    # Generate map if successful
    if 'success' in result and HAS_FOLIUM:
        try:
            map_result = generate_folium_map(result['interpolation'], args.colormap, args.parameter)
            result['map'] = map_result
        except Exception as e:
            result['map_error'] = str(e)
    
    # Output result
    output = json.dumps(result)
    
    if args.output:
        with open(args.output, 'w') as f:
            f.write(output)
    else:
        print(output)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

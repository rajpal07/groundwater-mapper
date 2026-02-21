"""
Contour generation service for groundwater visualization.
Handles interpolation, contour plotting, and map generation.
"""

import os
import io
import base64
import logging
from typing import Optional, Tuple, Dict, Any, List

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from matplotlib import cm
from scipy.interpolate import griddata
from scipy.ndimage import gaussian_filter

# Configure logging
logger = logging.getLogger(__name__)


def check_gee_available() -> bool:
    """
    Check if Google Earth Engine credentials are available.
    
    Checks for GEE in order:
    1. EARTHENGINE_TOKEN environment variable (JSON string)
    2. Secret file at /etc/secrets/gee-service-account.json (or path in GEE_SECRET_FILE env var)
    3. Auto-detect ANY .json file in /etc/secrets/ (for Render secret files)
    4. Standard GEE credentials file ~/.config/gcloud/application_default_credentials.json
    """
    # Check 1: Environment variable
    if os.getenv("EARTHENGINE_TOKEN"):
        return True
    
    # Check 2: Secret file (for Render deployment)
    secret_file = os.environ.get('GEE_SECRET_FILE', '/etc/secrets/gee-service-account.json')
    if os.path.exists(secret_file):
        return True
    
    # Check 3: Auto-detect any JSON file in /etc/secrets/ (for Render secret files)
    secrets_dir = '/etc/secrets'
    if os.path.exists(secrets_dir):
        try:
            for filename in os.listdir(secrets_dir):
                if filename.endswith('.json'):
                    return True
        except Exception as e:
            print(f"Warning: Error scanning secrets directory: {e}")
    
    # Check 4: Standard GCP credentials file
    gcp_creds = os.path.expanduser("~/.config/gcloud/application_default_credentials.json")
    if os.path.exists(gcp_creds):
        return True
    
    return False


# Helper function to find any JSON file in secrets directory
def find_secret_json_file() -> Optional[str]:
    """Find any JSON file in the secrets directory."""
    secrets_dir = '/etc/secrets'
    if os.path.exists(secrets_dir):
        try:
            for filename in os.listdir(secrets_dir):
                if filename.endswith('.json'):
                    return os.path.join(secrets_dir, filename)
        except Exception as e:
            logger.warning(f"Error scanning secrets directory: {e}")
    return None


# Google Earth Engine availability
GEE_AVAILABLE = False
try:
    import ee
    # Check if credentials are available
    if check_gee_available():
        gee_token = os.getenv("EARTHENGINE_TOKEN")
        secret_file = os.environ.get('GEE_SECRET_FILE', '/etc/secrets/gee-service-account.json')
        
        try:
            if gee_token:
                # Use environment variable token
                import json
                import tempfile
                try:
                    if isinstance(gee_token, str):
                        credentials = json.loads(gee_token)
                    else:
                        credentials = gee_token
                    
                    # Write to temp file
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                        json.dump(credentials, f)
                        temp_path = f.name
                    
                    # Extract project_id from credentials for ee.Initialize
                    project_id = credentials.get('project_id', 'geekahn')
                    ee.Initialize(credentials=temp_path, project=project_id)
                    GEE_AVAILABLE = True
                    logger.info(f"Google Earth Engine initialized successfully from env var with project: {project_id}")
                except Exception as e:
                    logger.warning(f"Failed to initialize GEE from env var: {e}")
            elif os.path.exists(secret_file):
                # Use secret file - extract project_id from the file
                import json
                with open(secret_file, 'r') as f:
                    creds = json.load(f)
                    project_id = creds.get('project_id', 'geekahn')
                ee.Initialize(credentials=secret_file, project=project_id)
                GEE_AVAILABLE = True
                logger.info(f"Google Earth Engine initialized successfully from secret file with project: {project_id}")
            else:
                # Auto-detect any JSON file in /etc/secrets/ (for Render secret files)
                auto_detected_file = find_secret_json_file()
                if auto_detected_file:
                    # Extract project_id from the file
                    import json
                    with open(auto_detected_file, 'r') as f:
                        creds = json.load(f)
                        project_id = creds.get('project_id', 'geekahn')
                    ee.Initialize(credentials=auto_detected_file, project=project_id)
                    GEE_AVAILABLE = True
                    logger.info(f"Google Earth Engine initialized successfully from auto-detected secret file: {auto_detected_file} with project: {project_id}")
                else:
                    logger.warning("No GEE credentials found")
        except Exception as e:
            logger.warning(f"Failed to initialize GEE: {e}")
except ImportError:
    logger.warning("Google Earth Engine not installed")


class ContourGeneratorService:
    """Service for generating contour plots and maps."""
    
    def __init__(self):
        self.gee_available = GEE_AVAILABLE
    
    def generate_contour_plot(
        self,
        df: pd.DataFrame,
        parameter: str,
        lat_col: str = "Latitude",
        lon_col: str = "Longitude",
        colormap: str = "viridis",
        show_contours: bool = True,
        show_scatter: bool = True,
        title: Optional[str] = None,
        resolution: int = 100,
        interpolation_method: str = "linear",
        smooth_sigma: float = 0.5
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate a contour plot from point data.
        
        Args:
            df: DataFrame with coordinates and parameter values
            parameter: Column name for the parameter to visualize
            lat_col: Latitude column name
            lon_col: Longitude column name
            colormap: Matplotlib colormap name
            show_contours: Whether to show filled contours
            show_scatter: Whether to show scatter points
            title: Custom plot title
            resolution: Grid resolution for interpolation
            interpolation_method: 'linear', 'cubic', or 'nearest'
            smooth_sigma: Gaussian smoothing sigma
            
        Returns:
            Tuple of (base64_encoded_image, metadata_dict)
        """
        # Extract valid data
        lat = pd.to_numeric(df[lat_col], errors='coerce')
        lon = pd.to_numeric(df[lon_col], errors='coerce')
        values = pd.to_numeric(df[parameter], errors='coerce')
        
        # Filter valid points
        valid_mask = ~(lat.isna() | lon.isna() | values.isna())
        lat_valid = lat[valid_mask].values
        lon_valid = lon[valid_mask].values
        values_valid = values[valid_mask].values
        
        if len(lat_valid) < 3:
            raise ValueError(f"Need at least 3 valid data points, got {len(lat_valid)}")
        
        logger.info(f"Generating contour plot for {parameter}: {len(lat_valid)} valid points")
        
        # Create grid for interpolation
        lat_min, lat_max = lat_valid.min(), lat_valid.max()
        lon_min, lon_max = lon_valid.min(), lon_valid.max()
        
        # Add padding
        lat_padding = (lat_max - lat_min) * 0.1
        lon_padding = (lon_max - lon_min) * 0.1
        
        lat_range = np.linspace(lat_min - lat_padding, lat_max + lat_padding, resolution)
        lon_range = np.linspace(lon_min - lon_padding, lon_max + lon_padding, resolution)
        
        lon_grid, lat_grid = np.meshgrid(lon_range, lat_range)
        
        # Interpolate values onto grid
        try:
            grid_values = griddata(
                points=(lon_valid, lat_valid),
                values=values_valid,
                xi=(lon_grid, lat_grid),
                method=interpolation_method,
                fill_value=np.nan
            )
        except Exception as e:
            logger.warning(f"Interpolation failed, falling back to nearest: {e}")
            grid_values = griddata(
                points=(lon_valid, lat_valid),
                values=values_valid,
                xi=(lon_grid, lat_grid),
                method='nearest'
            )
        
        # Apply Gaussian smoothing
        if smooth_sigma > 0:
            # Only smooth non-NaN values
            valid_grid = ~np.isnan(grid_values)
            if valid_grid.any():
                grid_values_smooth = gaussian_filter(
                    np.nan_to_num(grid_values, nan=0),
                    sigma=smooth_sigma
                )
                # Restore NaN values
                grid_values_smooth[~valid_grid] = np.nan
                grid_values = grid_values_smooth
        
        # Create figure
        fig, ax = plt.subplots(figsize=(12, 10), dpi=100)
        
        # Plot contours
        if show_contours:
            # Filled contours
            levels = np.linspace(np.nanmin(grid_values), np.nanmax(grid_values), 20)
            contour_fill = ax.contourf(
                lon_grid, lat_grid, grid_values,
                levels=levels,
                cmap=colormap,
                alpha=0.8
            )
            
            # Contour lines
            contour_lines = ax.contour(
                lon_grid, lat_grid, grid_values,
                levels=levels,
                colors='black',
                linewidths=0.5,
                alpha=0.5
            )
            
            # Add colorbar
            cbar = plt.colorbar(contour_fill, ax=ax, shrink=0.8)
            cbar.set_label(parameter, fontsize=12)
        
        # Plot scatter points
        if show_scatter:
            scatter = ax.scatter(
                lon_valid, lat_valid,
                c=values_valid,
                cmap=colormap,
                s=50,
                edgecolors='black',
                linewidths=1,
                zorder=5
            )
        
        # Set labels and title
        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        
        if title:
            ax.set_title(title, fontsize=14, fontweight='bold')
        else:
            ax.set_title(f'{parameter} Contour Map', fontsize=14, fontweight='bold')
        
        # Add grid
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Set aspect ratio
        ax.set_aspect('equal', adjustable='box')
        
        # Tight layout
        plt.tight_layout()
        
        # Convert to base64
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        plt.close(fig)
        
        # Metadata
        metadata = {
            "parameter": parameter,
            "colormap": colormap,
            "row_count": len(lat_valid),
            "interpolation_method": interpolation_method,
            "resolution": resolution,
            "min_value": float(np.nanmin(values_valid)),
            "max_value": float(np.nanmax(values_valid)),
            "mean_value": float(np.nanmean(values_valid)),
            "bounds": {
                "min_lat": float(lat_min),
                "max_lat": float(lat_max),
                "min_lon": float(lon_min),
                "max_lon": float(lon_max)
            }
        }
        
        return image_base64, metadata
    
    def generate_multi_layer_map(
        self,
        df: pd.DataFrame,
        parameter: str,
        layer_column: str,
        lat_col: str = "Latitude",
        lon_col: str = "Longitude",
        colormap_per_layer: Optional[Dict[str, str]] = None,
        show_legend: bool = True,
        opacity: float = 0.7
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Generate a multi-layer contour map for different aquifer layers.
        
        Args:
            df: DataFrame with coordinates, parameter, and layer column
            parameter: Column name for the parameter to visualize
            layer_column: Column name for layer separation
            colormap_per_layer: Custom colormap for each layer
            show_legend: Whether to show legend
            opacity: Layer opacity
            
        Returns:
            Tuple of (base64_encoded_image, metadata_dict)
        """
        # Get unique layers
        layers = df[layer_column].dropna().unique()
        
        if len(layers) < 1:
            raise ValueError(f"No valid layers found in column '{layer_column}'")
        
        # Default colormaps
        default_colormaps = ['viridis', 'plasma', 'inferno', 'magma', 'cividis']
        
        # Create figure
        fig, ax = plt.subplots(figsize=(14, 10), dpi=100)
        
        legend_info = {}
        
        for i, layer in enumerate(layers):
            layer_df = df[df[layer_column] == layer]
            
            if len(layer_df) < 3:
                logger.warning(f"Skipping layer {layer}: only {len(layer_df)} points")
                continue
            
            # Get colormap for this layer
            cmap = colormap_per_layer.get(str(layer), default_colormaps[i % len(default_colormaps)]) if colormap_per_layer else default_colormaps[i % len(default_colormaps)]
            
            # Generate contour for this layer
            lat = pd.to_numeric(layer_df[lat_col], errors='coerce')
            lon = pd.to_numeric(layer_df[lon_col], errors='coerce')
            values = pd.to_numeric(layer_df[parameter], errors='coerce')
            
            valid_mask = ~(lat.isna() | lon.isna() | values.isna())
            
            if valid_mask.sum() < 3:
                continue
            
            lat_valid = lat[valid_mask].values
            lon_valid = lon[valid_mask].values
            values_valid = values[valid_mask].values
            
            # Create grid
            lat_min, lat_max = lat_valid.min(), lat_valid.max()
            lon_min, lon_max = lon_valid.min(), lon_valid.max()
            
            lat_padding = (lat_max - lat_min) * 0.1
            lon_padding = (lon_max - lon_min) * 0.1
            
            resolution = 80
            lat_range = np.linspace(lat_min - lat_padding, lat_max + lat_padding, resolution)
            lon_range = np.linspace(lon_min - lon_padding, lon_max + lon_padding, resolution)
            
            lon_grid, lat_grid = np.meshgrid(lon_range, lat_range)
            
            # Interpolate
            grid_values = griddata(
                points=(lon_valid, lat_valid),
                values=values_valid,
                xi=(lon_grid, lat_grid),
                method='linear',
                fill_value=np.nan
            )
            
            # Plot contours
            levels = np.linspace(np.nanmin(grid_values), np.nanmax(grid_values), 15)
            contour = ax.contourf(
                lon_grid, lat_grid, grid_values,
                levels=levels,
                cmap=cmap,
                alpha=opacity
            )
            
            # Scatter points
            ax.scatter(
                lon_valid, lat_valid,
                c=values_valid,
                cmap=cmap,
                s=30,
                edgecolors='white',
                linewidths=0.5,
                alpha=0.8
            )
            
            legend_info[str(layer)] = cmap
        
        # Labels and title
        ax.set_xlabel('Longitude', fontsize=12)
        ax.set_ylabel('Latitude', fontsize=12)
        ax.set_title(f'{parameter} - Multi-Layer Map', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Add legend
        if show_legend and legend_info:
            legend_elements = [plt.Rectangle((0, 0), 1, 1, fc='gray', alpha=opacity, label=f'Layer: {layer}') 
                              for layer in legend_info.keys()]
            ax.legend(handles=legend_elements, loc='upper right')
        
        plt.tight_layout()
        
        # Convert to base64
        buffer = io.BytesIO()
        fig.savefig(buffer, format='png', dpi=100, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        plt.close(fig)
        
        metadata = {
            "parameter": parameter,
            "layer_column": layer_column,
            "layers": list(legend_info.keys()),
            "layer_count": len(legend_info),
            "legend": legend_info
        }
        
        return image_base64, metadata


# Global service instance
contour_generator = ContourGeneratorService()


def generate_contour_plot(
    df: pd.DataFrame,
    parameter: str,
    **kwargs
) -> Tuple[str, Dict[str, Any]]:
    """Convenience function for contour plot generation."""
    return contour_generator.generate_contour_plot(df, parameter, **kwargs)

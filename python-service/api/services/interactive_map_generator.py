"""
Interactive Map Generator Service.
Creates folium-based interactive HTML maps with contour overlays.
"""

import base64
import io
import logging
from typing import Optional, List, Dict, Any, Tuple
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib import cm
import folium
from folium.raster_layers import ImageOverlay
from folium.vector_layers import CircleMarker
from scipy.interpolate import griddata

from api.models import WellPoint, CoordinateSystemInfo
from api.services.coordinate_converter import CoordinateConverterService

logger = logging.getLogger(__name__)


class InteractiveMapGeneratorService:
    """Service for generating interactive folium-based HTML maps."""
    
    # Google Hybrid basemap tiles
    GOOGLE_HYBRID_TILES = 'https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}'
    GOOGLE_SATELLITE_TILES = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
    
    # Colormap definitions for legend
    COLORMAPS = {
        'viridis': {'low': '#440154', 'mid': '#31688E', 'high': '#FDE725', 'high_desc': 'High', 'low_desc': 'Low'},
        'plasma': {'low': '#0D0887', 'mid': '#CC4778', 'high': '#F0F921', 'high_desc': 'High', 'low_desc': 'Low'},
        'inferno': {'low': '#000004', 'mid': '#BC3754', 'high': '#FCFFA4', 'high_desc': 'High', 'low_desc': 'Low'},
        'magma': {'low': '#000004', 'mid': '#8B0AA5', 'high': '#FEFBBF', 'high_desc': 'High', 'low_desc': 'Low'},
        'cividis': {'low': '#00204D', 'mid': '#7C7B78', 'high': '#FFE945', 'high_desc': 'High', 'low_desc': 'Low'},
        'coolwarm': {'low': '#3B4CC0', 'mid': '#BFBFBF', 'high': '#B40426', 'high_desc': 'High', 'low_desc': 'Low'},
        'RdYlBu': {'low': '#313695', 'mid': '#FFFFBF', 'high': '#A50026', 'high_desc': 'High', 'low_desc': 'Low'},
        'RdYlGn': {'low': '#1A9641', 'mid': '#FFFFBF', 'high': '#D7191C', 'high_desc': 'High', 'low_desc': 'Low'},
        'jet': {'low': '#000080', 'mid': '#00FF00', 'high': '#800000', 'high_desc': 'High', 'low_desc': 'Low'},
        'rainbow': {'low': '#0000FF', 'mid': '#00FF00', 'high': '#FF0000', 'high_desc': 'High', 'low_desc': 'Low'},
    }
    
    def __init__(self):
        self.coord_converter = CoordinateConverterService()
    
    def get_colormap_info(self, colormap_name: str) -> Tuple[str, str, str, str, str]:
        """
        Get colormap hex codes and labels.
        
        Returns:
            Tuple of (low_hex, mid_hex, high_hex, high_desc, low_desc)
        """
        info = self.COLORMAPS.get(colormap_name, self.COLORMAPS['viridis'])
        return info['low'], info['mid'], info['high'], info['high_desc'], info['low_desc']
    
    def generate_contour_image(
        self,
        easting: np.ndarray,
        northing: np.ndarray,
        values: np.ndarray,
        colormap: str = 'viridis',
        resolution: int = 100,
        show_contours: bool = True
    ) -> Tuple[str, np.ndarray, np.ndarray, float, float, float, float, float, float]:
        """
        Generate contour image with transparent background.
        
        Returns:
            Tuple of (base64_image, grid_x, grid_y, min_val, max_val, min_x, max_x, min_y, max_y)
        """
        # Create grid for interpolation
        min_x, max_x = easting.min(), easting.max()
        min_y, max_y = northing.min(), northing.max()
        
        # Add padding
        padding_x = (max_x - min_x) * 0.1
        padding_y = (max_y - min_y) * 0.1
        min_x -= padding_x
        max_x += padding_x
        min_y -= padding_y
        max_y += padding_y
        
        # Create grid
        xi = np.linspace(min_x, max_x, resolution)
        yi = np.linspace(min_y, max_y, resolution)
        grid_x, grid_y = np.meshgrid(xi, yi)
        
        # Interpolate values
        points = np.column_stack([easting, northing])
        grid_z = griddata(points, values, (grid_x, grid_y), method='linear')
        
        # Get colormap
        cmap = cm.get_cmap(colormap)
        
        # Normalize values
        min_val = np.nanmin(values)
        max_val = np.nanmax(values)
        
        if min_val == max_val:
            min_val -= 1
            max_val += 1
        
        # Create figure with transparent background
        fig, ax = plt.subplots(figsize=(12, 10), dpi=150)
        fig.patch.set_alpha(0)
        ax.set_axis_off()
        
        if show_contours:
            # Create filled contour
            norm = mcolors.Normalize(vmin=min_val, vmax=max_val)
            contour = ax.contourf(grid_x, grid_y, grid_z, levels=20, cmap=cmap, norm=norm, alpha=0.8)
        
        # Set extent
        ax.set_xlim(min_x, max_x)
        ax.set_ylim(min_y, max_y)
        
        # Save to buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', pad_inches=0, transparent=True)
        plt.close(fig)
        buf.seek(0)
        
        # Convert to base64
        img_base64 = base64.b64encode(buf.read()).decode('utf-8')
        
        return img_base64, grid_x, grid_y, min_val, max_val, min_x, max_x, min_y, max_y
    
    def create_interactive_map(
        self,
        easting: np.ndarray,
        northing: np.ndarray,
        values: np.ndarray,
        labels: Optional[List[str]] = None,
        colormap: str = 'viridis',
        resolution: int = 100,
        show_contours: bool = True,
        show_wells: bool = True,
        show_legend: bool = True,
        show_compass: bool = True,
        show_controls: bool = True,
        legend_label: str = "Groundwater Elevation (mAHD)",
        opacity: float = 0.7,
        title: Optional[str] = None
    ) -> Tuple[str, List[WellPoint], Dict[str, float], Dict[str, str]]:
        """
        Create an interactive folium map with contour overlay and well markers.
        
        Returns:
            Tuple of (html_content, well_points, bounds, legend_colors)
        """
        # Generate contour image
        img_base64, grid_x, grid_y, min_val, max_val, min_x, max_x, min_y, max_y = self.generate_contour_image(
            easting, northing, values, colormap, resolution, show_contours
        )
        
        # Convert UTM bounds to lat/lon using pyproj directly
        center_easting = (easting.min() + easting.max()) / 2
        center_northing = (northing.min() + northing.max()) / 2
        
        # Detect UTM zone using the coordinate converter's internal method
        x_min, x_max = float(easting.min()), float(easting.max())
        y_min, y_max = float(northing.min()), float(northing.max())
        utm_zone = self.coord_converter._detect_australian_utm_zone(x_min, x_max, y_min, y_max)
        
        # Get transformer for UTM to WGS84
        transformer = self.coord_converter.get_transformer(utm_zone, southern_hemisphere=True)
        
        # Convert center to lat/lon
        center_lon, center_lat = transformer.transform(center_easting, center_northing)
        
        # Convert image bounds to lat/lon
        # Image bounds: [[south, west], [north, east]]
        sw_lon, sw_lat = transformer.transform(min_x, min_y)
        ne_lon, ne_lat = transformer.transform(max_x, max_y)
        
        image_bounds = [[sw_lat, sw_lon], [ne_lat, ne_lon]]
        
        # Create folium map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=16,
            max_zoom=19,
            zoom_control=False,
            attribution_control=False,
            tiles=self.GOOGLE_HYBRID_TILES,
            attr='Google Hybrid'
        )
        
        # Add contour overlay
        if show_contours:
            img_url = f"data:image/png;base64,{img_base64}"
            ImageOverlay(
                image=img_url,
                bounds=image_bounds,
                opacity=opacity,
                interactive=False,
                cross_origin=True,
                zindex=1,
                name="Groundwater Contour"
            ).add_to(m)
        
        # Add well markers
        well_points = []
        if show_wells:
            for i, (e, n, v) in enumerate(zip(easting, northing, values)):
                w_lon, w_lat = transformer.transform(float(e), float(n))
                lat, lon = w_lat, w_lon
                label = labels[i] if labels and i < len(labels) else f"Well {i+1}: {v:.2f}"
                
                well_point = WellPoint(
                    latitude=lat,
                    longitude=lon,
                    value=float(v),
                    label=label
                )
                well_points.append(well_point)
                
                # Add marker
                CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color='white',
                    weight=2,
                    fill=True,
                    fill_color='#FF4444',
                    fill_opacity=0.9,
                    popup=folium.Popup(label, max_width=200),
                    tooltip=label,
                    z_index_offset=1000
                ).add_to(m)
        
        # Fit bounds to data
        m.fit_bounds(image_bounds)
        
        # Get HTML content
        html_content = m._repr_html_()
        
        # Inject controls if requested
        if show_legend or show_compass or show_controls:
            html_content = self._inject_controls(
                html_content,
                colormap=colormap,
                min_val=min_val,
                max_val=max_val,
                legend_label=legend_label,
                show_legend=show_legend,
                show_compass=show_compass,
                show_controls=show_controls,
                title=title
            )
        
        # Prepare bounds
        bounds = {
            'south': sw_lat,
            'west': sw_lon,
            'north': ne_lat,
            'east': ne_lon,
            'center_lat': center_lat,
            'center_lon': center_lon
        }
        
        # Get legend colors
        low_hex, mid_hex, high_hex, high_desc, low_desc = self.get_colormap_info(colormap)
        legend_colors = {
            'low': low_hex,
            'mid': mid_hex,
            'high': high_hex,
            'high_desc': high_desc,
            'low_desc': low_desc
        }
        
        return html_content, well_points, bounds, legend_colors
    
    def create_interactive_map_from_dataframe(
        self,
        df: pd.DataFrame,
        parameter: str,
        easting_col: Optional[str] = None,
        northing_col: Optional[str] = None,
        lat_col: Optional[str] = None,
        lon_col: Optional[str] = None,
        label_col: Optional[str] = None,
        colormap: str = 'viridis',
        resolution: int = 100,
        show_contours: bool = True,
        show_wells: bool = True,
        show_legend: bool = True,
        show_compass: bool = True,
        show_controls: bool = True,
        legend_label: Optional[str] = None,
        opacity: float = 0.7,
        title: Optional[str] = None,
        interpolation_method: str = 'linear'
    ) -> Tuple[str, List[WellPoint], Dict[str, float], Dict[str, str], CoordinateSystemInfo]:
        """
        Create an interactive map from a DataFrame.
        
        Automatically detects coordinate system and converts to lat/lon for folium.
        
        Args:
            df: DataFrame with coordinate and parameter data
            parameter: Column name for the parameter to visualize
            easting_col: Column name for easting (X) coordinates
            northing_col: Column name for northing (Y) coordinates
            lat_col: Column name for latitude
            lon_col: Column name for longitude
            label_col: Column name for well labels
            colormap: Matplotlib colormap name
            resolution: Grid resolution for interpolation
            show_contours: Whether to show contour overlay
            show_wells: Whether to show well markers
            show_legend: Whether to show legend
            show_compass: Whether to show compass
            show_controls: Whether to show map controls
            legend_label: Label for the legend
            opacity: Opacity of contour overlay
            title: Title for the map
            interpolation_method: Interpolation method (linear, cubic, nearest)
            
        Returns:
            Tuple of (html_content, well_points, bounds, legend_colors, coord_info)
        """
        # Detect coordinate columns if not provided
        if lat_col is None and lon_col is None:
            # Try to detect lat/lon columns
            lat_candidates = ['lat', 'latitude', 'Lat', 'Latitude', 'LAT', 'LATITUDE']
            lon_candidates = ['lon', 'long', 'longitude', 'Lon', 'Long', 'Longitude', 'LON', 'LONG', 'LONGITUDE']
            
            for col in df.columns:
                if col in lat_candidates:
                    lat_col = col
                if col in lon_candidates:
                    lon_col = col
        
        if easting_col is None and northing_col is None:
            # Try to detect UTM columns
            easting_candidates = ['easting', 'x', 'Easting', 'X', 'EASTING', 'utm_e', 'utm_x']
            northing_candidates = ['northing', 'y', 'Northing', 'Y', 'NORTHING', 'utm_n', 'utm_y']
            
            for col in df.columns:
                if col in easting_candidates:
                    easting_col = col
                if col in northing_candidates:
                    northing_col = col
        
        # Determine coordinate system
        is_latlon = lat_col is not None and lon_col is not None
        is_utm = easting_col is not None and northing_col is not None
        
        if not is_latlon and not is_utm:
            raise ValueError("Could not detect coordinate columns. Please specify easting_col/northing_col or lat_col/lon_col.")
        
        # Extract data
        values = df[parameter].values
        labels = df[label_col].tolist() if label_col else None
        
        # Set default legend label
        if legend_label is None:
            legend_label = parameter
        
        if is_latlon:
            # Already in lat/lon - create map directly
            lats = df[lat_col].values
            lons = df[lon_col].values
            
            # For lat/lon data, we need to create a different approach
            # since the contour generator expects UTM coordinates
            # We'll create a simple map with markers for now
            center_lat = np.mean(lats)
            center_lon = np.mean(lons)
            
            # Create folium map
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=14,
                max_zoom=19,
                zoom_control=False,
                attribution_control=False,
                tiles=self.GOOGLE_HYBRID_TILES,
                attr='Google Hybrid'
            )
            
            # Add well markers
            well_points = []
            min_val = np.nanmin(values)
            max_val = np.nanmax(values)
            
            for i, (lat, lon, v) in enumerate(zip(lats, lons, values)):
                label = labels[i] if labels and i < len(labels) else f"Well {i+1}: {v:.2f}"
                
                well_point = WellPoint(
                    latitude=float(lat),
                    longitude=float(lon),
                    value=float(v),
                    label=label
                )
                well_points.append(well_point)
                
                # Add marker
                CircleMarker(
                    location=[lat, lon],
                    radius=6,
                    color='white',
                    weight=2,
                    fill=True,
                    fill_color='#FF4444',
                    fill_opacity=0.9,
                    popup=folium.Popup(label, max_width=200),
                    tooltip=label,
                    z_index_offset=1000
                ).add_to(m)
            
            # Fit bounds
            bounds = {
                'south': float(np.min(lats)),
                'west': float(np.min(lons)),
                'north': float(np.max(lats)),
                'east': float(np.max(lons)),
                'center_lat': float(center_lat),
                'center_lon': float(center_lon)
            }
            m.fit_bounds([[bounds['south'], bounds['west']], [bounds['north'], bounds['east']]])
            
            # Get HTML
            html_content = m._repr_html_()
            
            # Inject controls
            if show_legend or show_compass or show_controls:
                html_content = self._inject_controls(
                    html_content,
                    colormap=colormap,
                    min_val=min_val,
                    max_val=max_val,
                    legend_label=legend_label,
                    show_legend=show_legend,
                    show_compass=show_compass,
                    show_controls=show_controls,
                    title=title
                )
            
            # Get legend colors
            low_hex, mid_hex, high_hex, high_desc, low_desc = self.get_colormap_info(colormap)
            legend_colors = {
                'low': low_hex,
                'mid': mid_hex,
                'high': high_hex,
                'high_desc': high_desc,
                'low_desc': low_desc
            }
            
            coord_info = CoordinateSystemInfo(
                type="latlon",
                utm_zone=None,
                epsg_code="EPSG:4326",
                easting_column=None,
                northing_column=None,
                latitude_column=lat_col,
                longitude_column=lon_col,
                bounds=bounds
            )
            
            return html_content, well_points, bounds, legend_colors, coord_info
        
        else:
            # UTM coordinates - use the existing method
            easting = df[easting_col].values
            northing = df[northing_col].values
            
            # Detect UTM zone
            center_easting = np.mean(easting)
            center_northing = np.mean(northing)
            utm_zone = self.coord_converter.detect_utm_zone(center_easting, center_northing)
            
            # Call the existing method
            html_content, well_points, bounds, legend_colors = self.create_interactive_map(
                easting=easting,
                northing=northing,
                values=values,
                labels=labels,
                colormap=colormap,
                resolution=resolution,
                show_contours=show_contours,
                show_wells=show_wells,
                show_legend=show_legend,
                show_compass=show_compass,
                show_controls=show_controls,
                legend_label=legend_label,
                opacity=opacity,
                title=title
            )
            
            coord_info = CoordinateSystemInfo(
                type="utm",
                utm_zone=utm_zone,
                epsg_code=f"EPSG:327{utm_zone}" if utm_zone >= 50 else f"EPSG:326{utm_zone}",
                easting_column=easting_col,
                northing_column=northing_col,
                latitude_column=None,
                longitude_column=None,
                bounds=bounds
            )
            
            return html_content, well_points, bounds, legend_colors, coord_info

    def create_interactive_multi_layer_map_from_dataframe(
        self,
        df: pd.DataFrame,
        parameter: str,
        layer_column: str,
        easting_col: Optional[str] = None,
        northing_col: Optional[str] = None,
        lat_col: Optional[str] = "Latitude",
        lon_col: Optional[str] = "Longitude",
        colormap_per_layer: Optional[Dict[str, str]] = None,
        show_legend: bool = True,
        show_compass: bool = True,
        show_controls: bool = True,
        opacity: float = 0.7,
        interpolation_method: str = 'linear',
        resolution: int = 100
    ) -> Tuple[str, Dict[str, float], Dict[str, str], CoordinateSystemInfo]:
        """
        Create a multi-layer interactive map from a pandas DataFrame.
        """
        import folium
        from folium.plugins import Fullscreen, Draw, MousePosition
        from scipy.interpolate import griddata
        
        # Ensure we have coordinates
        if lat_col not in df.columns or lon_col not in df.columns:
            # Try to convert if we have UTM
            if easting_col and northing_col and easting_col in df.columns and northing_col in df.columns:
                try:
                    df = self.coord_converter.convert_to_latlon(
                        df, 
                        easting_col=easting_col, 
                        northing_col=northing_col
                    )
                except Exception as e:
                    logger.error(f"Error converting coordinates: {e}")
                    raise ValueError(f"Coordinate conversion failed: {str(e)}")
            else:
                raise ValueError(f"Missing coordinate columns: ({lat_col}, {lon_col}) or ({easting_col}, {northing_col})")

        # Get unique layers
        layers = df[layer_column].dropna().unique()
        if len(layers) == 0:
            raise ValueError(f"No valid layers found in column '{layer_column}'")

        # Default colormaps if none provided
        default_colormaps = ['viridis', 'plasma', 'inferno', 'magma', 'cividis']

        # Determine center of the all valid data
        valid_df = df.dropna(subset=[lat_col, lon_col])
        if valid_df.empty:
            raise ValueError("No valid coordinates found")
            
        center_lat = np.mean(valid_df[lat_col])
        center_lon = np.mean(valid_df[lon_col])

        # Create map
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=12,
            max_zoom=19,
            zoom_control=False,
            attribution_control=False,
            tiles=self.GOOGLE_HYBRID_TILES,
            attr='Google Hybrid'
        )

        legend_info = {}
        bounds_agg = {'south': 90, 'west': 180, 'north': -90, 'east': -180}

        for i, layer in enumerate(layers):
            layer_df = valid_df[valid_df[layer_column] == layer]
            
            # Drop bad rows for this layer
            layer_df = layer_df.dropna(subset=[parameter])
            if len(layer_df) < 3:
                logger.warning(f"Skipping layer {layer}: only {len(layer_df)} distinct points")
                continue

            lats = layer_df[lat_col].values
            lons = layer_df[lon_col].values
            values = pd.to_numeric(layer_df[parameter], errors='coerce')
            
            valid_mask = ~np.isnan(values)
            if valid_mask.sum() < 3:
                continue

            lats = lats[valid_mask]
            lons = lons[valid_mask]
            values = values[valid_mask]

            # Bounds
            bounds_agg['south'] = min(bounds_agg['south'], np.min(lats))
            bounds_agg['west'] = min(bounds_agg['west'], np.min(lons))
            bounds_agg['north'] = max(bounds_agg['north'], np.max(lats))
            bounds_agg['east'] = max(bounds_agg['east'], np.max(lons))

            # Choose colormap
            cmap_name = default_colormaps[i % len(default_colormaps)]
            if colormap_per_layer and str(layer) in colormap_per_layer:
                cmap_name = colormap_per_layer[str(layer)]
                
            try:
                import matplotlib.cm as cm
                import matplotlib.colors as colors
                cmap = cm.get_cmap(cmap_name)
            except Exception:
                cmap = cm.get_cmap('viridis')

            # Create grid
            lat_min, lat_max = np.min(lats), np.max(lats)
            lon_min, lon_max = np.min(lons), np.max(lons)
            lat_padding = (lat_max - lat_min) * 0.1
            lon_padding = (lon_max - lon_min) * 0.1
            
            lat_range = np.linspace(lat_min - lat_padding, lat_max + lat_padding, resolution)
            lon_range = np.linspace(lon_min - lon_padding, lon_max + lon_padding, resolution)
            lon_grid, lat_grid = np.meshgrid(lon_range, lat_range)
            
            # Interpolate
            grid_values = griddata(
                (lons, lats),
                values,
                (lon_grid, lat_grid),
                method=interpolation_method,
                fill_value=np.nan
            )
            
            # Create feature group for layer
            fg = folium.FeatureGroup(name=str(layer), overlay=True, control=True)

            # Convert to image for overlay
            from PIL import Image
            import io
            import base64
            
            norm = colors.Normalize(vmin=np.nanmin(grid_values), vmax=np.nanmax(grid_values))
            if np.isnan(norm.vmin) or np.isnan(norm.vmax):
                continue
                
            img_data = cmap(norm(grid_values))
            
            alpha_channel = np.where(np.isnan(grid_values), 0, opacity * 255).astype(np.uint8)
            img_data = (img_data[:, :, :3] * 255).astype(np.uint8)
            rgba_image = np.dstack((img_data, alpha_channel))
            
            img = Image.fromarray(rgba_image, 'RGBA')
            # Flip image because coordinate systems
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
            
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            data_url = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('utf-8')
            
            # Add ImageOverlay to FeatureGroup
            folium.raster_layers.ImageOverlay(
                image=data_url,
                bounds=[[lat_min - lat_padding, lon_min - lon_padding], 
                        [lat_max + lat_padding, lon_max + lon_padding]],
                opacity=opacity,
                interactive=True,
                cross_origin=False,
                zindex=1
            ).add_to(fg)

            # Add feature group to map
            fg.add_to(m)
            
            legend_info[str(layer)] = cmap_name

        # Finalize Map
        try:
            m.fit_bounds([[bounds_agg['south'], bounds_agg['west']], [bounds_agg['north'], bounds_agg['east']]])
        except Exception:
            pass

        folium.LayerControl().add_to(m)

        html_content = m._repr_html_()

        # Add generic controls
        if show_compass or show_controls:
            html_content = self._inject_controls(
                html_content,
                colormap="viridis", # Placeholder
                min_val=0, max_val=1,
                legend_label=parameter,
                show_legend=show_legend,
                show_compass=show_compass,
                show_controls=show_controls,
                title=f"{parameter} - Multi-Layer"
            )

        coord_info = CoordinateSystemInfo(
            type="latlon",
            utm_zone=None,
            epsg_code="EPSG:4326",
            easting_column=None, northing_column=None,
            latitude_column=lat_col, longitude_column=lon_col,
            bounds=bounds_agg
        )
            
        return html_content, bounds_agg, legend_info, coord_info
    
    def _inject_controls(
        self,
        html_content: str,
        colormap: str,
        min_val: float,
        max_val: float,
        legend_label: str,
        show_legend: bool,
        show_compass: bool,
        show_controls: bool,
        title: Optional[str] = None
    ) -> str:
        """
        Inject CSS and JavaScript controls into the HTML map.
        Includes legend, compass, and map controls.
        """
        # Get colormap info
        low_hex, mid_hex, high_hex, high_desc, low_desc = self.get_colormap_info(colormap)
        
        # Format values
        min_str = f"{min_val:.1f}"
        max_str = f"{max_val:.1f}"
        mid_val = (min_val + max_val) / 2
        mid_str = f"{mid_val:.1f}"
        
        # Build CSS
        css = """
        <style>
            /* Map Container */
            .map-container {
                position: relative;
                width: 100%;
                height: 100%;
            }
            
            /* Legend Styles */
            .map-legend {
                position: absolute;
                bottom: 30px;
                right: 20px;
                background: rgba(255, 255, 255, 0.95);
                padding: 15px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                z-index: 1000;
                font-family: 'Segoe UI', Arial, sans-serif;
                min-width: 150px;
                resize: both;
                overflow: auto;
            }
            
            .legend-title {
                font-weight: bold;
                font-size: 14px;
                margin-bottom: 10px;
                color: #333;
                text-align: center;
            }
            
            .legend-gradient {
                width: 30px;
                height: 150px;
                margin: 0 auto;
                border-radius: 4px;
                border: 1px solid #ccc;
            }
            
            .legend-labels {
                display: flex;
                flex-direction: column;
                justify-content: space-between;
                height: 150px;
                margin-left: 10px;
                font-size: 12px;
                color: #555;
            }
            
            .legend-container {
                display: flex;
                align-items: stretch;
            }
            
            /* Compass Styles */
            .map-compass {
                position: absolute;
                top: 20px;
                left: 20px;
                width: 80px;
                height: 80px;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 50%;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                z-index: 1000;
                cursor: move;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            
            .compass-arrow {
                width: 0;
                height: 0;
                border-left: 15px solid transparent;
                border-right: 15px solid transparent;
                border-bottom: 50px solid #c0392b;
                position: relative;
            }
            
            .compass-arrow::after {
                content: '';
                position: absolute;
                left: -15px;
                top: 50px;
                width: 0;
                height: 0;
                border-left: 15px solid transparent;
                border-right: 15px solid transparent;
                border-top: 30px solid #ecf0f1;
            }
            
            .compass-n {
                position: absolute;
                top: 5px;
                font-weight: bold;
                font-size: 14px;
                color: #333;
            }
            
            /* Map Controls */
            .map-controls {
                position: absolute;
                top: 20px;
                right: 20px;
                display: flex;
                flex-direction: column;
                gap: 10px;
                z-index: 1000;
            }
            
            .control-btn {
                width: 40px;
                height: 40px;
                background: rgba(255, 255, 255, 0.95);
                border: none;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                cursor: pointer;
                font-size: 18px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.2s;
            }
            
            .control-btn:hover {
                background: #f0f0f0;
                transform: scale(1.05);
            }
            
            /* Title */
            .map-title {
                position: absolute;
                top: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(255, 255, 255, 0.95);
                padding: 10px 20px;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.3);
                z-index: 1000;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-weight: bold;
                font-size: 16px;
                color: #333;
            }
            
            /* Footer for snapshots */
            .map-footer {
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 30px;
                background: rgba(255, 255, 255, 0.95);
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0 15px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 11px;
                color: #666;
                z-index: 999;
            }
        </style>
        """
        
        # Build HTML for legend
        legend_html = ""
        if show_legend:
            legend_html = f"""
            <div class="map-legend" id="mapLegend">
                <div class="legend-title">{legend_label}</div>
                <div class="legend-container">
                    <div class="legend-gradient" style="background: linear-gradient(to bottom, {high_hex}, {mid_hex}, {low_hex});"></div>
                    <div class="legend-labels">
                        <span>{max_str} ({high_desc})</span>
                        <span>{mid_str}</span>
                        <span>{min_str} ({low_desc})</span>
                    </div>
                </div>
            </div>
            """
        
        # Build HTML for compass
        compass_html = ""
        if show_compass:
            compass_html = """
            <div class="map-compass" id="mapCompass">
                <span class="compass-n">N</span>
                <div class="compass-arrow"></div>
            </div>
            """
        
        # Build HTML for controls
        controls_html = ""
        if show_controls:
            controls_html = """
            <div class="map-controls">
                <button class="control-btn" onclick="resetMapView()" title="Reset View">⟲</button>
                <button class="control-btn" onclick="takeSnapshot()" title="Take Snapshot">📷</button>
                <button class="control-btn" onclick="toggleLegend()" title="Toggle Legend">📊</button>
            </div>
            """
        
        # Build title HTML
        title_html = ""
        if title:
            title_html = f'<div class="map-title">{title}</div>'
        
        # Build JavaScript
        javascript = """
        <script>
            // Store initial map state
            let initialCenter, initialZoom;
            
            document.addEventListener('DOMContentLoaded', function() {
                // Get map instance
                const mapContainer = document.querySelector('.folium-map');
                if (mapContainer && mapContainer._leaflet_map) {
                    const map = mapContainer._leaflet_map;
                    initialCenter = map.getCenter();
                    initialZoom = map.getZoom();
                }
                
                // Make compass draggable
                makeDraggable('mapCompass');
                makeDraggable('mapLegend');
            });
            
            // Reset map view
            function resetMapView() {
                const mapContainer = document.querySelector('.folium-map');
                if (mapContainer && mapContainer._leaflet_map) {
                    const map = mapContainer._leaflet_map;
                    if (initialCenter && initialZoom) {
                        map.setView(initialCenter, initialZoom);
                    }
                }
            }
            
            // Toggle legend visibility
            function toggleLegend() {
                const legend = document.getElementById('mapLegend');
                if (legend) {
                    legend.style.display = legend.style.display === 'none' ? 'block' : 'none';
                }
            }
            
            // Take snapshot
            function takeSnapshot() {
                alert('Snapshot functionality requires html-to-image library. In production, this would capture the map as an image.');
            }
            
            // Make element draggable
            function makeDraggable(elementId) {
                const element = document.getElementById(elementId);
                if (!element) return;
                
                let isDragging = false;
                let offsetX, offsetY;
                
                element.addEventListener('mousedown', function(e) {
                    isDragging = true;
                    offsetX = e.clientX - element.offsetLeft;
                    offsetY = e.clientY - element.offsetTop;
                    element.style.cursor = 'grabbing';
                });
                
                document.addEventListener('mousemove', function(e) {
                    if (isDragging) {
                        element.style.left = (e.clientX - offsetX) + 'px';
                        element.style.top = (e.clientY - offsetY) + 'px';
                        element.style.right = 'auto';
                        element.style.bottom = 'auto';
                    }
                });
                
                document.addEventListener('mouseup', function() {
                    isDragging = false;
                    element.style.cursor = 'move';
                });
            }
        </script>
        """
        
        # Build footer
        footer_html = """
        <div class="map-footer">
            <span>Groundwater Mapper Pro</span>
            <span id="snapshotDate"></span>
        </div>
        """
        
        # Inject into HTML
        injection = css
        
        # Add elements before closing body tag
        body_content = ""
        if title_html:
            body_content += title_html
        if compass_html:
            body_content += compass_html
        if controls_html:
            body_content += controls_html
        if legend_html:
            body_content += legend_html
        
        body_content += footer_html
        body_content += javascript
        
        # Insert before </body>
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', body_content + '</body>')
        else:
            # If no body tag, append at the end
            html_content += body_content
        
        return html_content

"""
Coordinate conversion service for UTM to Lat/Lon conversion.
Handles coordinate system detection and transformation.
"""

import logging
from typing import Optional, Tuple, Dict, Any

import numpy as np
import pandas as pd
from pyproj import Transformer, CRS

# Configure logging
logger = logging.getLogger(__name__)


class CoordinateSystemInfo:
    """Information about detected coordinate system."""
    def __init__(
        self,
        type: str = "unknown",
        utm_zone: Optional[int] = None,
        epsg_code: Optional[str] = None,
        easting_column: Optional[str] = None,
        northing_column: Optional[str] = None,
        latitude_column: Optional[str] = None,
        longitude_column: Optional[str] = None,
        bounds: Optional[Dict[str, float]] = None
    ):
        self.type = type
        self.utm_zone = utm_zone
        self.epsg_code = epsg_code
        self.easting_column = easting_column
        self.northing_column = northing_column
        self.latitude_column = latitude_column
        self.longitude_column = longitude_column
        self.bounds = bounds or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "utm_zone": self.utm_zone,
            "epsg_code": self.epsg_code,
            "easting_column": self.easting_column,
            "northing_column": self.northing_column,
            "latitude_column": self.latitude_column,
            "longitude_column": self.longitude_column,
            "bounds": self.bounds
        }


class CoordinateConverterService:
    """Service for coordinate system detection and conversion."""
    
    # Australian UTM zones
    AUSTRALIAN_UTM_ZONES = {
        (112, 114): 50,
        (114, 120): 51,
        (120, 126): 52,
        (126, 132): 53,
        (132, 138): 54,
        (138, 144): 55,
        (144, 150): 56,
    }
    
    # Common column name patterns
    EASTING_PATTERNS = ['easting', 'x', 'east', 'utm_x', 'utm_e', 'x_coord', 'xcoord']
    NORTHING_PATTERNS = ['northing', 'y', 'north', 'utm_y', 'utm_n', 'y_coord', 'ycoord']
    LATITUDE_PATTERNS = ['latitude', 'lat', 'y_lat', 'lat_y', 'lat_deg']
    LONGITUDE_PATTERNS = ['longitude', 'lon', 'long', 'lng', 'x_lon', 'lon_x', 'lon_deg']
    
    def __init__(self):
        self._transformers: Dict[str, Transformer] = {}
    
    def get_transformer(self, utm_zone: int, southern_hemisphere: bool = True) -> Transformer:
        """Get or create a transformer for UTM to WGS84 conversion."""
        key = f"utm{utm_zone}_{'s' if southern_hemisphere else 'n'}"
        
        if key not in self._transformers:
            # UTM zone CRS
            utm_crs = CRS.from_epsg(32700 + utm_zone) if southern_hemisphere else CRS.from_epsg(32600 + utm_zone)
            wgs84_crs = CRS.from_epsg(4326)
            
            self._transformers[key] = Transformer.from_crs(
                utm_crs, wgs84_crs, always_xy=True
            )
        
        return self._transformers[key]
    
    def _find_column_by_patterns(self, columns: list, patterns: list) -> Optional[str]:
        """Find a column name matching any of the patterns."""
        columns_lower = {col.lower(): col for col in columns}
        for pattern in patterns:
            for col_lower, col_original in columns_lower.items():
                if pattern in col_lower or col_lower in pattern:
                    return col_original
        return None
    
    def detect_coordinate_system(
        self,
        df: pd.DataFrame,
        x_col: Optional[str] = None,
        y_col: Optional[str] = None
    ) -> CoordinateSystemInfo:
        """
        Detect the coordinate system from the data.
        
        Returns CoordinateSystemInfo with:
        - type: 'latlon' or 'utm'
        - utm_zone: int if UTM detected
        - epsg_code: str if determined
        - bounds: dict with min/max values
        - column names for coordinates
        """
        # Try to find coordinate columns
        easting_col = x_col or self._find_column_by_patterns(df.columns, self.EASTING_PATTERNS)
        northing_col = y_col or self._find_column_by_patterns(df.columns, self.NORTHING_PATTERNS)
        lat_col = self._find_column_by_patterns(df.columns, self.LATITUDE_PATTERNS)
        lon_col = self._find_column_by_patterns(df.columns, self.LONGITUDE_PATTERNS)
        
        # Check for Lat/Lon columns first
        if lat_col and lon_col:
            lat = pd.to_numeric(df[lat_col], errors='coerce')
            lon = pd.to_numeric(df[lon_col], errors='coerce')
            
            if not lat.isna().all() and not lon.isna().all():
                lat_min, lat_max = float(lat.min()), float(lat.max())
                lon_min, lon_max = float(lon.min()), float(lon.max())
                
                # Validate Lat/Lon ranges
                if -90 <= lat_min <= 90 and -90 <= lat_max <= 90 and -180 <= lon_min <= 180 and -180 <= lon_max <= 180:
                    return CoordinateSystemInfo(
                        type="latlon",
                        epsg_code="EPSG:4326",
                        latitude_column=lat_col,
                        longitude_column=lon_col,
                        bounds={
                            "min_lat": lat_min,
                            "max_lat": lat_max,
                            "min_lon": lon_min,
                            "max_lon": lon_max
                        }
                    )
        
        # Check for UTM columns
        if easting_col and northing_col:
            x = pd.to_numeric(df[easting_col], errors='coerce')
            y = pd.to_numeric(df[northing_col], errors='coerce')
            
            if not x.isna().all() and not y.isna().all():
                x_min, x_max = float(x.min()), float(x.max())
                y_min, y_max = float(y.min()), float(y.max())
                
                # Check if values are in UTM range
                if 100000 <= x_min and x_max <= 900000:
                    # Likely UTM
                    utm_zone = self._detect_australian_utm_zone(x_min, x_max, y_min, y_max)
                    southern_hemisphere = y_min < 5000000
                    epsg_code = f"EPSG:327{utm_zone:02d}" if southern_hemisphere else f"EPSG:326{utm_zone:02d}"
                    
                    return CoordinateSystemInfo(
                        type="utm",
                        utm_zone=utm_zone,
                        epsg_code=epsg_code,
                        easting_column=easting_col,
                        northing_column=northing_col,
                        bounds={
                            "min_x": x_min,
                            "max_x": x_max,
                            "min_y": y_min,
                            "max_y": y_max
                        }
                    )
        
        # Return unknown if no coordinate system detected
        return CoordinateSystemInfo(type="unknown")
    
    def _detect_australian_utm_zone(
        self,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float
    ) -> int:
        """
        Detect UTM zone for Australian coordinates.
        
        Uses heuristics based on coordinate ranges.
        """
        # Default to zone 55 (most common for eastern Australia)
        default_zone = 55
        
        # Try to infer from northing range
        avg_northing = (y_min + y_max) / 2
        
        # This is a rough heuristic - in practice, you'd need more context
        if avg_northing > 8000000:
            return 53  # Northern Territory
        elif avg_northing > 7000000:
            return 54  # Queensland
        elif avg_northing > 6500000:
            return 55  # NSW/Victoria
        elif avg_northing > 6000000:
            return 56  # Victoria/Tasmania
        else:
            return default_zone
    
    def convert_to_latlon(
        self,
        df: pd.DataFrame,
        easting_col: Optional[str] = None,
        northing_col: Optional[str] = None,
        zone: Optional[int] = None,
        southern_hemisphere: bool = True
    ) -> pd.DataFrame:
        """
        Convert UTM coordinates to Lat/Lon.
        
        Args:
            df: DataFrame with coordinate columns
            easting_col: Column name for Easting/X
            northing_col: Column name for Northing/Y
            zone: UTM zone (auto-detected if None)
            southern_hemisphere: Whether coordinates are in southern hemisphere
            
        Returns:
            DataFrame with added 'Latitude' and 'Longitude' columns
        """
        df = df.copy()
        
        # Auto-detect coordinate system if columns not provided
        if easting_col is None or northing_col is None:
            coord_info = self.detect_coordinate_system(df)
            
            if coord_info.type == "latlon":
                # Already in Lat/Lon, just rename columns
                if coord_info.latitude_column and coord_info.longitude_column:
                    df["Latitude"] = pd.to_numeric(df[coord_info.latitude_column], errors='coerce')
                    df["Longitude"] = pd.to_numeric(df[coord_info.longitude_column], errors='coerce')
                return df
            
            easting_col = easting_col or coord_info.easting_column
            northing_col = northing_col or coord_info.northing_column
            zone = zone or coord_info.utm_zone
        
        if easting_col is None or northing_col is None:
            raise ValueError("Could not determine coordinate columns")
        
        if zone is None:
            zone = 55  # Default zone
        
        # Get transformer
        transformer = self.get_transformer(zone, southern_hemisphere)
        
        # Convert coordinates
        x = pd.to_numeric(df[easting_col], errors='coerce').values
        y = pd.to_numeric(df[northing_col], errors='coerce').values
        
        # Create mask for valid coordinates
        valid_mask = ~(np.isnan(x) | np.isnan(y))
        
        # Initialize output arrays
        lon = np.full_like(x, np.nan)
        lat = np.full_like(y, np.nan)
        
        # Transform valid coordinates
        if valid_mask.any():
            lon[valid_mask], lat[valid_mask] = transformer.transform(
                x[valid_mask], y[valid_mask]
            )
        
        df["Longitude"] = lon
        df["Latitude"] = lat
        
        logger.info(f"Converted {valid_mask.sum()} coordinates from UTM zone {zone} to Lat/Lon")
        
        return df
    
    def get_bounds(
        self,
        df: pd.DataFrame,
        lat_col: str = "Latitude",
        lon_col: str = "Longitude"
    ) -> Optional[Dict[str, float]]:
        """Get geographic bounds from DataFrame."""
        lat = pd.to_numeric(df[lat_col], errors='coerce')
        lon = pd.to_numeric(df[lon_col], errors='coerce')
        
        if lat.isna().all() or lon.isna().all():
            return None
        
        return {
            "min_lat": float(lat.min()),
            "max_lat": float(lat.max()),
            "min_lon": float(lon.min()),
            "max_lon": float(lon.max())
        }


# Global service instance
coordinate_converter = CoordinateConverterService()


def detect_coordinates_system(df: pd.DataFrame, x_col: Optional[str] = None, y_col: Optional[str] = None) -> CoordinateSystemInfo:
    """Convenience function for coordinate system detection."""
    return coordinate_converter.detect_coordinate_system(df, x_col, y_col)


def convert_to_latlon(
    df: pd.DataFrame,
    easting_col: Optional[str] = None,
    northing_col: Optional[str] = None,
    zone: Optional[int] = None
) -> pd.DataFrame:
    """Convenience function for coordinate conversion."""
    return coordinate_converter.convert_to_latlon(df, easting_col, northing_col, zone)

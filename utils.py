"""
utils.py - Backward Compatibility Layer
This file re-exports functionality from the new modular structure in `src/`.
Please use `src.geo`, `src.data`, `src.visualization`, and `src.templates` directly in new code.
"""

# Re-export from Geo
from src.geo import (
    calculate_utm_zone_from_lonlat,
    get_australian_utm_zones,
    auto_detect_utm_zone,
    extract_kmz_points,
    HAS_LAND_MASK
)

# Re-export from Data
from src.data import (
    process_excel_data,
    get_point_name
)

# Re-export from Visualization
from src.visualization import (
    init_earth_engine,
    create_map,
    GEE_PROJECT_ID
)

# Re-export from Templates
from src.templates import (
    get_colormap_info,
    inject_controls_to_html
)

# Common imports used by scripts that might assume utils has them
import pandas as pd
import numpy as np
import os
import json

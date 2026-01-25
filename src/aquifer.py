"""
Aquifer Stratification Module

This module implements "Jaggedness Intelligence" to detect and handle
multiple aquifer layers at the same location (Impossible Physics).

Features:
- Auto-detection of nested wells (same coordinates, different values)
- Smart Well ID pattern analysis (A/B/C, Deep/Shallow suffixes)
- Dynamic layer splitting
- Singleton bore identification (regional context wells)
"""

import pandas as pd
import numpy as np
from collections import defaultdict
import re

def detect_nested_wells(df, location_threshold=1.0, use_latlon=False):
    """
    Detect wells at the same location with different values (Impossible Physics).
    
    Args:
        df: DataFrame with coordinate columns
        location_threshold: Distance threshold to consider wells at same location
                           For UTM: meters (default 1.0)
                           For Lat/Lon: degrees (use 0.00001 ≈ 1 meter)
        use_latlon: If True, use Latitude/Longitude instead of Easting/Northing
        
    Returns:
        dict: {(x, y): [list of well indices at this location]}
    """
    nested_locations = defaultdict(list)
    
    # Determine which columns to use
    if use_latlon:
        x_col, y_col = 'Longitude', 'Latitude'
        # For lat/lon, use smaller threshold (degrees)
        if location_threshold == 1.0:  # Default value, adjust for lat/lon
            location_threshold = 0.0001  # ~11 meters in degrees (Relaxed for GPS drift)
    else:
        x_col, y_col = 'Easting', 'Northing'
        # Also relax UTM threshold if default 1.0 is used. 
        # GPS drift can be 3-5m easily.
        if location_threshold == 1.0:
            location_threshold = 10.0 # 10 meters default logic
    
    print(f"DEBUG detect_nested_wells: use_latlon={use_latlon}, threshold={location_threshold}")
    print(f"DEBUG: Using columns: {x_col}, {y_col}")
    
    # Group wells by approximate location
            
    # Improved detection: Round to nearest threshold, but check adjacent bins or use loose rounding
    # Simple rounding can split close points if they straddle a threshold boundary (e.g. 0.49 and 0.51)
    
    # Strategy: First pass with rounding. If not found, check distances manually for small datasets (<1000 points)
    # Since we have small datasets (<100 wells), O(N^2) comparison is fine and accurate.
    
    # Convert to list of dicts for easier iteration
    points = []
    ids = []
    for idx, row in df.iterrows():
        if pd.isna(row.get(x_col)) or pd.isna(row.get(y_col)):
            continue
        points.append((row[x_col], row[y_col]))
        ids.append(idx)
        
    # Brute force clustering for small N
    # Group indices that are within threshold of each other
    processed = set()
    
    for i in range(len(points)):
        if i in processed: continue
        
        current_cluster = [ids[i]]
        processed.add(i)
        
        p1 = points[i]
        
        for j in range(i + 1, len(points)):
            if j in processed: continue
            
            p2 = points[j]
            # Manhattan distance or Euclidean? 
            # Simple box check is enough for thresholding
            dx = abs(p1[0] - p2[0])
            dy = abs(p1[1] - p2[1])
            
            if dx <= location_threshold and dy <= location_threshold:
                current_cluster.append(ids[j])
                processed.add(j)
        
        # Determine strict location key (use centroid or first point)
        # Using first point's rounded coords as key to keep compatible structure
        x_key = round(p1[0] / location_threshold) * location_threshold
        y_key = round(p1[1] / location_threshold) * location_threshold
        
        # If multiple points, store them
        if len(current_cluster) > 1:
            nested_locations[(x_key, y_key)] = current_cluster
    
    print(f"DEBUG: Total unique locations: {len(nested_locations)}")
    print(f"DEBUG: Locations with multiple wells: {sum(1 for indices in nested_locations.values() if len(indices) > 1)}")
    
    # Filter to only locations with multiple wells
    nested_only = {loc: indices for loc, indices in nested_locations.items() if len(indices) > 1}
    
    if nested_only:
        print(f"DEBUG: Found {len(nested_only)} nested locations:")
        for loc, indices in list(nested_only.items())[:3]:  # Show first 3
            well_ids = [df.loc[idx, 'Well ID'] if 'Well ID' in df.columns else f"Well_{idx}" for idx in indices]
            print(f"  Location {loc}: {len(indices)} wells - {well_ids}")
    
    return nested_only

def extract_layer_suffix(well_id):
    """
    Extract layer identifier from Well ID.
    
    Patterns recognized:
    - MW01A, MW01B, MW01C -> A, B, C
    - BH1-Deep, BH1-Shallow -> Deep, Shallow
    - Well_1A, Well_1B -> A, B
    
    Args:
        well_id: Well identifier string
        
    Returns:
        str: Layer suffix (A, B, C, Deep, Shallow, etc.) or None
    """
    well_id_str = str(well_id).strip()
    
    # Pattern 1: Ends with single letter (A, B, C, etc.)
    match = re.search(r'([A-Z])$', well_id_str, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    # Pattern 2: Deep/Shallow suffix
    if 'deep' in well_id_str.lower():
        return 'Deep'
    if 'shallow' in well_id_str.lower():
        return 'Shallow'
    
    # Pattern 3: Hyphen or underscore followed by letter
    match = re.search(r'[-_]([A-Z])$', well_id_str, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    
    return None

def analyze_aquifer_layers(df, value_column, well_id_column='Well ID'):
    """
    Analyze data for aquifer stratification.
    
    Args:
        df: DataFrame with well data
        value_column: Column name containing the measured values
        well_id_column: Column name containing well identifiers
        
    Returns:
        dict: {
            'has_stratification': bool,
            'layers': list of layer names,
            'nested_locations': dict,
            'singleton_indices': list of indices for singleton bores
        }
    """
    # Determine coordinate system
    # PRIORITY: Use Easting/Northing if available (more accurate for nested well detection)
    use_latlon = True  # Default to Lat/Lon
    
    print(f"DEBUG: Checking coordinates...")
    print(f"  Easting column exists: {'Easting' in df.columns}, non-null: {df['Easting'].notna().sum() if 'Easting' in df.columns else 0}")
    print(f"  Northing column exists: {'Northing' in df.columns}, non-null: {df['Northing'].notna().sum() if 'Northing' in df.columns else 0}")
    print(f"  Latitude column exists: {'Latitude' in df.columns}, non-null: {df['Latitude'].notna().sum() if 'Latitude' in df.columns else 0}")
    print(f"  Longitude column exists: {'Longitude' in df.columns}, non-null: {df['Longitude'].notna().sum() if 'Longitude' in df.columns else 0}")
    
    if 'Easting' in df.columns and 'Northing' in df.columns:
        if df['Easting'].notna().any() and df['Northing'].notna().any():
            use_latlon = False
            print("✓ Using Easting/Northing for aquifer detection (more accurate)")
    elif 'Latitude' in df.columns and 'Longitude' in df.columns:
        if df['Latitude'].notna().any() and df['Longitude'].notna().any():
            use_latlon = True
            print("✓ Using Latitude/Longitude for aquifer detection")
    
    # Step 1: Detect nested wells (Impossible Physics)
    nested_locations = detect_nested_wells(df, use_latlon=use_latlon)
    
    if not nested_locations:
        return {
            'has_stratification': False,
            'layers': ['All Data'],
            'nested_locations': {},
            'singleton_indices': list(df.index)
        }
    
    print(f"Detected {len(nested_locations)} nested wells at shared locations. Checking for aquifer stratification...")
    
    # Step 2: Analyze Well ID patterns at nested locations
    layer_counts = defaultdict(int)
    nested_indices = set()
    
    for location, indices in nested_locations.items():
        for idx in indices:
            nested_indices.add(idx)
            well_id = df.loc[idx, well_id_column]
            layer_suffix = extract_layer_suffix(well_id)
            if layer_suffix:
                layer_counts[layer_suffix] += 1
    
    # Step 3: Determine if we have clear stratification
    if not layer_counts:
        print("  No clear layer patterns found in Well IDs. Treating as single layer.")
        return {
            'has_stratification': False,
            'layers': ['All Data'],
            'nested_locations': nested_locations,
            'singleton_indices': list(df.index)
        }
    
    # Step 4: Identify layers
    layers = sorted(layer_counts.keys())
    
    # Step 5: Identify singleton bores (not at nested locations)
    # AND include nested wells that didn't have a valid suffix (don't hide data!)
    
    # Start with true singletons
    singleton_indices = [idx for idx in df.index if idx not in nested_indices]
    
    # Add back nested wells that had NO suffix matches
    # If a well is nested but returns None for suffix, we should treat it as context
    # so it appears in all layers instead of disappearing.
    for location, indices in nested_locations.items():
        for idx in indices:
            well_id = df.loc[idx, well_id_column]
            if extract_layer_suffix(well_id) is None:
                if idx not in singleton_indices:
                    singleton_indices.append(idx)
                    # print(f"DEBUG: Recovering well {well_id} (No suffix) as context/singleton")
    
    singleton_indices = sorted(list(set(singleton_indices)))
    
    print(f"Auto-detected multiple aquifer layers: {layers}")
    print(f"  Nested wells (stratified): {len(nested_indices) - (len(singleton_indices) - (len(df.index) - len(nested_indices)))}")
    print(f"  Singleton/Context bores: {len(singleton_indices)}")
    
    return {
        'has_stratification': True,
        'layers': layers,
        'nested_locations': nested_locations,
        'singleton_indices': singleton_indices
    }

def split_by_aquifer_layer(df, layer_name, analysis_result, well_id_column='Well ID'):
    """
    Create a dataset for a specific aquifer layer.
    
    Includes:
    - Wells from this specific layer (at nested locations)
    - All singleton bores (for regional context)
    
    Args:
        df: Original DataFrame
        layer_name: Name of the layer (e.g., 'A', 'B', 'Deep')
        analysis_result: Result from analyze_aquifer_layers()
        well_id_column: Column name containing well identifiers
        
    Returns:
        DataFrame: Subset of data for this layer
    """
    layer_indices = []
    
    # Add singleton bores (appear in all layers for context, UNLESS they belong to another layer)
    # E.g. If we are processing Layer 'A', we should NOT include a singleton "Well 6B".
    # But we SHOULD include "Well 7" (no suffix) as context.
    
    for idx in analysis_result['singleton_indices']:
        well_id = df.loc[idx, well_id_column]
        suffix = extract_layer_suffix(well_id)
        
        # Include if:
        # 1. No suffix (Context well like M17, M22)
        # 2. Suffix matches current layer (Singleton well belonging to this layer)
        if suffix is None or suffix == layer_name:
            layer_indices.append(idx)
    
    # Add wells from this specific layer (for nested wells)
    for location, indices in analysis_result['nested_locations'].items():
        for idx in indices:
            well_id = df.loc[idx, well_id_column]
            layer_suffix = extract_layer_suffix(well_id)
            if layer_suffix == layer_name:
                # Avoid duplicates if it was somehow in singleton list (unlikely with logic, but safe)
                if idx not in layer_indices:
                    layer_indices.append(idx)
    
    return df.loc[layer_indices].copy()

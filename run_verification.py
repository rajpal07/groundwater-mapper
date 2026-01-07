import pandas as pd
import matplotlib.cm as cm
import matplotlib.colors as colors
import warnings
warnings.filterwarnings('ignore')

def verify_ammonia_colors():
    file_path = "processed_data.xlsx"
    col_name = "Ammonia as N"
    
    print(f"Loading {file_path}...")
    try:
        df = pd.read_excel(file_path)
    except FileNotFoundError:
        print("processed_data.xlsx not found.")
        return
    
    if col_name not in df.columns:
        print(f"Column '{col_name}' not found!")
        return
        
    # Drop NaNs
    data = df.dropna(subset=[col_name]).copy()
    
    if data.empty:
        print("No valid data for Ammonia.")
        return

    min_val = data[col_name].min()
    max_val = data[col_name].max()
    
    print(f"\n--- Data Analysis for '{col_name}' ---")
    print(f"Min Value: {min_val} (Maps to Dark Purple/Blue)")
    print(f"Max Value: {max_val} (Maps to Yellow/Bright Green)")
    print(f"Total Data Points: {len(data)}")
    
    # Normalize
    try:
        norm = colors.Normalize(vmin=min_val, vmax=max_val)
        cmap = cm.get_cmap('viridis')
    except Exception as e:
        print(f"Error setting up colormap: {e}")
        return
    
    print("\n--- Point Color Simulation ---")
    sorted_df = data.sort_values(by=col_name)
    
    print("Lowest 3 Values:")
    for idx, row in sorted_df.head(3).iterrows():
        val = row[col_name]
        well = row.get('Well ID', f"Row {idx}")
        rgba = cmap(norm(val))
        print(f"  Well {well}: {val:.4f} -> {get_color_desc(rgba)}")

    print("\nHighest 3 Values:")
    for idx, row in sorted_df.tail(3).iterrows():
        val = row[col_name]
        well = row.get('Well ID', f"Row {idx}")
        rgba = cmap(norm(val))
        print(f"  Well {well}: {val:.4f} -> {get_color_desc(rgba)}")

def get_color_desc(rgba):
    r, g, b, a = rgba
    # Viridis Logic approx:
    if r > 0.8 and g > 0.8: return "YELLOW (High)"
    if g > 0.7: return "GREEN/TEAL (Medium)"
    if b > 0.4 and r < 0.4: return "PURPLE/BLUE (Low)"
    return f"Mix (R={r:.1f}, G={g:.1f}, B={b:.1f})"

if __name__ == "__main__":
    verify_ammonia_colors()

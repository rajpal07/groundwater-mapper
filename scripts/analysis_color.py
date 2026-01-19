import pandas as pd
import numpy as np

file_path = "processed_data.xlsx"
df = pd.read_excel(file_path)

# Force numeric
for col in df.columns:
    if "Well" not in col and "Easting" not in col and "Northing" not in col:
        df[col] = pd.to_numeric(df[col], errors='coerce')

ph_col = [c for c in df.columns if "pH" in c][0]

wells = ['M16', 'M12A', 'M3', 'M9', 'M21', 'M23', 'M7']
mask = df['Well ID'].astype(str).str.strip().isin(wells)
subset = df[mask][['Well ID', ph_col, 'Easting', 'Northing']].sort_values(by=ph_col, ascending=True)

print("\n--- User Query Analysis ---")
print(subset)

print(f"\nStats:")
print(f"Max pH: {df[ph_col].max()}")
print(f"Min pH: {df[ph_col].min()}")
print(f"Mean pH: {df[ph_col].mean()}")

# Distance check for M16 vs neighbors
m16 = df[df['Well ID'].astype(str).str.strip() == 'M16'].iloc[0]
others = subset[subset['Well ID'] != 'M16']
others['Dist_to_M16'] = np.sqrt((others['Easting'] - m16['Easting'])**2 + (others['Northing'] - m16['Northing'])**2)
print("\nDistance from M16:")
print(others[['Well ID', ph_col, 'Dist_to_M16']].sort_values(by='Dist_to_M16'))

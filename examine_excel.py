import pandas as pd

# Read the Excel file
df = pd.read_excel('WCT Huntly 12052025.xlsx')

print("=" * 80)
print("COLUMNS IN EXCEL FILE:")
print("=" * 80)
for i, col in enumerate(df.columns):
    print(f"{i+1}. {col}")

print("\n" + "=" * 80)
print("FIRST 10 ROWS:")
print("=" * 80)
print(df.head(10).to_string())

print("\n" + "=" * 80)
print("DATA TYPES:")
print("=" * 80)
print(df.dtypes)

print("\n" + "=" * 80)
print("SHAPE:")
print("=" * 80)
print(f"Rows: {len(df)}, Columns: {len(df.columns)}")

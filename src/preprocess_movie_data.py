import pandas as pd
import numpy as np

# --- CONFIG ---
# Update this to your raw data source if needed:
RAW_DATA = 'data/Movie_Location_Dataframe_w_Guess.csv'
OUTPUT_CSV = 'data/processed_movie_locations.csv'

# --- LOAD RAW DATA ---
df = pd.read_csv(RAW_DATA)

# --- PROCESSING LOGIC ---
# Ensure required columns exist. If your actual logic is more complex, add it here.
# This is a template; adapt as needed to match your real data cleaning/feature engineering.

# Example: create release_decade if not present
if 'release_decade' not in df.columns:
    if 'release_year' in df.columns:
        df['release_decade'] = (df['release_year'] // 10) * 10
    else:
        df['release_decade'] = np.nan

# Example: ensure columns exist
for col in ['longitude', 'latitude', 'title', 'address', 'release_year', 'release_decade', 'nhood']:
    if col not in df.columns:
        df[col] = np.nan

# Drop rows missing essential map info
map_df = df.dropna(subset=['longitude', 'latitude', 'title'])

# --- OUTPUT ---
map_df[['longitude', 'latitude', 'title', 'address', 'release_year', 'release_decade', 'nhood']]\
    .to_csv(OUTPUT_CSV, index=False)

print(f"Processed data saved to {OUTPUT_CSV}. Columns: {list(map_df.columns)}")

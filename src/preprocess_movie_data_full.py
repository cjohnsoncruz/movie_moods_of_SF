import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import os

# --- CONFIG ---
RAW_MOVIE_DATA = 'data/Movie_Location_Dataframe_w_Guess.csv'
RAW_ADDRESS_DATA = 'data/Raw_SF_address_df.csv'
LANDMARK_CSV = 'data/Landmark_table_from_wikipedia.csv'
OUTPUT_CSV = 'data/processed_movie_locations.csv'

# --- 1. Load or Download Movie Location Data ---
if os.path.exists(RAW_MOVIE_DATA):
    df_movie_location = pd.read_csv(RAW_MOVIE_DATA)
else:
    # You can add API fetch logic here if needed
    raise FileNotFoundError(f"{RAW_MOVIE_DATA} not found.")

# --- 2. Basic Movie Info Table ---
key_IDs = ['title', 'release_year', 'locations']
df_movie_basic_info = df_movie_location.loc[:, key_IDs].copy()
df_movie_basic_info['locations'] = df_movie_basic_info['locations'].str.lower()
df_movie_basic_info.fillna('Empty', inplace=True)

# --- 3. Scrape Landmark List from Wikipedia (if not already saved) ---
if not os.path.exists(LANDMARK_CSV):
    sf_landmarks_wiki_url = 'https://en.wikipedia.org/wiki/List_of_San_Francisco_Designated_Landmarks'
    wiki_response = requests.get(sf_landmarks_wiki_url)
    soup = BeautifulSoup(wiki_response.text, 'html.parser')
    table = soup.find('table', {'class': 'wikitable sortable'})
    df_table_string = pd.read_html(str(table))
    df_landmark_wiki = pd.DataFrame(df_table_string[0])
    df_landmark_wiki.drop(['Image', 'Date designated'], axis=1, inplace=True, errors='ignore')
    df_landmark_wiki.rename(columns={'Name': 'Landmark Name'}, inplace=True)
    df_landmark_wiki['Landmark Name'] = df_landmark_wiki['Landmark Name'].str.lower()
    df_landmark_wiki['Address'] = df_landmark_wiki['Address'].str.lower()
    df_landmark_wiki.to_csv(LANDMARK_CSV, index=False)
else:
    df_landmark_wiki = pd.read_csv(LANDMARK_CSV)

# --- 4. (Placeholder) Address Data Loading ---
if os.path.exists(RAW_ADDRESS_DATA):
    df_all_sf_address = pd.read_csv(RAW_ADDRESS_DATA)
else:
    df_all_sf_address = pd.DataFrame()  # Not used directly in this script, but included for completeness

# --- 5. Landmark Matching (No Geocoding: geopy not allowed) ---
from tqdm import tqdm
from thefuzz import process, fuzz

# 1. Exact match to landmark
if 'locations' in df_movie_location.columns:
    df_movie_location['address'] = df_movie_location.apply(
        lambda row: df_landmark_wiki.loc[df_landmark_wiki['Landmark Name'] == str(row['locations']).strip().lower(), 'Address'].iloc[0]
        if not df_landmark_wiki.loc[df_landmark_wiki['Landmark Name'] == str(row['locations']).strip().lower()].empty
        else row.get('address', np.nan),
        axis=1
    )

# 2. Fuzzy match for locations with address still missing or 'Empty'
missing_addr = df_movie_location['address'].isna() | (df_movie_location['address'] == 'Empty')
if missing_addr.any():
    landmark_names = df_landmark_wiki['Landmark Name'].tolist()
    for idx, row in tqdm(df_movie_location[missing_addr].iterrows(), total=missing_addr.sum(), desc='Fuzzy landmark match'):
        loc = str(row['locations']).strip().lower()
        match = process.extractOne(loc, landmark_names, scorer=fuzz.token_set_ratio)
        # Accept only if similarity >= 90
        if match and match[1] >= 90:
            address = df_landmark_wiki.loc[df_landmark_wiki['Landmark Name'] == match[0], 'Address'].iloc[0]
            df_movie_location.at[idx, 'address'] = address

# 3. Geocoding is omitted because geopy/Nominatim is not in requirements_movie_sf.txt. If coordinates are missing, they remain NaN.
# If you wish to enable geocoding, please add geopy to your requirements and re-enable this section.

# Geocoding is omitted: If coordinates are missing, they remain NaN. To enable geocoding, add geopy to requirements and implement geocoding logic here.

# --- 6. Ensure Output Columns and Save ---
required_cols = ['longitude', 'latitude', 'title', 'address', 'release_year', 'release_decade', 'nhood']
for col in required_cols:
    if col not in df_movie_location.columns:
        df_movie_location[col] = np.nan

# Calculate release_decade if missing or not filled
if 'release_decade' not in df_movie_location.columns or df_movie_location['release_decade'].isna().all():
    if 'release_year' in df_movie_location.columns:
        df_movie_location['release_decade'] = np.floor(df_movie_location['release_year'].astype(float) / 10) * 10

# Type conversions to match notebook logic
if 'longitude' in df_movie_location.columns:
    df_movie_location['longitude'] = pd.to_numeric(df_movie_location['longitude'], errors='coerce')
if 'latitude' in df_movie_location.columns:
    df_movie_location['latitude'] = pd.to_numeric(df_movie_location['latitude'], errors='coerce')
if 'release_year' in df_movie_location.columns:
    df_movie_location['release_year'] = pd.to_numeric(df_movie_location['release_year'], errors='coerce').astype('Int64')
if 'release_decade' in df_movie_location.columns:
    df_movie_location['release_decade'] = pd.to_numeric(df_movie_location['release_decade'], errors='coerce').astype('Int64')
if 'nhood' in df_movie_location.columns:
    df_movie_location['nhood'] = df_movie_location['nhood'].astype(str)

map_df = df_movie_location.dropna(subset=['longitude', 'latitude', 'title'])
map_df[required_cols].to_csv(OUTPUT_CSV, index=False)

print(f"Processed data saved to {OUTPUT_CSV}. Columns: {list(map_df[required_cols].columns)}")

import pandas as pd
import requests
from tqdm import tqdm
import time
from data_paths import LOCATION_CSV, OMDB_KEY_PATH, OMDB_INFO_CSV

# Load OMDB API key
with open(OMDB_KEY_PATH, 'r') as f:
    omdb_key = f.read().strip()

omdb_url = f'http://www.omdbapi.com/?apikey={omdb_key}'

# Load movie location dataframe
print(f"Loading location data from: {LOCATION_CSV}")
df_movies = pd.read_csv(LOCATION_CSV)

# Get unique (title, release_year) pairs
movie_years = df_movies[['title', 'release_year']].drop_duplicates().dropna()

print(f"Querying OMDB for {len(movie_years)} unique movies...")

omdb_request_list = []

for _, row in tqdm(movie_years.iterrows(), total=len(movie_years)):
    title = row['title']
    year = int(row['release_year']) if not pd.isnull(row['release_year']) else ''
    params = {'t': title, 'y': year, 'plot': 'full'}
    try:
        response = requests.get(omdb_url, params=params, timeout=10)
        data = response.json()
        # Add info about the search
        data['searched_title'] = title
        data['release_year'] = year
        omdb_request_list.append(data)
        time.sleep(0.1)  # Be polite to OMDB API
    except Exception as e:
        print(f"Error querying OMDB for {title} ({year}): {e}")
        continue

# Convert to DataFrame and save
print(f"Saving OMDB results to: {OMDB_INFO_CSV}")
df_omdb_info = pd.DataFrame(omdb_request_list)
df_omdb_info.to_csv(OMDB_INFO_CSV, index=False)
print("Done.")

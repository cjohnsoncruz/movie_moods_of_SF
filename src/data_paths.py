import os

# Base directory for notebooks
BASE_DIR = os.path.dirname(__file__)

# Data file paths (relative to src directory)
LOCATION_CSV = os.path.abspath(os.path.join(BASE_DIR, '..', 'data', 'Movie Location Dataframe w Guess.csv'))
OMDB_INFO_CSV = os.path.abspath(os.path.join(BASE_DIR, '..', 'data', 'dataframe_omdb_info.csv'))
MERGED_OUTPUT_CSV = os.path.abspath(os.path.join(BASE_DIR, '..', 'data', 'movie_locations_with_omdb.csv'))

# Path to OMDB API key (relative to project root)
OMDB_KEY_PATH = os.path.abspath(os.path.join(BASE_DIR, '..', 'omdb_api_key.txt'))

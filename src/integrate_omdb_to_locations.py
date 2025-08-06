import pandas as pd
from data_paths import LOCATION_CSV, OMDB_INFO_CSV, MERGED_OUTPUT_CSV

# Load the dataframes
print(f"Loading location data from: {LOCATION_CSV}")
df_movies_full_address = pd.read_csv(LOCATION_CSV)
print(f"Loaded {len(df_movies_full_address)} rows from location data.")

print(f"Loading OMDB info from: {OMDB_INFO_CSV}")
df_omdb_info = pd.read_csv(OMDB_INFO_CSV)
print(f"Loaded {len(df_omdb_info)} rows from OMDB info.")

# Select OMDB columns to keep
omdb_col_to_keep = [
    "Title", "Year", "Genre", "Plot", "imdbRating", "release_year"
]

# Merge OMDB info into the location dataframe on movie title
print("Merging OMDB info into location dataframe...")
df_merged = pd.merge(
    df_movies_full_address,
    df_omdb_info[omdb_col_to_keep],
    how="left",
    left_on="title",
    right_on="Title"
)

print(f"Merged dataframe has {len(df_merged)} rows.")

# Save the merged dataframe
print(f"Saving merged dataframe to: {MERGED_OUTPUT_CSV}")
df_merged.to_csv(MERGED_OUTPUT_CSV, index=False)
print("Done.")

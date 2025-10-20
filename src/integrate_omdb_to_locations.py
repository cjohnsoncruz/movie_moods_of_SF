import pandas as pd
from data_paths import LOCATION_CSV, OMDB_INFO_CSV, MERGED_OUTPUT_CSV

# Load the dataframes
print(f"Loading location data from: {LOCATION_CSV}")
df_movies_full_address = pd.read_csv(LOCATION_CSV)
print(f"Loaded {len(df_movies_full_address)} rows from location data.")

print(f"Loading OMDB info from: {OMDB_INFO_CSV}")
# Read CSV and handle any index columns
df_omdb_info = pd.read_csv(OMDB_INFO_CSV)
# Drop any unnamed index columns
df_omdb_info = df_omdb_info.loc[:, ~df_omdb_info.columns.str.contains('^Unnamed')]
print(f"Loaded {len(df_omdb_info)} rows from OMDB info.")
print(f"Head of OMDB info:\n {df_omdb_info.head(3)}")
print(f"OMDB DataFrame columns: {list(df_omdb_info.columns[:10])}...")  # Show first 10

# Filter out failed OMDB queries (rows with Error field)
if 'Error' in df_omdb_info.columns:
    before = len(df_omdb_info)
    df_omdb_info = df_omdb_info[df_omdb_info['Error'].isna()]
    print(f"Filtered out {before - len(df_omdb_info)} failed OMDB queries.")

# Select OMDB columns to keep (only those that exist)
desired_cols = ["Title", "Year", "Genre", "Plot", "imdbRating", "searched_title"]
omdb_col_to_keep = [col for col in desired_cols if col in df_omdb_info.columns]
print(f"Available OMDB columns to merge: {omdb_col_to_keep}")

if not omdb_col_to_keep:
    print("ERROR: No valid OMDB columns found to merge!")
    print(f"Available columns in OMDB data: {list(df_omdb_info.columns)}")
    exit(1)

# Merge OMDB info into the location dataframe on movie title
print("Merging OMDB info into location dataframe...")
df_merged = pd.merge(
    df_movies_full_address,
    df_omdb_info[omdb_col_to_keep],
    how="left",
    left_on="title",
    right_on="searched_title" if "searched_title" in omdb_col_to_keep else "Title"
)

print(f"Merged dataframe has {len(df_merged)} rows.")

# Save the merged dataframe
print(f"Saving merged dataframe to: {MERGED_OUTPUT_CSV}")
df_merged.to_csv(MERGED_OUTPUT_CSV, index=False)
print("Done.")

# Manual Data Refresh Guide

This guide explains how to manually refresh the raw movie location data and OMDB metadata.

## Prerequisites

1. **Sodapy app token** (optional but recommended for fetching raw data)
   - Get one free at: https://data.sfgov.org/profile/app_tokens
   - Save to: `sodapy_app_token.txt` in project root

2. **OMDB API key** (required for movie metadata)
   - Get one free at: https://www.omdbapi.com/apikey.aspx
   - Save to: `omdb_api_key.txt` in project root

3. **Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Quick Start

### Option 1: Full Refresh (Fetch from Socrata + Address Matching + Process)

```bash
# Fetch fresh data from SF Socrata API with full address matching AND run pipeline
FETCH_SOCRATA=true python src/run_data_pipeline.py
```

Or on Windows PowerShell:
```powershell
$env:FETCH_SOCRATA="true"; python src/run_data_pipeline.py
```

**What this does:**
- Fetches ~2,000 film locations from SF Socrata
- Fetches ~224,000 SF street addresses from Socrata
- Uses fuzzy matching to match movie locations to real addresses
- Enriches with lat/lon coordinates and neighborhoods
- Processes with Wikipedia landmarks
- Queries OMDB for movie metadata
- Uploads to S3

**Time:** ~5-10 minutes (most time spent on address matching)

### Option 2: Process Existing Data Only (Default)

If you only want to re-process existing CSV data without fetching new raw data:

```bash
# Run full pipeline using existing Movie_Location_Dataframe_w_Guess.csv
python src/run_data_pipeline.py
```

**Time:** ~2-3 minutes

### Option 3: Partial Refresh (Re-query OMDB only)

If you only want to refresh OMDB metadata:

```bash
# Re-query OMDB for all movies
python src/query_omdb_from_locations.py

# Integrate OMDB data
python src/integrate_omdb_to_locations.py
```

**Time:** ~5 minutes

## What Gets Updated

### Full Refresh with Address Matching (Step 0 - Optional)

**Enabled by:** `FETCH_SOCRATA=true` environment variable

**Script:** `src/fetch_and_match_addresses.py`

**Updates:**
- `data/Movie_Location_Dataframe_w_Guess.csv` - Fresh film location data with addresses, lat/lon, neighborhoods

**Data sources:** 
- SF Film Locations: https://data.sfgov.org/Culture-and-Recreation/Film-Locations-in-San-Francisco/yitu-d5am
- SF Addresses: https://data.sfgov.org/Geographic-Locations-and-Boundaries/Addresses-Enterprise-Addressing-System/3mea-di5p
- SF Landmarks: https://en.wikipedia.org/wiki/List_of_San_Francisco_Designated_Landmarks

**When to run:**
- When new movies are filmed in SF
- When SF updates their dataset
- Generally: Once every few months

**What it does:**
1. Fetches all film locations from SF Socrata
2. Fetches complete SF address database (224k addresses)
3. Uses fuzzy string matching to match movie locations to real addresses
4. Falls back to landmark matching for non-street locations (e.g., "Ferry Building")
5. Enriches with latitude, longitude, and neighborhood data

### Running Pipeline (`run_data_pipeline.py`)

**Updates:**
- `data/processed_movie_locations.csv` - Cleaned location data with landmarks
- `data/dataframe_omdb_info.csv` - Movie metadata from OMDB
- `data/movie_locations_with_omdb.csv` - Merged dataset

**When to run:**
- After fetching new raw data
- To refresh OMDB metadata (ratings, plot, etc.)

## Pipeline Steps Explained

### Step 0: Fetch and Match Addresses (Optional)
```bash
# Runs when FETCH_SOCRATA=true
python src/fetch_and_match_addresses.py
```

**Input:** None (fetches from Socrata API)

**Output:** `data/Movie_Location_Dataframe_w_Guess.csv`

**What it does:**
- Downloads film locations from SF's open data portal
- Downloads all SF street addresses with coordinates
- Fuzzy matches "600 octavia street" → "600 octavia st" with lat/lon
- Fuzzy matches "ferry building" → landmark address with lat/lon
- Adds neighborhood data from address database

### Step 1: Process Locations & Match Additional Landmarks
```bash
python src/preprocess_movie_data_full.py
```

**Input:** `data/Movie_Location_Dataframe_w_Guess.csv`

**Output:** `data/processed_movie_locations.csv`

**What it does:**
- Scrapes SF landmarks from Wikipedia (if not cached)
- Fills in any remaining missing addresses using landmark matching
- Ensures proper data types (strings, floats, ints)
- Drops rows missing coordinates

### Step 2: Query OMDB for Movie Metadata
```bash
python src/query_omdb_from_locations.py
```

**Input:** `data/processed_movie_locations.csv`

**Output:** `data/dataframe_omdb_info.csv`

**What it does:**
- Extracts unique movie titles
- Queries OMDB API for each movie (title, year, genre, rating, plot, poster)
- Saves metadata to separate CSV

⚠️ **Note:** This can take 5-10 minutes due to API rate limiting (0.1s delay between requests)

### Step 3: Integrate OMDB Data (Optional)
```bash
python src/integrate_omdb_to_locations.py
```

**Input:** 
- `data/processed_movie_locations.csv`
- `data/dataframe_omdb_info.csv`

**Output:** `data/movie_locations_with_omdb.csv`

**What it does:**
- Merges OMDB metadata with location data
- Creates enriched dataset with both location and movie info

## Automated Refresh (GitHub Actions)

The pipeline automatically runs **every Sunday at 2 AM UTC** via GitHub Actions.

**Default behavior:**
- Uses existing `Movie_Location_Dataframe_w_Guess.csv` (committed to git)
- Re-queries OMDB for updated ratings/metadata
- Uploads to S3

To manually trigger with fresh Socrata data:
1. Go to: https://github.com/[your-username]/movie_moods_of_SF/actions
2. Select "Weekly Data Scraping Pipeline"
3. Click "Run workflow"
4. Set `fetch_socrata: true`

## Troubleshooting

### "No API key provided" error
- Check that `omdb_api_key.txt` exists in project root
- Verify the file contains your actual API key (not empty)

### "Rate limit exceeded" (Socrata)
- Get a free app token: https://data.sfgov.org/profile/app_tokens
- Save to `sodapy_app_token.txt`

### "FileNotFoundError: Movie_Location_Dataframe_w_Guess.csv"
- Run `FETCH_SOCRATA=true python src/run_data_pipeline.py` to download and match addresses
- Or run `python src/fetch_and_match_addresses.py` standalone

### "Addresses still empty in output"
- Make sure you ran with `FETCH_SOCRATA=true` to enable address matching
- Check that sodapy is installed: `pip install sodapy`
- Verify Socrata API is accessible (not blocked by firewall)

## Data Quality Notes

**Address Matching Success Rate:**
- ~95% of locations successfully matched to street addresses
- ~5% remain unmatched (generic locations like "financial district")

**Common Match Examples:**
- "600 octavia street" → "600 octavia st" (exact match)
- "mission st., embarcadero, and front between clay and market" → "0 the embarcadero" (fuzzy match)
- "ferry building" → "1 ferry building" (landmark match)
- "city hall" → "1 dr carlton b goodlett pl" (landmark match)

**Unmatched Locations:**
- Broad areas without specific addresses ("financial district")
- Descriptive locations ("between market and montgomery")
- Historical/demolished locations

## Data Sources

- **SF Film Locations:** https://data.sfgov.org/Culture-and-Recreation/Film-Locations-in-San-Francisco/yitu-d5am
- **SF Street Addresses:** https://data.sfgov.org/Geographic-Locations-and-Boundaries/Addresses-Enterprise-Addressing-System/3mea-di5p
- **SF Landmarks:** https://en.wikipedia.org/wiki/List_of_San_Francisco_Designated_Landmarks
- **Movie Metadata:** http://www.omdbapi.com/

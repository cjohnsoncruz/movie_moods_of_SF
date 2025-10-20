#!/usr/bin/env python3
"""
Address matching script that replicates the logic from data_preprocess_API_v1.ipynb

This script:
1. Fetches SF address database from Socrata (all street addresses in SF)
2. Fetches movie location data from Socrata  
3. Scrapes Wikipedia for SF landmarks
4. Uses fuzzy matching to match movie locations to street addresses
5. Outputs a CSV with complete address, lat/lon, and neighborhood data

Usage:
    python src/fetch_and_match_addresses.py
"""

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import os
from pathlib import Path
from sodapy import Socrata
from thefuzz import fuzz, process
from tqdm import tqdm

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SODA_TOKEN_PATH = PROJECT_ROOT / "sodapy_app_token.txt"

# Socrata API configuration
SF_DATABASE = 'data.sfgov.org'
SF_ADDRESS_API_KEY = "3mea-di5p"  # SF Addresses dataset
FILM_LOCATIONS_API_KEY = "yitu-d5am"  # Film Locations dataset

# Output files
OUTPUT_CSV = DATA_DIR / "Movie_Location_Dataframe_w_Guess.csv"
LANDMARK_CSV = DATA_DIR / "Landmark_table_from_wikipedia.csv"


def get_sodapy_token():
    """Load sodapy app token from file if available."""
    if SODA_TOKEN_PATH.exists():
        with open(SODA_TOKEN_PATH, 'r') as f:
            token = f.read().strip()
            print(f"Using sodapy app token from {SODA_TOKEN_PATH}")
            return token
    else:
        print("WARNING: No sodapy_app_token.txt found. API will be rate-limited.")
        return None


def fetch_sf_addresses(client):
    """Fetch all SF street addresses from Socrata API."""
    print("\n" + "=" * 80)
    print("Step 1: Fetching SF Address Database")
    print("=" * 80)
    
    # Get total count
    all_address_size = client.get(SF_ADDRESS_API_KEY, select='COUNT(*)')
    all_address_size = int(all_address_size[0]['COUNT'])
    print(f"Total SF addresses: {all_address_size}")
    
    # Fetch in chunks (pagination)
    limit_size = 5000
    street_stride = np.arange(0, all_address_size, limit_size)
    
    df_all_sf_address_list = []
    for stride_num, stride_start in enumerate(street_stride):
        print(f"Fetching chunk {stride_num + 1} of {len(street_stride)}...", end='\r')
        sf_address_all_request = client.get(
            SF_ADDRESS_API_KEY,
            limit=limit_size,
            offset=stride_start,
            order='Address'
        )
        df_all_sf_address_list.append(pd.DataFrame(sf_address_all_request))
    
    print(f"\nConcatenating {len(df_all_sf_address_list)} chunks...")
    df_all_sf_address = pd.concat(df_all_sf_address_list, ignore_index=True)
    
    # Clean and format
    df_all_sf_address['street_name'] = df_all_sf_address['street_name'].str.lower()
    df_all_sf_address['address'] = df_all_sf_address['address'].str.lower()
    df_all_sf_address['street_type'] = df_all_sf_address['street_type'].str.lower()
    
    # Fix "the embarcadero" naming
    df_all_sf_address.loc[df_all_sf_address['street_name'] == 'the embarcadero', 'street_name'] = 'embarcadero'
    
    print(f"✓ Loaded {len(df_all_sf_address)} SF addresses")
    return df_all_sf_address


def fetch_movie_locations(client):
    """Fetch movie location data from Socrata API."""
    print("\n" + "=" * 80)
    print("Step 2: Fetching Movie Location Data")
    print("=" * 80)
    
    movie_location_results = client.get(FILM_LOCATIONS_API_KEY, limit=5000)
    df_movie_location = pd.DataFrame(movie_location_results)
    
    # Extract basic info
    key_IDs = ['title', 'release_year', 'locations']
    df_movie_basic_info = df_movie_location[key_IDs].copy()
    df_movie_basic_info['locations'] = df_movie_basic_info['locations'].str.lower()
    df_movie_basic_info.fillna('Empty', inplace=True)
    
    print(f"✓ Loaded {len(df_movie_basic_info)} movie locations")
    return df_movie_basic_info, df_movie_location


def scrape_wikipedia_landmarks():
    """Scrape SF landmarks from Wikipedia."""
    print("\n" + "=" * 80)
    print("Step 3: Scraping Wikipedia Landmarks")
    print("=" * 80)
    
    if LANDMARK_CSV.exists():
        print(f"Loading cached landmarks from {LANDMARK_CSV}")
        df_landmark_wiki = pd.read_csv(LANDMARK_CSV, index_col=0)
    else:
        sf_landmarks_wiki_url = 'https://en.wikipedia.org/wiki/List_of_San_Francisco_Designated_Landmarks'
        wiki_response = requests.get(sf_landmarks_wiki_url)
        soup = BeautifulSoup(wiki_response.text, 'html.parser')
        table = soup.find('table', {'class': 'wikitable sortable'})
        
        df_table_string = pd.read_html(str(table))
        df_landmark_wiki = pd.DataFrame(df_table_string[0])
        df_landmark_wiki.drop(['Image', 'Date designated'], axis=1, inplace=True, errors='ignore')
        df_landmark_wiki.rename(columns={'Name': 'Landmark Name'}, inplace=True)
        
        # Clean and format
        df_landmark_wiki['Landmark Name'] = df_landmark_wiki['Landmark Name'].str.lower()
        df_landmark_wiki['Address'] = df_landmark_wiki['Address'].str.lower()
        
        # Save for future use
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        df_landmark_wiki.to_csv(LANDMARK_CSV)
        print(f"Saved landmarks to {LANDMARK_CSV}")
    
    print(f"✓ Loaded {len(df_landmark_wiki)} SF landmarks")
    return df_landmark_wiki


def fuzzy_match_addresses(df_movie_basic_info, df_all_sf_address):
    """Use fuzzy matching to match movie locations to SF addresses."""
    print("\n" + "=" * 80)
    print("Step 4: Fuzzy Matching Movie Locations to Addresses")
    print("=" * 80)
    
    all_unique_locations = list(df_movie_basic_info['locations'].unique())
    all_unique_street_names = df_all_sf_address['street_name'].unique()
    
    print(f"Processing {len(all_unique_locations)} unique movie locations...")
    
    # Step 1: Find which street names are mentioned in each location
    unique_street_names_in_movie_location = {}
    for movie_location in tqdm(all_unique_locations, desc="Finding street names"):
        matches = [street_name.lower() for street_name in all_unique_street_names 
                   if street_name.lower() in movie_location.lower()]
        unique_street_names_in_movie_location[movie_location] = matches
    
    # Step 2: Create dict of relevant addresses for each street
    df_relevant_sf_address = {}
    for movie_location in tqdm(unique_street_names_in_movie_location, desc="Filtering addresses"):
        if not unique_street_names_in_movie_location[movie_location]:
            df_relevant_sf_address[movie_location] = []
            continue
        
        street_is_substring_bool = df_all_sf_address['street_name'].isin(
            unique_street_names_in_movie_location[movie_location]
        )
        df_relevant_sf_address[movie_location] = df_all_sf_address.loc[street_is_substring_bool, :]
    
    # Step 3: Fuzzy match each movie location to best address
    movie_original_location_dict = {}
    for iter_location in tqdm(df_movie_basic_info['locations'], desc="Fuzzy matching"):
        movie_original_location_dict[iter_location] = 'Empty'
        
        if iter_location == 'Empty' or isinstance(df_relevant_sf_address[iter_location], list):
            continue
        
        list_of_choices = list(df_relevant_sf_address[iter_location]['address'].values)
        if not list_of_choices:
            continue
        
        sample_match_highest = process.extractOne(iter_location, list_of_choices, 
                                                   scorer=fuzz.token_sort_ratio)
        movie_original_location_dict[iter_location] = sample_match_highest[0]
    
    # Create DataFrame of guesses
    df_movie_location_fuzz_guess = pd.DataFrame(
        data=movie_original_location_dict.items(),
        columns=['Input Name', 'Best Guess']
    )
    
    print(f"✓ Matched {(df_movie_location_fuzz_guess['Best Guess'] != 'Empty').sum()} / {len(df_movie_location_fuzz_guess)} locations")
    return df_movie_location_fuzz_guess


def match_landmarks(df_movie_location_fuzz_guess, df_landmark_wiki):
    """Match remaining unmatched locations to landmarks."""
    print("\n" + "=" * 80)
    print("Step 5: Matching Unmatched Locations to Landmarks")
    print("=" * 80)
    
    df_non_matched_locations = df_movie_location_fuzz_guess.loc[
        df_movie_location_fuzz_guess["Best Guess"] == "Empty", :
    ].copy()
    
    print(f"Unmatched locations: {len(df_non_matched_locations)}")
    
    df_non_matched_locations_guesses = {}
    list_of_choices = list(df_landmark_wiki['Landmark Name'].values)
    
    for iter_location in tqdm(df_non_matched_locations['Input Name'], desc="Matching landmarks"):
        sample_match_highest = process.extractOne(iter_location, list_of_choices,
                                                   scorer=fuzz.token_set_ratio)
        df_non_matched_locations_guesses[iter_location] = sample_match_highest
    
    # Threshold at 90% similarity
    for key_val in list(df_non_matched_locations_guesses.keys()):
        if int(df_non_matched_locations_guesses[key_val][1]) < 90:
            df_non_matched_locations_guesses.pop(key_val, None)
        else:
            df_non_matched_locations_guesses[key_val] = df_non_matched_locations_guesses[key_val][0]
    
    # Update guesses with landmark matches
    for key in df_non_matched_locations_guesses:
        df_non_matched_locations.loc[
            df_non_matched_locations['Input Name'] == key, 'Best Guess'
        ] = df_non_matched_locations_guesses[key]
    
    # Merge landmark addresses
    for key in df_non_matched_locations_guesses:
        landmark_name = df_non_matched_locations_guesses[key]
        landmark_address = df_landmark_wiki.loc[
            df_landmark_wiki['Landmark Name'] == landmark_name, 'Address'
        ]
        if not landmark_address.empty:
            df_movie_location_fuzz_guess.loc[
                df_movie_location_fuzz_guess['Input Name'] == key, 'Best Guess'
            ] = landmark_address.iloc[0]
    
    print(f"✓ Matched {len(df_non_matched_locations_guesses)} additional locations via landmarks")
    return df_movie_location_fuzz_guess


def main():
    """Main execution function."""
    print("\n🎬 SF Movie Location Address Matcher")
    print("=" * 80)
    
    # Get Socrata token
    soda_token = get_sodapy_token()
    client = Socrata(SF_DATABASE, soda_token)
    
    try:
        # Step 1: Fetch SF addresses
        df_all_sf_address = fetch_sf_addresses(client)
        
        # Step 2: Fetch movie locations
        df_movie_basic_info, df_movie_location_full = fetch_movie_locations(client)
        
        # Step 3: Scrape Wikipedia landmarks
        df_landmark_wiki = scrape_wikipedia_landmarks()
        
        # Step 4: Fuzzy match to addresses
        df_movie_location_fuzz_guess = fuzzy_match_addresses(df_movie_basic_info, df_all_sf_address)
        
        # Step 5: Match remaining to landmarks
        df_movie_location_fuzz_guess = match_landmarks(df_movie_location_fuzz_guess, df_landmark_wiki)
        
        # Step 6: Join everything together
        print("\n" + "=" * 80)
        print("Step 6: Joining Data and Creating Final Output")
        print("=" * 80)
        
        df_movies_best_guesses = df_movie_basic_info.merge(
            df_movie_location_fuzz_guess, how='left',
            left_on='locations', right_on='Input Name'
        )
        
        df_movies_full_address = df_movies_best_guesses.merge(
            df_all_sf_address, how='left',
            left_on='Best Guess', right_on='address'
        )
        
        # Clean up data types
        df_movies_full_address['longitude'] = pd.to_numeric(df_movies_full_address['longitude'], errors='coerce')
        df_movies_full_address['latitude'] = pd.to_numeric(df_movies_full_address['latitude'], errors='coerce')
        df_movies_full_address['release_year'] = pd.to_numeric(df_movies_full_address['release_year'], errors='coerce').astype('Int64')
        df_movies_full_address['release_decade'] = (df_movies_full_address['release_year'] // 10) * 10
        df_movies_full_address['nhood'] = df_movies_full_address['nhood'].astype(str)
        
        # Save output
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        df_movies_full_address.to_csv(OUTPUT_CSV, index=False)
        
        print(f"\n✓ Saved {len(df_movies_full_address)} rows to {OUTPUT_CSV}")
        print(f"  - With addresses: {df_movies_full_address['address'].notna().sum()}")
        print(f"  - With coordinates: {df_movies_full_address['latitude'].notna().sum()}")
        print(f"  - With neighborhoods: {(df_movies_full_address['nhood'] != 'nan').sum()}")
        
        print("\n" + "=" * 80)
        print("✓ Address matching complete!")
        print("=" * 80)
        
    finally:
        client.close()


if __name__ == "__main__":
    main()

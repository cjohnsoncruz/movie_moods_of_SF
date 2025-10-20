#!/usr/bin/env python3
"""
Automated data pipeline orchestrating the complete ETL process:
0. (Optional) Fetch raw data from SF Socrata API
1. Scrape Wikipedia for SF landmarks
2. Query OMDB API for movie metadata
3. Integrate and process all data sources
4. Upload final dataset to S3
Designed to run in GitHub Actions on a weekly schedule.
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Get project root directory
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def run_script(script_path: Path, description: str) -> bool:
    """    Run a Python script and handle errors.

    Args:
        script_path: Path to the script to run
        description: Human-readable description for logging
        
    Returns:
        True if successful, False otherwise
    """
    logger.info(f"Starting: {description}")
    logger.info(f"Running script: {script_path}")
    
    try:
        # Inherit environment variables from parent process
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
            env=os.environ.copy()
        )
        
        # Log output
        if result.stdout:
            logger.info(f"Output:\n{result.stdout}")
        if result.stderr:
            logger.warning(f"Stderr:\n{result.stderr}")
            
        logger.info(f"✓ Completed: {description}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Failed: {description}")
        logger.error(f"Exit code: {e.returncode}")
        logger.error(f"Stdout:\n{e.stdout}")
        logger.error(f"Stderr:\n{e.stderr}")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error in {description}: {e}")
        return False


def fetch_from_socrata() -> bool:
    """
    Fetch raw film location data from SF's Socrata API.
    Only runs if FETCH_SOCRATA environment variable is set to 'true'.
    
    Returns:
        True if successful or skipped, False on error
    """
    logger.info("Starting: Fetch raw data from Socrata API")
    
    # Check if we should fetch from Socrata
    fetch_enabled = os.environ.get("FETCH_SOCRATA", "false").lower() == "true"
    if not fetch_enabled:
        logger.info("Skipping Socrata fetch (FETCH_SOCRATA not set to 'true')")
        logger.info("Using existing CSV file instead.")
        return True
    
    try:
        from sodapy import Socrata
    except ImportError:
        logger.error("sodapy not installed. Install with: pip install sodapy")
        return False
    
    # Configuration
    SF_DATABASE = 'data.sfgov.org'
    FILM_LOCATIONS_DATASET = 'yitu-d5am'
    OUTPUT_FILE = DATA_DIR / "Movie_Location_Dataframe_w_Guess.csv"
    SODA_TOKEN_PATH = PROJECT_ROOT / "sodapy_app_token.txt"
    
    # Load sodapy token if available
    soda_token = None
    if SODA_TOKEN_PATH.exists():
        with open(SODA_TOKEN_PATH, 'r') as f:
            soda_token = f.read().strip()
            logger.info("Using sodapy app token from sodapy_app_token.txt")
    else:
        logger.warning("No sodapy_app_token.txt found. API will be rate-limited.")
        logger.warning("Get a free token at: https://data.sfgov.org/profile/app_tokens")
    
    # Fetch data
    client = Socrata(SF_DATABASE, soda_token)
    try:
        logger.info(f"Fetching film locations from dataset: {FILM_LOCATIONS_DATASET}")
        logger.info("This may take 1-2 minutes...")
        
        results = client.get(FILM_LOCATIONS_DATASET, limit=10000)
        
        # Convert to DataFrame and save
        import pandas as pd
        df = pd.DataFrame.from_records(results)
        
        logger.info(f"Fetched {len(df)} film location records. Latest release: {df.get('release_year', pd.Series()).max() if 'release_year' in df.columns else 'N/A'}")
        logger.info(f"Columns fetched from Socrata: {list(df.columns[:15])}...") # Log first 15 columns
        
        # Map SF Gov column names to our expected names
        column_mapping = {
            'analysis_neighborhood': 'nhood',
            'Analysis Neighborhood': 'nhood'
        }
        df.rename(columns=column_mapping, inplace=True)
        
        # Check if nhood column exists after mapping
        if 'nhood' in df.columns:
            logger.info(f"Neighborhood data included: {df['nhood'].notna().sum()} rows have nhood")
        else:
            logger.warning("WARNING: 'nhood' column not found in Socrata data after mapping")
        
        df.to_csv(OUTPUT_FILE, index=False)
        logger.info(f"Saved to: {OUTPUT_FILE}")
        logger.info(f"✓ Completed: Fetch raw data from Socrata API")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to fetch from Socrata: {e}")
        return False
    finally:
        client.close()


def upload_to_s3() -> bool:
    """
    Upload the processed CSV to S3 using AWS CLI.
    
    Returns:
        True if successful, False otherwise
    """
    logger.info("Starting: Upload to S3")
    
    # Get S3 configuration from environment
    s3_bucket = os.environ.get("S3_BUCKET")
    s3_key = os.environ.get("S3_KEY", "processed_movie_locations.csv")
    
    if not s3_bucket:
        logger.error("S3_BUCKET environment variable not set")
        return False
    
    local_file = DATA_DIR / "processed_movie_locations.csv"
    
    if not local_file.exists():
        logger.error(f"File not found: {local_file}")
        return False
    
    s3_path = f"s3://{s3_bucket}/{s3_key}"
    logger.info(f"Uploading {local_file} to {s3_path}")
    
    try:
        result = subprocess.run(
            ["aws", "s3", "cp", str(local_file), s3_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"Output:\n{result.stdout}")
        logger.info(f"✓ Successfully uploaded to S3: {s3_path}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"✗ Failed to upload to S3")
        logger.error(f"Exit code: {e.returncode}")
        logger.error(f"Stderr:\n{e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("AWS CLI not found. Please install awscli.")
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error during S3 upload: {e}")
        return False


def main():
    """
    Main pipeline execution.
    """
    logger.info("=" * 80)
    logger.info("SF Movie Locations Data Pipeline")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("=" * 80)
    
    # Ensure data directory exists
    DATA_DIR.mkdir(exist_ok=True, parents=True)
    
    # Step 0: Optional Socrata fetch
    if not fetch_from_socrata():
        logger.error("Failed to fetch from Socrata (if enabled)")
        logger.info("Continuing with existing data file...")
    
    logger.info("-" * 80)
    
    # Define pipeline steps
    steps = [
        {
            "script": PROJECT_ROOT / "src" / "preprocess_movie_data_full.py",
            "description": "Scrape Wikipedia landmarks and process locations",
            "required": True
        },
        {
            "script": PROJECT_ROOT / "src" / "query_omdb_from_locations.py",
            "description": "Query OMDB API for movie metadata",
            "required": True
        },
        {
            "script": PROJECT_ROOT / "src" / "integrate_omdb_to_locations.py",
            "description": "Integrate OMDB data with locations",
            "required": False  # Optional if this step doesn't exist
        }
    ]
    
    # Execute pipeline steps
    success = True
    for step in steps:
        if not step["script"].exists():
            if step["required"]:
                logger.error(f"Required script not found: {step['script']}")
                success = False
                break
            else:
                logger.warning(f"Optional script not found, skipping: {step['script']}")
                continue
        
        if not run_script(step["script"], step["description"]):
            if step["required"]:
                success = False
                break
            else:
                logger.warning(f"Non-critical step failed, continuing: {step['description']}")
    
    # Upload to S3 if all steps succeeded and not skipped
    if success:
        logger.info("-" * 80)
        skip_upload = os.environ.get("SKIP_UPLOAD", "false").lower() == "true"
        if skip_upload:
            logger.info("Skipping S3 upload (SKIP_UPLOAD=true)")
        else:
            if not upload_to_s3():
                success = False
    
    # Final summary
    logger.info("=" * 80)
    if success:
        logger.info("✓ Pipeline completed successfully!")
        logger.info(f"Finished at: {datetime.now().isoformat()}")
        logger.info("=" * 80)
        sys.exit(0)
    else:
        logger.error("✗ Pipeline failed. Check logs above for details.")
        logger.info(f"Failed at: {datetime.now().isoformat()}")
        logger.info("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()

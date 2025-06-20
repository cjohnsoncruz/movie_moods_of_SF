from dash import Dash, dcc, html, Input, Output, State
import plotly.express as px
import pandas as pd
import os
import boto3
import time
import dotenv
from math import radians, cos, sin, asin, sqrt

# Only load from .env file in development environment (not in production/cloud)
if os.environ.get('AWS_EXECUTION_ENV') is None:
    try:
        from dotenv import load_dotenv
        env_loaded = load_dotenv()  # This will load .env from the current or parent directories
        if env_loaded:
            print("Development mode: Environment variables loaded from .env file")
        else:
            print("Development mode: No .env file found, using existing environment variables")
    except ImportError:
        print("python-dotenv not installed. Using environment variables directly.")

def haversine(lat1, lon1, lat2, lon2):
    """Calculate great-circle distance between two geographic points in meters."""
    R = 6371000  # Earth radius in meters
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    return R * c

# use_s3 = False
use_s3 = os.getenv("USE_S3", "false").lower() == "true"
LOCAL_DATA_PATH = "data/processed_movie_locations.csv"

if use_s3:
    print("Using S3")
    # --- S3 CONFIG ---
    # Set your S3 bucket and key for the data file
    S3_BUCKET = os.environ["S3_BUCKET"]
    S3_KEY    = os.environ["S3_KEY"]

    # Download file from S3 if not present locally
    def download_from_s3(bucket, key, local_path, retries=3, delay=5):
        s3 = boto3.client('s3')
        for attempt in range(1, retries + 1):
            try:
                s3.download_file(bucket, key, local_path)
                print(f"Downloaded {key} to {local_path} (attempt {attempt})")
                return
            except Exception as e:
                print(f"Download attempt {attempt} failed: {e}")
                if attempt < retries:
                    print(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    print("Max retries reached. Aborting.")
                    raise

    # Download with optional TTL-based cache
    ttl = int(os.getenv("S3_TTL_SECONDS", "0"))
    needs = True
    if os.path.exists(LOCAL_DATA_PATH) and ttl > 0:
        age = time.time() - os.path.getmtime(LOCAL_DATA_PATH)
        if age < ttl:
            print(f"Cache hit: {LOCAL_DATA_PATH} is {age:.0f}s old (< {ttl}s), skipping download.")
            needs = False
    if needs:
        print(f"Downloading {LOCAL_DATA_PATH} from s3://{S3_BUCKET}/{S3_KEY}...")
        os.makedirs(os.path.dirname(LOCAL_DATA_PATH), exist_ok=True)
        download_from_s3(S3_BUCKET, S3_KEY, LOCAL_DATA_PATH)
        print("Download complete.")

# Note: AWS credentials must be available in the environment (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and optionally AWS_DEFAULT_REGION)

# --- Data & Params ---
try:
    print(f"Attempting to load data from {LOCAL_DATA_PATH}...")
    if os.path.exists(LOCAL_DATA_PATH):
        print(f"File exists: {LOCAL_DATA_PATH}, size: {os.path.getsize(LOCAL_DATA_PATH)} bytes")
    else:
        print(f"WARNING: File does not exist: {LOCAL_DATA_PATH}")
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(LOCAL_DATA_PATH), exist_ok=True)
        
    plot_df = pd.read_csv(LOCAL_DATA_PATH) # Load your DataFrame
    print(f"Data loaded successfully with {len(plot_df)} rows")
    print(f"Columns: {plot_df.columns.tolist()}")
    print("Sample data:")
    print(plot_df.head(2))
except Exception as e:
    print(f"ERROR loading data: {e}")
    # Create empty dataframe with required columns as fallback
    plot_df = pd.DataFrame(columns=['title', 'address', 'release_year', 'nhood', 'latitude', 'longitude', 'release_decade'])
    print("Created empty dataframe as fallback")
# DEPRECATED- MAPBOX DROPPED in 2024 # Read Mapbox token from file and set it
# with open('C:\\Users\\13car\\Dropbox\\local_github_repos_personal\\mapbox_token.txt', 'r') as f:
#     mapbox_key = f.read().strip()
# px.set_mapbox_access_token(mapbox_key)
default_map_style = 'carto-voyager'  # Same as original code
print(f"With default map style: {default_map_style}")
map_params = dict(
    lon="longitude",
    lat="latitude",
    zoom=11,
    hover_name=None,  # We'll use a custom hovertemplate
    hover_data=None,
    color="release_decade",
    color_continuous_scale='jet',
    height=600,
    map_style=default_map_style  # Matching original code
)

# Custom hovertemplate for map points
hovertemplate = (
    '<b>%{customdata[0]}</b><br>' +
    'Address: %{customdata[1]}<br>' +
    'Year: %{customdata[2]}<br>' +
    'Neighborhood: %{customdata[3]}<extra></extra>'
)

markdown_text = """ Welcome to the Movies of San Francisco Dashboard! \
This dashboard shows filming locations for movies in San Francisco. \
Use the controls to filter by neighborhood. Filtering must be enabled for neighborhood selection to work. \
Built May 2025 by Carlos Johnson-Cruz. (Last updated: June 8th 2025) \
"""
dropdown_col = 'nhood'
dropdown_list = ['All'] + sorted(plot_df[dropdown_col].dropna().unique())

external_stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']
app = Dash(__name__, external_stylesheets=external_stylesheets)

# Set custom index_string to ensure viewport meta tag for mobile responsiveness
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

light_bg = '#f9f9f9'
dark_text = '#222222'

app.layout = html.Div([
    html.H1(
        'Movies of San Francisco: An Interactive Map of Filming Locations',
        style={'textAlign': 'left', 'color': dark_text, 'marginBottom': 10, 'marginTop': 10}
    ),
    html.Div([
        html.Div([
            dcc.Graph(id='graph', style={'height': '600px', 'width': '900px', 'backgroundColor': light_bg, 'boxShadow': '0 2px 8px rgba(0,0,0,0.1)'})
        ], style={'flex': 2, 'padding': 20, 'backgroundColor': light_bg, 'display': 'flex', 'marginRight': '20px'}),
        html.Div([
            dcc.Markdown(children=markdown_text, style={'color': dark_text, 'backgroundColor': light_bg}),
            html.Label('Filter Options:', style={'fontWeight': 'bold', 'marginTop': 10, 'color': dark_text}),
            dcc.RadioItems(
                options=[{'label': i, 'value': i} for i in ['No Filter', 'Filtering']],
                id='use_filter_radio',
                value='No Filter',
                style={
                    'marginBottom': 15, 
                    'color': dark_text, 
                    'backgroundColor': light_bg,
                    'display': 'flex',
                    'flexDirection': 'column',
                    'gap': '5px'
                }
            ),
            html.Label('Neighborhood:', style={'fontWeight': 'bold', 'color': dark_text}),
            dcc.Dropdown(
                id='dropdown_list',
                style={'backgroundColor': light_bg, 'color': dark_text},
            ),
            html.Label('Go to Address:', style={'fontWeight': 'bold', 'marginTop': 10, 'color': dark_text}),
            dcc.Input(id='address_input', type='text', placeholder='Enter address...', style={'width': '90%', 'backgroundColor': light_bg, 'color': dark_text}),
            # Button container for better alignment
            html.Div([
                html.Button(
                    'GO', 
                    id='go_button', 
                    n_clicks=0, 
                    style={
                        'backgroundColor': '#e0e0e0', 
                        'color': dark_text, 
                        'marginRight': '10px',
                        'padding': '8px 16px',
                        'fontSize': '14px',
                        'fontWeight': 'bold',
                        'border': '1px solid #ccc',
                        'borderRadius': '4px',
                        'cursor': 'pointer'
                    }
                ),
                html.Button(
                    'CLEAR', 
                    id='clear_button', 
                    n_clicks=0, 
                    style={
                        'backgroundColor': '#ffeaea', 
                        'color': dark_text,
                        'padding': '8px 16px',
                        'fontSize': '14px',
                        'fontWeight': 'bold',
                        'border': '1px solid #ccc',
                        'borderRadius': '4px',
                        'cursor': 'pointer'
                    }
                ),
            ], style={'display': 'flex', 'marginTop': '10px'}),
            dcc.Markdown(
                id='closest_movies_box',
                children="Enter an address and click Go to see the closest movies.",
                style={'marginTop': '15px', 'padding': '10px', 'backgroundColor': '#f5f5f5', 'border': '1px solid #ccc', 'borderRadius': '6px', 'color': dark_text}
            ),
        ],
        className='options-panel',
        style={
            'backgroundColor': light_bg,
            'padding': 20,
            'borderRadius': 8,
            'boxShadow': '0 2px 8px rgba(0,0,0,0.1)',
            'width': '350px',
            'minWidth': '300px'
        }),
    ],
    style={'display': 'flex', 'flexDirection': 'row', 'backgroundColor': light_bg},
    id='main-container'),
],
style={'backgroundColor': light_bg, 'minHeight': '100vh'})

# --- Refactored Callbacks ---
from dash.dependencies import Output
import numpy as np
import requests
import time
from dash import callback_context
from dash.dependencies import Input, Output, State
import plotly.graph_objects as go

def haversine(lat1, lon1, lat2, lon2):
    # Calculate the great-circle distance between two points on the Earth (in meters)
    R = 6371000  # Earth radius in meters
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2.0)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2.0)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

# Global variable to track last geocode time
last_geocode_time = 0

@app.callback(
    [Output('dropdown_list', 'options'),
     Output('dropdown_list', 'value'),
     Output('graph', 'figure'),
     Output('closest_movies_box', 'children'),
     Output('address_input', 'value')],
    [Input('use_filter_radio', 'value'),
     Input('dropdown_list', 'value'),
     Input('go_button', 'n_clicks'),
     Input('clear_button', 'n_clicks')],
    [State('address_input', 'value')]
)
def update_all(radio_filter_value, selected_value, go_n_clicks, clear_n_clicks, address):
    # Dropdown options and value
    options = [{'label': n, 'value': n} for n in dropdown_list]
    # Default to 'All' if nothing selected
    value = selected_value if selected_value else 'All'
    # Filter dataframe
    if value == 'All' or radio_filter_value == 'No Filter' or not value:
        filt_df = plot_df
    else:
        filt_df = plot_df[plot_df[dropdown_col] == value]
    # Build map
    fig = px.scatter_map(filt_df, **map_params)
    fig.update_traces(
        marker=dict(size=10, opacity=0.4,
                    colorbar=dict(
                        outlinecolor=dark_text,
                        outlinewidth=2,
                        bordercolor=dark_text,
                        borderwidth=2
                    )
        ),
        customdata=filt_df[['title', 'address', 'release_year', 'nhood']].values,
        hovertemplate=hovertemplate
    )
    fig.update_layout(map_style=default_map_style)  # Match original code
    # Closest movies logic
    ctx = callback_context
    closest_movies_text = ''
    user_lat, user_lon = None, None
    error_message = ''
    global last_geocode_time
    # Check if Clear button was clicked
    if ctx.triggered and ctx.triggered[0]['prop_id'].startswith('clear_button'):
        # Clear both text output, address marker, and input box
        return options, value, fig, '', ''
    if ctx.triggered and ctx.triggered[0]['prop_id'].startswith('go_button') and go_n_clicks and address:
        url = f"https://nominatim.openstreetmap.org/search?format=json&q={address}, San Francisco, CA"
        now = time.time()
        if now - last_geocode_time < 1.0:
            time.sleep(1.0 - (now - last_geocode_time))
        try:
            resp = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
            last_geocode_time = time.time()
            if resp.status_code == 200:
                data = resp.json()
                if data:
                    lat = float(data[0]['lat'])
                    lon = float(data[0]['lon'])
                    # San Francisco bounding box (approx):
                    # lat: 37.70 to 37.83, lon: -123.03 to -122.35
                    if 37.70 <= lat <= 37.83 and -123.03 <= lon <= -122.35:
                        user_lat, user_lon = lat, lon
                        fig.update_layout(map_center={"lat": lat, "lon": lon}, map_zoom=15)
                    else:
                        closest_movies_text = "Address is outside of San Francisco. Please enter a valid SF address."
                else:
                    closest_movies_text = "Address not found. Please try a different address."
            else:
                closest_movies_text = f"Geocoding failed: HTTP {resp.status_code}"
        except requests.exceptions.Timeout:
            closest_movies_text = "Geocoding request timed out. Please try again."
        except Exception as e:
            closest_movies_text = f"Geocoding failed: {e}"
    if user_lat is not None and user_lon is not None and (not closest_movies_text or 'outside of San Francisco' not in closest_movies_text):
        # Add a marker for the entered address
        fig.add_trace(go.Scattermap(
            lat=[user_lat],
            lon=[user_lon],
            mode='markers',
            marker=dict(size=18, color='blue', symbol='star'),
            name='Entered Address',
            hoverinfo='text',
            hovertext='Entered Address'
        ))
        def get_dist(row):
            if pd.notnull(row['latitude']) and pd.notnull(row['longitude']):
                return haversine(user_lat, user_lon, row['latitude'], row['longitude'])
            else:
                return float('inf')
        plot_df['distance'] = plot_df.apply(get_dist, axis=1)
        closest = plot_df.nsmallest(3, 'distance')
        def camelcase_address(addr):
            return ' '.join([w.capitalize() for w in str(addr).split()])
        closest_movies_text = '  \n'.join([
            f"**{row['title']}** ({camelcase_address(row['address'])}) - {row['distance']:.0f} m" for _, row in closest.iterrows()
        ])
        closest_movies_text = f"Closest Filming locations: \n {closest_movies_text}" if closest_movies_text else "No nearby filming locations found."
    elif not closest_movies_text:
        closest_movies_text = "Enter an address and click Go to see the closest filming locations."
    return options, value, fig, closest_movies_text, address

if __name__ == '__main__':
    # Use updated run() method in Dash
    app.run(debug=True, use_reloader=False, host='0.0.0.0', port=8050)

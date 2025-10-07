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
    plot_df['address'] = plot_df['address'].str.title()#capitalize addresses

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
    color="release_year",
    labels = {'release_decade': 'Release Decade', 'release_year': f'Release <br> Year'},
    color_continuous_scale='jet',
    height=600,
    map_style=default_map_style  # Matching original code
)
print(plot_df['release_decade'].unique())
# Custom hovertemplate for map points
hovertemplate = (
    '<b>%{customdata[0]}</b><br>' +
    'Closest Address: %{customdata[1]}<br>' +
    'Release Year: %{customdata[2]}<br>' +
    'Neighborhood: %{customdata[3]}<extra></extra>'
)

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
#store text to ddisplay 
markdown_text = f""" Welcome! This dashboard shows {len(plot_df)} Filming Locations for {len(plot_df["title"].unique())} productions
released between {plot_df["release_year"].min()}-{plot_df["release_year"].max()} in San Francisco. \
"""
attribution_text = """“Cities, like dreams, are made of desires and fears, even if the thread of their discourse is secret,
 their rules are absurd, their perspectives deceitful, and everything conceals something else.” ― Italo Calvino, Invisible Cities. <br>
Built May 2025 by Carlos Johnson-Cruz. (Filming data last updated: June 8th 2025) """ 

light_bg = '#f9f9f9'
dark_text = '#222222'
## app layout starts here 
app.layout = html.Div(
    [# 1) Inline CSS first
    dcc.Markdown('''
                <style>
                /* Desktop defaults */
                #main-flex-row, .main-flex-row {
                    display: flex;
                    flex-direction: row; /* default; will override to column inline */
                    flex-wrap: nowrap;
                }

                /* Map container */
                .map-container { position: relative; }

                /* Options panel as a full-width top bar */
                .options-panel { 
                    background: #f9f9f9;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    padding: 10px;
                    width: 90%;
                    max-width: 90%;
                }

                /* Mobile overrides */
                @media (max-width: 1024px) {
                    #main-flex-row {
                        flex-direction: column !important;
                        flex-wrap: nowrap !important;
                        padding: 0 !important;
                        margin: 0 !important;
                        align-items: stretch !important;
                    }

                    /* Make the graph fully responsive */
                    #graph {
                        width: 100% !important;
                        height: 50vh !important;
                        min-width: 0 !important;
                    }
                }
                </style>
    ''', dangerously_allow_html=True),
    html.H3(
        'Movies of San Francisco:',
        style={'textAlign': 'left', 'color': dark_text, 'marginBottom': 10, 'marginTop': 10}
    ),
    dcc.Markdown(markdown_text,
        style={'textAlign': 'left', 'color': dark_text, 'marginBottom': 10, 'marginTop': 10}
    ), #end title section
    html.Div([
        # Options bar above the map (full width)
        html.Div([
            html.Label('Filter by Neighborhood:', style={'fontWeight': 'bold', 'color': dark_text}),
            dcc.Dropdown(id='dropdown_list', style={'backgroundColor': light_bg, 'color': dark_text}),
            html.Label('Go to Address:', style={'fontWeight': 'bold', 'marginTop': 10, 'color': dark_text}),
            dcc.Input(id='address_input', type='text', placeholder='Enter address...', style={'width': '90%', 'backgroundColor': light_bg, 'color': dark_text}),
            html.Div([
                html.Button('GO', id='go_button', n_clicks=0, style={'backgroundColor': '#e0e0e0', 'color': dark_text, 'marginRight': '5px', 'padding': '8px 12px', 'lineHeight': 'normal', 'fontSize': '12px', 'fontWeight': 'bold', 'border': '1px solid #ccc', 'borderRadius': '4px', 'cursor': 'pointer'}), 
                html.Button('CLEAR', id='clear_button', n_clicks=0, style={'backgroundColor': '#ffeaea', 'color': dark_text, 'padding': '8px 12px', 'lineHeight': 'normal', 'fontSize': '12px', 'fontWeight': 'bold', 'border': '1px solid #ccc', 'borderRadius': '4px', 'cursor': 'pointer'}),
            ], style={'display': 'flex', 'marginTop': '10px'}),
            dcc.Markdown(id='closest_movies_box', children="Enter an address and click Go to see the closest movies.",
             style={'marginTop': '5px', 'padding': '10px', 'backgroundColor': '#f5f5f5', 'border': '1px solid #ccc', 'borderRadius': '6px', 'width': '70%', 'color': dark_text}),
        ], className='options-panel'),

        # Map below
        html.Div([
            dcc.Graph(id='graph', style={
                'height': '60svh',
                'width': '100%',
                'backgroundColor': light_bg,
                'boxShadow': '0 2px 8px rgba(0,0,0,0.1)'
            })
        ], className='map-container', style={'flex': 2, 'padding': 20, 'backgroundColor': light_bg, 'display': 'flex'}),
    ], className='main-flex-row', style={'display': 'flex', 'flexDirection': 'column', 'gap': '10px', 'backgroundColor': light_bg}, id='main-flex-row'),
    dcc.Markdown(attribution_text, style={
        'marginTop': '65px', 'padding': '20px', 'color': dark_text, 'fontSize': '10px'}, dangerously_allow_html=True),
], #app layout ends here
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
def camelcase_address(addr):
    return ' '.join([w.capitalize() for w in str(addr).split()])

# Global variable to track last geocode time
last_geocode_time = 0

@app.callback(
    [Output('dropdown_list', 'options'),
     Output('dropdown_list', 'value'),
     Output('graph', 'figure'),
     Output('closest_movies_box', 'children'),
     Output('address_input', 'value')],
    [Input('dropdown_list', 'value'),
     Input('go_button', 'n_clicks'),
     Input('clear_button', 'n_clicks')],
    [State('address_input', 'value')]
)
def update_all(selected_value, go_n_clicks, clear_n_clicks, address):
    # Dropdown options and value
    options = [{'label': n, 'value': n} for n in dropdown_list]
    # Default to 'All' if nothing selected
    value = selected_value if selected_value else 'All'
    # Filter dataframe
    if value == 'All' or not value:
        filt_df = plot_df
    else:
        filt_df = plot_df[plot_df[dropdown_col] == value]
    # Build map
    fig = px.scatter_map(filt_df, **map_params)
    fig.update_traces(
        marker=dict(size=8, opacity=0.35,
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
    fig.update_layout(map_style=default_map_style, margin=dict(l=5, r=5, t=5, b=5))  # Match original code
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
    N_locations = 3
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
        closest = plot_df.nsmallest(N_locations, 'distance')
        closest_movies_text = '  \n'.join([
            f""" \n **{row['title']}** 
            {camelcase_address(row['address'])}, {row['distance']:.0f} m away""" for _, row in closest.iterrows()
        ])
        closest_movies_text = f"Closest Filming Locations: \n {closest_movies_text}" if closest_movies_text else "No nearby filming locations found."

    elif not closest_movies_text:
        closest_movies_text = f"Enter an address and click Go to see the {N_locations} closest filming locations!"

    return options, value, fig, closest_movies_text, address

if __name__ == '__main__':
    # Use updated run() method in Dash
    app.run(debug=True, use_reloader=True, host='0.0.0.0', port=8050)

# Automatically install matching chromedriver for Selenium tests
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning, module='selenium.webdriver.remote.remote_connection')
import os
import chromedriver_autoinstaller

# Ensure a dummy CSV exists so app can load in UI tests
data_dir = os.path.join(os.getcwd(), 'data')
os.makedirs(data_dir, exist_ok=True)
csv_path = os.path.join(data_dir, 'processed_movie_locations.csv')
if not os.path.exists(csv_path):
    with open(csv_path, 'w', encoding='utf-8') as f:
        # minimal header for plot_df
        f.write('latitude,longitude,release_decade,nhood,title,address,release_year\n')

# Download and install the ChromeDriver that matches the installed Chrome version
chromedriver_path = chromedriver_autoinstaller.install()
# Prepend its directory to PATH so Selenium finds the correct driver
os.environ['PATH'] = os.path.dirname(chromedriver_path) + os.pathsep + os.environ.get('PATH', '')

import os
import subprocess
import time
import requests
import pytest

@ pytest.fixture(scope="module", autouse=True)
def docker_compose():
    # Launch the app in S3 mode
    env = os.environ.copy()
    env['USE_S3'] = 'true'
    proc = subprocess.Popen(
        ['docker', 'compose', 'up', '-d'],
        cwd=os.path.dirname(__file__) + "../..",
        env=env
    )
    # Wait for the server to start
    time.sleep(10)
    yield
    # Teardown
    subprocess.call(
        ['docker', 'compose', 'down'],
        cwd=os.path.dirname(__file__) + "../..",
        env=env
    )
    proc.terminate()


def test_homepage_loads():
    # fetch Dash layout JSON to verify app responded
    resp = requests.get('http://localhost:8050/_dash-layout')
    assert resp.status_code == 200
    assert 'Mapping Filming Locations in San Francisco' in resp.text

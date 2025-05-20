import pytest

@pytest.mark.parametrize("path", ["/"])
def test_app_starts_and_shows_header(dash_duo, path):
    from movie_moods_of_SF.src.app import app
    dash_duo.start_server(app)
    dash_duo.wait_for_text_to_equal("h1", "Mapping Filming Locations in San Francisco", timeout=5)
    assert dash_duo.find_element("#main-container") is not None

def test_closest_movies_box_empty_on_load(dash_duo):
    from movie_moods_of_SF.src.app import app
    dash_duo.start_server(app)
    box = dash_duo.find_element("#closest_movies_box")
    assert "Enter an address" in box.text

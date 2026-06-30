import pytest
import sys
import os

# Import cli code
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import scripts.cli as cli


@pytest.mark.integration
def test_live_site_list_api():
    """Verify the sites API is reachable and returns stop data."""
    url = f"{cli.TRANSPORT_API_URL}/sites"
    data = cli.make_request(url)
    
    assert data is not None
    assert isinstance(data, list)
    assert len(data) > 0
    
    first_item = data[0]
    assert "id" in first_item
    assert "name" in first_item
    assert isinstance(first_item["id"], int)


@pytest.mark.integration
def test_live_departures_api():
    """Verify the departures API is active and returns data for T-Centralen (9001)."""
    site_id = 9001
    url = f"{cli.TRANSPORT_API_URL}/sites/{site_id}/departures"
    data = cli.make_request(url, {"forecast": 30})
    
    assert data is not None
    assert "departures" in data
    assert isinstance(data["departures"], list)


@pytest.mark.integration
def test_live_deviations_api():
    """Verify the deviations API is active and returns data (even if empty)."""
    url = f"{cli.DEVIATIONS_API_URL}/messages"
    data = cli.make_request(url, {"future": False})
    
    assert data is not None
    assert isinstance(data, list)
    if len(data) > 0:
        first_dev = data[0]
        assert "id" in first_dev or "deviation_case_id" in first_dev
        assert "message_variants" in first_dev

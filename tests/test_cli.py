import pytest
from unittest.mock import patch, MagicMock
import os
import json
import sys
from datetime import datetime, timedelta

# Import cli code
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import scripts.cli as cli


@pytest.fixture
def prefs_path(tmp_path):
    """Fixture returning a temp file path for preferences."""
    return str(tmp_path / "preferences.json")


def test_load_prefs_empty(prefs_path):
    """Should load default dictionary when file doesn't exist."""
    prefs = cli.load_prefs(prefs_path)
    assert prefs == {"favourite_stops": [], "favourite_routes": []}


def test_save_and_load_prefs(prefs_path):
    """Should save and correctly reload preferences."""
    sample = {
        "favourite_stops": [{"id": 9999, "name": "Test Site"}],
        "favourite_routes": []
    }
    cli.save_prefs(sample, prefs_path)
    loaded = cli.load_prefs(prefs_path)
    assert loaded["favourite_stops"][0]["id"] == 9999
    assert loaded["favourite_stops"][0]["name"] == "Test Site"


def test_add_favorite_site(prefs_path):
    """Should add a site to favorites."""
    args = MagicMock()
    args.preferences = prefs_path
    args.site_id = "1234"
    args.name = "My Stop"
    args.lines = "10,20"
    args.modes = "bus,metro"

    cli.cmd_favorite_site_add(args)
    prefs = cli.load_prefs(prefs_path)
    assert len(prefs["favourite_stops"]) == 1
    
    stop = prefs["favourite_stops"][0]
    assert stop["id"] == 1234
    assert stop["name"] == "My Stop"
    assert stop["lines"] == ["10", "20"]
    assert stop["transport_modes"] == ["BUS", "METRO"]


def test_remove_favorite_site(prefs_path):
    """Should remove a site from favorites."""
    prefs = {
        "favourite_stops": [{"id": 1234, "name": "Stop A"}],
        "favourite_routes": []
    }
    cli.save_prefs(prefs, prefs_path)

    args = MagicMock()
    args.preferences = prefs_path
    args.site_id = "1234"

    cli.cmd_favorite_site_remove(args)
    prefs = cli.load_prefs(prefs_path)
    assert len(prefs["favourite_stops"]) == 0


@patch('scripts.cli.make_request')
def test_monitor_tight_connection_warning(mock_make_request, prefs_path):
    """Should raise tight connection warning if buffer < 5 minutes."""
    route = {
        "name": "Commute Route",
        "legs": [
            {
                "lines": ["10"],
                "from": {"id": 1, "name": "Site A"},
                "to": {"id": 2, "name": "Site B"},
                "travel_time_minutes": 10
            },
            {
                "lines": ["20"],
                "from": {"id": 2, "name": "Site B"},
                "to": {"id": 3, "name": "Site C"}
            }
        ]
    }
    cli.save_prefs({"favourite_stops": [], "favourite_routes": [route]}, prefs_path)

    now = datetime.now()
    dep1_time = now.replace(hour=8, minute=0, second=0, microsecond=0)
    dep2_time = now.replace(hour=8, minute=13, second=0, microsecond=0)

    def mock_api(url, params=None):
        if "sites/1/departures" in url:
            return {
                "departures": [{
                    "line": {"designation": "10"},
                    "destination": "Site B",
                    "scheduled": dep1_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "expected": dep1_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "state": "EXPECTED"
                }]
            }
        elif "sites/2/departures" in url:
            return {
                "departures": [{
                    "line": {"designation": "20"},
                    "destination": "Site C",
                    "scheduled": dep2_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "expected": dep2_time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "state": "EXPECTED"
                }]
            }
        return {}

    mock_make_request.side_effect = mock_api

    args = MagicMock()
    args.preferences = prefs_path

    with patch('sys.stdout.write') as mock_stdout:
        cli.cmd_monitor(args)
        written_calls = "".join(call[0][0] for call in mock_stdout.call_args_list)
        assert "Status: WARNING" in written_calls
        assert "Tight Connection warning" in written_calls
        assert "has only 3 min buffer" in written_calls

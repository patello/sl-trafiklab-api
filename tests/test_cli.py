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


def test_save_site_to_favorites(prefs_path):
    """Should add a site to favorites."""
    args = MagicMock()
    args.preferences = prefs_path
    args.site_id = "1234"
    args.name = "My Stop"
    args.lines = "10,20"
    args.modes = "bus,metro"

    cli.cmd_site_save(args)
    prefs = cli.load_prefs(prefs_path)
    assert len(prefs["favourite_stops"]) == 1
    
    stop = prefs["favourite_stops"][0]
    assert stop["id"] == 1234
    assert stop["name"] == "My Stop"
    assert stop["lines"] == ["10", "20"]
    assert stop["transport_modes"] == ["BUS", "METRO"]


def test_remove_site_from_favorites(prefs_path):
    """Should remove a site from favorites."""
    prefs = {
        "favourite_stops": [{"id": 1234, "name": "Stop A"}],
        "favourite_routes": []
    }
    cli.save_prefs(prefs, prefs_path)

    args = MagicMock()
    args.preferences = prefs_path
    args.site_id = "1234"

    cli.cmd_site_remove(args)
    prefs = cli.load_prefs(prefs_path)
    assert len(prefs["favourite_stops"]) == 0


@patch('scripts.cli.make_request')
def test_site_check_single_and_all(mock_make_request, prefs_path):
    """Should fetch status for one or all stops."""
    prefs = {
        "favourite_stops": [
            {"id": 1111, "name": "Stop One", "lines": ["10"], "transport_modes": ["BUS"]},
            {"id": 2222, "name": "Stop Two"}
        ],
        "favourite_routes": []
    }
    cli.save_prefs(prefs, prefs_path)

    def mock_api(url, params=None):
        if "messages" in url:
            return [{
                "id": "D1",
                "message_variants": [{"header": "Disruption here"}]
            }]
        elif "departures" in url:
            return {
                "departures": [{
                    "line": {"designation": "10"},
                    "destination": "Destination",
                    "scheduled": "2026-06-30T12:00:00",
                    "expected": "2026-06-30T12:00:00",
                    "state": "CANCELLED"
                }]
            }
        return {}

    mock_make_request.side_effect = mock_api

    # 1. Check all stops
    args = MagicMock()
    args.preferences = prefs_path
    args.site_id = None
    args.verbose = True

    with patch('sys.stdout.write') as mock_stdout:
        cli.cmd_site_check(args)
        written_calls = "".join(call[0][0] for call in mock_stdout.call_args_list)
        assert "Checking all favorite sites..." in written_calls
        assert "Status: WARNING" in written_calls
        assert "Disruption at Stop One" in written_calls
        assert "Canceled: Line 10 to Destination" in written_calls

    # 2. Check single stop
    args.site_id = "2222"
    with patch('sys.stdout.write') as mock_stdout:
        cli.cmd_site_check(args)
        written_calls = "".join(call[0][0] for call in mock_stdout.call_args_list)
        assert "Checking site Stop Two..." in written_calls


@patch('scripts.cli.make_request')
def test_route_check_tight_connection_warning(mock_make_request, prefs_path):
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
    args.alias = None
    args.verbose = False

    with patch('sys.stdout.write') as mock_stdout:
        cli.cmd_route_check(args)
        written_calls = "".join(call[0][0] for call in mock_stdout.call_args_list)
        assert "Warnings:" in written_calls
        assert "Tight connection" in written_calls
        assert "has only 3 min buffer" in written_calls


@patch('scripts.cli.make_request')
def test_route_check_with_direction_filtering_and_sequential_filtering(mock_make_request, prefs_path):
    """Verify that direction list filtering and sequential arrival filtering works in route check."""
    route = {
      "name": "Commute Route",
      "legs": [
        {
          "lines": ["10"],
          "from": { "id": 1386, "name": "Stop A" },
          "to": { "id": 1339, "name": "Station B" },
          "travel_time_minutes": 7
        },
        {
          "lines": ["40", "41"],
          "from": { "id": 9530, "name": "Station B" },
          "to": { "id": 9526, "name": "Stop C" },
          "travel_time_minutes": 14,
          "direction": ["Terminus B", "Terminus C"]
        }
      ]
    }
    cli.save_prefs({"favourite_stops": [], "favourite_routes": [route]}, prefs_path)

    now = datetime.now()
    bus_dep = now.replace(hour=8, minute=0, second=0, microsecond=0)
    
    # Leg 2 options:
    # 1. Terminus A (wrong direction, arrives 08:10)
    # 2. Terminus B (right direction, arrives 08:05 - before bus arrives at 08:07 - should be filtered sequentially)
    # 3. Terminus C (right direction, arrives 08:11 - valid connection)
    train_uppsala = now.replace(hour=8, minute=10, second=0, microsecond=0)
    train_tumba_early = now.replace(hour=8, minute=5, second=0, microsecond=0)
    train_sodertalje = now.replace(hour=8, minute=11, second=0, microsecond=0)

    def mock_api(url, params=None):
        if "sites/1386/departures" in url:
            return {
                "departures": [{
                    "line": {"designation": "10"},
                    "destination": "Destination A",
                    "scheduled": bus_dep.strftime("%Y-%m-%dT%H:%M:%S"),
                    "expected": bus_dep.strftime("%Y-%m-%dT%H:%M:%S"),
                    "state": "EXPECTED"
                }]
            }
        elif "sites/9530/departures" in url:
            return {
                "departures": [
                    {
                        "line": {"designation": "40"},
                        "destination": "Terminus A",
                        "direction": "Terminus A",
                        "direction_code": 1,
                        "scheduled": train_uppsala.strftime("%Y-%m-%dT%H:%M:%S"),
                        "expected": train_uppsala.strftime("%Y-%m-%dT%H:%M:%S"),
                        "state": "EXPECTED"
                    },
                    {
                        "line": {"designation": "40"},
                        "destination": "Terminus B",
                        "direction": "Terminus B",
                        "direction_code": 2,
                        "scheduled": train_tumba_early.strftime("%Y-%m-%dT%H:%M:%S"),
                        "expected": train_tumba_early.strftime("%Y-%m-%dT%H:%M:%S"),
                        "state": "EXPECTED"
                    },
                    {
                        "line": {"designation": "41"},
                        "destination": "Terminus C",
                        "direction": "Terminus C",
                        "direction_code": 2,
                        "scheduled": train_sodertalje.strftime("%Y-%m-%dT%H:%M:%S"),
                        "expected": train_sodertalje.strftime("%Y-%m-%dT%H:%M:%S"),
                        "state": "EXPECTED"
                    }
                ]
            }
        return {}

    mock_make_request.side_effect = mock_api

    args = MagicMock()
    args.preferences = prefs_path
    args.alias = "Commute Route"
    args.verbose = False

    with patch('sys.stdout.write') as mock_stdout:
        cli.cmd_route_check(args)
        written_calls = "".join(call[0][0] for call in mock_stdout.call_args_list)
        
        # Verify departures printing
        assert "Leg 1: Line 10 from Stop A" in written_calls
        assert "08:00 (Destination A)" in written_calls
        assert "Leg 2: Line 40, 41 from Station B" in written_calls
        
        # Terminus C should be listed (valid connection >= 08:07 and correct direction)
        assert "08:11 (Terminus C)" in written_calls
        
        # Terminus A (wrong direction) and Terminus B early (before arrival time 08:07) should NOT be listed
        assert "Terminus A" not in written_calls
        assert "08:05 (Terminus B)" not in written_calls
        
        # Verify tight connection message contents
        assert "Warnings:" in written_calls
        assert "leaving Stop A at 08:00" in written_calls
        assert "expected arrival 08:07" in written_calls
        assert "toward Terminus C departing at 08:11" in written_calls
        assert "has only 4 min buffer" in written_calls


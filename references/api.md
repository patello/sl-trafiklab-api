# SL Trafiklab CLI & API References

The `sl-trafiklab-api` skill wraps the SL Integration and Deviations APIs using a standalone, zero-dependency Python script at `scripts/cli.py`.

---

## State Storage (`.sl/preferences.json`)

The monitoring preferences file stores sites and multi-leg routes configured for autonomous background check notifications. It is loaded and modified using the `favorite` namespace commands.

### Format Example
```json
{
  "favourite_stops": [
    { 
      "id": 9001, 
      "name": "T-Centralen" 
    },
    { 
      "id": 9117, 
      "name": "Odenplan",
      "transport_modes": ["METRO"]
    },
    { 
      "id": 9192, 
      "name": "Gullmarsplan",
      "lines": ["4", "66"],
      "transport_modes": ["BUS", "METRO"]
    }
  ],
  "favourite_routes": [
    {
      "name": "Daily Commute",
      "legs": [
        { 
          "lines": ["66"], 
          "from": { "id": 1001, "name": "Generic Stop A" }, 
          "to": { "id": 1002, "name": "Generic Stop B" },
          "travel_time_minutes": 15
        },
        { 
          "lines": ["40", "41"], 
          "from": { "id": 9002, "name": "Generic Station B" }, 
          "to": { "id": 9003, "name": "Generic Station C" },
          "travel_time_minutes": 20
        }
      ]
    }
  ]
}
```

---

## CLI Reference

All commands are run using Python:

### 1. `site` Core Commands

- **Search Sites:** Search for a transit stop's numeric Site ID by name.
  ```bash
  python scripts/cli.py site list "Odenplan"
  ```
- **Fetch Departures:** Get live upcoming departures for a site.
  ```bash
  python scripts/cli.py site departures 9117 --line 4 --transport BUS
  ```

### 2. `site` Favorite & Check Commands

- **Check Stations:** Verify departures and disruptions for one or all saved favorite sites.
  ```bash
  # Check all favorite sites
  python scripts/cli.py site check

  # Check only site ID 9117 (with verbose details)
  python scripts/cli.py site check 9117 -v
  ```
- **Save Favorite Site:** Add or update a station/stop site in preferences.
  ```bash
  python scripts/cli.py site save 9001 "T-Centralen" --lines "17,18,19" --modes METRO
  ```
- **Remove Favorite Site:** Remove a site from preferences.
  ```bash
  python scripts/cli.py site remove 9001
  ```

### 3. `route` Commands

- **Check Routes:** Evaluate departures and connection buffers for one or all favorite routes.
  ```bash
  # Check all favorite routes
  python scripts/cli.py route check

  # Check only the "Daily Commute" route
  python scripts/cli.py route check "Daily Commute" -v
  ```
- **Save Favorite Route:** Add or update a multi-leg route (using a JSON representation of the legs array).
  ```bash
  python scripts/cli.py route save "Daily Commute" '[{"lines":["66"],"from":{"id":1001,"name":"Generic Stop A"},"to":{"id":1002,"name":"Generic Stop B"},"travel_time_minutes":15}]'
  ```
- **Remove Favorite Route:** Remove a route by alias.
  ```bash
  python scripts/cli.py route remove "Daily Commute"
  ```

### 4. `deviations` Command

- **Fetch Transit Disruptions:** Check active deviations affecting specific lines or stop sites.
  ```bash
  python scripts/cli.py deviations --site 9001 --line 40 -v
  ```


---

## Running the Test Suite

The skill includes a built-in test suite using **pytest** to verify CLI and API functionality:

- **Run all tests (both offline unit tests and live integration checks):**
  ```bash
  pytest
  ```
- **Run only unit tests (offline mock testing):**
  ```bash
  pytest -m "not integration"
  ```
- **Run only integration tests (live network testing):**
  ```bash
  pytest -m integration
  ```


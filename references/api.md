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

### 1. `site` Commands

- **Search Sites:** Search for a transit stop's numeric Site ID by name.
  ```bash
  python scripts/cli.py site list "Odenplan"
  ```
- **Fetch Departures:** Get live upcoming departures for a site.
  ```bash
  python scripts/cli.py site departures 9117 --line 4 --transport BUS
  ```

### 2. `deviations` Command

- **Fetch Transit Disruptions:** Check active deviations affecting specific lines or stop sites.
  ```bash
  python scripts/cli.py deviations --site 9001 --line 40 -v
  ```

### 3. `favorite` Commands

- **List Favorites:** View saved favorite sites and routes.
  ```bash
  python scripts/cli.py favorite list
  ```
- **Add Favorite Site:** Add a station/stop site to preferences.
  ```bash
  python scripts/cli.py favorite site-add 9001 "T-Centralen" --lines "17,18,19" --modes METRO
  ```
- **Remove Favorite Site:** Remove a site from preferences.
  ```bash
  python scripts/cli.py favorite site-remove 9001
  ```
- **Add Favorite Route:** Add a multi-leg route (using double-escaped JSON representation of the legs array).
  ```bash
  python scripts/cli.py favorite route-add "Daily Commute" '[{"lines":["66"],"from":{"id":1001,"name":"Generic Stop A"},"to":{"id":1002,"name":"Generic Stop B"},"travel_time_minutes":15}]'
  ```
- **Remove Favorite Route:** Remove a route by name.
  ```bash
  python scripts/cli.py favorite route-remove "Daily Commute"
  ```

### 4. `monitor` Command

- **Run Autonomous Checks:** Evaluates schedules and deviations for all saved favorites, returning connection alerts or transit disruption warnings.
  ```bash
  python scripts/cli.py monitor
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


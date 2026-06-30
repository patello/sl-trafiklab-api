---
name: sl-trafiklab-api
description: "Fetch real-time SL (Stockholm public transport) departures and deviation information using a Python CLI tool. Use when checking upcoming departures, querying transit delays, or configuring favourite sites/routes for autonomous monitoring. Note: The skill can query ANY site or line on demand; favorites are solely for autonomous background monitoring."
metadata: {"openclaw": {"requires": {"bins": ["python"]}}}
---

# SL Trafiklab API Skill

This skill retrieves real-time departure and deviation information from SL (Stockholm public transport) via a Python CLI client. It **does NOT require registration** of sites to make queries—you can query departures and deviations for any site or line on demand. The favorites configuration is **only for autonomous background monitoring** (e.g., heartbeat checks, cron jobs that proactively notify about disruptions).

The most critical task when handling background monitoring is to **filter out noise**. The user should not be notified about disruptions at sites/lines they're not actually using on that specific route.

## Preferences Storage
Preferences for **autonomous monitoring** are stored in your workspace at `.sl/preferences.json`.
You must interact with this configuration exclusively via the `python scripts/cli.py favorite` subcommands, which handles validation.

## Core Actions
All actions are performed by invoking `python scripts/cli.py`. For detailed command arguments and response layouts, refer to **`references/api.md`**.

1. **site list**: Search for a transit site's numeric ID by name.
   - Command: `python scripts/cli.py site list "<query>"`
2. **site departures**: Fetch upcoming real-time departures.
   - Command: `python scripts/cli.py site departures <site_id> [--line <line>] [--transport <mode>] [--direction <dir>] [--forecast <forecast>]`
3. **deviations**: Fetch active or planned transit disruptions.
   - Command: `python scripts/cli.py deviations [--site <site_id>] [--line <line>] [--future]`
4. **favorite management**: Add, remove, or list favourite sites/routes for monitoring.
   - Commands: `python scripts/cli.py favorite [list | site-add | site-remove | route-add | route-remove] ...`
5. **monitor**: Run autonomous checks for all configured favorites.
   - Command: `python scripts/cli.py monitor`

## Autonomous Directives (Background Monitoring)
During autonomous execution (e.g., background heartbeat or cron job):
1. Execute `python scripts/cli.py monitor`.
2. Inspect the output:
   - If output starts with `Status: OK`, take no action.
   - If output starts with `Status: WARNING`, parse the warnings list (e.g. `[ROUTE_DISRUPTION]`, `[TIGHT_CONNECTION]`).
3. Compare returned warnings against context memory.
4. Only send a notification if a new, relevant warning is detected.
5. Adhere to Trafiklab's limit of maximum 1 request per minute (monitored internally).

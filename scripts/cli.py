#!/usr/bin/env python3
"""
CLI wrapper for the SL Trafiklab API.
Provides site search, departures, deviations, favorite management, and autonomous monitoring.
Zero dependencies: uses only Python standard libraries.
"""

import argparse
import sys
import os
import json
import urllib.request
import urllib.parse
from datetime import datetime, timedelta

# API Base URLs
TRANSPORT_API_URL = "https://transport.integration.sl.se/v1"
DEVIATIONS_API_URL = "https://deviations.integration.sl.se/v1"


def make_request(url, params=None):
    """Perform HTTP GET request and return parsed JSON."""
    if params:
        # Filter out None values and handle lists/iterables for doseq
        filtered_params = {}
        for k, v in params.items():
            if v is not None:
                if isinstance(v, bool):
                    filtered_params[k] = str(v).lower()
                else:
                    filtered_params[k] = v
        url = f"{url}?{urllib.parse.urlencode(filtered_params, doseq=True)}"

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "OpenClaw-SL-Trafiklab/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        sys.stderr.write(f"Error fetching data from API: {e}\n")
        return None


# =====================================================================
# Preference Helpers
# =====================================================================

def get_prefs_path(path=None):
    """Retrieve preferences path, defaulting to .sl/preferences.json in CWD."""
    if path:
        return path
    return os.path.join(os.getcwd(), ".sl", "preferences.json")


def load_prefs(path=None):
    """Load configuration from preferences file."""
    p = get_prefs_path(path)
    if not os.path.exists(p):
        return {"favourite_stops": [], "favourite_routes": []}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure keys exist
            if "favourite_stops" not in data:
                data["favourite_stops"] = []
            if "favourite_routes" not in data:
                data["favourite_routes"] = []
            return data
    except Exception:
        return {"favourite_stops": [], "favourite_routes": []}


def save_prefs(prefs, path=None):
    """Save configuration to preferences file."""
    p = get_prefs_path(path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(prefs, f, indent=2, ensure_ascii=False)


# =====================================================================
# CLI Commands implementation
# =====================================================================

def cmd_site_list(args):
    """List/Search sites matching query term."""
    url = f"{TRANSPORT_API_URL}/sites"
    sys.stdout.write("Fetching site list...\n")
    data = make_request(url)
    if not data:
        sys.exit(1)

    query = args.query.lower()
    matches = []
    for item in data:
        name = item.get("name", "")
        if query in name.lower():
            matches.append({
                "id": item.get("id"),
                "name": name
            })

    if not matches:
        sys.stdout.write(f"No sites found matching '{args.query}'.\n")
        return

    sys.stdout.write(f"Found {len(matches)} matching sites (showing top {args.limit}):\n")
    for m in matches[:args.limit]:
        sys.stdout.write(f"- {m['id']}: {m['name']}\n")


def cmd_site_departures(args):
    """Fetch departures for a specific site ID."""
    url = f"{TRANSPORT_API_URL}/sites/{args.site_id}/departures"
    params = {
        "line": args.line,
        "transport": args.transport,
        "direction": args.direction,
        "forecast": args.forecast
    }
    data = make_request(url, params)
    if not data:
        sys.exit(1)

    departures = data.get("departures", [])
    if not departures:
        sys.stdout.write("No upcoming departures found.\n")
        return

    sys.stdout.write(f"Departures for site {args.site_id}:\n")
    header = f"{'Line':<6} {'Destination':<22} {'Expected/Scheduled':<24} {'State'}"
    sys.stdout.write(header + "\n" + "-" * len(header) + "\n")
    for dep in departures:
        line = dep.get("line", {}).get("designation", "")
        dest = dep.get("destination", "")
        sched = dep.get("scheduled", "")
        expected = dep.get("expected", sched)
        state = dep.get("state", "EXPECTED")

        # Format departure time display
        time_str = expected
        if dep.get("display"):
            time_str = f"{dep.get('display')} ({expected})"

        sys.stdout.write(f"{line:<6} {dest:<22} {time_str:<24} {state}\n")


def cmd_deviations(args):
    """Fetch deviations generally or filtered by site/line."""
    url = f"{DEVIATIONS_API_URL}/messages"
    params = {
        "future": args.future,
        "site": args.site,
        "line": args.line
    }
    data = make_request(url, params)
    if data is None:
        sys.exit(1)

    if not data:
        sys.stdout.write("No active deviations found.\n")
        return

    sys.stdout.write(f"Active deviations ({len(data)}):\n")
    for item in data:
        dev_id = item.get("id") or item.get("deviation_case_id")
        variants = item.get("message_variants", [])
        header = "No header available"
        details = ""
        if variants:
            header = variants[0].get("header", header)
            details = variants[0].get("details", "")

        sys.stdout.write(f"\n[{dev_id}] {header}\n")
        if args.verbose and details:
            sys.stdout.write(f"Details: {details}\n")


def cmd_favorite_list(args):
    """List current favorites."""
    prefs = load_prefs(args.preferences)
    stops = prefs.get("favourite_stops", [])
    routes = prefs.get("favourite_routes", [])

    sys.stdout.write("Favorite Sites:\n")
    if not stops:
        sys.stdout.write("  None\n")
    else:
        for s in stops:
            lines = f" (Lines: {', '.join(s['lines'])})" if "lines" in s else ""
            sys.stdout.write(f"  - {s['id']}: {s['name']}{lines}\n")

    sys.stdout.write("\nFavorite Routes:\n")
    if not routes:
        sys.stdout.write("  None\n")
    else:
        for r in routes:
            sys.stdout.write(f"  - {r['name']} ({len(r.get('legs', []))} legs)\n")


def cmd_favorite_site_add(args):
    """Add/Update favorite site."""
    prefs = load_prefs(args.preferences)
    stops = prefs.get("favourite_stops", [])
    site_id = int(args.site_id)

    # Filter out existing to prevent duplicates
    stops = [s for s in stops if s.get("id") != site_id]

    entry = {"id": site_id, "name": args.name}
    if args.lines:
        entry["lines"] = [l.strip() for l in args.lines.split(",")]
    if args.modes:
        entry["transport_modes"] = [m.strip().upper() for m in args.modes.split(",")]

    stops.append(entry)
    prefs["favourite_stops"] = stops
    save_prefs(prefs, args.preferences)
    sys.stdout.write(f"Successfully added favorite site: {args.name} ({site_id})\n")


def cmd_favorite_site_remove(args):
    """Remove favorite site."""
    prefs = load_prefs(args.preferences)
    stops = prefs.get("favourite_stops", [])
    site_id = int(args.site_id)

    filtered = [s for s in stops if s.get("id") != site_id]
    if len(stops) == len(filtered):
        sys.stdout.write(f"Site ID {site_id} not found in favorites.\n")
        return

    prefs["favourite_stops"] = filtered
    save_prefs(prefs, args.preferences)
    sys.stdout.write(f"Successfully removed favorite site: {site_id}\n")


def cmd_favorite_route_add(args):
    """Add/Update favorite route."""
    prefs = load_prefs(args.preferences)
    routes = prefs.get("favourite_routes", [])

    try:
        legs = json.loads(args.legs_json)
        if not isinstance(legs, list):
            raise ValueError("Legs must be a JSON array of leg objects.")
    except Exception as e:
        sys.stderr.write(f"Invalid legs JSON: {e}\n")
        sys.exit(1)

    # Remove existing route by name
    routes = [r for r in routes if r.get("name") != args.name]
    routes.append({
        "name": args.name,
        "legs": legs
    })
    prefs["favourite_routes"] = routes
    save_prefs(prefs, args.preferences)
    sys.stdout.write(f"Successfully added favorite route: {args.name}\n")


def cmd_favorite_route_remove(args):
    """Remove favorite route."""
    prefs = load_prefs(args.preferences)
    routes = prefs.get("favourite_routes", [])

    filtered = [r for r in routes if r.get("name") != args.name]
    if len(routes) == len(filtered):
        sys.stdout.write(f"Route '{args.name}' not found in favorites.\n")
        return

    prefs["favourite_routes"] = filtered
    save_prefs(prefs, args.preferences)
    sys.stdout.write(f"Successfully removed favorite route: {args.name}\n")


# =====================================================================
# Autonomous Monitoring Engine
# =====================================================================

def parse_time(time_str):
    """Parse API ISO datetime string."""
    if not time_str:
        return None
    try:
        # Strip timezone offset if present for simplicity
        clean_str = time_str.split("+")[0]
        return datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
    except Exception:
        return None


def cmd_monitor(args):
    """Autonomous monitor: evaluates deviations and schedules for favourites."""
    prefs = load_prefs(args.preferences)
    stops = prefs.get("favourite_stops", [])
    routes = prefs.get("favourite_routes", [])

    warnings = []

    # 1. Check Favorite Sites
    if stops:
        sys.stdout.write("Checking favorite sites...\n")
        for site in stops:
            site_id = site["id"]
            site_name = site["name"]

            # Check Deviations
            dev_url = f"{DEVIATIONS_API_URL}/messages"
            devs = make_request(dev_url, {"future": False, "site": site_id})
            if devs:
                for dev in devs:
                    variants = dev.get("message_variants", [])
                    if variants:
                        warnings.append({
                            "type": "SITE_DISRUPTION",
                            "message": f"Disruption at {site_name}: {variants[0]['header']}",
                            "details": variants[0].get("details", "")
                        })

            # Check Canceled/Delayed Departures (queried generally and filtered locally)
            dep_url = f"{TRANSPORT_API_URL}/sites/{site_id}/departures"
            dep_data = make_request(dep_url, {
                "transport": site.get("transport_modes")
            })
            if dep_data and site.get("lines"):
                line_strs = [str(l) for l in site.get("lines")]
                dep_data["departures"] = [
                    d for d in dep_data.get("departures", [])
                    if d.get("line", {}).get("designation") in line_strs
                ]
            if dep_data:
                for dep in dep_data.get("departures", []):
                    state = dep.get("state", "")
                    line = dep.get("line", {}).get("designation", "")
                    dest = dep.get("destination", "")
                    if state == "CANCELLED":
                        warnings.append({
                            "type": "CANCELLED_DEPARTURE",
                            "message": f"Canceled: Line {line} to {dest} at {site_name}"
                        })

    # 2. Check Favorite Routes (Multi-leg check)
    if routes:
        sys.stdout.write("Checking favorite routes...\n")
        for route in routes:
            route_name = route["name"]
            legs = route.get("legs", [])
            leg_departures = []

            for i, leg in enumerate(legs):
                from_site = leg.get("from", {})
                from_id = from_site.get("id")
                from_name = from_site.get("name")
                lines = leg.get("lines", [])

                # Fetch departures for boarding stop (queried generally and filtered locally to avoid Bad Request with multiple lines)
                dep_url = f"{TRANSPORT_API_URL}/sites/{from_id}/departures"
                dep_data = make_request(dep_url)
                if dep_data and lines:
                    line_strs = [str(l) for l in lines]
                    dep_data["departures"] = [
                        d for d in dep_data.get("departures", [])
                        if d.get("line", {}).get("designation") in line_strs
                    ]
                
                valid_deps = []
                if dep_data:
                    for dep in dep_data.get("departures", []):
                        if dep.get("state") != "CANCELLED":
                            valid_deps.append(dep)
                
                leg_departures.append(valid_deps)

                # Fetch deviations affecting this leg (site or line)
                dev_url = f"{DEVIATIONS_API_URL}/messages"
                for line_id in lines:
                    devs = make_request(dev_url, {"future": False, "line": line_id})
                    if devs:
                        for dev in devs:
                            # Apply strict deviation assessment: ignore if localized to an unused stop point
                            stop_areas = dev.get("scope", {}).get("stop_areas", [])
                            affected_stop_ids = [sa.get("id") for sa in stop_areas if sa.get("id")]
                            
                            # If deviation is stop-specific and doesn't match our start/end site, skip
                            if affected_stop_ids and from_id not in affected_stop_ids:
                                continue
                            
                            variants = dev.get("message_variants", [])
                            if variants:
                                warnings.append({
                                    "type": "ROUTE_DISRUPTION",
                                    "message": f"Route '{route_name}' Leg {i+1} (Line {line_id}): {variants[0]['header']}",
                                    "details": variants[0].get("details", "")
                                })

            # Evaluate Connections between sequential legs
            for i in range(len(legs) - 1):
                leg1 = legs[i]
                leg2 = legs[i+1]
                travel_time = leg1.get("travel_time_minutes")

                if not travel_time:
                    # Skip connection verification if travel_time_minutes is not defined
                    continue

                # Look for connecting departure pairs
                deps1 = leg_departures[i]
                deps2 = leg_departures[i+1]

                for d1 in deps1[:3]: # check top 3 upcoming
                    d1_time = parse_time(d1.get("expected") or d1.get("scheduled"))
                    if not d1_time:
                        continue
                    
                    arrival_time = d1_time + timedelta(minutes=travel_time)

                    # Find the first departure on leg 2 after arrival
                    matching_d2 = None
                    for d2 in deps2:
                        d2_time = parse_time(d2.get("expected") or d2.get("scheduled"))
                        if d2_time and d2_time >= arrival_time:
                            matching_d2 = d2
                            break
                    
                    if matching_d2:
                        d2_time = parse_time(matching_d2.get("expected") or matching_d2.get("scheduled"))
                        buffer = (d2_time - arrival_time).total_seconds() / 60
                        if buffer < 5.0:
                            line1 = d1.get("line", {}).get("designation", "")
                            line2 = matching_d2.get("line", {}).get("designation", "")
                            warnings.append({
                                "type": "TIGHT_CONNECTION",
                                "message": f"Tight Connection warning on '{route_name}': Leg {i+1} ({line1} expected arrival {arrival_time.strftime('%H:%M')}) to Leg {i+2} ({line2} departure {d2_time.strftime('%H:%M')}) has only {int(buffer)} min buffer (min required: 5 min)."
                            })

    # Output Warnings
    if not warnings:
        sys.stdout.write("Status: OK. No disruptions or connection issues detected.\n")
        return

    sys.stdout.write(f"Status: WARNING. Detected {len(warnings)} issues:\n")
    for w in warnings:
        sys.stdout.write(f"- [{w['type']}] {w['message']}\n")


# =====================================================================
# Main Parser
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="SL Trafiklab CLI Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # site list
    p_site_list = subparsers.add_parser("site", help="Site operations")
    s_sub = p_site_list.add_subparsers(dest="subcommand", help="Site subcommands")
    
    p_list = s_sub.add_parser("list", help="Search/List sites")
    p_list.add_argument("query", help="Search string for stop names")
    p_list.add_argument("--limit", type=int, default=10, help="Maximum search results")

    # site departures
    p_dep = s_sub.add_parser("departures", help="Fetch departures for a site")
    p_dep.add_argument("site_id", help="Numeric Site ID")
    p_dep.add_argument("--line", help="Filter by line designation")
    p_dep.add_argument("--transport", help="Filter by transport mode (BUS, METRO, TRAIN, etc.)")
    p_dep.add_argument("--direction", type=int, choices=[1, 2], help="Filter by direction code")
    p_dep.add_argument("--forecast", type=int, help="Forecast window in minutes")

    # deviations
    p_dev = subparsers.add_parser("deviations", help="Fetch transit deviations")
    p_dev.add_argument("--site", help="Filter by Site ID")
    p_dev.add_argument("--line", help="Filter by line designation")
    p_dev.add_argument("--future", type=bool, default=False, help="Show planned/future deviations")
    p_dev.add_argument("-v", "--verbose", action="store_true", help="Print deviation details")

    # favorite
    p_fav = subparsers.add_parser("favorite", help="Favorite preference management")
    p_fav.add_argument("--preferences", help="Override preferences file path")
    fav_sub = p_fav.add_subparsers(dest="subcommand", help="Favorite subcommands")

    fav_sub.add_parser("list", help="List favorites")

    p_fav_add_site = fav_sub.add_parser("site-add", help="Add favorite site")
    p_fav_add_site.add_argument("site_id", help="Numeric Site ID")
    p_fav_add_site.add_argument("name", help="Display name for favorite site")
    p_fav_add_site.add_argument("--lines", help="Comma-separated line filters")
    p_fav_add_site.add_argument("--modes", help="Comma-separated transport mode filters")

    p_fav_rem_site = fav_sub.add_parser("site-remove", help="Remove favorite site")
    p_fav_rem_site.add_argument("site_id", help="Site ID to remove")

    p_fav_add_route = fav_sub.add_parser("route-add", help="Add favorite route")
    p_fav_add_route.add_argument("name", help="Route name")
    p_fav_add_route.add_argument("legs_json", help="JSON array of route legs")

    p_fav_rem_route = fav_sub.add_parser("route-remove", help="Remove favorite route")
    p_fav_rem_route.add_argument("name", help="Route name to remove")

    # monitor
    p_mon = subparsers.add_parser("monitor", help="Run autonomous monitor checks")
    p_mon.add_argument("--preferences", help="Override preferences file path")

    args = parser.parse_args()

    # Routing
    if args.command == "site" and args.subcommand == "list":
        cmd_site_list(args)
    elif args.command == "site" and args.subcommand == "departures":
        cmd_site_departures(args)
    elif args.command == "deviations":
        cmd_deviations(args)
    elif args.command == "favorite" and args.subcommand == "list":
        cmd_favorite_list(args)
    elif args.command == "favorite" and args.subcommand == "site-add":
        cmd_favorite_site_add(args)
    elif args.command == "favorite" and args.subcommand == "site-remove":
        cmd_favorite_site_remove(args)
    elif args.command == "favorite" and args.subcommand == "route-add":
        cmd_favorite_route_add(args)
    elif args.command == "favorite" and args.subcommand == "route-remove":
        cmd_favorite_route_remove(args)
    elif args.command == "monitor":
        cmd_monitor(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

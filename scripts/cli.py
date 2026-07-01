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


def cmd_site_save(args):
    """Save favorite site."""
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


def cmd_site_remove(args):
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


def cmd_route_save(args):
    """Save favorite route."""
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


def cmd_route_remove(args):
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


def check_single_site(site_id, site_name, transport_modes, lines, verbose=False):
    """Check departures and deviations for a single site and return issues."""
    warnings = []

    # 1. Check Deviations
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

    # 2. Check Canceled/Delayed Departures
    dep_url = f"{TRANSPORT_API_URL}/sites/{site_id}/departures"
    dep_data = make_request(dep_url, {
        "transport": transport_modes
    })
    if dep_data and lines:
        line_strs = [str(l) for l in lines]
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
    return warnings


def cmd_site_check(args):
    """Check departures and active disruptions for one or all favorite sites."""
    prefs = load_prefs(args.preferences)
    stops = prefs.get("favourite_stops", [])

    warnings = []

    if args.site_id:
        site_id = int(args.site_id)
        site_name = f"Site {site_id}"
        transport_modes = None
        lines = None

        # Try to resolve details from favorites
        for s in stops:
            if s.get("id") == site_id:
                site_name = s.get("name", site_name)
                transport_modes = s.get("transport_modes")
                lines = s.get("lines")
                break

        sys.stdout.write(f"Checking site {site_name}...\n")
        warnings.extend(check_single_site(site_id, site_name, transport_modes, lines, args.verbose))
    else:
        if not stops:
            sys.stdout.write("No favorite sites configured to check.\n")
            return

        sys.stdout.write("Checking all favorite sites...\n")
        for s in stops:
            site_id = s["id"]
            site_name = s["name"]
            transport_modes = s.get("transport_modes")
            lines = s.get("lines")
            warnings.extend(check_single_site(site_id, site_name, transport_modes, lines, args.verbose))

    # Output Warnings
    if not warnings:
        sys.stdout.write("Status: OK. No disruptions or cancelled departures detected.\n")
        return

    sys.stdout.write(f"Status: WARNING. Detected {len(warnings)} issues:\n")
    for w in warnings:
        sys.stdout.write(f"- [{w['type']}] {w['message']}\n")
        if args.verbose and w.get("details"):
            sys.stdout.write(f"  Details: {w['details']}\n")


def check_single_route(route, warnings, verbose=False):
    """Check departures and deviations for a single route, printing upcoming departures and warnings for each leg."""
    route_name = route["name"]
    legs = route.get("legs", [])
    leg_departures = []
    route_warnings = []

    sys.stdout.write(f"\nChecking route '{route_name}'...\n")

    for i, leg in enumerate(legs):
        from_site = leg.get("from", {})
        from_id = from_site.get("id")
        from_name = from_site.get("name")
        lines = leg.get("lines", [])
        direction_pref = leg.get("direction")

        # Fetch departures for boarding stop starting from current time
        dep_url = f"{TRANSPORT_API_URL}/sites/{from_id}/departures"
        dep_data = make_request(dep_url)

        # 1. Filter by lines
        if dep_data and lines:
            line_strs = [str(l) for l in lines]
            dep_data["departures"] = [
                d for d in dep_data.get("departures", [])
                if d.get("line", {}).get("designation") in line_strs
            ]

        valid_deps = []
        if dep_data:
            for dep in dep_data.get("departures", []):
                if dep.get("state") == "CANCELLED":
                    continue

                # 2. Filter by direction (case-insensitive destination substring or numeric direction code)
                if direction_pref:
                    if isinstance(direction_pref, list):
                        check_dirs = direction_pref
                    else:
                        check_dirs = [direction_pref]

                    dir_matched = False
                    for p_dir in check_dirs:
                        if str(p_dir) in ["1", "2"]:
                            if dep.get("direction_code") == int(p_dir):
                                dir_matched = True
                                break
                        else:
                            d_dir = dep.get("direction", "")
                            d_dest = dep.get("destination", "")
                            if (p_dir.lower() in d_dir.lower()) or (p_dir.lower() in d_dest.lower()):
                                dir_matched = True
                                break
                    if not dir_matched:
                        continue

                valid_deps.append(dep)

        # 3. Apply Sequential Arrival Filtering for subsequent legs
        if i > 0 and leg_departures[i-1]:
            prev_leg = legs[i-1]
            prev_travel = prev_leg.get("travel_time_minutes") or 0
            first_prev_dep = leg_departures[i-1][0]
            first_prev_time = parse_time(first_prev_dep.get("expected") or first_prev_dep.get("scheduled"))
            if first_prev_time:
                earliest_arrival = first_prev_time + timedelta(minutes=prev_travel)
                # Filter departures to only keep those leaving at or after earliest arrival
                filtered_deps = []
                for dep in valid_deps:
                    dep_time = parse_time(dep.get("expected") or dep.get("scheduled"))
                    if dep_time and dep_time >= earliest_arrival:
                        filtered_deps.append(dep)
                valid_deps = filtered_deps

        leg_departures.append(valid_deps)

        # 4. Display upcoming departures for this leg
        line_csv = ", ".join(str(l) for l in lines)
        sys.stdout.write(f"Leg {i+1}: Line {line_csv} from {from_name}\n")
        if not valid_deps:
            sys.stdout.write("  - No upcoming departures found\n")
        else:
            now_time = datetime.now()
            for dep in valid_deps[:3]:
                dest = dep.get("destination", "")
                sched = dep.get("scheduled", "")
                expected = dep.get("expected", sched)
                expected_parsed = parse_time(expected)
                expected_str = expected_parsed.strftime("%H:%M") if expected_parsed else expected
                
                # Format with display string, converting absolute clock time to relative minutes and "Nu" to "now"
                display_time = dep.get("display")
                if display_time:
                    if "nu" in display_time.lower():
                        display_str = "now"
                    elif "min" in display_time.lower():
                        display_str = display_time.lower()
                    else:
                        if expected_parsed:
                            diff_mins = int((expected_parsed - now_time).total_seconds() / 60)
                            display_str = f"{diff_mins} min" if diff_mins > 0 else "now"
                        else:
                            display_str = display_time
                else:
                    if expected_parsed:
                        diff_mins = int((expected_parsed - now_time).total_seconds() / 60)
                        display_str = f"{diff_mins} min" if diff_mins > 0 else "now"
                    else:
                        display_str = ""

                if display_str:
                    sys.stdout.write(f"  - {expected_str} ({dest}) -- {display_str}\n")
                else:
                    sys.stdout.write(f"  - {expected_str} ({dest})\n")

        # Fetch deviations affecting this leg (site or line)
        dev_url = f"{DEVIATIONS_API_URL}/messages"
        seen_dev_headers = set()

        # 1. Query station-wide deviations for this boarding site
        site_devs = make_request(dev_url, {"future": False, "site": from_id})
        if site_devs:
            for dev in site_devs:
                variants = dev.get("message_variants", [])
                if variants:
                    header = variants[0]['header']
                    if header not in seen_dev_headers:
                        seen_dev_headers.add(header)
                        route_warnings.append({
                            "type": "STATION_DISRUPTION",
                            "leg": i + 1,
                            "message": header,
                            "details": variants[0].get("details", "")
                        })

        # 2. Query line-specific deviations for this leg
        for line_id in lines:
            line_devs = make_request(dev_url, {"future": False, "line": line_id})
            if line_devs:
                for dev in line_devs:
                    # Apply strict deviation assessment
                    stop_areas = dev.get("scope", {}).get("stop_areas", [])
                    affected_stop_ids = [sa.get("id") for sa in stop_areas if sa.get("id")]
                    if affected_stop_ids and from_id not in affected_stop_ids:
                        continue

                    variants = dev.get("message_variants", [])
                    if variants:
                        header = variants[0]['header']
                        if header not in seen_dev_headers:
                            seen_dev_headers.add(header)
                            route_warnings.append({
                                "type": "ROUTE_DISRUPTION",
                                "leg": i + 1,
                                "message": header,
                                "details": variants[0].get("details", "")
                            })

    # Evaluate Connections between sequential legs
    for i in range(len(legs) - 1):
        leg1 = legs[i]
        leg2 = legs[i+1]
        travel_time = leg1.get("travel_time_minutes")

        if not travel_time:
            continue

        deps1 = leg_departures[i]
        deps2 = leg_departures[i+1]

        for d1 in deps1[:3]:
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
                    from_name_val = leg1.get("from", {}).get("name", "Origin")
                    d2_dir = matching_d2.get("direction", "destination")
                    route_warnings.append({
                        "type": "TIGHT_CONNECTION",
                        "leg": i + 1,
                        "message": f"({line1} leaving {from_name_val} at {d1_time.strftime('%H:%M')}, expected arrival {arrival_time.strftime('%H:%M')}) to Leg {i+2} ({line2} toward {d2_dir} departing at {d2_time.strftime('%H:%M')}) has only {int(buffer)} min buffer (min required: 5 min)."
                    })

    # Output route-specific warnings immediately below departures
    if route_warnings:
        sys.stdout.write("Warnings:\n")
        grouped = {}
        order = []
        for rw in route_warnings:
            key = (rw["type"], rw["leg"])
            if key not in grouped:
                grouped[key] = []
                order.append(key)
            grouped[key].append(rw)

        for (w_type, leg_num) in order:
            items = grouped[(w_type, leg_num)]
            leg_label = f"Leg {leg_num}"

            if w_type == "STATION_DISRUPTION":
                header_label = f"Station disruption on {leg_label}"
            elif w_type == "ROUTE_DISRUPTION":
                header_label = f"Route disruption on {leg_label}"
            elif w_type == "TIGHT_CONNECTION":
                header_label = f"Tight connection on {leg_label}"
            else:
                header_label = f"{w_type} on {leg_label}"

            if len(items) == 1:
                sys.stdout.write(f"  - {header_label}: {items[0]['message']}\n")
                if verbose and items[0].get("details"):
                    sys.stdout.write(f"    Details: {items[0]['details']}\n")
            else:
                sys.stdout.write(f"  - {header_label}:\n")
                for item in items:
                    sys.stdout.write(f"    - {item['message']}\n")
                    if verbose and item.get("details"):
                        sys.stdout.write(f"      Details: {item['details']}\n")

    warnings.extend(route_warnings)


def cmd_route_check(args):
    """Check departures and connection safety buffer for one or all favorite routes."""
    prefs = load_prefs(args.preferences)
    routes = prefs.get("favourite_routes", [])

    warnings = []

    if args.alias:
        target = None
        for r in routes:
            if r.get("name") == args.alias:
                target = r
                break
        if not target:
            sys.stderr.write(f"Route '{args.alias}' not found in favorites.\n")
            sys.exit(1)

        check_single_route(target, warnings, verbose=args.verbose)
    else:
        if not routes:
            sys.stdout.write("No favorite routes configured to check.\n")
            return

        sys.stdout.write("Checking all favorite routes...\n")
        for r in routes:
            check_single_route(r, warnings, verbose=args.verbose)




# =====================================================================
# Main Parser
# =====================================================================

def main():
    parser = argparse.ArgumentParser(description="SL Trafiklab CLI Tool")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # site namespace
    p_site = subparsers.add_parser("site", help="Site operations")
    site_sub = p_site.add_subparsers(dest="subcommand", help="Site subcommands")

    # site list
    p_list = site_sub.add_parser("list", help="Search/List sites")
    p_list.add_argument("query", help="Search string for stop names")
    p_list.add_argument("--limit", type=int, default=10, help="Maximum search results")

    # site departures
    p_dep = site_sub.add_parser("departures", help="Fetch departures for a site")
    p_dep.add_argument("site_id", help="Numeric Site ID")
    p_dep.add_argument("--line", help="Filter by line designation")
    p_dep.add_argument("--transport", help="Filter by transport mode (BUS, METRO, TRAIN, etc.)")
    p_dep.add_argument("--direction", type=int, choices=[1, 2], help="Filter by direction code")
    p_dep.add_argument("--forecast", type=int, help="Forecast window in minutes")

    # site check
    p_site_chk = site_sub.add_parser("check", help="Check departures and disruptions for one or all favorite sites")
    p_site_chk.add_argument("site_id", nargs="?", help="Optional numeric Site ID to check a single station")
    p_site_chk.add_argument("--preferences", help="Override preferences file path")
    p_site_chk.add_argument("-v", "--verbose", action="store_true", help="Print details of deviations")

    # site save
    p_site_save = site_sub.add_parser("save", help="Save favorite site")
    p_site_save.add_argument("site_id", help="Numeric Site ID")
    p_site_save.add_argument("name", help="Display name for favorite site")
    p_site_save.add_argument("--lines", help="Comma-separated line filters")
    p_site_save.add_argument("--modes", help="Comma-separated transport mode filters")
    p_site_save.add_argument("--preferences", help="Override preferences file path")

    # site remove
    p_site_rem = site_sub.add_parser("remove", help="Remove favorite site")
    p_site_rem.add_argument("site_id", help="Site ID to remove")
    p_site_rem.add_argument("--preferences", help="Override preferences file path")

    # deviations namespace
    p_dev = subparsers.add_parser("deviations", help="Fetch transit deviations")
    p_dev.add_argument("--site", help="Filter by Site ID")
    p_dev.add_argument("--line", help="Filter by line designation")
    p_dev.add_argument("--future", type=bool, default=False, help="Show planned/future deviations")
    p_dev.add_argument("-v", "--verbose", action="store_true", help="Print deviation details")

    # route namespace
    p_route = subparsers.add_parser("route", help="Route operations")
    route_sub = p_route.add_subparsers(dest="subcommand", help="Route subcommands")

    # route check
    p_route_chk = route_sub.add_parser("check", help="Check departures and connection safety buffers for one or all routes")
    p_route_chk.add_argument("alias", nargs="?", help="Optional Route alias to check a single route")
    p_route_chk.add_argument("--preferences", help="Override preferences file path")
    p_route_chk.add_argument("-v", "--verbose", action="store_true", help="Print details of disruptions")

    # route save
    p_route_save = route_sub.add_parser("save", help="Save favorite route")
    p_route_save.add_argument("name", help="Route alias name")
    p_route_save.add_argument("legs_json", help="JSON array of route legs")
    p_route_save.add_argument("--preferences", help="Override preferences file path")

    # route remove
    p_route_rem = route_sub.add_parser("remove", help="Remove favorite route")
    p_route_rem.add_argument("name", help="Route alias to remove")
    p_route_rem.add_argument("--preferences", help="Override preferences file path")

    args = parser.parse_args()

    # Routing
    if args.command == "site":
        if args.subcommand == "list":
            cmd_site_list(args)
        elif args.subcommand == "departures":
            cmd_site_departures(args)
        elif args.subcommand == "check":
            cmd_site_check(args)
        elif args.subcommand == "save":
            cmd_site_save(args)
        elif args.subcommand == "remove":
            cmd_site_remove(args)
        else:
            p_site.print_help()
    elif args.command == "route":
        if args.subcommand == "check":
            cmd_route_check(args)
        elif args.subcommand == "save":
            cmd_route_save(args)
        elif args.subcommand == "remove":
            cmd_route_remove(args)
        else:
            p_route.print_help()
    elif args.command == "deviations":
        cmd_deviations(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""
Sync PM2.5 air quality readings from the NSW Air Quality API into the eczema
app backend.

Designed to run as an hourly cron job. Fetches recent hourly PM2.5 averages
from configured monitoring stations and POSTs them to /api/air-quality.

Usage:
    airquality_sync.py --backend http://localhost:8000

Or set env var: ECZEMA_BACKEND.

Cron example (hourly at :05):
    5 * * * * cd /home/felix/Documents/eczema-app && python3 scripts/airquality_sync.py --backend http://localhost:8000 >> data/airquality_sync.log 2>&1

Data source: NSW Dept of Planning and Environment
    https://data.airquality.nsw.gov.au/api/Data
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx

# Import config from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from config import (
    AIR_QUALITY_API_BASE,
    AIR_QUALITY_STATIONS,
    AIR_QUALITY_PARAMETERS,
    AIR_QUALITY_DEFAULT_HOURS_BACK,
    AIR_QUALITY_MAX_HOURS_BACK,
    AEST_TIMEZONE,
)


def fetch_observations(
    start: datetime, end: datetime
) -> list[dict]:
    """Fetch PM2.5 observations from the NSW Air Quality API."""
    payload = {
        "Parameters": AIR_QUALITY_PARAMETERS,
        "Sites": list(AIR_QUALITY_STATIONS.keys()),
        "StartDate": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "EndDate": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "Categories": ["Averages"],
        "Frequency": ["Hourly average"],
    }

    resp = httpx.post(
        f"{AIR_QUALITY_API_BASE}/get_Observations",
        json=payload,
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def transform_observations(raw: list[dict]) -> list[dict]:
    """Transform NSW API response into our schema."""
    local_tz = ZoneInfo(AEST_TIMEZONE)
    readings = []
    for obs in raw:
        site_id = obs.get("Site_Id")
        if site_id not in AIR_QUALITY_STATIONS:
            continue

        date_str = obs.get("Date", "")
        hour = obs.get("Hour", 0)
        if not date_str:
            continue

        # NSW API times are in AEST/AEDT — convert to UTC for storage
        try:
            local_dt = datetime.strptime(date_str[:10], "%Y-%m-%d").replace(
                hour=int(hour), tzinfo=local_tz
            )
        except (ValueError, TypeError):
            continue
        utc_dt = local_dt.astimezone(timezone.utc)

        value = obs.get("Value")
        if isinstance(value, dict):
            value = value.get("Value")

        param = obs.get("Parameter")
        if isinstance(param, dict):
            param_code = param.get("ParameterCode", "PM2.5")
        else:
            param_code = "PM2.5"

        readings.append({
            "timestamp": utc_dt.isoformat().replace("+00:00", "Z"),
            "site_id": site_id,
            "site_name": AIR_QUALITY_STATIONS[site_id],
            "parameter": param_code,
            "value": float(value) if value is not None else None,
            "unit": "µg/m³",
            "category": obs.get("AirQualityCategory"),
        })
    return readings


def post_readings(backend: str, readings: list[dict]) -> dict:
    """POST readings to the eczema backend; return {inserted, total}."""
    url = backend.rstrip("/") + "/api/air-quality"
    resp = httpx.post(
        url,
        json={"readings": readings, "source": "nsw_dpie"},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync NSW PM2.5 air quality data into the eczema app."
    )
    parser.add_argument(
        "--backend",
        default=os.environ.get("ECZEMA_BACKEND"),
        help="Eczema app backend base URL (or env ECZEMA_BACKEND)",
    )
    parser.add_argument(
        "--hours-back",
        type=int,
        default=AIR_QUALITY_DEFAULT_HOURS_BACK,
        help=f"Hours of history to fetch (default {AIR_QUALITY_DEFAULT_HOURS_BACK}, "
             f"max {AIR_QUALITY_MAX_HOURS_BACK})",
    )
    parser.add_argument(
        "--start-date",
        help="Explicit start date for backfill (ISO format, e.g. 2026-04-01)",
    )
    parser.add_argument(
        "--end-date",
        help="Explicit end date for backfill (ISO format, e.g. 2026-04-16)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch from NSW API but don't POST to backend",
    )
    args = parser.parse_args()

    if not args.dry_run and not args.backend:
        parser.error("--backend is required unless --dry-run (or set ECZEMA_BACKEND)")

    # Determine time range
    if args.start_date or args.end_date:
        local_tz = ZoneInfo(AEST_TIMEZONE)
        if args.start_date:
            start = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=local_tz)
        else:
            start = datetime.now(timezone.utc) - timedelta(hours=AIR_QUALITY_DEFAULT_HOURS_BACK)
        if args.end_date:
            end = datetime.strptime(args.end_date, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=local_tz
            )
        else:
            end = datetime.now(timezone.utc)
    else:
        hours_back = min(args.hours_back, AIR_QUALITY_MAX_HOURS_BACK)
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours_back)

    start_local = start.astimezone(ZoneInfo(AEST_TIMEZONE))
    end_local = end.astimezone(ZoneInfo(AEST_TIMEZONE))
    print(
        f"Fetching PM2.5 data from {start_local:%Y-%m-%d %H:%M} to {end_local:%Y-%m-%d %H:%M} AEST "
        f"({len(AIR_QUALITY_STATIONS)} stations)...",
        file=sys.stderr,
    )

    try:
        raw = fetch_observations(start, end)
    except Exception as e:
        print(f"API fetch failed: {e}", file=sys.stderr)
        return 1

    readings = transform_observations(raw)
    stations_seen = len(set(r["site_id"] for r in readings))
    print(
        f"Got {len(readings)} readings from {stations_seen} station(s)",
        file=sys.stderr,
    )

    if not readings:
        print("No readings returned.", file=sys.stderr)
        return 0

    if args.dry_run:
        for r in readings[:10]:
            val = f"{r['value']:.1f}" if r["value"] is not None else "null"
            print(
                f"  {r['timestamp']} | {r['site_name']:20s} | "
                f"PM2.5={val} µg/m³ [{r['category']}]"
            )
        if len(readings) > 10:
            print(f"  ... and {len(readings) - 10} more")
        return 0

    print(f"POSTing to {args.backend}...", file=sys.stderr)
    try:
        result = post_readings(args.backend, readings)
    except Exception as e:
        print(f"POST failed: {e}", file=sys.stderr)
        return 1

    print(
        f"Saved {result['inserted']} new readings "
        f"({result['total'] - result['inserted']} already on file)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

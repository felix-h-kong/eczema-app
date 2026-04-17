# Add Outdoor PM2.5 Air Quality Tracking

## Context

Back-burning smoke is a plausible trigger for eczema flares (supported by literature: Fadadu et al. 2021 JAMA Dermatology). Felix has noted wheezing and back-burning on recent flare days but has no air quality data to correlate with. This feature adds automated hourly PM2.5 ingestion from the NSW government Air Quality API so we can start building that dataset.

## Data Source

**NSW Air Quality API** — no auth required.

- Base: `https://data.airquality.nsw.gov.au/api/Data`
- `GET /get_SiteDetails` — all stations
- `GET /get_ParameterDetails` — parameter codes, units, frequencies
- `POST /get_Observations` — hourly PM2.5 averages by station + date range
- API docs: https://data.airquality.nsw.gov.au/docs/index.html
- User guide PDF: https://www.environment.nsw.gov.au/research-and-publications/publications-search/air-quality-application-programming-interface-api-user-guide

**Example request** (`POST /get_Observations`):
```json
{
    "Parameters": ["PM2.5"],
    "Sites": [70, 113, 155, 1001, 1007, 15],
    "StartDate": "2026-04-15T00:00:00",
    "EndDate": "2026-04-16T00:00:00",
    "Categories": ["Averages"],
    "Frequency": ["Hourly average"]
}
```

Response: array of objects with `Site_Id`, `Date`, `Hour`, `Value`, `AirQualityCategory`, `Parameter` info.

**Stations to poll** (covers home in North/NW Sydney + CBD/Redfern for work/outings):

| Site ID | Name            | Area             |
|---------|-----------------|------------------|
| 70      | Lindfield       | North            |
| 113     | Macquarie Park  | North-west       |
| 155     | Rouse Hill      | North-west       |
| 1001    | Cook and Phillip| Sydney CBD       |
| 1007    | Ultimo-UTS      | Sydney CBD       |
| 15      | Alexandria      | Near Redfern     |

**Historical backfill:** The API accepts arbitrary date ranges via `StartDate`/`EndDate`, so we can backfill weeks/months of historical data on first run (not just the rolling 25h window). The sync script supports `--hours-back N` (up to 168h = 7 days per run). For longer backfill, use `--start-date` / `--end-date` flags.

**Other data sources considered but deferred:**
- **RFS hazard reduction burns:** GeoJSON feed at `rfs.nsw.gov.au/feeds/majorIncidents.json` (filter `category: "Planned Burn"`) and community feed at `beyondtracks.com/contrib/nsw-rfs-hazardreduction.geojson`. Useful for "why was PM2.5 high?" context but not needed for v1.
- **Xiaomi air purifier (indoor PM2.5):** Accessible via python-miio library. Deferred — outdoor PM2.5 is more relevant to back-burning correlation.

## Scope

**In scope:** database table, backend API, sync script, cron setup, tests, frontend API types.
**Out of scope:** frontend UI/charts, flare correlation in analysis.py, location-based effective AQI (future — depends on location tracking from `docs/location-tracking-design.md`).

## Implementation

### 1. Config — `backend/config.py`

Add constants:
```python
AIR_QUALITY_API_BASE = "https://data.airquality.nsw.gov.au/api/Data"
AIR_QUALITY_STATIONS = {
    70: "Lindfield",
    113: "Macquarie Park",
    155: "Rouse Hill",
    1001: "Cook and Phillip",
    1007: "Ultimo-UTS",
    15: "Alexandria",
}
AIR_QUALITY_PARAMETERS = ["PM2.5"]
AIR_QUALITY_DEFAULT_HOURS_BACK = 25   # 1h overlap for hourly cron
AIR_QUALITY_MAX_HOURS_BACK = 168      # max backfill = 7 days
```

### 2. Database — `backend/db.py`

New table in `init()`:
```sql
CREATE TABLE IF NOT EXISTS air_quality_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    site_id INTEGER NOT NULL,
    site_name TEXT NOT NULL,
    parameter TEXT NOT NULL DEFAULT 'PM2.5',
    value REAL,
    unit TEXT DEFAULT 'µg/m³',
    category TEXT,
    source TEXT NOT NULL DEFAULT 'nsw_dpie',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(timestamp, site_id, parameter)
);
CREATE INDEX IF NOT EXISTS idx_aq_timestamp ON air_quality_readings(timestamp);
CREATE INDEX IF NOT EXISTS idx_aq_site ON air_quality_readings(site_id);
```

Design notes:
- Separate table from `environment_readings` (indoor temp/humidity) — different source semantics
- `UNIQUE(timestamp, site_id, parameter)` — dedup key allows multiple stations per hour
- `value` is nullable — stores "checked but no data" vs "didn't check"
- `category` stores the API's AirQualityCategory string (e.g. "Good", "Fair", "Poor")
- `site_name` denormalized to avoid joins (station list is tiny and stable)

Two new methods mirroring the existing `insert_environment_readings` / `list_environment_readings` pattern:
- `insert_air_quality_readings(readings, source="nsw_dpie")` — INSERT OR IGNORE, returns count
- `list_air_quality_readings(from_date, to_date, site_id)` — date range + optional site filter

### 3. API — `backend/main.py`

New Pydantic models (`AirQualityReading`, `AirQualitySyncRequest`) and two endpoints following the existing `/api/environment` pattern:
- `POST /api/air-quality` — batch insert, returns `{inserted, total}`
- `GET /api/air-quality?from=&to=&site_id=` — query with filters

### 4. Sync Script — `scripts/airquality_sync.py` (new file)

Standalone script (mirrors `scripts/govee_sync.py` pattern):
- `fetch_observations(hours_back)` — POST to NSW API for PM2.5 hourly averages
- `transform_observations(raw)` — convert NSW API response (AEST date+hour) to our schema (UTC ISO timestamps)
- `post_readings(backend, readings)` — POST to `/api/air-quality`
- CLI args: `--backend URL`, `--hours-back N` (default 25), `--start-date` / `--end-date` (for historical backfill), `--dry-run`
- Uses `httpx` for HTTP
- Converts NSW API's AEST timestamps to UTC using `zoneinfo` + existing `AEST_TIMEZONE` config

Cron entry (hourly):
```
5 * * * * cd /home/felix/Documents/eczema-app && python3 scripts/airquality_sync.py --backend http://localhost:8000 >> data/airquality_sync.log 2>&1
```

### 5. Frontend Types — `frontend/src/api.ts`

Add `AirQualityReading` interface and `getAirQualityReadings()` function (read-only — sync is backend-only).

### 6. Tests

- `backend/tests/test_db.py`: insert, dedup, null values, date/site filtering
- `backend/tests/test_main.py`: POST batch, dedup, GET with filters

## Verification

1. Run existing tests: `cd backend && python -m pytest`
2. Start backend: `cd backend && python main.py`
3. Dry-run the sync script: `python scripts/airquality_sync.py --dry-run` — should print sample PM2.5 readings from the 6 stations
4. Live sync: `python scripts/airquality_sync.py --backend http://localhost:8000`
5. Query the API: `curl 'http://localhost:8000/api/air-quality?from=2026-04-15'` — should return stored readings
6. Run full tests again to confirm nothing broke

## Future: Location-Based Effective AQI

Once location tracking (`docs/location-tracking-design.md`) is implemented, we can compute an "effective AQI" by matching location pings to the nearest monitoring station. This would give a personalised air quality exposure score based on where Felix actually was during the day, rather than a fixed set of stations. The `air_quality_readings` table already stores per-station data, so the join is straightforward: for each location ping, find the nearest station by haversine distance and look up the corresponding hourly PM2.5 reading.

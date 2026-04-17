# Location Tracking — Implementation Design

Track location throughout the day to correlate environments/places with eczema flares. Auto-label locations via reverse geocoding, allow user overrides (e.g. "Home", "Office", "In-laws").

## Architecture

```
GPSLogger / OwnTracks (Android)  --HTTP POST-->  Python backend --> SQLite
                                                       |
                                                       v
                                              Nominatim (reverse geocode)
```

## App choice: undecided

Two strong candidates. Either works — decision comes down to battery priority vs reliability priority.

### Option A: OwnTracks (significant changes mode)

- Uses Google Fused Location Provider (smarter, more battery-efficient)
- Detects cell/WiFi transitions — purpose-built for "you moved from A to B"
- Disk-backed HTTP queue, 10k retries — very reliable delivery
- Fixed JSON payload format (we adapt our endpoint to it)
- Available on Play Store
- ~2-5% battery/day
- Single maintainer risk (growse)

### Option B: GPSLogger (passive + fallback GPS)

- Passive mode piggybacks on other apps' location requests (near-zero battery)
- Add a fallback GPS ping every ~15-30 min if no passive fix arrives
- Enable "significant motion" sensor to skip logging when stationary
- Fully customisable HTTP payload (we design the format)
- Only 3 HTTP retries — need CSV local logging as backup + batch auto-send
- F-Droid / APK only (not on Play Store)
- Single maintainer (mendhak, but 15 years of continuous development)
- Does NOT use Fused Location Provider (less battery-efficient for active GPS)
- Log to CSV + HTTP simultaneously for durability

### Recommendation

OwnTracks is simpler and more reliable for the core use case ("which place am I at").
GPSLogger is more flexible and potentially lower battery if passive mode gets enough fixes.

Try OwnTracks first. If battery is a problem, switch to GPSLogger passive+fallback.

## Backend

### New table: location_pings

```sql
CREATE TABLE IF NOT EXISTS location_pings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    accuracy REAL,
    battery REAL,
    source TEXT NOT NULL DEFAULT 'owntracks',  -- or 'gpslogger'
    raw_json TEXT,  -- store full payload for debugging
    location_id INTEGER,  -- FK to locations, set by matching
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (location_id) REFERENCES locations(id)
);
```

### New table: locations (named places)

```sql
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,  -- "Home", "Campus A", or auto from geocoding
    auto_name TEXT,  -- original name from reverse geocoding
    latitude REAL NOT NULL,  -- cluster centre
    longitude REAL NOT NULL,
    radius_m REAL NOT NULL DEFAULT 150,
    user_override INTEGER NOT NULL DEFAULT 0,  -- 1 if user renamed it
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

### New endpoints

```
POST /api/location/ping          -- receive ping from OwnTracks/GPSLogger
GET  /api/locations               -- list named locations
PUT  /api/locations/{id}          -- rename / edit a location
GET  /api/location/history        -- query location history (date range, etc.)
GET  /api/location/timeline       -- daily timeline view
```

### OwnTracks webhook format

OwnTracks POSTs to a single endpoint (conventionally `/pub`):

```json
{
    "_type": "location",
    "tid": "FK",
    "lat": -33.8688,
    "lon": 151.2093,
    "acc": 25,
    "tst": 1713234567,
    "batt": 85,
    "vel": 0
}
```

Must return a JSON response (can be empty `{}`).

### GPSLogger webhook format (if we go that route)

Template-based — we'd configure it to POST:

```json
{
    "lat": %LAT,
    "lon": %LON,
    "timestamp": "%TIMESTAMP",
    "accuracy": %ACC,
    "battery": %BATT,
    "speed": %SPD
}
```

### Reverse geocoding

Use OpenStreetMap Nominatim (free, no API key):

```
GET https://nominatim.openstreetmap.org/reverse?lat=-33.87&lon=151.21&format=json
```

- Rate limit: 1 request/second
- Batch geocode: don't geocode every ping — geocode when a new cluster is detected
- Extract suburb/road from response as default location name

### Location matching logic

On each incoming ping:

1. Check if coords fall within any existing location's radius
2. If yes: set `location_id` on the ping
3. If no: leave unmatched — periodically scan for clusters of unmatched pings
4. When a new cluster is found (3+ pings within 150m of each other):
   - Reverse geocode the cluster centre
   - Create a new location with auto_name from geocoding
   - Backfill location_id on the clustered pings

### Haversine distance

For matching pings to locations (~150m radius at Sydney latitudes):

```python
from math import radians, sin, cos, sqrt, atan2

def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000  # earth radius in metres
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon/2)**2
    return R * 2 * atan2(sqrt(a), sqrt(1-a))
```

## Frontend

### Location management page

- List all named locations with ping count
- Tap to rename (override auto-generated name)
- Tap to adjust radius
- Delete a location (pings become unmatched again)
- "Add current location" button (grabs phone GPS, reverse geocodes, creates entry)

### Timeline view

- Daily view showing location transitions: "Home 7:00-8:30 → Campus A 9:00-17:00 → Home 17:30-..."
- Tap a segment to see pings on a map

### Integration with existing logs

- Show location label on existing log entries (meals, flares, meds) by matching log timestamp to nearest location ping
- Analysis: correlate locations with flare frequency

## Security

- Webhook endpoint needs auth (API key or basic auth) — OwnTracks supports basic auth
- Nominatim gets your coordinates (acceptable for self-hosted personal use)
- Raw coords stored in DB — fine since self-hosted

## Implementation order

1. Backend: tables + ping endpoint + basic auth
2. OwnTracks setup: install app, configure HTTP mode pointing at backend
3. Let it collect data for a few days
4. Backend: clustering + reverse geocoding + location matching
5. Frontend: location management page
6. Frontend: timeline view
7. Frontend: integrate location labels into existing log views
8. Analysis: add location as a factor in correlations

## Open questions

- What cluster radius works best? Start with 150m, tune later.
- Should we store pings indefinitely or prune old ones? Probably keep all — disk is cheap.
- Do we need a map view? Nice to have but not essential for v1.
- How to handle travel/transit? Probably just "Unknown" for pings that don't match any location.

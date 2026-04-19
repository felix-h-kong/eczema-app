# Govee H5075 Sync — Design

Sync temperature/humidity data from a portable Govee H5075 BLE sensor into the eczema app. The sensor travels with the user (desk at home, desk at work, etc.). The phone scans for BLE advertisements automatically every ~10 minutes (foreground) or ~15 minutes (background), reads the live temp/humidity from the manufacturer data, and sends it to the backend.

A successful scan serves as a co-location signal — if the phone saw the sensor, the user was physically present for that reading.

## Status

**Backend: complete.** `environment_readings` table, `POST /api/environment`, `GET /api/environment` — all implemented and tested (17 tests).

**Capacitor app: complete.** Native Android shell wrapping the PWA, with `@capacitor-community/bluetooth-le` for BLE and `@transistorsoft/capacitor-background-fetch` for background tasks.

**Advertisement scanning: implemented, needs on-device testing.** `scanForReading()` in `govee.ts` scans for the H5075's BLE advertisement and decodes temp/humidity from manufacturer data. The exact byte offset in the payload needs empirical confirmation on first run (debug logging is built in).

**GATT history download: implemented, kept as fallback.** `syncH5075History()` connects via GATT and downloads stored readings (up to ~2 days). Available for future backfill but not the primary sync path.

**Foreground polling: implemented.** 10-minute `setInterval` when the app is open.

**Background sync: implemented.** 15-minute `BackgroundFetch` (Android minimum) when the app is closed.

**UI: implemented.** Floating LED indicator (green/amber/grey) on all pages with tap-to-expand details. Dedicated "Env" tab with Chart.js time series visualization (24h default, pinch-to-zoom, drag-to-pan).

## Sensor details

- **Model:** Govee H5075
- **MAC:** `A4:C1:38:59:69:C3` (Govee OUI: `A4:C1:38`)
- **Broadcast name:** `GVH5075_69C3`
- **Advertised service UUID:** `0000ec88-0000-1000-8000-00805f9b34fb` (short UUID 0xEC88)
- **Manufacturer data company ID:** `0xEC88` (in main advertisement, carries live temp/humidity)
- **On-device storage:** ~2 days of minute-by-minute readings
- **Cloud API:** not available for BLE-only models (H5075 is `isAPIDevice: false`)
- **Usage:** portable — user carries the sensor between locations

## Architecture

```
Govee H5075  --BLE-->  Capacitor Android app   --HTTP-->  Python backend --> SQLite
                       (hourly background sync)            (on server)
```

Phone must be in BLE range (~10m). Backend must be network-reachable.

### Sync flow

1. Background task fires (hourly)
2. App scans for the sensor by name prefix (`GVH5075`) or MAC
3. If found: connect, download last 2 hours of readings, POST to backend
4. If not found (out of range, sensor off): silently skip, retry next hour
5. Backend deduplicates on timestamp (INSERT OR IGNORE), so overlapping windows are safe

### Why hourly

- Sensor stores ~2 days (~2880 readings). Hourly sync means ~48 attempts per storage window — plenty of redundancy for missed syncs.
- Each hourly sync only needs to pull ~60 readings (1 hour of minute-by-minute data), though requesting a wider window (e.g. last 2 hours) provides overlap for resilience.
- Full 2-day download takes ~30-60 seconds; a 2-hour window is much faster.

## Backend (complete)

### Table

```sql
CREATE TABLE IF NOT EXISTS environment_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL UNIQUE,
    temperature REAL NOT NULL,
    humidity REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'govee_h5075',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

UNIQUE on timestamp so re-syncs are safe (INSERT OR IGNORE).

### Endpoints

```
POST /api/environment  — batch insert [{timestamp, temperature, humidity}, ...]
GET  /api/environment  — query with ?from=&to= for charts
```

### Files

- `backend/db.py` — table + `insert_environment_readings()`, `list_environment_readings()`
- `backend/main.py` — `EnvironmentReading` / `EnvironmentSyncRequest` models + endpoints
- `backend/tests/test_db.py` — 8 tests for DB layer
- `backend/tests/test_main.py` — 9 tests for API endpoints

## H5075 BLE protocol

Protocol reverse-engineered by Heckie75:
https://github.com/Heckie75/govee-h5075-thermo-hygrometer

### GATT details (post-connection)

- GATT service: `494e5445-4c4c-495f-524f-434b535f4857` (ASCII: "INTELLI_ROCKS_HW")
- Command characteristic (write + notify): `494e5445-4c4c-495f-524f-434b535f2012`
- Data characteristic (notify only): `494e5445-4c4c-495f-524f-434b535f2013`

Note: the GATT service UUID is different from the advertised service UUID (`0000ec88...`). The GATT UUID is only discoverable after connection.

### Protocol sequence

1. Scan for device (by name prefix `GVH5075` or known MAC address)
2. Connect GATT, get service, get characteristics
3. Subscribe to notifications on command + data characteristics
4. Write history request to command char: `33 01 [start_hi start_lo] [end_hi end_lo] ...pad... checksum`
   - For hourly sync: `00 78` = 120 minutes (2 hours back, for overlap)
   - `00 01` = up to 1 minute ago
   - For manual full sync: `0B 40` = 2880 minutes = 2 days back
5. Receive ack on command char: `33 01 00 ...`
6. Receive data notifications (20 bytes each, 6 records per message)
7. Receive completion on command char: `EE 01 [count_hi] [count_lo] ...`

### Data decoding

Each record is 3 bytes:
```
raw = (b0 << 16) | (b1 << 8) | b2
isNegative = !!(raw & 0x800000)
if (isNegative) raw ^= 0x800000
temperature = floor(raw / 1000) / 10   // Celsius
humidity = (raw % 1000) / 10            // % RH
```

Example: bytes `03 71 E7` → raw 225767 → 22.5°C, 76.7% RH (verified in tests).

### Timestamps

Device sends "minutes ago" as big-endian uint16 (bytes 0-1 of each notification). Convert to absolute time using the moment the request was sent:
```
timestamp = requestTime - (minutesBack * 60000)
```

### Message format

All commands are 20 bytes, zero-padded, with XOR checksum in byte 19.

## Frontend

### Existing files

- `frontend/src/govee.ts` — BLE protocol implementation (~200 lines). Includes `buildCommand()`, `decodeRecord()` (pure, tested), `syncH5075()`. Currently uses Web Bluetooth — needs migration to Capacitor BLE plugin.
- `frontend/src/api.ts` — `EnvironmentReading` type, `submitEnvironmentReadings()`, `getEnvironmentReadings()`
- `frontend/src/pages/LogHub.tsx` — manual "Sync Govee sensor" button with progress display, error handling, wake lock

### Remaining work

1. **Capacitor setup** — wrap the existing PWA in a Capacitor Android shell. Install `@capacitor-community/bluetooth-le`.
2. **BLE transport swap** — replace Web Bluetooth calls in `govee.ts` with Capacitor BLE plugin equivalents. Protocol logic (packet parsing, checksum, decode) is unchanged.
3. **Background sync** — register an hourly background task that runs the sync without user interaction. On Android, this likely uses WorkManager or AlarmManager via a Capacitor background task plugin.
4. **Manual sync button** — keep the existing manual sync in LogHub as a fallback (e.g. after being away from the sensor for >2 days).

### Dev workflow

Configure Capacitor to load from the Vite dev server URL for hot reload on all non-native changes. Only rebuild the APK when native plugin code changes.

## Utility script

`scripts/govee_sync.py` — standalone Python script using `bleak` for BLE on Linux. Useful for testing the protocol on a laptop/desktop with Bluetooth, or as a manual sync tool. Not part of the primary phone-based flow.

## Dead ends (reference)

**Web Bluetooth on Chrome Android:** The H5075 broadcasts its name and service UUID in its advertisement, but Chrome's Web Bluetooth picker does not show the device — even with `acceptAllDevices: true`. nRF Connect sees it immediately. This is a known class of Chrome-on-Android limitation with certain BLE advertisement formats. Tested with name prefix filter, service UUID filter, manufacturer data filter, and no filter. None worked.

**Termux + Python (bleak):** `bleak` on Android requires Android's framework Bluetooth APIs (`android.bluetooth.*`), which are only accessible from inside a real Android app process. Termux runs a Linux userland without access to these APIs. BlueZ is not available in Termux either (requires root + HCI socket access). Termux:API does not expose BLE GATT operations. Dead end on non-rooted devices.

**Govee cloud API:** The H5075 is flagged `isAPIDevice: false` in Govee's system. Even though the Govee app syncs data to their cloud for 2-year retention, the public developer API does not expose BLE device data. Only WiFi-capable models (H5179, H5100) are API-accessible.

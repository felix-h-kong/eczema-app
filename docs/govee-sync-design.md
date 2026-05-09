# Govee H5075 Sync — Implementation Design

> **Status (2026-04-21): Abandoned.** All sync paths attempted (Web Bluetooth PWA, Capacitor native wrapper, Termux+bleak) failed for different reasons — see [Postmortem](#postmortem-202604) at the bottom. The reverse-engineered protocol details below are preserved as a reference if anyone wants to try again with a different platform (e.g. iOS, dedicated Pi, ESP32 bridge).

Sync temperature/humidity data from a Govee H5075 BLE sensor into the eczema app via Web Bluetooth. User taps a button in the app, phone connects to the sensor, downloads stored history, sends it to the backend.

## Architecture

```
Govee H5075  --BLE-->  Phone browser (Web Bluetooth)  --HTTP-->  Python backend --> SQLite
```

Phone must be in BLE range (~10m). Backend can be anywhere.

## Hardware

- Govee H5075 (~$20 AUD, battery-operated, stores 2 days on device)
- Android phone with Chrome (Web Bluetooth support)

## Backend

### New table

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

### New endpoints

```
POST /api/environment  — batch insert [{timestamp, temperature, humidity}, ...]
GET  /api/environment  — query with ?from=&to= for charts
```

### Files to change

- `db.py` — new table in init(), insert/query methods
- `main.py` — two new endpoints

## Frontend

### New file: `govee.ts`

Web Bluetooth module. Protocol based on Heckie75's reverse-engineering:
https://github.com/Heckie75/govee-h5075-thermo-hygrometer

#### GATT details

- Service: `494e5445-4c4c-495f-524f-434b535f4857`
- Command characteristic (write + notify): `494e5445-4c4c-495f-524f-434b535f2012`
- Data characteristic (notify only): `494e5445-4c4c-495f-524f-434b535f2013`

#### Protocol sequence

1. `navigator.bluetooth.requestDevice({ filters: [{ namePrefix: 'GVH5075' }], optionalServices: [SERVICE_UUID] })`
2. Connect GATT, get service, get characteristics
3. Subscribe to notifications on command + data characteristics
4. Write history request to command char: `33 01 0B 40 00 01 ...pad... checksum`
   - `0B 40` = 2880 minutes = 2 days back
   - `00 01` = up to 1 minute ago
5. Receive ack on command char: `33 01 00 ...`
6. Receive ~480 data notifications (20 bytes each, 6 records per message)
7. Receive completion on command char: `EE 01 [count_hi] [count_lo] ...`

#### Data decoding

Each record is 3 bytes:
```js
raw = (b0 << 16) | (b1 << 8) | b2
isNegative = !!(raw & 0x800000)
if (isNegative) raw ^= 0x800000
temperature = Math.floor(raw / 1000) / 10  // Celsius
humidity = (raw % 1000) / 10               // % RH
```

#### Timestamps

Device sends "minutes ago" as big-endian uint16 (bytes 0-1 of each notification). Convert to absolute time using the request timestamp:
```js
new Date(requestTime.getTime() - minutesBack * 60000)
```

#### Message format

All commands are 20 bytes, zero-padded, with XOR checksum in byte 19:
```js
let xor = 0;
for (let i = 0; i < 19; i++) xor ^= buf[i];
buf[19] = xor;
```

### Files to change

- New `govee.ts` — BLE connect, protocol, decode (~120 lines)
- `api.ts` — new `submitEnvironmentReadings()` function
- `LogHub.tsx` — add "Sync Sensor" button
- `History.tsx` — overlay temp/humidity on severity chart (later)

## Constraints

- Web Bluetooth requires HTTPS (or localhost)
- Web Bluetooth requires user gesture (button tap) — cannot auto-sync
- Chrome on Android only (not Safari/Firefox)
- ~30-60 seconds for full 2-day download
- Sensor stores 2 days max — sync at least every 2 days to avoid gaps

## Not needed

- No Raspberry Pi
- No Govee cloud API (H5075 is BLE-only, not exposed)
- No Termux
- No background scanning — user-initiated foreground sync only

---

## Postmortem (2026-04)

This section records what was tried, what failed, and why — so the next person (or future me) doesn't re-walk the same dead ends.

**Goal:** continuous indoor temperature/humidity logging correlated with eczema severity, with the sensor carried around (home, office, gym bag) on a single battery-powered device.

### What was attempted

**1. Web Bluetooth PWA (the original design above).**
- Worked end-to-end on desktop Chrome.
- On Android Chrome: `requestDevice()` shows the picker but the H5075 inconsistently appeared, and connections dropped mid-history-transfer ~50% of the time.
- Killer constraint: PWAs cannot use Web Bluetooth in the background, *and* Web Bluetooth requires a fresh user gesture every connect. So even when it worked, the user had to open the app and tap a button — which defeats the point of "always-on" environment logging.
- Verdict: dead end on Android. Documented for posterity, do not retry.

**2. Termux + Python `bleak`.**
- Considered as a way to run an unattended sync script on the phone. Termux's BLE story is broken: no permission to access Android's BluetoothAdapter from a non-system app shell. The `scripts/govee_sync.py` Python script in the repo works fine on Linux desktop but not on Android via Termux.
- Verdict: do not retry on Android. (Script kept for desktop/Pi use.)

**3. Capacitor native Android wrapper (commit 3d47806, reverted in 4f5f6a7).**
- Wrapped the existing PWA in a Capacitor shell so we could call native BLE APIs via `@capacitor-community/bluetooth-le`.
- Two sync modes: foreground `setInterval` every 10 min while app open, background `BackgroundFetch` every 15 min.
- Quick GATT-connect-and-read-latest design (not full history download) to keep each sync <5 s.
- **Why it was abandoned:**
  1. **Battery drain.** Even with 15-min BackgroundFetch intervals, BLE scanning + GATT connect attempts noticeably drained the phone over a day.
  2. **Background sync was unreliable.** Android aggressively kills BackgroundFetch tasks under Doze and battery optimisation. In practice, background readings stopped within hours of last foreground use, leaving large gaps.
  3. **Maintenance cost.** Capacitor adds an Android Studio + Gradle build pipeline to a project that was otherwise just `vite build` + a Python backend. Not worth it for one feature.
- Verdict: technically functional but operationally not viable for "wear it around" use.

### Why none of these worked for the actual use case

The use case is "carry a small BLE sensor around all day and have its readings end up in the database without me thinking about it." That requires *something* doing background BLE scanning reliably with low power impact. Android phones are not that something — battery optimisation will always kill long-lived BLE listeners from third-party apps.

The right architecture would be a dedicated always-on BLE gateway (Pi Zero W, ESP32, or similar) co-located with the sensor — but that contradicts the "carry it around" requirement. There's no good solution for portable continuous sync without the user wearing both the sensor and a gateway.

### Decision (2026-04-21)

**Abandon automated sync. Capture environment context manually as notes** in the existing NoteLog ("hot office today", "cold gym", "humid bathroom after shower"). Less precise but zero infrastructure cost and zero battery impact.

### What was kept

- `docs/govee-sync-design.md` — this file (protocol reference).
- `scripts/govee_sync.py` — works on Linux/Pi if anyone wants to set up a stationary gateway later.
- `environment_readings` DB table + `POST/GET /api/environment` endpoints — harmless to leave; the table just stays empty.
- `frontend/src/govee.ts` — Web Bluetooth client. Dead code on Android but functional on desktop Chrome; kept in case of a future stationary-gateway approach.

### What was removed (in revert 4f5f6a7)

- `frontend/android/` Capacitor project + Gradle build
- `@capacitor-community/bluetooth-le`, `@transistorsoft/capacitor-background-fetch` deps
- `frontend/src/background-sync.ts`, `foreground-sync.ts`, `govee-protocol.ts`, `govee-state.ts`, `useSensorState.ts`
- `frontend/src/components/SensorLED.tsx` (floating sensor status dot)
- `frontend/src/pages/Environment.tsx` (Chart.js temp/humidity time series)

# Govee H5075 Sync — Implementation Design

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

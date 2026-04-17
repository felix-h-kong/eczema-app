#!/usr/bin/env python3
"""
Sync Govee H5075 stored readings into the eczema app backend.

Designed to run from Termux on Android (where Web Bluetooth fails) but works
on any Linux machine with Bluetooth in range of the sensor.

Connects to the H5075 by MAC address, downloads stored historical
temperature/humidity readings (up to ~2 days), POSTs them to the backend's
`/api/environment` endpoint.

Usage:
    govee_sync.py --mac A4:C1:38:59:69:C3 --backend https://your-server/

Or set env vars: GOVEE_MAC, ECZEMA_BACKEND.

Protocol reverse-engineered by Heckie75:
    https://github.com/Heckie75/govee-h5075-thermo-hygrometer
"""

import argparse
import asyncio
import math
import os
import sys
from datetime import datetime, timezone

import httpx
from bleak import BleakClient, BleakScanner

# --- BLE UUIDs ---
SERVICE_UUID = "494e5445-4c4c-495f-524f-434b535f4857"
COMMAND_CHAR_UUID = "494e5445-4c4c-495f-524f-434b535f2012"
DATA_CHAR_UUID = "494e5445-4c4c-495f-524f-434b535f2013"


def build_command(cmd_bytes: list[int], params: list[int] | None = None) -> bytes:
    """Build a 20-byte command packet with XOR checksum at byte 19."""
    buf = bytearray(20)
    buf[: len(cmd_bytes)] = cmd_bytes
    if params:
        buf[len(cmd_bytes) : len(cmd_bytes) + len(params)] = params
    xor = 0
    for i in range(19):
        xor ^= buf[i]
    buf[19] = xor
    return bytes(buf)


def decode_record(b0: int, b1: int, b2: int) -> tuple[float, float]:
    """Decode a 3-byte historical record into (temperature_c, humidity_pct)."""
    raw = (b0 << 16) | (b1 << 8) | b2
    is_negative = bool(raw & 0x800000)
    if is_negative:
        raw ^= 0x800000
    temperature = math.floor(raw / 1000) / 10.0
    if is_negative:
        temperature = -temperature
    humidity = (raw % 1000) / 10.0
    return temperature, humidity


def is_padding(b0: int, b1: int, b2: int) -> bool:
    return b0 == 0xFF and b1 == 0xFF and b2 == 0xFF


async def sync_h5075(mac: str, minutes_back: int = 2880, timeout_s: float = 90.0) -> list[dict]:
    """Connect to H5075, download stored history, return decoded readings."""
    print(f"Scanning for {mac}...", file=sys.stderr)
    device = await BleakScanner.find_device_by_address(mac, timeout=15.0)
    if device is None:
        raise RuntimeError(f"Device {mac} not found within scan timeout")

    print(f"Connecting to {device.name or mac}...", file=sys.stderr)
    minutes_back = min(minutes_back, 28800)
    expected_packets = math.ceil(minutes_back / 6)
    request_time = datetime.now(timezone.utc)
    readings: list[dict] = []
    received = 0
    completed = asyncio.Event()

    async with BleakClient(device) as client:

        def on_data(_, data: bytearray):
            nonlocal received
            if len(data) < 20:
                return
            start_offset = (data[0] << 8) | data[1]
            for i in range(6):
                off = 2 + i * 3
                b0, b1, b2 = data[off], data[off + 1], data[off + 2]
                if is_padding(b0, b1, b2):
                    continue
                temp, hum = decode_record(b0, b1, b2)
                minutes_ago = start_offset - i
                if minutes_ago < 0:
                    continue
                ts = request_time.timestamp() - minutes_ago * 60
                readings.append({
                    "timestamp": datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                    "temperature": temp,
                    "humidity": hum,
                })
            received += 1
            if received % 50 == 0:
                print(f"  received {received}/{expected_packets} packets", file=sys.stderr)

        def on_command(_, data: bytearray):
            if len(data) < 2:
                return
            # EE 01 = transfer complete
            if data[0] == 0xEE and data[1] == 0x01:
                completed.set()

        await client.start_notify(DATA_CHAR_UUID, on_data)
        await client.start_notify(COMMAND_CHAR_UUID, on_command)

        # Send history request: 33 01 [start_hi start_lo] [end_hi end_lo]
        cmd = build_command(
            [0x33, 0x01],
            [(minutes_back >> 8) & 0xFF, minutes_back & 0xFF, 0x00, 0x01],
        )
        await client.write_gatt_char(COMMAND_CHAR_UUID, cmd, response=True)

        try:
            await asyncio.wait_for(completed.wait(), timeout=timeout_s)
        except asyncio.TimeoutError:
            raise RuntimeError(
                f"Sync timed out after {timeout_s}s "
                f"(received {received}/{expected_packets} packets)"
            )

        await client.stop_notify(DATA_CHAR_UUID)
        await client.stop_notify(COMMAND_CHAR_UUID)

    readings.sort(key=lambda r: r["timestamp"])
    return readings


def post_readings(backend: str, readings: list[dict]) -> dict:
    """POST readings to the eczema backend; return {inserted, total}."""
    url = backend.rstrip("/") + "/api/environment"
    resp = httpx.post(
        url,
        json={"readings": readings, "source": "govee_h5075"},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mac", default=os.environ.get("GOVEE_MAC"),
                        help="MAC address of the Govee sensor (or env GOVEE_MAC)")
    parser.add_argument("--backend", default=os.environ.get("ECZEMA_BACKEND"),
                        help="Eczema app backend base URL (or env ECZEMA_BACKEND)")
    parser.add_argument("--minutes-back", type=int, default=2880,
                        help="How many minutes of history to fetch (max 28800; default 2880 = 2 days)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Read sensor but don't POST to backend")
    args = parser.parse_args()

    if not args.mac:
        parser.error("--mac is required (or set GOVEE_MAC env var)")
    if not args.dry_run and not args.backend:
        parser.error("--backend is required unless --dry-run (or set ECZEMA_BACKEND env var)")

    try:
        readings = await sync_h5075(args.mac, minutes_back=args.minutes_back)
    except Exception as e:
        print(f"Sync failed: {e}", file=sys.stderr)
        return 1

    print(f"Got {len(readings)} readings", file=sys.stderr)
    if not readings:
        print("No readings on sensor.", file=sys.stderr)
        return 0

    if args.dry_run:
        # Print first and last reading for sanity check
        print(f"First: {readings[0]}")
        print(f"Last:  {readings[-1]}")
        return 0

    print(f"POSTing to {args.backend}...", file=sys.stderr)
    try:
        result = post_readings(args.backend, readings)
    except Exception as e:
        print(f"POST failed: {e}", file=sys.stderr)
        return 1

    print(f"Saved {result['inserted']} new readings "
          f"({result['total'] - result['inserted']} already on file)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

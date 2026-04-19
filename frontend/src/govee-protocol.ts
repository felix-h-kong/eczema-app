// Govee H5075 BLE protocol constants and pure helpers.
// No BLE library imports — testable in Node.
//
// Protocol reverse-engineered by Heckie75:
// https://github.com/Heckie75/govee-h5075-thermo-hygrometer

import type { EnvironmentReading } from './api';

// --- BLE UUIDs ---

// Service UUID that the H5075 advertises in its scan packet (short 0xEC88
// expanded to the standard 128-bit Bluetooth Base UUID format).
export const ADVERTISED_SERVICE_UUID = '0000ec88-0000-1000-8000-00805f9b34fb';

// GATT custom service UUID exposed *after* connection (ASCII: "INTELLI_ROCKS_HW").
export const SERVICE_UUID = '494e5445-4c4c-495f-524f-434b535f4857';
export const COMMAND_CHAR_UUID = '494e5445-4c4c-495f-524f-434b535f2012';
export const DATA_CHAR_UUID = '494e5445-4c4c-495f-524f-434b535f2013';

// Known MAC address of our sensor
export const SENSOR_MAC = 'A4:C1:38:59:69:C3';

// --- Types ---

export interface SyncOptions {
  /** Minutes back to request from the sensor. Max 28800 (20 days); H5075 stores ~2 days = 2880 min. */
  minutesBack?: number;
  /** Called as packets arrive. `total` is approximate (computed from minutesBack/6). */
  onProgress?: (received: number, total: number) => void;
  /** Abort the sync if no completion packet arrives within this many ms. Default 90s. */
  timeoutMs?: number;
}

export type { EnvironmentReading };

// --- Pure helpers ---

/**
 * Build a 20-byte command packet with XOR checksum at byte 19.
 * Bytes are: cmdBytes, then params, zero-padded to 19 bytes, then checksum.
 */
export function buildCommand(cmdBytes: number[], params: number[] = []): Uint8Array {
  const buf = new Uint8Array(20);
  buf.set(cmdBytes, 0);
  buf.set(params, cmdBytes.length);
  let xor = 0;
  for (let i = 0; i < 19; i++) xor ^= buf[i];
  buf[19] = xor;
  return buf;
}

/**
 * Decode a 3-byte historical record into temperature (C) and humidity (% RH).
 * Bit 23 (MSB of byte 0) is the negative-temperature flag.
 */
export function decodeRecord(b0: number, b1: number, b2: number): { temperature: number; humidity: number } {
  let raw = (b0 << 16) | (b1 << 8) | b2;
  let isNegative = false;
  if (raw & 0x800000) {
    isNegative = true;
    raw ^= 0x800000;
  }
  let temperature = Math.floor(raw / 1000) / 10;
  if (isNegative) temperature = -temperature;
  const humidity = (raw % 1000) / 10;
  return { temperature, humidity };
}

/** Returns true if the 3 bytes are FF FF FF (no-data padding). */
export function isPadding(b0: number, b1: number, b2: number): boolean {
  return b0 === 0xff && b1 === 0xff && b2 === 0xff;
}

// --- Advertisement decoding ---

// Manufacturer data company ID as decimal string (0xEC88 = 60552).
// The Capacitor BLE plugin uses decimal string keys in ScanResult.manufacturerData.
export const MANUFACTURER_DATA_KEY = '60552';

/**
 * Decode temperature and humidity from the H5075's BLE advertisement
 * manufacturer data payload (the DataView from ScanResult.manufacturerData["60552"]).
 *
 * The payload encoding uses the same 3-byte format as GATT historical records.
 * The exact byte offset within the payload needs empirical confirmation — this
 * function tries the most common offsets and returns the first plausible result.
 *
 * Returns null if the payload is too short or no offset yields a sane reading.
 */
export function decodeAdvertisement(payload: DataView): { temperature: number; humidity: number } | null {
  // Log raw bytes for debugging during initial testing
  const bytes: number[] = [];
  for (let i = 0; i < payload.byteLength; i++) bytes.push(payload.getUint8(i));
  console.log('[govee-adv] raw manufacturer data:', bytes.map(b => b.toString(16).padStart(2, '0')).join(' '));

  if (payload.byteLength < 3) return null;

  // Try candidate offsets where the 3-byte temp/humidity encoding might live.
  // Common positions in Govee H5075 advertisements: bytes 3-5 or 1-3.
  const candidateOffsets = [3, 1, 0, 2, 4];
  for (const offset of candidateOffsets) {
    if (offset + 3 > payload.byteLength) continue;
    const b0 = payload.getUint8(offset);
    const b1 = payload.getUint8(offset + 1);
    const b2 = payload.getUint8(offset + 2);
    if (isPadding(b0, b1, b2)) continue;
    const { temperature, humidity } = decodeRecord(b0, b1, b2);
    // Sanity check: reasonable indoor conditions
    if (temperature >= -10 && temperature <= 60 && humidity >= 0 && humidity <= 100) {
      console.log(`[govee-adv] decoded at offset ${offset}: ${temperature}°C, ${humidity}% RH`);
      return { temperature, humidity };
    }
  }

  console.warn('[govee-adv] no plausible reading found in payload');
  return null;
}

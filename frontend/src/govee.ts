// Govee H5075 Bluetooth thermometer/hygrometer client.
//
// Connects via Web Bluetooth, downloads stored historical temperature and
// humidity readings (up to ~2 days), returns them as an array.
//
// Protocol reverse-engineered by Heckie75:
// https://github.com/Heckie75/govee-h5075-thermo-hygrometer
//
// Web Bluetooth requires HTTPS or localhost, a user gesture to initiate, and
// is supported in Chromium-based browsers (incl. Chrome on Android).

import type { EnvironmentReading } from './api';

// --- Minimal Web Bluetooth type declarations (avoids @types/web-bluetooth dep) ---

interface BluetoothManufacturerDataFilter {
  companyIdentifier: number;
}

interface BluetoothRequestDeviceFilter {
  namePrefix?: string;
  services?: string[];
  manufacturerData?: BluetoothManufacturerDataFilter[];
}

interface BluetoothRequestDeviceOptions {
  filters?: BluetoothRequestDeviceFilter[];
  optionalServices?: string[];
  acceptAllDevices?: boolean;
}

interface BluetoothRemoteGATTCharacteristic extends EventTarget {
  value?: DataView;
  startNotifications(): Promise<BluetoothRemoteGATTCharacteristic>;
  stopNotifications(): Promise<BluetoothRemoteGATTCharacteristic>;
  writeValueWithResponse(value: ArrayBuffer | ArrayBufferView): Promise<void>;
}

interface BluetoothRemoteGATTService {
  getCharacteristic(uuid: string): Promise<BluetoothRemoteGATTCharacteristic>;
}

interface BluetoothRemoteGATTServer {
  connected: boolean;
  connect(): Promise<BluetoothRemoteGATTServer>;
  disconnect(): void;
  getPrimaryService(uuid: string): Promise<BluetoothRemoteGATTService>;
}

interface BluetoothDevice extends EventTarget {
  id: string;
  name?: string;
  gatt?: BluetoothRemoteGATTServer;
}

interface Bluetooth {
  requestDevice(options: BluetoothRequestDeviceOptions): Promise<BluetoothDevice>;
}

declare global {
  interface Navigator {
    bluetooth?: Bluetooth;
  }
}

// --- BLE UUIDs ---

// Service UUID that the H5075 advertises in its scan packet (short 0xEC88
// expanded to the standard 128-bit Bluetooth Base UUID format). Use this
// for filtering in `requestDevice()`.
const ADVERTISED_SERVICE_UUID = '0000ec88-0000-1000-8000-00805f9b34fb';

// GATT custom service UUID exposed *after* connection (ASCII: "INTELLI_ROCKS_HW").
// Used to read historical data via GATT characteristics.
const SERVICE_UUID = '494e5445-4c4c-495f-524f-434b535f4857';
const COMMAND_CHAR_UUID = '494e5445-4c4c-495f-524f-434b535f2012';
const DATA_CHAR_UUID = '494e5445-4c4c-495f-524f-434b535f2013';

// --- Pure helpers (testable without a device) ---

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
function isPadding(b0: number, b1: number, b2: number): boolean {
  return b0 === 0xff && b1 === 0xff && b2 === 0xff;
}

// --- Main sync function ---

export interface SyncOptions {
  /** Minutes back to request from the sensor. Max 28800 (20 days); H5075 stores ~2 days = 2880 min. */
  minutesBack?: number;
  /** Called as packets arrive. `total` is approximate (computed from minutesBack/6). */
  onProgress?: (received: number, total: number) => void;
  /** Abort the sync if no completion packet arrives within this many ms. Default 90s. */
  timeoutMs?: number;
}

export class WebBluetoothUnavailableError extends Error {
  constructor() {
    super('Web Bluetooth is not available in this browser. Use Chrome on Android or desktop Chrome/Edge.');
  }
}

/**
 * Connect to a Govee H5075, download stored history, and return decoded readings.
 * Must be called from a user gesture handler (e.g. button click).
 */
export async function syncH5075(options: SyncOptions = {}): Promise<EnvironmentReading[]> {
  if (!navigator.bluetooth) {
    throw new WebBluetoothUnavailableError();
  }

  const minutesBack = Math.min(options.minutesBack ?? 2880, 28800);
  const onProgress = options.onProgress;
  const timeoutMs = options.timeoutMs ?? 90_000;

  // The H5075 broadcasts its name as "GVH5075_XXXX" (last 4 hex chars of MAC)
  // and the short service UUID 0x0000EC88. Filtering with these triggers an
  // *active* BLE scan in Chrome, which is more reliable than acceptAllDevices
  // (which uses passive scanning and can miss the device).
  const device = await navigator.bluetooth.requestDevice({
    filters: [
      { namePrefix: 'GVH5075' },
      { services: [ADVERTISED_SERVICE_UUID] },
    ],
    optionalServices: [SERVICE_UUID, ADVERTISED_SERVICE_UUID],
  });
  console.log('[govee] selected device:', device.name, device.id);

  if (!device.gatt) throw new Error('Selected device has no GATT server');

  // Keep the screen awake during sync — without this, the phone backgrounds
  // the tab and the BLE connection drops partway through the ~30-60s transfer.
  // Wake Lock API is available in modern Chrome on Android.
  let wakeLock: WakeLockSentinel | null = null;
  if ('wakeLock' in navigator) {
    try {
      wakeLock = await navigator.wakeLock.request('screen');
    } catch {
      // Wake lock is best-effort; if it fails (e.g. low battery mode), continue
      // without it. The user may need to keep the screen on manually.
    }
  }

  const server = await device.gatt.connect();
  try {
    const service = await server.getPrimaryService(SERVICE_UUID);
    const commandChar = await service.getCharacteristic(COMMAND_CHAR_UUID);
    const dataChar = await service.getCharacteristic(DATA_CHAR_UUID);

    // Buffer to collect data notifications keyed by their `minutes_back` offset
    // (the first 2 bytes of each packet). The sensor sends ~480 packets for 2 days.
    const expectedPackets = Math.ceil(minutesBack / 6);
    const requestTime = Date.now();
    const readings: EnvironmentReading[] = [];
    let receivedPackets = 0;

    const completed = new Promise<void>((resolve, reject) => {
      const timeoutHandle = setTimeout(() => {
        reject(new Error(`Sync timed out after ${timeoutMs}ms (received ${receivedPackets}/${expectedPackets} packets)`));
      }, timeoutMs);

      const onDataNotification = (event: Event) => {
        const target = event.target as BluetoothRemoteGATTCharacteristic;
        const v = target.value;
        if (!v || v.byteLength < 20) return;
        const startOffset = (v.getUint8(0) << 8) | v.getUint8(1);
        for (let i = 0; i < 6; i++) {
          const off = 2 + i * 3;
          const b0 = v.getUint8(off);
          const b1 = v.getUint8(off + 1);
          const b2 = v.getUint8(off + 2);
          if (isPadding(b0, b1, b2)) continue;
          const { temperature, humidity } = decodeRecord(b0, b1, b2);
          const minutesAgo = startOffset - i;
          if (minutesAgo < 0) continue;
          const ts = new Date(requestTime - minutesAgo * 60_000);
          readings.push({
            timestamp: ts.toISOString(),
            temperature,
            humidity,
          });
        }
        receivedPackets++;
        onProgress?.(receivedPackets, expectedPackets);
      };

      const onCommandNotification = (event: Event) => {
        const target = event.target as BluetoothRemoteGATTCharacteristic;
        const v = target.value;
        if (!v || v.byteLength < 2) return;
        const b0 = v.getUint8(0);
        const b1 = v.getUint8(1);
        // EE 01 = transfer complete
        if (b0 === 0xee && b1 === 0x01) {
          clearTimeout(timeoutHandle);
          dataChar.removeEventListener('characteristicvaluechanged', onDataNotification);
          commandChar.removeEventListener('characteristicvaluechanged', onCommandNotification);
          resolve();
        }
        // 33 01 = ack of history request, no action needed
      };

      dataChar.addEventListener('characteristicvaluechanged', onDataNotification);
      commandChar.addEventListener('characteristicvaluechanged', onCommandNotification);
    });

    await commandChar.startNotifications();
    await dataChar.startNotifications();

    // Send history request: 33 01 [start_hi start_lo] [end_hi end_lo]
    // start = older boundary in minutes back, end = newer boundary.
    const startHi = (minutesBack >> 8) & 0xff;
    const startLo = minutesBack & 0xff;
    const cmd = buildCommand([0x33, 0x01], [startHi, startLo, 0x00, 0x01]);
    await commandChar.writeValueWithResponse(cmd);

    await completed;

    // Sort by timestamp ascending — sensor sends roughly chronological but
    // packets can arrive out of order if any get re-sent.
    readings.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
    return readings;
  } finally {
    if (server.connected) server.disconnect();
    if (wakeLock) {
      try { await wakeLock.release(); } catch { /* ignore */ }
    }
  }
}

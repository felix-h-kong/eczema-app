// Govee H5075 Bluetooth thermometer/hygrometer client.
//
// Two modes:
//   1. scanForReading() — quick GATT connect, grab the latest reading, disconnect.
//      Used for periodic monitoring (~2-5 seconds per poll).
//
//   2. syncH5075History() — connect via GATT, download stored historical readings
//      (up to ~2 days). Slower but can backfill gaps. Kept for future use.
//
// Note: BLE advertisement scanning doesn't work for this sensor on Android
// (same limitation as Chrome Web Bluetooth). Direct GATT connect by MAC works.
//
// Protocol reverse-engineered by Heckie75:
// https://github.com/Heckie75/govee-h5075-thermo-hygrometer

import { BleClient, numbersToDataView } from '@capacitor-community/bluetooth-le';
import type { EnvironmentReading } from './api';
import {
  ADVERTISED_SERVICE_UUID,
  SERVICE_UUID,
  COMMAND_CHAR_UUID,
  DATA_CHAR_UUID,
  SENSOR_MAC,
  buildCommand,
  decodeRecord,
  isPadding,
} from './govee-protocol';
import type { SyncOptions } from './govee-protocol';
import { debugLogAppend } from './govee-state';

export { buildCommand, decodeRecord } from './govee-protocol';
export type { SyncOptions } from './govee-protocol';

// Module-level lock to prevent concurrent scans/syncs
let scanInProgress = false;

export class BleUnavailableError extends Error {
  constructor(message = 'Bluetooth is not available on this device.') {
    super(message);
    this.name = 'BleUnavailableError';
  }
}

// --- Advertisement scanning (primary path) ---

/**
 * Quick GATT connect to the Govee H5075 to grab the most recent reading.
 *
 * Connects by known MAC, requests last 2 minutes of history, takes the newest
 * reading, and disconnects. Takes ~2-5 seconds.
 *
 * Note: advertisement scanning doesn't work for this sensor on Android
 * (same limitation as Chrome Web Bluetooth — the device doesn't appear in scan
 * results despite being visible in nRF Connect). Direct GATT connect by MAC
 * works fine.
 */
export async function scanForReading(timeoutMs = 15_000): Promise<EnvironmentReading | null> {
  if (scanInProgress) {
    debugLogAppend('sync already in progress, skipping');
    return null;
  }
  scanInProgress = true;
  debugLogAppend('connecting to sensor...');

  try {
    await BleClient.initialize({ androidNeverForLocation: true });

    const isEnabled = await BleClient.isEnabled();
    if (!isEnabled) {
      debugLogAppend('Bluetooth is off');
      throw new BleUnavailableError('Bluetooth is turned off. Please enable Bluetooth.');
    }

    // Direct connect by known MAC — no scanning needed.
    // BLE connections are inherently flaky, so retry a few times.
    let connected = false;
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        debugLogAppend(`connect attempt ${attempt}/3...`);
        await BleClient.connect(SENSOR_MAC, () => {
          debugLogAppend('disconnected by sensor');
        });
        connected = true;
        break;
      } catch (err) {
        debugLogAppend(`attempt ${attempt} failed: ${err instanceof Error ? err.message : String(err)}`);
        if (attempt < 3) {
          // Brief delay before retry
          await new Promise(r => setTimeout(r, 1000));
        }
      }
    }
    if (!connected) {
      debugLogAppend('gave up after 3 attempts');
      return null;
    }
    debugLogAppend('connected, stabilizing...');

    // Small delay to let the GATT connection stabilize before starting operations
    await new Promise(r => setTimeout(r, 500));

    try {
      // Request last 10 minutes of history — grab a few readings, keep the latest
      const minutesBack = 10;
      const requestTime = Date.now();
      const readings: EnvironmentReading[] = [];

      debugLogAppend('subscribing to notifications...');

      let resolveCompleted: () => void;
      let rejectCompleted: (err: Error) => void;
      const completed = new Promise<void>((resolve, reject) => {
        resolveCompleted = resolve;
        rejectCompleted = reject;
      });

      const timeoutHandle = setTimeout(() => {
        rejectCompleted(new Error('timed out waiting for data'));
      }, timeoutMs);

      // Subscribe to notifications and AWAIT them before sending the command.
      // Without awaiting, the write can fire before the sensor knows we're listening.
      await BleClient.startNotifications(SENSOR_MAC, SERVICE_UUID, DATA_CHAR_UUID, (value: DataView) => {
        if (value.byteLength < 20) return;
        const startOffset = (value.getUint8(0) << 8) | value.getUint8(1);
        for (let i = 0; i < 6; i++) {
          const off = 2 + i * 3;
          const b0 = value.getUint8(off);
          const b1 = value.getUint8(off + 1);
          const b2 = value.getUint8(off + 2);
          if (isPadding(b0, b1, b2)) continue;
          const { temperature, humidity } = decodeRecord(b0, b1, b2);
          const minutesAgo = startOffset - i;
          if (minutesAgo < 0) continue;
          const ts = new Date(requestTime - minutesAgo * 60_000);
          readings.push({ timestamp: ts.toISOString(), temperature, humidity });
        }
        debugLogAppend(`received packet, ${readings.length} readings so far`);
      });

      await BleClient.startNotifications(SENSOR_MAC, SERVICE_UUID, COMMAND_CHAR_UUID, (value: DataView) => {
        if (value.byteLength < 2) return;
        const b0 = value.getUint8(0);
        const b1 = value.getUint8(1);
        debugLogAppend(`command response: 0x${b0.toString(16)} 0x${b1.toString(16)}`);
        if (b0 === 0xee && b1 === 0x01) {
          clearTimeout(timeoutHandle);
          resolveCompleted();
        }
      });

      debugLogAppend('notifications ready');

      // Send history request for last 10 minutes
      debugLogAppend('requesting last 10 min of history...');
      const startHi = (minutesBack >> 8) & 0xff;
      const startLo = minutesBack & 0xff;
      const cmd = buildCommand([0x33, 0x01], [startHi, startLo, 0x00, 0x01]);
      await BleClient.write(SENSOR_MAC, SERVICE_UUID, COMMAND_CHAR_UUID, numbersToDataView(Array.from(cmd)));
      debugLogAppend('command sent, waiting for data...');

      await completed;
      debugLogAppend(`transfer complete, got ${readings.length} readings`);

      await BleClient.stopNotifications(SENSOR_MAC, SERVICE_UUID, DATA_CHAR_UUID);
      await BleClient.stopNotifications(SENSOR_MAC, SERVICE_UUID, COMMAND_CHAR_UUID);

      if (readings.length === 0) {
        debugLogAppend('no readings in last 10 min');
        return null;
      }

      // Take the most recent reading
      readings.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
      const latest = readings[0];
      debugLogAppend(`latest: ${latest.temperature.toFixed(1)}°C, ${latest.humidity.toFixed(0)}% RH`);
      return latest;
    } finally {
      try { await BleClient.disconnect(SENSOR_MAC); } catch { /* ignore */ }
    }
  } finally {
    scanInProgress = false;
  }
}

// --- GATT history download (kept for future backfill use) ---

/**
 * Connect to a Govee H5075, download stored history, and return decoded readings.
 * This is the slower path — use scanForReading() for periodic monitoring.
 *
 * On Android via Capacitor, this uses the native BLE stack (same as nRF Connect).
 * No user gesture required — works for both manual taps and background sync.
 */
export async function syncH5075History(options: SyncOptions = {}): Promise<EnvironmentReading[]> {
  if (scanInProgress) {
    throw new Error('Scan or sync already in progress');
  }
  scanInProgress = true;

  try {
    await BleClient.initialize({ androidNeverForLocation: true });

    const isEnabled = await BleClient.isEnabled();
    if (!isEnabled) {
      throw new BleUnavailableError('Bluetooth is turned off. Please enable Bluetooth.');
    }

    const minutesBack = Math.min(options.minutesBack ?? 2880, 28800);
    const onProgress = options.onProgress;
    const timeoutMs = options.timeoutMs ?? 90_000;

    // Try direct connect to known MAC first (faster, no scan needed).
    // On Android, deviceId is the MAC address.
    let deviceId: string | undefined;
    try {
      await BleClient.connect(SENSOR_MAC, () => {
        console.log('[govee] disconnected');
      });
      deviceId = SENSOR_MAC;
      console.log('[govee] direct connect to', SENSOR_MAC);
    } catch {
      // Direct connect failed (out of range, or device not seen before).
      // Fall back to scanning.
      console.log('[govee] direct connect failed, scanning...');
      deviceId = await scanForDeviceId();
      if (!deviceId) {
        throw new Error('Govee H5075 sensor not found. Make sure the sensor is nearby and powered on.');
      }
      await BleClient.connect(deviceId, () => {
        console.log('[govee] disconnected');
      });
      console.log('[govee] connected via scan to', deviceId);
    }

    try {
      const expectedPackets = Math.ceil(minutesBack / 6);
      const requestTime = Date.now();
      const readings: EnvironmentReading[] = [];
      let receivedPackets = 0;

      const completed = new Promise<void>((resolve, reject) => {
        const timeoutHandle = setTimeout(() => {
          reject(new Error(
            `Sync timed out after ${timeoutMs}ms (${receivedPackets}/${expectedPackets} packets)`,
          ));
        }, timeoutMs);

        BleClient.startNotifications(deviceId!, SERVICE_UUID, DATA_CHAR_UUID, (value: DataView) => {
          if (value.byteLength < 20) return;
          const startOffset = (value.getUint8(0) << 8) | value.getUint8(1);
          for (let i = 0; i < 6; i++) {
            const off = 2 + i * 3;
            const b0 = value.getUint8(off);
            const b1 = value.getUint8(off + 1);
            const b2 = value.getUint8(off + 2);
            if (isPadding(b0, b1, b2)) continue;
            const { temperature, humidity } = decodeRecord(b0, b1, b2);
            const minutesAgo = startOffset - i;
            if (minutesAgo < 0) continue;
            const ts = new Date(requestTime - minutesAgo * 60_000);
            readings.push({ timestamp: ts.toISOString(), temperature, humidity });
          }
          receivedPackets++;
          onProgress?.(receivedPackets, expectedPackets);
        });

        BleClient.startNotifications(deviceId!, SERVICE_UUID, COMMAND_CHAR_UUID, (value: DataView) => {
          if (value.byteLength < 2) return;
          if (value.getUint8(0) === 0xee && value.getUint8(1) === 0x01) {
            clearTimeout(timeoutHandle);
            resolve();
          }
        });
      });

      const startHi = (minutesBack >> 8) & 0xff;
      const startLo = minutesBack & 0xff;
      const cmd = buildCommand([0x33, 0x01], [startHi, startLo, 0x00, 0x01]);
      await BleClient.write(deviceId, SERVICE_UUID, COMMAND_CHAR_UUID, numbersToDataView(Array.from(cmd)));

      await completed;

      await BleClient.stopNotifications(deviceId, SERVICE_UUID, DATA_CHAR_UUID);
      await BleClient.stopNotifications(deviceId, SERVICE_UUID, COMMAND_CHAR_UUID);

      readings.sort((a, b) => a.timestamp.localeCompare(b.timestamp));
      return readings;
    } finally {
      try {
        await BleClient.disconnect(deviceId);
      } catch {
        // ignore disconnect errors
      }
    }
  } finally {
    scanInProgress = false;
  }
}

/** Scan for a GVH5075 device, returning the deviceId (MAC on Android). Used by GATT sync. */
async function scanForDeviceId(timeoutMs = 10_000): Promise<string | undefined> {
  return new Promise<string | undefined>((resolve) => {
    const timeout = setTimeout(async () => {
      await BleClient.stopLEScan();
      resolve(undefined);
    }, timeoutMs);

    BleClient.requestLEScan(
      { services: [ADVERTISED_SERVICE_UUID], namePrefix: 'GVH5075' },
      (result) => {
        clearTimeout(timeout);
        BleClient.stopLEScan();
        resolve(result.device.deviceId);
      },
    );
  });
}

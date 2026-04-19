// Background BLE sync for the Govee H5075 sensor.
//
// Uses @transistorsoft/capacitor-background-fetch to wake the app periodically.
// When the task fires, we scan for the sensor's BLE advertisement and read the
// live temp/humidity from its manufacturer data — no GATT connection needed.
//
// If the sensor isn't in range or any step fails, we silently skip.
// Android enforces a 15-minute minimum interval for background tasks.

import { BackgroundFetch } from '@transistorsoft/capacitor-background-fetch';
import { scanForReading } from './govee';
import { submitEnvironmentReadings } from './api';
import { updateSensorState } from './govee-state';

/** Run a single BLE scan cycle. Swallows all errors — expected when out of range. */
async function performSync(context: string): Promise<void> {
  try {
    const reading = await scanForReading();
    if (reading) {
      const result = await submitEnvironmentReadings([reading]);
      updateSensorState({
        lastReading: reading,
        lastSeen: reading.timestamp,
        lastSyncError: null,
      });
      console.log(`[${context}] saved reading: ${reading.temperature}°C, ${reading.humidity}% RH (${result.inserted} new)`);
    } else {
      updateSensorState({ lastSyncError: 'Sensor not found' });
      console.log(`[${context}] sensor not in range`);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    updateSensorState({ lastSyncError: message });
    console.log(`[${context}] sync skipped:`, message);
  }
}

/**
 * Configure background sync. Call once at app startup, guarded by
 * Capacitor.isNativePlatform().
 */
export async function setupBackgroundSync(): Promise<void> {
  const status = await BackgroundFetch.configure(
    {
      minimumFetchInterval: 15,  // minutes (Android minimum)
      stopOnTerminate: false,
      startOnBoot: true,
      enableHeadless: true,
    },
    async (taskId: string) => {
      console.log('[bg-sync] task fired:', taskId);
      await performSync('bg-sync');
      BackgroundFetch.finish(taskId);
    },
    async (taskId: string) => {
      console.log('[bg-sync] task timed out:', taskId);
      BackgroundFetch.finish(taskId);
    },
  );

  if (status === BackgroundFetch.STATUS_AVAILABLE) {
    console.log('[bg-sync] configured, status: available');
  } else if (status === BackgroundFetch.STATUS_DENIED) {
    console.warn('[bg-sync] background fetch denied by user');
  } else if (status === BackgroundFetch.STATUS_RESTRICTED) {
    console.warn('[bg-sync] background fetch restricted by system');
  }
}

/** Exported for use by foreground polling — same logic, reusable. */
export { performSync };

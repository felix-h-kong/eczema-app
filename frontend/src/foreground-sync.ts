// Foreground polling for BLE advertisement scanning.
//
// When the app is in the foreground, we can poll more frequently than the
// Android 15-minute background minimum. Uses a simple setInterval.

import { performSync } from './background-sync';

const DEFAULT_INTERVAL_MS = 10 * 60 * 1000; // 10 minutes

/**
 * Start polling for sensor readings at a fixed interval.
 * Performs an immediate scan on start, then repeats.
 * Returns a cleanup function to stop polling.
 */
export function startForegroundPolling(intervalMs = DEFAULT_INTERVAL_MS): () => void {
  console.log(`[fg-sync] starting foreground polling every ${intervalMs / 1000}s`);

  // Immediate first scan
  performSync('fg-sync');

  const handle = setInterval(() => {
    performSync('fg-sync');
  }, intervalMs);

  return () => {
    console.log('[fg-sync] stopping foreground polling');
    clearInterval(handle);
  };
}

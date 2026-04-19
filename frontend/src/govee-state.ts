// Shared sensor state for the Govee H5075.
// No React dependency — components subscribe via onSensorStateChange().

export interface SensorState {
  /** Latest decoded reading, or null if no reading yet this session. */
  lastReading: { temperature: number; humidity: number; timestamp: string } | null;
  /** ISO timestamp of the last time a scan found the sensor (even if decode failed). */
  lastSeen: string | null;
  /** Last error message from a failed scan, or null if last scan succeeded. */
  lastSyncError: string | null;
}

const state: SensorState = {
  lastReading: null,
  lastSeen: null,
  lastSyncError: null,
};

type Listener = (state: SensorState) => void;
const listeners = new Set<Listener>();

export function getSensorState(): SensorState {
  return { ...state };
}

export function updateSensorState(partial: Partial<SensorState>): void {
  Object.assign(state, partial);
  for (const fn of listeners) {
    fn({ ...state });
  }
}

/** Subscribe to state changes. Returns an unsubscribe function. */
export function onSensorStateChange(callback: Listener): () => void {
  listeners.add(callback);
  return () => { listeners.delete(callback); };
}

// --- Debug log ---

const MAX_LOG_LINES = 50;
const debugLog: string[] = [];
type LogListener = (lines: string[]) => void;
const logListeners = new Set<LogListener>();

/** Append a line to the in-app debug log. */
export function debugLogAppend(message: string): void {
  const ts = new Date().toLocaleTimeString('en-AU', { hour12: false });
  debugLog.push(`${ts} ${message}`);
  if (debugLog.length > MAX_LOG_LINES) debugLog.shift();
  for (const fn of logListeners) fn([...debugLog]);
}

export function getDebugLog(): string[] {
  return [...debugLog];
}

export function onDebugLogChange(callback: LogListener): () => void {
  logListeners.add(callback);
  return () => { logListeners.delete(callback); };
}

import { useState, useEffect } from 'react';
import { getSensorState, onSensorStateChange } from './govee-state';
import type { SensorState } from './govee-state';

/** React hook that subscribes to shared sensor state and triggers re-renders on change. */
export function useSensorState(): SensorState {
  const [state, setState] = useState<SensorState>(getSensorState);

  useEffect(() => {
    return onSensorStateChange(setState);
  }, []);

  return state;
}

import { useState } from 'react';
import { useSensorState } from '../useSensorState';

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

type LEDColor = 'green' | 'amber' | 'grey';

function getLEDColor(lastReadingTime: string | null): LEDColor {
  if (!lastReadingTime) return 'grey';
  const ageMs = Date.now() - new Date(lastReadingTime).getTime();
  if (ageMs < 15 * 60_000) return 'green';   // < 15 min
  if (ageMs < 60 * 60_000) return 'amber';   // < 60 min
  return 'grey';
}

const LED_COLORS: Record<LEDColor, string> = {
  green: '#4CAF50',
  amber: '#FF9800',
  grey: '#9E9E9E',
};

export function SensorLED() {
  const [expanded, setExpanded] = useState(false);
  const { lastReading, lastSeen, lastSyncError } = useSensorState();

  const readingTime = lastReading?.timestamp ?? null;
  const color = getLEDColor(readingTime);

  return (
    <>
      {/* Floating LED dot */}
      <button
        onClick={() => setExpanded(!expanded)}
        aria-label="Sensor status"
        style={{
          position: 'fixed',
          bottom: 'calc(env(safe-area-inset-bottom, 0px) + 58px)',
          right: 12,
          width: 16,
          height: 16,
          borderRadius: '50%',
          border: '2px solid var(--bg-surface)',
          background: LED_COLORS[color],
          cursor: 'pointer',
          zIndex: 101,
          padding: 0,
          boxShadow: color === 'green'
            ? `0 0 6px ${LED_COLORS.green}80`
            : '0 1px 3px rgba(0,0,0,0.2)',
          transition: 'background 0.3s, box-shadow 0.3s',
        }}
      />

      {/* Expanded detail panel */}
      {expanded && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setExpanded(false)}
            style={{
              position: 'fixed', inset: 0,
              zIndex: 200,
            }}
          />
          {/* Panel */}
          <div style={{
            position: 'fixed',
            bottom: 'calc(env(safe-area-inset-bottom, 0px) + 80px)',
            right: 12,
            background: 'var(--bg-surface)',
            border: '0.5px solid var(--border)',
            borderRadius: 12,
            padding: '12px 16px',
            zIndex: 201,
            minWidth: 200,
            boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
          }}>
            {lastReading ? (
              <div style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {lastReading.temperature.toFixed(1)}°C&nbsp;&nbsp;{lastReading.humidity.toFixed(0)}% RH
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-hint)', marginTop: 2 }}>
                  Updated {timeAgo(lastReading.timestamp)}
                </div>
              </div>
            ) : (
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 8 }}>
                No readings yet
              </div>
            )}

            <div style={{ fontSize: 11, color: 'var(--text-hint)' }}>
              {lastSeen
                ? `Sensor last seen ${timeAgo(lastSeen)}`
                : 'Sensor not yet detected'}
            </div>
            {lastSyncError && (
              <div style={{ fontSize: 11, color: '#E57373', marginTop: 2 }}>
                {lastSyncError}
              </div>
            )}
          </div>
        </>
      )}
    </>
  );
}

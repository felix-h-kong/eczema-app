import { useState, useEffect } from 'react';
import { getLogEntries, sendTestNotification, submitEnvironmentReadings } from '../api';
import { setupPushNotifications } from '../App';
import { syncH5075History, BleUnavailableError } from '../govee';
import type { LogEntry } from '../api';

interface LogHubProps {
  onSelect: (form: string) => void;
}

function formatDate(): string {
  return new Date().toLocaleDateString('en-AU', {
    weekday: 'long', day: 'numeric', month: 'long',
  });
}

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' });
}

export function LogHub({ onSelect }: LogHubProps) {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [testSending, setTestSending] = useState(false);
  const [testStatus, setTestStatus] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [syncStatus, setSyncStatus] = useState('');

  useEffect(() => {
    const today = new Date();
    const from = new Date(today.getFullYear(), today.getMonth(), today.getDate()).toISOString();
    getLogEntries({ from }).then(setEntries).catch(() => {});
  }, []);

  return (
    <div style={{ padding: '16px 20px', paddingBottom: 80 }}>
      <div style={{
        fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
        textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 4,
      }}>
        {formatDate()}
      </div>
      <h1 style={{ fontSize: 24, fontWeight: 500, marginBottom: 16, color: 'var(--text-primary)' }}>Log</h1>

      {/* Action cards */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {/* Meal — primary full-width card */}
        <button onClick={() => onSelect('meal')} style={{
          display: 'flex', alignItems: 'center', gap: 14,
          background: 'var(--primary)', border: 'none', borderRadius: 18,
          padding: '14px 16px', cursor: 'pointer', textAlign: 'left', width: '100%',
        }}>
          <div style={{
            width: 38, height: 38, borderRadius: 11,
            background: 'var(--primary-dark)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18, flexShrink: 0,
          }}>{'\u{1F37D}'}</div>
          <div>
            <div style={{ fontSize: 15, fontWeight: 500, color: '#FDF8F3' }}>Log food</div>
            <div style={{ fontSize: 12, color: 'var(--primary-light)' }}>Breakfast · Lunch · Dinner · Snack</div>
          </div>
        </button>

        {/* 2x2 grid for secondary cards */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {([
            { key: 'flare', emoji: '\u{1F534}', label: 'Skin check', sub: 'Rate · Photos' },
            { key: 'note', emoji: '\u{1F4DD}', label: 'Log note', sub: 'Observations' },
            { key: 'event', emoji: '\u{1F4CB}', label: 'Log event', sub: 'Nails · Shower' },
            { key: 'meds', emoji: '\u{1F48A}', label: 'Medication', sub: 'Drug · Dose' },
          ] as const).map(({ key, emoji, label, sub }) => (
            <button key={key} onClick={() => onSelect(key)} style={{
              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6,
              background: 'var(--bg-surface-2)', border: '0.5px solid var(--border)', borderRadius: 18,
              padding: '14px 8px', cursor: 'pointer', textAlign: 'center',
            }}>
              <div style={{
                width: 38, height: 38, borderRadius: 11,
                background: 'var(--bg-surface-2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18,
              }}>{emoji}</div>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>{label}</div>
                <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{sub}</div>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Today section */}
      {entries.length > 0 && (
        <div style={{ marginTop: 24 }}>
          <div style={{
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            marginBottom: 8,
          }}>
            <span style={{
              fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
              textTransform: 'uppercase', color: 'var(--text-secondary)',
            }}>Today</span>
          </div>
          <div style={{
            background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
            borderRadius: 14, overflow: 'hidden',
          }}>
            {entries.map((entry, i) => {
              const typeColor = entry.type === 'meal' ? 'var(--type-meal)'
                : entry.type === 'flare' ? 'var(--type-flare)'
                : entry.type === 'note' ? 'var(--text-secondary)'
                : 'var(--type-med)';
              const label = entry.type === 'flare' ? `Skin \u00B7 ${entry.severity}/10`
                : entry.type === 'medication' ? entry.medication_name || 'Medication'
                : entry.type === 'note' ? 'Event'
                : 'Food';
              const body = entry.raw_input || entry.notes || '';
              return (
                <div key={entry.id} style={{
                  padding: '11px 14px',
                  borderTop: i > 0 ? '0.5px solid var(--border)' : 'none',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 12, fontWeight: 500, color: typeColor }}>{label}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-hint)' }}>{formatTime(entry.timestamp)}</span>
                  </div>
                  {body && (
                    <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.4, marginTop: 2 }}>
                      {body}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      <div style={{ marginTop: 32, textAlign: 'center' }}>
        <button
          onClick={async () => {
            setTestSending(true);
            setTestStatus('');
            try {
              setTestStatus('Setting up push...');
              await setupPushNotifications();
              setTestStatus('Sending notification...');
              await sendTestNotification();
              setTestStatus('Sent! Check your notifications.');
            } catch (err) {
              setTestStatus(`Error: ${err}`);
            } finally { setTestSending(false); }
          }}
          disabled={testSending}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 12, color: 'var(--text-hint)', textDecoration: 'underline',
          }}
        >
          {testSending ? 'Sending...' : 'Send test notification'}
        </button>
        {testStatus && (
          <div style={{ fontSize: 11, color: 'var(--text-hint)', marginTop: 4 }}>{testStatus}</div>
        )}
      </div>

      <div style={{ marginTop: 16, textAlign: 'center' }}>
        <button
          onClick={async () => {
            setSyncing(true);
            setSyncStatus('');
            try {
              const readings = await syncH5075History({
                onProgress: (received, total) => {
                  setSyncStatus(`Downloading ${received}/${total} packets...`);
                },
              });
              if (readings.length === 0) {
                setSyncStatus('No readings on sensor.');
                return;
              }
              setSyncStatus(`Saving ${readings.length} readings...`);
              const result = await submitEnvironmentReadings(readings);
              setSyncStatus(
                `Saved ${result.inserted} new readings (${result.total - result.inserted} already on file).`,
              );
            } catch (err) {
              if (err instanceof BleUnavailableError) {
                setSyncStatus(err.message);
              } else if (err instanceof Error && err.name === 'NotFoundError') {
                setSyncStatus('Sensor not found. Make sure it is nearby and powered on.');
              } else {
                setSyncStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
              }
            } finally {
              setSyncing(false);
            }
          }}
          disabled={syncing}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            fontSize: 12, color: 'var(--text-hint)', textDecoration: 'underline',
          }}
        >
          {syncing ? 'Syncing...' : 'Sync Govee sensor'}
        </button>
        {syncStatus && (
          <div style={{ fontSize: 11, color: 'var(--text-hint)', marginTop: 4 }}>{syncStatus}</div>
        )}
      </div>
    </div>
  );
}

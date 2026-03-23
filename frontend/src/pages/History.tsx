import { useState, useEffect } from 'react';
import { getLogEntries } from '../api';
import type { LogEntry } from '../api';

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' });
}

function formatWeekRange(): string {
  const now = new Date();
  const start = new Date(now);
  start.setDate(now.getDate() - 6);
  const fmt = (d: Date) => d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' });
  return `${fmt(start)} \u2013 ${fmt(now)}`;
}

function groupByDay(entries: LogEntry[]): Record<string, LogEntry[]> {
  const groups: Record<string, LogEntry[]> = {};
  for (const entry of entries) {
    const day = new Date(entry.timestamp).toLocaleDateString('en-AU', {
      weekday: 'long', day: 'numeric', month: 'long',
    });
    if (!groups[day]) groups[day] = [];
    groups[day].push(entry);
  }
  return groups;
}

export function History() {
  const [entries, setEntries] = useState<LogEntry[]>([]);

  useEffect(() => {
    const now = new Date();
    const from = new Date(now);
    from.setDate(now.getDate() - 6);
    from.setHours(0, 0, 0, 0);
    getLogEntries({ from: from.toISOString() }).then(setEntries).catch(() => {});
  }, []);

  const grouped = groupByDay(entries);

  return (
    <div style={{ padding: '16px 20px', paddingBottom: 80 }}>
      <div style={{
        fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
        textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 4,
      }}>
        {formatWeekRange()}
      </div>
      <h1 style={{ fontSize: 24, fontWeight: 500, marginBottom: 16, color: 'var(--text-primary)' }}>History</h1>

      {Object.keys(grouped).length === 0 && (
        <p style={{ color: 'var(--text-hint)', textAlign: 'center', padding: 32, fontSize: 14 }}>
          No entries this week. Start logging!
        </p>
      )}

      {Object.entries(grouped).map(([day, dayEntries]) => (
        <div key={day} style={{ marginBottom: 20 }}>
          <div style={{
            fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
            textTransform: 'uppercase', color: 'var(--text-secondary)',
            marginBottom: 8,
          }}>
            {day}
          </div>
          <div style={{
            background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
            borderRadius: 14, overflow: 'hidden',
          }}>
            {dayEntries.map((entry, i) => {
              const typeColor = entry.type === 'meal' ? 'var(--type-meal)'
                : entry.type === 'flare' ? 'var(--type-flare)'
                : 'var(--type-med)';
              const label = entry.type === 'flare' ? `Flare \u00B7 severity ${entry.severity}`
                : entry.type === 'medication' ? entry.medication_name || 'Medication'
                : 'Meal';
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
      ))}
    </div>
  );
}

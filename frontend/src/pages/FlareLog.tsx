import { useState } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

interface FlareLogProps {
  onBack: () => void;
}

export function FlareLog({ onBack }: FlareLogProps) {
  const [severity, setSeverity] = useState(5);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(false);
  const [error, setError] = useState('');
  const [customTime, setCustomTime] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await createLogEntry({
        timestamp: customTime ? new Date(customTime).toISOString() : new Date().toISOString(),
        type: 'flare',
        severity,
        notes: notes.trim() || undefined,
      });
      setSeverity(5);
      setNotes('');
      setToast(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ padding: '16px 20px 100px' }}>
      <button onClick={onBack} style={{
        background: 'none', border: 'none', cursor: 'pointer',
        fontSize: 14, fontWeight: 500, color: 'var(--primary)',
        padding: '4px 0', marginBottom: 12,
      }}>
        {'\u2190'} Log flare
      </button>

      <form onSubmit={handleSubmit}>
        <div style={{
          background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
          borderRadius: 14, padding: 14, marginBottom: 12,
        }}>
          <label style={{
            display: 'block', fontSize: 11, fontWeight: 500,
            letterSpacing: '0.05em', textTransform: 'uppercase',
            color: 'var(--text-secondary)', marginBottom: 8,
          }}>
            Severity: {severity} / 10
          </label>
          <input
            type="range"
            min={1}
            max={10}
            value={severity}
            onChange={e => setSeverity(Number(e.target.value))}
            style={{ width: '100%', marginBottom: 4 }}
          />
          <div style={{
            display: 'flex', justifyContent: 'space-between',
            fontSize: 11, color: 'var(--text-hint)',
          }}>
            <span>Mild (1)</span>
            <span>Severe (10)</span>
          </div>
        </div>

        <div style={{
          background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
          borderRadius: 14, padding: 14, marginBottom: 12,
        }}>
          <label style={{
            display: 'block', fontSize: 11, fontWeight: 500,
            letterSpacing: '0.05em', textTransform: 'uppercase',
            color: 'var(--text-secondary)', marginBottom: 6,
          }}>
            Notes (optional)
          </label>
          <textarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Location, possible triggers\u2026"
            rows={3}
            style={{
              width: '100%', padding: 0, fontSize: 15,
              border: 'none', background: 'transparent',
              resize: 'vertical', fontFamily: 'inherit',
              color: 'var(--text-primary)', outline: 'none',
              lineHeight: 1.5,
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: customTime !== null ? 8 : 16 }}>
          <button type="button" onClick={() => setCustomTime(customTime !== null ? null : '')} style={{
            background: customTime !== null ? 'var(--primary-light)' : 'var(--bg-surface-2)',
            border: '0.5px solid var(--border)',
            borderRadius: 14, padding: '8px 14px', fontSize: 13, fontWeight: 500,
            color: customTime !== null ? 'var(--primary)' : 'var(--text-secondary)',
            cursor: 'pointer',
          }}>
            Set time
          </button>
        </div>
        {customTime !== null && (
          <div style={{ marginBottom: 16 }}>
            <input
              type="datetime-local"
              value={customTime}
              onChange={e => setCustomTime(e.target.value)}
              style={{
                width: '100%', padding: '10px 14px', fontSize: 15,
                border: '0.5px solid var(--border)', borderRadius: 14,
                background: 'var(--bg-surface)', color: 'var(--text-primary)',
                fontFamily: 'inherit',
              }}
            />
          </div>
        )}

        {error && <p style={{ color: 'var(--type-flare)', marginBottom: 8, fontSize: 13 }}>{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          style={{
            width: '100%', padding: '12px 0',
            fontSize: 15, fontWeight: 500, borderRadius: 14,
            border: 'none', background: 'var(--primary)', color: '#FDF8F3',
            cursor: submitting ? 'not-allowed' : 'pointer',
            opacity: submitting ? 0.6 : 1,
          }}
        >
          {submitting ? 'Saving\u2026' : 'Log Flare'}
        </button>
      </form>
      <Toast message="Flare logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}

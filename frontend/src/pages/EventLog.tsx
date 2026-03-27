import { useState, useEffect } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

interface EventLogProps {
  onBack: () => void;
}

export function EventLog({ onBack }: EventLogProps) {
  const [presets, setPresets] = useState<string[]>([]);
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(false);
  const [error, setError] = useState('');
  const [customTime, setCustomTime] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/event-presets').then(r => r.json()).then(setPresets).catch(() => {});
  }, []);

  async function handleSubmit(value?: string) {
    const note = (value || text).trim();
    if (!note) return;
    setSubmitting(true);
    setError('');
    try {
      await createLogEntry({
        timestamp: customTime ? new Date(customTime).toISOString() : new Date().toISOString(),
        type: 'note',
        notes: note,
      });
      setText('');
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
        {'\u2190'} Log event
      </button>

      <div style={{
        fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
        textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 8,
      }}>
        Quick log
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        {presets.map(preset => (
          <button
            key={preset}
            type="button"
            onClick={() => setText(preset)}
            style={{
              background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
              borderRadius: 14, padding: '8px 14px', fontSize: 13, fontWeight: 500,
              color: 'var(--text-primary)', cursor: 'pointer',
            }}
          >
            {preset}
          </button>
        ))}
      </div>

      <form onSubmit={e => { e.preventDefault(); handleSubmit(); }}>
        <div style={{
          background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
          borderRadius: 14, padding: 14, marginBottom: 12,
        }}>
          <label style={{
            display: 'block', fontSize: 11, fontWeight: 500,
            letterSpacing: '0.05em', textTransform: 'uppercase',
            color: 'var(--text-secondary)', marginBottom: 6,
          }}>
            Or describe it
          </label>
          <input
            type="text"
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="e.g. new laundry detergent, ate out at restaurant"
            style={{
              width: '100%', padding: 0, fontSize: 15,
              border: 'none', background: 'transparent',
              fontFamily: 'inherit', color: 'var(--text-primary)', outline: 'none',
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
          disabled={submitting || !text.trim()}
          style={{
            width: '100%', padding: '12px 0',
            fontSize: 15, fontWeight: 500, borderRadius: 14,
            border: 'none', background: 'var(--primary)', color: '#FDF8F3',
            cursor: submitting || !text.trim() ? 'not-allowed' : 'pointer',
            opacity: submitting || !text.trim() ? 0.6 : 1,
          }}
        >
          {submitting ? 'Saving\u2026' : 'Log Event'}
        </button>
      </form>
      <Toast message="Event logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}

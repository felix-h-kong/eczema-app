import { useState, useRef } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

interface MedsLogProps {
  onBack: () => void;
}

export function MedsLog({ onBack }: MedsLogProps) {
  const [name, setName] = useState('');
  const [dose, setDose] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(false);
  const [error, setError] = useState('');
  const nameRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setSubmitting(true);
    setError('');
    try {
      await createLogEntry({
        timestamp: new Date().toISOString(),
        type: 'medication',
        medication_name: name.trim(),
        medication_dose: dose.trim() || undefined,
      });
      setName('');
      setDose('');
      setToast(true);
      nameRef.current?.focus();
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
        {'\u2190'} Log medication
      </button>

      <form onSubmit={handleSubmit}>
        <div style={{
          background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
          borderRadius: 14, padding: 14, marginBottom: 12,
        }}>
          <label style={{
            display: 'block', fontSize: 11, fontWeight: 500,
            letterSpacing: '0.05em', textTransform: 'uppercase',
            color: 'var(--text-secondary)', marginBottom: 6,
          }}>
            Medication name
          </label>
          <input
            ref={nameRef}
            autoFocus
            type="text"
            value={name}
            onChange={e => setName(e.target.value)}
            placeholder="e.g. Hydrocortisone, Cetirizine"
            style={{
              width: '100%', padding: 0, fontSize: 15,
              border: 'none', background: 'transparent',
              fontFamily: 'inherit', color: 'var(--text-primary)',
              outline: 'none',
            }}
          />
        </div>

        <div style={{
          background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
          borderRadius: 14, padding: 14, marginBottom: 16,
        }}>
          <label style={{
            display: 'block', fontSize: 11, fontWeight: 500,
            letterSpacing: '0.05em', textTransform: 'uppercase',
            color: 'var(--text-secondary)', marginBottom: 6,
          }}>
            Dose (optional)
          </label>
          <input
            type="text"
            value={dose}
            onChange={e => setDose(e.target.value)}
            placeholder="e.g. 10mg, 1 tablet, apply topically"
            style={{
              width: '100%', padding: 0, fontSize: 15,
              border: 'none', background: 'transparent',
              fontFamily: 'inherit', color: 'var(--text-primary)',
              outline: 'none',
            }}
          />
        </div>

        {error && <p style={{ color: 'var(--type-flare)', marginBottom: 8, fontSize: 13 }}>{error}</p>}

        <button
          type="submit"
          disabled={submitting || !name.trim()}
          style={{
            width: '100%', padding: '12px 0',
            fontSize: 15, fontWeight: 500, borderRadius: 14,
            border: 'none', background: 'var(--primary)', color: '#FDF8F3',
            cursor: submitting || !name.trim() ? 'not-allowed' : 'pointer',
            opacity: submitting || !name.trim() ? 0.6 : 1,
          }}
        >
          {submitting ? 'Saving\u2026' : 'Log Medication'}
        </button>
      </form>
      <Toast message="Medication logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}

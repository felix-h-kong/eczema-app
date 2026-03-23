import { useState } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

export function FlareLog() {
  const [severity, setSeverity] = useState(5);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await createLogEntry({
        timestamp: new Date().toISOString(),
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
    <div style={{ padding: '24px 16px 100px' }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 16 }}>Log Flare</h1>
      <form onSubmit={handleSubmit}>
        <label style={{ display: 'block', marginBottom: 8, fontWeight: 500 }}>
          Severity: <strong>{severity}</strong> / 10
        </label>
        <input
          type="range"
          min={1}
          max={10}
          value={severity}
          onChange={e => setSeverity(Number(e.target.value))}
          style={{ width: '100%', marginBottom: 16 }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: -12, marginBottom: 16, fontSize: 12, color: '#666' }}>
          <span>Mild (1)</span>
          <span>Severe (10)</span>
        </div>
        <textarea
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Optional notes (location, possible triggers…)"
          rows={4}
          style={{
            width: '100%', padding: 12, fontSize: 16,
            border: '1px solid #ccc', borderRadius: 8,
            resize: 'vertical', fontFamily: 'inherit',
          }}
        />
        {error && <p style={{ color: 'red', marginTop: 8 }}>{error}</p>}
        <button
          type="submit"
          disabled={submitting}
          style={{
            marginTop: 12, width: '100%', padding: '12px 0',
            fontSize: 16, fontWeight: 600, borderRadius: 8,
            border: 'none', background: '#dc2626', color: '#fff',
            cursor: submitting ? 'not-allowed' : 'pointer',
            opacity: submitting ? 0.6 : 1,
          }}
        >
          {submitting ? 'Saving…' : 'Log Flare'}
        </button>
      </form>
      <Toast message="Flare logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}

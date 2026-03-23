import { useState, useRef } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

export function MedsLog() {
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
    <div style={{ padding: '24px 16px 100px' }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 16 }}>Log Medication</h1>
      <form onSubmit={handleSubmit}>
        <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>
          Medication name <span style={{ color: 'red' }}>*</span>
        </label>
        <input
          ref={nameRef}
          autoFocus
          type="text"
          value={name}
          onChange={e => setName(e.target.value)}
          placeholder="e.g. Hydrocortisone, Cetirizine"
          style={{
            width: '100%', padding: 12, fontSize: 16,
            border: '1px solid #ccc', borderRadius: 8,
            fontFamily: 'inherit', marginBottom: 16,
          }}
        />
        <label style={{ display: 'block', marginBottom: 4, fontWeight: 500 }}>
          Dose (optional)
        </label>
        <input
          type="text"
          value={dose}
          onChange={e => setDose(e.target.value)}
          placeholder="e.g. 10mg, 1 tablet, apply topically"
          style={{
            width: '100%', padding: 12, fontSize: 16,
            border: '1px solid #ccc', borderRadius: 8,
            fontFamily: 'inherit',
          }}
        />
        {error && <p style={{ color: 'red', marginTop: 8 }}>{error}</p>}
        <button
          type="submit"
          disabled={submitting || !name.trim()}
          style={{
            marginTop: 12, width: '100%', padding: '12px 0',
            fontSize: 16, fontWeight: 600, borderRadius: 8,
            border: 'none', background: '#059669', color: '#fff',
            cursor: submitting || !name.trim() ? 'not-allowed' : 'pointer',
            opacity: submitting || !name.trim() ? 0.6 : 1,
          }}
        >
          {submitting ? 'Saving…' : 'Log Medication'}
        </button>
      </form>
      <Toast message="Medication logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}

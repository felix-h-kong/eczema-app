import { useState, useRef } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

export function NoteLog() {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(false);
  const [error, setError] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSubmitting(true);
    setError('');
    try {
      await createLogEntry({
        timestamp: new Date().toISOString(),
        type: 'note',
        notes: text.trim(),
      });
      setText('');
      setToast(true);
      textareaRef.current?.focus();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div style={{ padding: '24px 16px 100px' }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 16 }}>Log Note</h1>
      <form onSubmit={handleSubmit}>
        <textarea
          ref={textareaRef}
          autoFocus
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="Any observations, environmental factors, stress levels…"
          rows={6}
          style={{
            width: '100%', padding: 12, fontSize: 16,
            border: '1px solid #ccc', borderRadius: 8,
            resize: 'vertical', fontFamily: 'inherit',
          }}
        />
        {error && <p style={{ color: 'red', marginTop: 8 }}>{error}</p>}
        <button
          type="submit"
          disabled={submitting || !text.trim()}
          style={{
            marginTop: 12, width: '100%', padding: '12px 0',
            fontSize: 16, fontWeight: 600, borderRadius: 8,
            border: 'none', background: '#7c3aed', color: '#fff',
            cursor: submitting || !text.trim() ? 'not-allowed' : 'pointer',
            opacity: submitting || !text.trim() ? 0.6 : 1,
          }}
        >
          {submitting ? 'Saving…' : 'Save Note'}
        </button>
      </form>
      <Toast message="Note saved!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}

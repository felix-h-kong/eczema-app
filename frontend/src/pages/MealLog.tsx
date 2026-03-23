import { useState, useRef } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

export function MealLog() {
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
        type: 'meal',
        raw_input: text.trim(),
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
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 16 }}>Log Meal</h1>
      <form onSubmit={handleSubmit}>
        <textarea
          ref={textareaRef}
          autoFocus
          value={text}
          onChange={e => setText(e.target.value)}
          placeholder="What did you eat? (e.g. oatmeal with blueberries, almond milk)"
          rows={5}
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
            border: 'none', background: '#4f46e5', color: '#fff',
            cursor: submitting || !text.trim() ? 'not-allowed' : 'pointer',
            opacity: submitting || !text.trim() ? 0.6 : 1,
          }}
        >
          {submitting ? 'Saving…' : 'Log Meal'}
        </button>
      </form>
      <Toast message="Meal logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}

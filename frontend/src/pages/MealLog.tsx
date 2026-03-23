import { useState, useRef } from 'react';
import { createLogEntry } from '../api';
import { Toast } from '../components/Toast';

interface MealLogProps {
  onBack: () => void;
}

export function MealLog({ onBack }: MealLogProps) {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(false);
  const [error, setError] = useState('');
  const [customTime, setCustomTime] = useState<string | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) return;
    setSubmitting(true);
    setError('');
    try {
      await createLogEntry({
        timestamp: customTime ? new Date(customTime).toISOString() : new Date().toISOString(),
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
    <div style={{ padding: '16px 20px 100px' }}>
      <button onClick={onBack} style={{
        background: 'none', border: 'none', cursor: 'pointer',
        fontSize: 14, fontWeight: 500, color: 'var(--primary)',
        padding: '4px 0', marginBottom: 12,
      }}>
        {'\u2190'} Log meal
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
            What did you eat?
          </label>
          <textarea
            ref={textareaRef}
            autoFocus
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="e.g. oatmeal with blueberries, almond milk"
            rows={4}
            style={{
              width: '100%', padding: 0, fontSize: 15,
              border: 'none', background: 'transparent',
              resize: 'vertical', fontFamily: 'inherit',
              color: 'var(--text-primary)', outline: 'none',
              lineHeight: 1.5,
            }}
          />
        </div>

        <div style={{ display: 'flex', gap: 8, marginBottom: customTime !== null ? 8 : 16, flexWrap: 'wrap' }}>
          <button type="button" style={{
            background: 'var(--bg-surface-2)', border: '0.5px solid var(--border)',
            borderRadius: 14, padding: '8px 14px', fontSize: 13, fontWeight: 500,
            color: 'var(--text-secondary)', cursor: 'pointer',
          }}>
            Photo
          </button>
          <button type="button" style={{
            background: 'var(--bg-surface-2)', border: '0.5px solid var(--border)',
            borderRadius: 14, padding: '8px 14px', fontSize: 13, fontWeight: 500,
            color: 'var(--text-secondary)', cursor: 'pointer',
          }}>
            Barcode
          </button>
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
          {submitting ? 'Saving\u2026' : 'Log Meal'}
        </button>
      </form>
      <Toast message="Meal logged!" visible={toast} onDone={() => setToast(false)} />
    </div>
  );
}

import { useState, useRef } from 'react';
import { createLogEntry, uploadImage } from '../api';
import { Toast } from '../components/Toast';

interface FlareLogProps {
  onBack: () => void;
}

export function FlareLog({ onBack }: FlareLogProps) {
  const [severity, setSeverity] = useState(5);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState('');
  const [error, setError] = useState('');
  const [customTime, setCustomTime] = useState<string | null>(null);
  const [photos, setPhotos] = useState<File[]>([]);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const { id } = await createLogEntry({
        timestamp: customTime ? new Date(customTime).toISOString() : new Date().toISOString(),
        type: 'flare',
        severity,
        notes: notes.trim() || undefined,
      });
      for (const photo of photos) {
        await uploadImage(id, photo);
      }
      setSeverity(5);
      setNotes('');
      setPhotos([]);
      setToast(photos.length > 0 ? 'Skin check logged with photo!' : 'Skin check logged!');
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
        {'\u2190'} Skin check
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

        {/* Photo thumbnails */}
        {photos.length > 0 && (
          <div style={{ display: 'flex', gap: 8, marginBottom: 12, flexWrap: 'wrap' }}>
            {photos.map((photo, i) => (
              <div key={i} style={{ position: 'relative' }}>
                <img
                  src={URL.createObjectURL(photo)}
                  alt={`Photo ${i + 1}`}
                  style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 10, border: '0.5px solid var(--border)' }}
                />
                <button type="button" onClick={() => setPhotos(prev => prev.filter((_, j) => j !== i))} style={{
                  position: 'absolute', top: -6, right: -6,
                  width: 20, height: 20, borderRadius: '50%',
                  background: 'var(--type-flare)', color: '#fff',
                  border: 'none', fontSize: 12, lineHeight: '20px',
                  cursor: 'pointer', padding: 0,
                }}>
                  {'\u00D7'}
                </button>
              </div>
            ))}
          </div>
        )}

        <input
          ref={cameraRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={e => {
            const files = e.target.files;
            if (files && files.length > 0) setPhotos(prev => [...prev, ...Array.from(files)]);
            e.target.value = '';
          }}
          style={{ display: 'none' }}
        />
        <input
          ref={galleryRef}
          type="file"
          accept="image/*"
          onChange={e => {
            const files = e.target.files;
            if (files && files.length > 0) setPhotos(prev => [...prev, ...Array.from(files)]);
            e.target.value = '';
          }}
          style={{ display: 'none' }}
        />

        <div style={{ display: 'flex', gap: 8, marginBottom: customTime !== null ? 8 : 16 }}>
          <button type="button" onClick={() => cameraRef.current?.click()} style={{
            background: photos.length > 0 ? 'var(--primary-light)' : 'var(--bg-surface-2)',
            border: '0.5px solid var(--border)',
            borderRadius: 14, padding: '8px 14px', fontSize: 13, fontWeight: 500,
            color: photos.length > 0 ? 'var(--primary)' : 'var(--text-secondary)',
            cursor: 'pointer',
          }}>
            Camera{photos.length > 0 ? ` (${photos.length})` : ''}
          </button>
          <button type="button" onClick={() => galleryRef.current?.click()} style={{
            background: 'var(--bg-surface-2)',
            border: '0.5px solid var(--border)',
            borderRadius: 14, padding: '8px 14px', fontSize: 13, fontWeight: 500,
            color: 'var(--text-secondary)',
            cursor: 'pointer',
          }}>
            Gallery
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
          disabled={submitting}
          style={{
            width: '100%', padding: '12px 0',
            fontSize: 15, fontWeight: 500, borderRadius: 14,
            border: 'none', background: 'var(--primary)', color: '#FDF8F3',
            cursor: submitting ? 'not-allowed' : 'pointer',
            opacity: submitting ? 0.6 : 1,
          }}
        >
          {submitting ? 'Saving\u2026' : 'Log Skin Check'}
        </button>
      </form>
      <Toast message={toast} visible={!!toast} onDone={() => setToast('')} />
    </div>
  );
}

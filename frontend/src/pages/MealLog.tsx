import { useState, useRef, useCallback } from 'react';
import { createLogEntry, uploadImage, lookupBarcode } from '../api';
import { Toast } from '../components/Toast';
import { BarcodeScanner } from '../components/BarcodeScanner';

interface MealLogProps {
  onBack: () => void;
}

function SkinCheck({ onDone }: { onDone: () => void }) {
  const [severity, setSeverity] = useState(3);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setSubmitting(true);
    try {
      await createLogEntry({
        timestamp: new Date().toISOString(),
        type: 'flare',
        severity,
        notes: 'skin-checkin:pre-meal',
      });
    } catch {
      // Non-critical, don't block
    }
    onDone();
  }

  return (
    <div style={{
      background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
      borderRadius: 14, padding: 16, textAlign: 'center',
    }}>
      <div style={{
        fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
        textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 8,
      }}>
        Quick skin check
      </div>
      <div style={{ fontSize: 14, color: 'var(--text-primary)', marginBottom: 12 }}>
        How is your skin just before your meal? <strong>{severity}</strong> / 10
      </div>
      <input
        type="range" min={1} max={10} value={severity}
        onChange={e => setSeverity(Number(e.target.value))}
        style={{ width: '100%', marginBottom: 4 }}
      />
      <div style={{
        display: 'flex', justifyContent: 'space-between',
        fontSize: 11, color: 'var(--text-hint)', marginBottom: 14,
      }}>
        <span>Clear (1)</span>
        <span>Severe (10)</span>
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={handleSubmit} disabled={submitting} style={{
          flex: 1, padding: '10px 0', fontSize: 14, fontWeight: 500, borderRadius: 14,
          border: 'none', background: 'var(--primary)', color: '#FDF8F3', cursor: 'pointer',
        }}>
          Log
        </button>
        <button onClick={onDone} style={{
          flex: 1, padding: '10px 0', fontSize: 14, fontWeight: 500, borderRadius: 14,
          border: '0.5px solid var(--border)', background: 'var(--bg-surface-2)',
          color: 'var(--text-secondary)', cursor: 'pointer',
        }}>
          Skip
        </button>
      </div>
    </div>
  );
}

export function MealLog({ onBack }: MealLogProps) {
  const [text, setText] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState('');
  const [error, setError] = useState('');
  const [customTime, setCustomTime] = useState<string | null>(null);
  const [photos, setPhotos] = useState<File[]>([]);
  const [barcodeMode, setBarcodeMode] = useState<'off' | 'manual' | 'scanning'>('off');
  const [upc, setUpc] = useState('');
  const [barcodeLoading, setBarcodeLoading] = useState(false);
  const [showSkinCheck, setShowSkinCheck] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() && photos.length === 0) return;
    setSubmitting(true);
    setError('');
    try {
      const { id } = await createLogEntry({
        timestamp: customTime ? new Date(customTime).toISOString() : new Date().toISOString(),
        type: 'meal',
        raw_input: text.trim() || undefined,
      });
      // Upload any attached photos
      for (const photo of photos) {
        await uploadImage(id, photo);
      }
      setText('');
      setPhotos([]);
      setToast(photos.length > 0 ? 'Meal logged with photo!' : 'Meal logged!');
      setShowSkinCheck(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setSubmitting(false);
    }
  }

  function handlePhotoSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (files && files.length > 0) {
      setPhotos(prev => [...prev, ...Array.from(files)]);
    }
    // Reset so the same file can be selected again
    e.target.value = '';
  }

  async function doBarcodeLookup(code: string) {
    if (!code.trim()) return;
    setBarcodeLoading(true);
    setError('');
    try {
      const { ingredients } = await lookupBarcode(code.trim());
      setText(prev => prev ? `${prev}\n${ingredients}` : ingredients);
      setBarcodeMode('off');
      setUpc('');
      setToast('Ingredients added from barcode');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Barcode lookup failed');
    } finally {
      setBarcodeLoading(false);
    }
  }

  const handleBarcodeDetected = useCallback((code: string) => {
    setBarcodeMode('off');
    doBarcodeLookup(code);
  }, []);

  const pillStyle = (active?: boolean) => ({
    background: active ? 'var(--primary-light)' : 'var(--bg-surface-2)',
    border: '0.5px solid var(--border)',
    borderRadius: 14, padding: '8px 14px', fontSize: 13, fontWeight: 500 as const,
    color: active ? 'var(--primary)' : 'var(--text-secondary)',
    cursor: 'pointer' as const,
  });

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
          onChange={handlePhotoSelect}
          style={{ display: 'none' }}
        />
        <input
          ref={galleryRef}
          type="file"
          accept="image/*"
          onChange={handlePhotoSelect}
          style={{ display: 'none' }}
        />

        <div style={{ display: 'flex', gap: 8, marginBottom: barcodeMode !== 'off' || customTime !== null ? 8 : 16, flexWrap: 'wrap' }}>
          <button type="button" onClick={() => cameraRef.current?.click()} style={pillStyle(photos.length > 0)}>
            Camera{photos.length > 0 ? ` (${photos.length})` : ''}
          </button>
          <button type="button" onClick={() => galleryRef.current?.click()} style={pillStyle(false)}>
            Gallery
          </button>
          <button type="button" onClick={() => {
            if (barcodeMode !== 'off') { setBarcodeMode('off'); }
            else { setBarcodeMode('scanning'); }
          }} style={pillStyle(barcodeMode !== 'off')}>
            Barcode
          </button>
          <button type="button" onClick={() => setCustomTime(customTime !== null ? null : '')} style={pillStyle(customTime !== null)}>
            Set time
          </button>
        </div>

        {barcodeMode === 'manual' && (
          <div style={{
            display: 'flex', gap: 8, marginBottom: customTime !== null ? 8 : 16,
          }}>
            <input
              autoFocus
              type="text"
              inputMode="numeric"
              value={upc}
              onChange={e => setUpc(e.target.value)}
              placeholder="Enter barcode number"
              onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); doBarcodeLookup(upc); } }}
              style={{
                flex: 1, padding: '10px 14px', fontSize: 15,
                border: '0.5px solid var(--border)', borderRadius: 14,
                background: 'var(--bg-surface)', color: 'var(--text-primary)',
                fontFamily: 'inherit', outline: 'none',
              }}
            />
            <button type="button" onClick={() => doBarcodeLookup(upc)} disabled={barcodeLoading || !upc.trim()} style={{
              padding: '10px 16px', fontSize: 14, fontWeight: 500, borderRadius: 14,
              border: 'none', background: 'var(--primary)', color: '#FDF8F3',
              cursor: barcodeLoading || !upc.trim() ? 'not-allowed' : 'pointer',
              opacity: barcodeLoading || !upc.trim() ? 0.6 : 1,
            }}>
              {barcodeLoading ? '\u2026' : 'Look up'}
            </button>
          </div>
        )}

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
          disabled={submitting || (!text.trim() && photos.length === 0)}
          style={{
            width: '100%', padding: '12px 0',
            fontSize: 15, fontWeight: 500, borderRadius: 14,
            border: 'none', background: 'var(--primary)', color: '#FDF8F3',
            cursor: submitting || (!text.trim() && photos.length === 0) ? 'not-allowed' : 'pointer',
            opacity: submitting || (!text.trim() && photos.length === 0) ? 0.6 : 1,
          }}
        >
          {submitting ? 'Saving\u2026' : 'Log Meal'}
        </button>
      </form>
      {barcodeLoading && (
        <div style={{
          textAlign: 'center', padding: 12, fontSize: 13,
          color: 'var(--text-secondary)', marginTop: 8,
        }}>
          Looking up barcode\u2026
        </div>
      )}
      {showSkinCheck && (
        <div style={{ marginTop: 16 }}>
          <SkinCheck onDone={() => { setShowSkinCheck(false); textareaRef.current?.focus(); }} />
        </div>
      )}
      <Toast message={toast} visible={!!toast} onDone={() => setToast('')} />
      {barcodeMode === 'scanning' && (
        <BarcodeScanner
          onDetected={handleBarcodeDetected}
          onClose={() => setBarcodeMode('off')}
          onManualEntry={() => setBarcodeMode('manual')}
        />
      )}
    </div>
  );
}

import { useRef, useEffect, useState, useCallback } from 'react';

interface BarcodeScannerProps {
  onDetected: (code: string) => void;
  onClose: () => void;
  onManualEntry: () => void;
}

export function BarcodeScanner({ onDetected, onClose, onManualEntry }: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [mode, setMode] = useState<'starting' | 'live' | 'photo'>('starting');
  const [error, setError] = useState('');
  const [processing, setProcessing] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const stopStream = useCallback(() => {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
  }, []);

  useEffect(() => {
    let cancelled = false;
    let animFrame: number;

    async function tryLiveScanning() {
      // Need both BarcodeDetector and getUserMedia
      const hasBarcodeDetector = 'BarcodeDetector' in window;
      let hasCamera = false;

      if (hasBarcodeDetector) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
          });
          if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
          streamRef.current = stream;
          hasCamera = true;
        } catch {
          // getUserMedia failed (likely insecure context over HTTP)
        }
      }

      if (hasCamera && hasBarcodeDetector) {
        // Live scanning mode — set mode first, wait for React to render the video element
        if (cancelled) return;
        setMode('live');

        // Wait for the video element to appear in the DOM
        await new Promise<void>(resolve => {
          const check = () => {
            if (videoRef.current || cancelled) resolve();
            else requestAnimationFrame(check);
          };
          check();
        });

        if (cancelled || !videoRef.current) return;
        videoRef.current.srcObject = streamRef.current;
        await videoRef.current.play();

        // @ts-ignore
        const detector = new BarcodeDetector({
          formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128'],
        });

        async function scan() {
          if (cancelled || !videoRef.current) return;
          try {
            const barcodes = await detector.detect(videoRef.current);
            if (barcodes.length > 0 && !cancelled) {
              onDetected(barcodes[0].rawValue);
              return;
            }
          } catch {
            // Frame not ready, keep trying
          }
          animFrame = requestAnimationFrame(scan);
        }

        setTimeout(() => { if (!cancelled) scan(); }, 500);
      } else {
        // Fall back to photo mode
        if (cancelled) return;
        setMode('photo');
        if (!hasBarcodeDetector) {
          setError('Barcode detection not supported. Enter the number manually.');
        }
      }
    }

    tryLiveScanning();

    return () => {
      cancelled = true;
      cancelAnimationFrame(animFrame);
      stopStream();
    };
  }, [onDetected, stopStream]);

  async function handlePhoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;

    if (!('BarcodeDetector' in window)) {
      setError('Barcode detection not supported on this browser.');
      return;
    }

    setProcessing(true);
    setError('');
    try {
      const bitmap = await createImageBitmap(file);
      // @ts-ignore
      const detector = new BarcodeDetector({
        formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128'],
      });
      const barcodes = await detector.detect(bitmap);
      bitmap.close();
      if (barcodes.length > 0) {
        onDetected(barcodes[0].rawValue);
      } else {
        setError('No barcode found in photo. Try again or enter manually.');
      }
    } catch {
      setError('Failed to read barcode. Try again or enter manually.');
    } finally {
      setProcessing(false);
    }
  }

  function handleClose() {
    stopStream();
    onClose();
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: '#000', display: 'flex', flexDirection: 'column',
    }}>
      {/* Camera / photo area */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        {mode === 'live' && (
          <video
            ref={videoRef}
            playsInline
            muted
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
          />
        )}

        {mode === 'photo' && (
          <div style={{
            width: '100%', height: '100%',
            display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 16,
            padding: 32,
          }}>
            <div style={{ fontSize: 40 }}>{'\uD83D\uDCF7'}</div>
            <div style={{ color: '#fff', fontSize: 15, textAlign: 'center', lineHeight: 1.5 }}>
              Live scanning needs HTTPS.<br />
              Take a photo of the barcode instead.
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handlePhoto}
              style={{ display: 'none' }}
            />
            <button onClick={() => fileRef.current?.click()} disabled={processing} style={{
              padding: '14px 32px', fontSize: 16, fontWeight: 500, borderRadius: 14,
              border: 'none', background: 'var(--primary)', color: '#FDF8F3',
              cursor: processing ? 'not-allowed' : 'pointer',
              opacity: processing ? 0.6 : 1,
            }}>
              {processing ? 'Reading\u2026' : 'Take photo'}
            </button>
          </div>
        )}

        {mode === 'starting' && (
          <div style={{
            width: '100%', height: '100%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'rgba(255,255,255,0.6)', fontSize: 14,
          }}>
            Starting camera\u2026
          </div>
        )}

        {/* Scanning guide overlay (live mode) */}
        {mode === 'live' && (
          <div style={{
            position: 'absolute', inset: 0,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              width: '75%', height: 120, border: '2px solid rgba(255,255,255,0.6)',
              borderRadius: 12,
            }} />
          </div>
        )}

        {/* Status text */}
        <div style={{
          position: 'absolute', bottom: 120, left: 0, right: 0,
          textAlign: 'center', color: error ? '#E06848' : 'rgba(255,255,255,0.8)',
          fontSize: 14, fontFamily: 'inherit', padding: '0 20px',
        }}>
          {error || (mode === 'live' ? 'Point at a barcode' : '')}
        </div>
      </div>

      {/* Bottom controls */}
      <div style={{
        padding: '16px 20px', paddingBottom: 32,
        background: 'rgba(0,0,0,0.85)',
        display: 'flex', gap: 12,
      }}>
        <button onClick={handleClose} style={{
          flex: 1, padding: '12px 0', fontSize: 15, fontWeight: 500, borderRadius: 14,
          border: '1px solid rgba(255,255,255,0.3)', background: 'transparent',
          color: '#fff', cursor: 'pointer',
        }}>
          Cancel
        </button>
        <button onClick={() => { handleClose(); onManualEntry(); }} style={{
          flex: 1, padding: '12px 0', fontSize: 15, fontWeight: 500, borderRadius: 14,
          border: 'none', background: 'var(--primary)', color: '#FDF8F3', cursor: 'pointer',
        }}>
          Type number
        </button>
      </div>
    </div>
  );
}

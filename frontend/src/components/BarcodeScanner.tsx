import { useRef, useEffect, useState } from 'react';

interface BarcodeScannerProps {
  onDetected: (code: string) => void;
  onClose: () => void;
  onManualEntry: () => void;
}

export function BarcodeScanner({ onDetected, onClose, onManualEntry }: BarcodeScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    let animFrame: number;

    async function start() {
      // Check for BarcodeDetector support
      if (!('BarcodeDetector' in window)) {
        setError('Barcode scanning not supported on this browser.');
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
        });
        if (cancelled) { stream.getTracks().forEach(t => t.stop()); return; }
        streamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          await videoRef.current.play();
        }
      } catch {
        setError('Camera access denied or unavailable. Use manual entry instead.');
        return;
      }

      // @ts-ignore - BarcodeDetector not in TS lib
      const detector = new BarcodeDetector({
        formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128'],
      });

      async function scan() {
        if (cancelled || !videoRef.current) return;
        try {
          const barcodes = await detector.detect(videoRef.current);
          if (barcodes.length > 0 && !cancelled) {
            onDetected(barcodes[0].rawValue);
            return; // Stop scanning
          }
        } catch {
          // Frame not ready yet, keep trying
        }
        animFrame = requestAnimationFrame(scan);
      }

      // Small delay for camera to warm up
      setTimeout(() => { if (!cancelled) scan(); }, 500);
    }

    start();

    return () => {
      cancelled = true;
      cancelAnimationFrame(animFrame);
      streamRef.current?.getTracks().forEach(t => t.stop());
    };
  }, [onDetected]);

  function handleClose() {
    streamRef.current?.getTracks().forEach(t => t.stop());
    onClose();
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: '#000', display: 'flex', flexDirection: 'column',
    }}>
      {/* Camera view */}
      <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
        <video
          ref={videoRef}
          playsInline
          muted
          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
        />
        {/* Scanning guide overlay */}
        <div style={{
          position: 'absolute', inset: 0,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            width: '75%', height: 120, border: '2px solid rgba(255,255,255,0.6)',
            borderRadius: 12,
          }} />
        </div>
        {/* Hint text */}
        <div style={{
          position: 'absolute', bottom: 120, left: 0, right: 0,
          textAlign: 'center', color: 'rgba(255,255,255,0.8)',
          fontSize: 14, fontFamily: 'inherit',
        }}>
          {error || 'Point at a barcode'}
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
          Enter manually
        </button>
      </div>
    </div>
  );
}

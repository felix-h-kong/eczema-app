import { useState, useEffect, useCallback } from 'react';
import useEmblaCarousel from 'embla-carousel-react';

interface PhotoGalleryProps {
  images: string[];
  initialIndex?: number;
  onClose: () => void;
}

export function PhotoGallery({ images, initialIndex = 0, onClose }: PhotoGalleryProps) {
  const [emblaRef, emblaApi] = useEmblaCarousel({ startIndex: initialIndex, loop: false });
  const [currentIndex, setCurrentIndex] = useState(initialIndex);

  const multi = images.length > 1;

  const onSelect = useCallback(() => {
    if (!emblaApi) return;
    setCurrentIndex(emblaApi.selectedScrollSnap());
  }, [emblaApi]);

  useEffect(() => {
    if (!emblaApi) return;
    emblaApi.on('select', onSelect);
    return () => { emblaApi.off('select', onSelect); };
  }, [emblaApi, onSelect]);

  // Body scroll lock
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = prev; };
  }, []);

  // Keyboard navigation
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft') emblaApi?.scrollPrev();
      if (e.key === 'ArrowRight') emblaApi?.scrollNext();
    }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [emblaApi, onClose]);

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 1000,
      background: '#000', display: 'flex', flexDirection: 'column',
    }}>
      {/* Top bar */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '16px', paddingTop: 48, background: 'rgba(0,0,0,0.5)',
        position: 'absolute', top: 0, left: 0, right: 0, zIndex: 2,
      }}>
        <button
          onClick={onClose}
          style={{
            width: 36, height: 36, borderRadius: 18,
            background: 'rgba(255,255,255,0.15)', border: 'none',
            color: '#fff', fontSize: 20, cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}
        >
          ✕
        </button>
        {multi && (
          <span style={{ color: '#fff', fontSize: 14, fontWeight: 500 }}>
            {currentIndex + 1} / {images.length}
          </span>
        )}
        <div style={{ width: 36 }} />
      </div>

      {/* Embla carousel */}
      <div ref={emblaRef} style={{ flex: 1, overflow: 'hidden' }}>
        <div style={{ display: 'flex', height: '100%' }}>
          {images.map((src, i) => (
            <div key={i} style={{
              flex: '0 0 100%', display: 'flex',
              alignItems: 'center', justifyContent: 'center',
            }}>
              <img
                src={src}
                alt=""
                draggable={false}
                style={{
                  maxWidth: '100%', maxHeight: '100%',
                  objectFit: 'contain', userSelect: 'none',
                }}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Bottom nav */}
      {multi && (
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          padding: '16px 24px', paddingBottom: 32,
          position: 'absolute', bottom: 0, left: 0, right: 0, zIndex: 2,
          background: 'rgba(0,0,0,0.5)',
        }}>
          <button
            onClick={() => emblaApi?.scrollPrev()}
            style={{
              width: 44, height: 44, borderRadius: 22,
              background: 'rgba(255,255,255,0.15)', border: 'none',
              color: '#fff', fontSize: 22, cursor: 'pointer',
              opacity: currentIndex === 0 ? 0.3 : 1,
            }}
          >
            ‹
          </button>
          <button
            onClick={() => emblaApi?.scrollNext()}
            style={{
              width: 44, height: 44, borderRadius: 22,
              background: 'rgba(255,255,255,0.15)', border: 'none',
              color: '#fff', fontSize: 22, cursor: 'pointer',
              opacity: currentIndex === images.length - 1 ? 0.3 : 1,
            }}
          >
            ›
          </button>
        </div>
      )}
    </div>
  );
}

import { useEffect } from 'react';

interface ToastProps {
  message: string;
  visible: boolean;
  onDone: () => void;
  duration?: number;
}

export function Toast({ message, visible, onDone, duration = 2000 }: ToastProps) {
  useEffect(() => {
    if (visible) {
      const timer = setTimeout(onDone, duration);
      return () => clearTimeout(timer);
    }
  }, [visible, onDone, duration]);

  if (!visible) return null;

  return (
    <div style={{
      position: 'fixed', bottom: 80, left: '50%', transform: 'translateX(-50%)',
      background: '#333', color: '#fff', padding: '12px 24px', borderRadius: 8,
      zIndex: 1000, fontSize: 14,
    }}>
      {message}
    </div>
  );
}

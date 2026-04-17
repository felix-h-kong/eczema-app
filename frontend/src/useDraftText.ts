import { useState, useCallback } from 'react';

type SetAction = string | ((prev: string) => string);

export function useDraftText(key: string): [string, (v: SetAction) => void, () => void] {
  const [value, setValue] = useState(() => sessionStorage.getItem(key) || '');

  const set = useCallback((v: SetAction) => {
    setValue(prev => {
      const next = typeof v === 'function' ? v(prev) : v;
      if (next) {
        sessionStorage.setItem(key, next);
      } else {
        sessionStorage.removeItem(key);
      }
      return next;
    });
  }, [key]);

  const clear = useCallback(() => {
    setValue('');
    sessionStorage.removeItem(key);
  }, [key]);

  return [value, set, clear];
}

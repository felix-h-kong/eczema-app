import { useState, useEffect, useCallback } from 'react';

const DB_NAME = 'eczema-drafts';
const STORE_NAME = 'photos';
const DB_VERSION = 1;

interface StoredPhoto {
  draftKey: string;
  index: number;
  blob: Blob;
  name: string;
  type: string;
}

interface DraftPhoto {
  file: File;
  url: string;
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { autoIncrement: true });
        store.createIndex('draftKey', 'draftKey', { unique: false });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function loadPhotos(draftKey: string): Promise<DraftPhoto[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly');
    const idx = tx.objectStore(STORE_NAME).index('draftKey');
    const req = idx.getAll(draftKey);
    req.onsuccess = () => {
      const rows = req.result as StoredPhoto[];
      rows.sort((a, b) => a.index - b.index);
      resolve(rows.map(r => {
        const file = new File([r.blob], r.name, { type: r.type });
        return { file, url: URL.createObjectURL(file) };
      }));
    };
    req.onerror = () => reject(req.error);
  });
}

async function savePhoto(draftKey: string, index: number, file: File): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    tx.objectStore(STORE_NAME).add({
      draftKey,
      index,
      blob: file,
      name: file.name,
      type: file.type,
    } as StoredPhoto);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function clearStore(draftKey: string): Promise<void> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite');
    const store = tx.objectStore(STORE_NAME);
    const idx = store.index('draftKey');
    const req = idx.openCursor(draftKey);
    req.onsuccess = () => {
      const cursor = req.result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

export function useDraftPhotos(draftKey: string) {
  const [photos, setPhotos] = useState<DraftPhoto[]>([]);
  const nextIndexRef = { current: 0 };

  useEffect(() => {
    loadPhotos(draftKey).then(restored => {
      if (restored.length > 0) {
        setPhotos(restored);
        nextIndexRef.current = restored.length;
      }
    }).catch(() => {});
  }, [draftKey]);

  const addPhotos = useCallback((files: File[]) => {
    const newPhotos: DraftPhoto[] = [];
    for (const file of files) {
      savePhoto(draftKey, nextIndexRef.current, file).catch(() => {});
      newPhotos.push({ file, url: URL.createObjectURL(file) });
      nextIndexRef.current++;
    }
    setPhotos(prev => [...prev, ...newPhotos]);
  }, [draftKey]);

  const removePhoto = useCallback((index: number) => {
    setPhotos(prev => {
      URL.revokeObjectURL(prev[index].url);
      return prev.filter((_, i) => i !== index);
    });
    // Simplest approach: rewrite the store from current state
    clearStore(draftKey).then(() => {
      setPhotos(current => {
        current.forEach((p, i) => savePhoto(draftKey, i, p.file).catch(() => {}));
        return current;
      });
    }).catch(() => {});
  }, [draftKey]);

  const clearPhotos = useCallback(() => {
    setPhotos(prev => {
      prev.forEach(p => URL.revokeObjectURL(p.url));
      return [];
    });
    nextIndexRef.current = 0;
    clearStore(draftKey).catch(() => {});
  }, [draftKey]);

  return { photos, addPhotos, removePhoto, clearPhotos };
}

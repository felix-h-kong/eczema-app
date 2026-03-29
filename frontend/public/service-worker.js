// Service Worker for Eczema Tracker PWA

const CACHE_NAME = 'eczema-tracker-v1';
const OFFLINE_QUEUE_STORE = 'offline-queue';

// Cache app shell on install
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(['/', '/index.html']);
    })
  );
  self.skipWaiting();
});

// Clean old caches on activate
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// Network-first for API, cache-first for assets
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  if (url.pathname.startsWith('/api/')) {
    // For POST /api/log — queue if offline
    if (event.request.method === 'POST' && url.pathname === '/api/log') {
      event.respondWith(
        fetch(event.request.clone()).catch(async () => {
          const body = await event.request.json();
          await saveToOfflineQueue(body);
          return new Response(JSON.stringify({ id: -1, queued: true }), {
            headers: { 'Content-Type': 'application/json' },
          });
        })
      );
      return;
    }
    return;
  }

  // App shell: network-first, fall back to cache when offline
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        const clone = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});

// Handle push notifications
self.addEventListener('push', (event) => {
  const data = event.data?.json() || { title: 'Eczema Tracker', body: 'Time to log!' };
  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: '/icon-192.png',
    })
  );
});

// Click notification -> open app
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  event.waitUntil(self.clients.openWindow('/'));
});

// IndexedDB helpers for offline queue
function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('eczema-offline', 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(OFFLINE_QUEUE_STORE, { autoIncrement: true });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function saveToOfflineQueue(entry) {
  const db = await openDB();
  const tx = db.transaction(OFFLINE_QUEUE_STORE, 'readwrite');
  tx.objectStore(OFFLINE_QUEUE_STORE).add(entry);
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function replayOfflineQueue() {
  const db = await openDB();
  const tx = db.transaction(OFFLINE_QUEUE_STORE, 'readwrite');
  const store = tx.objectStore(OFFLINE_QUEUE_STORE);
  const entries = await new Promise((resolve, reject) => {
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  for (const entry of entries) {
    try {
      await fetch('/api/log', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry),
      });
    } catch {
      return;
    }
  }

  const clearTx = db.transaction(OFFLINE_QUEUE_STORE, 'readwrite');
  clearTx.objectStore(OFFLINE_QUEUE_STORE).clear();
}

// Replay offline queue when told
self.addEventListener('message', (event) => {
  if (event.data === 'replay-queue') {
    replayOfflineQueue();
  }
});

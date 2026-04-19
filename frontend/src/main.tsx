import React from 'react'
import ReactDOM from 'react-dom/client'
import { Capacitor } from '@capacitor/core'
import { setupBackgroundSync } from './background-sync'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Capacitor native: set up hourly background BLE sync.
// enableHeadless in the config handles Android terminated-app events natively.
if (Capacitor.isNativePlatform()) {
  setupBackgroundSync().catch((err) => {
    console.error('[bg-sync] setup failed:', err);
  });
}

// Register service worker (web PWA only — skip in Capacitor where assets load
// from the filesystem and SW caching is unnecessary and can conflict)
if ('serviceWorker' in navigator && import.meta.env.PROD && !Capacitor.isNativePlatform()) {
  window.addEventListener('load', async () => {
    try {
      const registration = await navigator.serviceWorker.register('/service-worker.js');
      console.log('SW registered:', registration.scope);

      window.addEventListener('online', () => {
        navigator.serviceWorker.controller?.postMessage('replay-queue');
      });
    } catch (err) {
      console.error('SW registration failed:', err);
    }
  });
}

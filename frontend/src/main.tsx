import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

// Register service worker
if ('serviceWorker' in navigator) {
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

import { useState, useEffect } from 'react';
import { TabBar } from './components/TabBar';
import { LogHub } from './pages/LogHub';
import { MealLog } from './pages/MealLog';
import { FlareLog } from './pages/FlareLog';
import { MedsLog } from './pages/MedsLog';
import { EventLog } from './pages/EventLog';
import { History } from './pages/History';
import { Analysis } from './pages/Analysis';
import { subscribePush } from './api';

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = atob(base64);
  const arr = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
  return arr;
}

export async function setupPushNotifications() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) return;
  if (Notification.permission === 'denied') return;
  // Only request permission if not yet granted (needs user gesture on Android)
  if (Notification.permission !== 'granted') {
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return;
  }
  try {
    const resp = await fetch('/api/push/vapid-key');
    if (!resp.ok) return;
    const { public_key } = await resp.json();
    const registration = await navigator.serviceWorker.ready;
    let subscription = await registration.pushManager.getSubscription();
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(public_key) as BufferSource,
      });
    }
    await subscribePush(subscription);
  } catch (err) {
    console.error('Push setup failed:', err);
  }
}

function App() {
  const [tab, setTab] = useState(() => sessionStorage.getItem('tab') || 'log');
  const [logForm, setLogForm] = useState<string | null>(() => sessionStorage.getItem('logForm') || null);

  useEffect(() => { sessionStorage.setItem('tab', tab); }, [tab]);
  useEffect(() => {
    if (logForm) sessionStorage.setItem('logForm', logForm);
    else sessionStorage.removeItem('logForm');
  }, [logForm]);

  useEffect(() => { setupPushNotifications(); }, []);

  // Deep-link from notification clicks (e.g. weekly task -> event page)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const action = params.get('action');
    if (action === 'event') {
      setTab('log');
      setLogForm('event');
      window.history.replaceState({}, '', '/');
    }
  }, []);

  const handleBack = () => setLogForm(null);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)' }}>
      {tab === 'log' && !logForm && <LogHub onSelect={setLogForm} />}
      {tab === 'log' && logForm === 'meal' && <MealLog onBack={handleBack} />}
      {tab === 'log' && logForm === 'flare' && <FlareLog onBack={handleBack} />}
      {tab === 'log' && logForm === 'meds' && <MedsLog onBack={handleBack} />}
      {tab === 'log' && logForm === 'event' && <EventLog onBack={handleBack} />}
      {tab === 'history' && <History />}
      {tab === 'analysis' && <Analysis />}
      <TabBar active={tab} onSelect={(t) => { setTab(t); setLogForm(null); }} />
    </div>
  );
}

export default App;

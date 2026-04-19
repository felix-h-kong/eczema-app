import { useState, useEffect, useCallback } from 'react';
import { Capacitor } from '@capacitor/core';
import { TabBar } from './components/TabBar';
import { SensorLED } from './components/SensorLED';
import { LogHub } from './pages/LogHub';
import { MealLog } from './pages/MealLog';
import { FlareLog } from './pages/FlareLog';
import { MedsLog } from './pages/MedsLog';
import { EventLog } from './pages/EventLog';
import { NoteLog } from './pages/NoteLog';
import { History } from './pages/History';
import { Analysis } from './pages/Analysis';
import { Environment } from './pages/Environment';
import { startForegroundPolling } from './foreground-sync';
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

  // Foreground BLE polling — scan for sensor every 10 min when the app is open
  useEffect(() => {
    if (!Capacitor.isNativePlatform()) return;
    return startForegroundPolling();
  }, []);

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

  // Push a history entry when navigating into a log sub-form so that
  // Android's back gesture returns to the hub instead of minimizing the app.
  const openLogForm = useCallback((form: string) => {
    setLogForm(form);
    window.history.pushState({ logForm: form }, '');
  }, []);

  const handleBack = useCallback(() => {
    if (logForm) {
      window.history.back();
    }
  }, [logForm]);

  useEffect(() => {
    const onPopState = () => {
      // When the user navigates back (Android gesture or browser back),
      // return to the log hub if we're in a sub-form.
      setLogForm((prev) => prev ? null : prev);
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)' }}>
      {tab === 'log' && !logForm && <LogHub onSelect={openLogForm} />}
      {tab === 'log' && logForm === 'meal' && <MealLog onBack={handleBack} />}
      {tab === 'log' && logForm === 'flare' && <FlareLog onBack={handleBack} />}
      {tab === 'log' && logForm === 'meds' && <MedsLog onBack={handleBack} />}
      {tab === 'log' && logForm === 'event' && <EventLog onBack={handleBack} />}
      {tab === 'log' && logForm === 'note' && <NoteLog onBack={handleBack} />}
      {tab === 'history' && <History />}
      {tab === 'analysis' && <Analysis />}
      {tab === 'environment' && <Environment />}
      {Capacitor.isNativePlatform() && <SensorLED />}
      <TabBar active={tab} onSelect={(t) => { setTab(t); setLogForm(null); }} />
    </div>
  );
}

export default App;

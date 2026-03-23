import { useState } from 'react';
import { TabBar } from './components/TabBar';
import { MealLog } from './pages/MealLog';
import { FlareLog } from './pages/FlareLog';
import { MedsLog } from './pages/MedsLog';
import { NoteLog } from './pages/NoteLog';
import { Analysis } from './pages/Analysis';

function App() {
  const [tab, setTab] = useState('meal');
  return (
    <div style={{ minHeight: '100vh', background: '#fafafa' }}>
      {tab === 'meal' && <MealLog />}
      {tab === 'flare' && <FlareLog />}
      {tab === 'meds' && <MedsLog />}
      {tab === 'note' && <NoteLog />}
      {tab === 'analysis' && <Analysis />}
      <TabBar active={tab} onSelect={setTab} />
    </div>
  );
}

export default App;

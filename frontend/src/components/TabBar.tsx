const TABS = [
  { key: 'log', label: 'Log' },
  { key: 'history', label: 'History' },
  { key: 'analysis', label: 'Analyse' },
];

interface TabBarProps {
  active: string;
  onSelect: (key: string) => void;
}

export function TabBar({ active, onSelect }: TabBarProps) {
  return (
    <nav style={{
      position: 'fixed', bottom: 0, left: 0, right: 0,
      display: 'flex', justifyContent: 'space-around',
      background: 'var(--bg-surface)',
      borderTop: '0.5px solid var(--border)',
      paddingBottom: 'env(safe-area-inset-bottom)',
      zIndex: 100,
    }}>
      {TABS.map(tab => (
        <button key={tab.key} onClick={() => onSelect(tab.key)} style={{
          flex: 1, border: 'none', background: 'none', padding: '10px 0 8px',
          cursor: 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
        }}>
          <div style={{
            width: 14, height: 14, borderRadius: 7,
            background: active === tab.key ? 'var(--primary)' : 'var(--bg-surface-2)',
          }} />
          <span style={{
            fontSize: 10,
            color: active === tab.key ? 'var(--primary)' : 'var(--text-hint)',
          }}>{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}

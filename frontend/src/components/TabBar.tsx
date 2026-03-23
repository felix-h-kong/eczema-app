const TABS = [
  { key: 'meal', label: 'Meal', icon: '\u{1F37D}' },
  { key: 'flare', label: 'Flare', icon: '\u{1F534}' },
  { key: 'meds', label: 'Meds', icon: '\u{1F48A}' },
  { key: 'note', label: 'Note', icon: '\u{1F4DD}' },
  { key: 'analysis', label: 'Analysis', icon: '\u{1F4CA}' },
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
      background: '#fff', borderTop: '1px solid #e0e0e0',
      paddingBottom: 'env(safe-area-inset-bottom)', zIndex: 100,
    }}>
      {TABS.map(tab => (
        <button key={tab.key} onClick={() => onSelect(tab.key)} style={{
          flex: 1, border: 'none', background: 'none', padding: '8px 0',
          cursor: 'pointer', opacity: active === tab.key ? 1 : 0.5,
          display: 'flex', flexDirection: 'column', alignItems: 'center', fontSize: 12,
        }}>
          <span style={{ fontSize: 24 }}>{tab.icon}</span>
          <span>{tab.label}</span>
        </button>
      ))}
    </nav>
  );
}

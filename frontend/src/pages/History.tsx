import { useState, useEffect } from 'react';
import { getLogEntries, updateLogEntry, deleteLogEntry } from '../api';
import type { LogEntry } from '../api';
import { Toast } from '../components/Toast';

function formatTime(ts: string): string {
  return new Date(ts).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' });
}

function formatWeekRange(): string {
  const now = new Date();
  const start = new Date(now);
  start.setDate(now.getDate() - 6);
  const fmt = (d: Date) => d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' });
  return `${fmt(start)} \u2013 ${fmt(now)}`;
}

function groupByDay(entries: LogEntry[]): Record<string, LogEntry[]> {
  const groups: Record<string, LogEntry[]> = {};
  for (const entry of entries) {
    const day = new Date(entry.timestamp).toLocaleDateString('en-AU', {
      weekday: 'long', day: 'numeric', month: 'long',
    });
    if (!groups[day]) groups[day] = [];
    groups[day].push(entry);
  }
  return groups;
}

interface EditState {
  raw_input?: string;
  severity?: number;
  medication_name?: string;
  medication_dose?: string;
  notes?: string;
}

function EditForm({ entry, onSave, onCancel }: {
  entry: LogEntry;
  onSave: (fields: EditState) => void;
  onCancel: () => void;
}) {
  const [fields, setFields] = useState<EditState>(() => {
    if (entry.type === 'meal') return { raw_input: entry.raw_input || '' };
    if (entry.type === 'flare') return { severity: entry.severity ?? 5, notes: entry.notes || '' };
    return { medication_name: entry.medication_name || '', medication_dose: entry.medication_dose || '' };
  });

  const inputStyle = {
    width: '100%', padding: '8px 10px', fontSize: 14,
    border: '0.5px solid var(--border)', borderRadius: 10,
    background: 'var(--bg-base)', color: 'var(--text-primary)',
    fontFamily: 'inherit', outline: 'none',
  } as const;

  return (
    <div style={{ marginTop: 8 }}>
      {entry.type === 'meal' && (
        <textarea
          autoFocus
          value={fields.raw_input}
          onChange={e => setFields({ ...fields, raw_input: e.target.value })}
          rows={3}
          style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.4 }}
        />
      )}
      {entry.type === 'flare' && (
        <>
          <label style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
            Severity: {fields.severity} / 10
          </label>
          <input
            type="range" min={1} max={10} value={fields.severity}
            onChange={e => setFields({ ...fields, severity: Number(e.target.value) })}
            style={{ width: '100%', marginBottom: 8 }}
          />
          <textarea
            value={fields.notes}
            onChange={e => setFields({ ...fields, notes: e.target.value })}
            placeholder="Notes"
            rows={2}
            style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.4 }}
          />
        </>
      )}
      {entry.type === 'medication' && (
        <>
          <input
            autoFocus
            type="text"
            value={fields.medication_name}
            onChange={e => setFields({ ...fields, medication_name: e.target.value })}
            placeholder="Medication name"
            style={{ ...inputStyle, marginBottom: 6 }}
          />
          <input
            type="text"
            value={fields.medication_dose}
            onChange={e => setFields({ ...fields, medication_dose: e.target.value })}
            placeholder="Dose"
            style={inputStyle}
          />
        </>
      )}
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button onClick={() => onSave(fields)} style={{
          padding: '6px 14px', fontSize: 13, fontWeight: 500, borderRadius: 10,
          border: 'none', background: 'var(--primary)', color: '#FDF8F3', cursor: 'pointer',
        }}>
          Save
        </button>
        <button onClick={onCancel} style={{
          padding: '6px 14px', fontSize: 13, fontWeight: 500, borderRadius: 10,
          border: '0.5px solid var(--border)', background: 'var(--bg-surface-2)',
          color: 'var(--text-secondary)', cursor: 'pointer',
        }}>
          Cancel
        </button>
      </div>
    </div>
  );
}

export function History() {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [toast, setToast] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);

  function loadEntries() {
    const now = new Date();
    const from = new Date(now);
    from.setDate(now.getDate() - 6);
    from.setHours(0, 0, 0, 0);
    getLogEntries({ from: from.toISOString() }).then(setEntries).catch(() => {});
  }

  useEffect(() => { loadEntries(); }, []);

  async function handleSave(id: number, fields: EditState) {
    try {
      await updateLogEntry(id, fields);
      setEditingId(null);
      setExpandedId(null);
      setToast('Entry updated');
      loadEntries();
    } catch {
      setToast('Failed to update');
    }
  }

  async function handleDelete(id: number) {
    try {
      await deleteLogEntry(id);
      setConfirmDeleteId(null);
      setExpandedId(null);
      setToast('Entry deleted');
      loadEntries();
    } catch {
      setToast('Failed to delete');
    }
  }

  const grouped = groupByDay(entries);

  return (
    <div style={{ padding: '16px 20px', paddingBottom: 80 }}>
      <div style={{
        fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
        textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 4,
      }}>
        {formatWeekRange()}
      </div>
      <h1 style={{ fontSize: 24, fontWeight: 500, marginBottom: 16, color: 'var(--text-primary)' }}>History</h1>

      {Object.keys(grouped).length === 0 && (
        <p style={{ color: 'var(--text-hint)', textAlign: 'center', padding: 32, fontSize: 14 }}>
          No entries this week. Start logging!
        </p>
      )}

      {Object.entries(grouped).map(([day, dayEntries]) => (
        <div key={day} style={{ marginBottom: 20 }}>
          <div style={{
            fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
            textTransform: 'uppercase', color: 'var(--text-secondary)',
            marginBottom: 8,
          }}>
            {day}
          </div>
          <div style={{
            background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
            borderRadius: 14, overflow: 'hidden',
          }}>
            {dayEntries.map((entry, i) => {
              const typeColor = entry.type === 'meal' ? 'var(--type-meal)'
                : entry.type === 'flare' ? 'var(--type-flare)'
                : 'var(--type-med)';
              const label = entry.type === 'flare' ? `Flare \u00B7 severity ${entry.severity}`
                : entry.type === 'medication' ? entry.medication_name || 'Medication'
                : 'Meal';
              const body = entry.raw_input || entry.notes || '';
              const isExpanded = expandedId === entry.id;
              const isEditing = editingId === entry.id;
              const isConfirmingDelete = confirmDeleteId === entry.id;

              return (
                <div key={entry.id} style={{
                  padding: '11px 14px',
                  borderTop: i > 0 ? '0.5px solid var(--border)' : 'none',
                  cursor: isEditing ? 'default' : 'pointer',
                }} onClick={() => {
                  if (isEditing) return;
                  setExpandedId(isExpanded ? null : entry.id);
                  setConfirmDeleteId(null);
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: 12, fontWeight: 500, color: typeColor }}>{label}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-hint)' }}>{formatTime(entry.timestamp)}</span>
                  </div>

                  {body && !isEditing && (
                    <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.4, marginTop: 2 }}>
                      {body}
                    </div>
                  )}

                  {isEditing && (
                    <EditForm
                      entry={entry}
                      onSave={(fields) => handleSave(entry.id, fields)}
                      onCancel={() => setEditingId(null)}
                    />
                  )}

                  {isExpanded && !isEditing && (
                    <div style={{ display: 'flex', gap: 8, marginTop: 8 }} onClick={e => e.stopPropagation()}>
                      <button onClick={() => { setEditingId(entry.id); }} style={{
                        padding: '5px 12px', fontSize: 12, fontWeight: 500, borderRadius: 8,
                        border: '0.5px solid var(--border)', background: 'var(--bg-surface-2)',
                        color: 'var(--text-secondary)', cursor: 'pointer',
                      }}>
                        Edit
                      </button>
                      {isConfirmingDelete ? (
                        <>
                          <button onClick={() => handleDelete(entry.id)} style={{
                            padding: '5px 12px', fontSize: 12, fontWeight: 500, borderRadius: 8,
                            border: 'none', background: 'var(--type-flare)', color: '#fff', cursor: 'pointer',
                          }}>
                            Confirm delete
                          </button>
                          <button onClick={() => setConfirmDeleteId(null)} style={{
                            padding: '5px 12px', fontSize: 12, fontWeight: 500, borderRadius: 8,
                            border: '0.5px solid var(--border)', background: 'var(--bg-surface-2)',
                            color: 'var(--text-secondary)', cursor: 'pointer',
                          }}>
                            Cancel
                          </button>
                        </>
                      ) : (
                        <button onClick={() => setConfirmDeleteId(entry.id)} style={{
                          padding: '5px 12px', fontSize: 12, fontWeight: 500, borderRadius: 8,
                          border: '0.5px solid var(--border)', background: 'var(--bg-surface-2)',
                          color: 'var(--type-flare)', cursor: 'pointer',
                        }}>
                          Delete
                        </button>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      ))}
      <Toast message={toast} visible={!!toast} onDone={() => setToast('')} />
    </div>
  );
}

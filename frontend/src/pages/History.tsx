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
  timestamp?: string;
  raw_input?: string;
  severity?: number;
  medication_name?: string;
  medication_dose?: string;
  notes?: string;
}

function toLocalDatetime(iso: string): string {
  const d = new Date(iso);
  const offset = d.getTimezoneOffset();
  const local = new Date(d.getTime() - offset * 60000);
  return local.toISOString().slice(0, 16);
}

function EditForm({ entry, onSave, onCancel }: {
  entry: LogEntry;
  onSave: (fields: EditState) => void;
  onCancel: () => void;
}) {
  const [fields, setFields] = useState<EditState>(() => {
    const base = { timestamp: toLocalDatetime(entry.timestamp) };
    if (entry.type === 'meal') return { ...base, raw_input: entry.raw_input || '', notes: entry.notes || '' };
    if (entry.type === 'flare') return { ...base, severity: entry.severity ?? 5, notes: entry.notes || '' };
    if (entry.type === 'note') return { ...base, notes: entry.notes || '' };
    return { ...base, medication_name: entry.medication_name || '', medication_dose: entry.medication_dose || '', notes: entry.notes || '' };
  });

  const labelStyle = {
    fontSize: 11, fontWeight: 500 as const, letterSpacing: '0.05em',
    textTransform: 'uppercase' as const, color: 'var(--text-secondary)',
    display: 'block', marginBottom: 4,
  };

  const inputStyle = {
    width: '100%', padding: '8px 10px', fontSize: 14,
    border: '0.5px solid var(--border)', borderRadius: 10,
    background: 'var(--bg-base)', color: 'var(--text-primary)',
    fontFamily: 'inherit', outline: 'none',
  } as const;

  function handleSave() {
    const out: EditState = { ...fields };
    // Convert local datetime back to ISO
    if (out.timestamp) {
      out.timestamp = new Date(out.timestamp).toISOString();
    }
    onSave(out);
  }

  return (
    <div style={{ marginTop: 8 }}>
      {/* Time — always shown */}
      <label style={{ ...labelStyle, marginTop: 0 }}>Time</label>
      <input
        type="datetime-local"
        value={fields.timestamp}
        onChange={e => setFields({ ...fields, timestamp: e.target.value })}
        style={{ ...inputStyle, marginBottom: 8 }}
      />

      {entry.type === 'meal' && (
        <>
          {entry.images && entry.images.length > 0 && (
            <div style={{ display: 'flex', gap: 6, marginBottom: 8, flexWrap: 'wrap' }}>
              {entry.images.map((src, j) => (
                <img
                  key={j}
                  src={src}
                  alt=""
                  style={{
                    width: 56, height: 56, objectFit: 'cover',
                    borderRadius: 8, border: '0.5px solid var(--border)',
                  }}
                />
              ))}
            </div>
          )}
          <label style={labelStyle}>What you ate</label>
          <textarea
            autoFocus
            value={fields.raw_input}
            onChange={e => setFields({ ...fields, raw_input: e.target.value })}
            rows={3}
            style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.4, marginBottom: 8 }}
          />
        </>
      )}
      {entry.type === 'flare' && (
        <>
          <label style={labelStyle}>
            Severity: {fields.severity} / 10
          </label>
          <input
            type="range" min={1} max={10} value={fields.severity}
            onChange={e => setFields({ ...fields, severity: Number(e.target.value) })}
            style={{ width: '100%', marginBottom: 8 }}
          />
        </>
      )}
      {entry.type === 'medication' && (
        <>
          <label style={labelStyle}>Medication</label>
          <input
            autoFocus
            type="text"
            value={fields.medication_name}
            onChange={e => setFields({ ...fields, medication_name: e.target.value })}
            placeholder="Medication name"
            style={{ ...inputStyle, marginBottom: 6 }}
          />
          <label style={labelStyle}>Dose</label>
          <input
            type="text"
            value={fields.medication_dose}
            onChange={e => setFields({ ...fields, medication_dose: e.target.value })}
            placeholder="Dose"
            style={{ ...inputStyle, marginBottom: 8 }}
          />
        </>
      )}

      {/* Notes — shown for all types */}
      <label style={labelStyle}>Notes</label>
      <textarea
        value={fields.notes}
        onChange={e => setFields({ ...fields, notes: e.target.value })}
        placeholder="Notes"
        rows={2}
        style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.4 }}
      />

      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <button onClick={handleSave} style={{
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
                : entry.type === 'note' ? 'var(--text-secondary)'
                : 'var(--type-med)';
              const typeIcon = entry.type === 'meal' ? '\u{1F37D}'
                : entry.type === 'flare' ? '\u{1F534}'
                : entry.type === 'note' ? '\u{1F4CB}'
                : '\u{1F48A}';
              const bodyText = entry.type === 'flare'
                ? `Severity ${entry.severity}/10`
                : entry.type === 'medication'
                ? `${entry.medication_name || 'Medication'}${entry.medication_dose ? ` ${entry.medication_dose}` : ''}`
                : entry.raw_input || entry.notes || '';
              const secondaryText = entry.type === 'flare' ? (entry.notes || '') : '';
              const isExpanded = expandedId === entry.id;
              const isEditing = editingId === entry.id;
              const isConfirmingDelete = confirmDeleteId === entry.id;

              // Parse ingredients for summary/expanded view
              let confirmed: string[] = [];
              let likely: string[] = [];
              if (entry.parsed_ingredients) {
                try {
                  const parsed = JSON.parse(entry.parsed_ingredients);
                  confirmed = parsed.confirmed || [];
                  likely = parsed.likely || [];
                } catch { /* ignore */ }
              }
              const hasIngredients = confirmed.length > 0 || likely.length > 0;

              // Collapsed: show first image thumbnail on the right
              const hasImages = entry.images && entry.images.length > 0;

              return (
                <div key={entry.id} style={{
                  padding: '13px 16px',
                  borderTop: i > 0 ? '0.5px solid var(--border)' : 'none',
                  borderLeft: `3px solid ${typeColor}`,
                  cursor: isEditing ? 'default' : 'pointer',
                  background: entry.type === 'flare' ? 'rgba(232, 96, 72, 0.08)' : undefined,
                }} onClick={() => {
                  if (isEditing) return;
                  setExpandedId(isExpanded ? null : entry.id);
                  setConfirmDeleteId(null);
                }}>
                  {/* Main row: icon + body + time/thumb */}
                  <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    {/* Type icon */}
                    <div style={{
                      width: 26, height: 26, borderRadius: 7,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 14, flexShrink: 0, marginTop: 1,
                    }}>
                      {typeIcon}
                    </div>

                    {/* Body column */}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      {bodyText && !isEditing && (
                        <div style={{
                          fontSize: 14, color: 'var(--text-primary)', lineHeight: 1.4,
                          overflow: 'hidden', textOverflow: 'ellipsis',
                          ...(isExpanded ? {} : { display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' as const }),
                        }}>
                          {bodyText}
                        </div>
                      )}
                      {secondaryText && !isEditing && (
                        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4, marginTop: 2 }}>
                          {secondaryText}
                        </div>
                      )}

                      {/* Ingredient summary (collapsed) */}
                      {hasIngredients && !isExpanded && !isEditing && (
                        <div style={{ fontSize: 11, color: 'var(--text-hint)', marginTop: 3 }}>
                          {confirmed.length > 0 && `${confirmed.length} ingredient${confirmed.length !== 1 ? 's' : ''}`}
                          {confirmed.length > 0 && likely.length > 0 && ' \u00B7 '}
                          {likely.length > 0 && `+${likely.length} likely`}
                        </div>
                      )}
                    </div>

                    {/* Right column: time + optional thumbnail */}
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', flexShrink: 0, gap: 4 }}>
                      <span style={{ fontSize: 11, color: 'var(--text-hint)', whiteSpace: 'nowrap' }}>
                        {formatTime(entry.timestamp)}
                      </span>
                      {hasImages && !isExpanded && !isEditing && (
                        <div style={{ position: 'relative' }}>
                          <img
                            src={entry.images![0]}
                            alt=""
                            style={{
                              width: 32, height: 32, objectFit: 'cover',
                              borderRadius: 6, border: '0.5px solid var(--border)',
                            }}
                          />
                          {entry.images!.length > 1 && (
                            <span style={{
                              position: 'absolute', bottom: -2, right: -2,
                              background: 'var(--bg-surface-2)', border: '0.5px solid var(--border)',
                              borderRadius: 4, fontSize: 9, padding: '0 3px',
                              color: 'var(--text-hint)',
                            }}>
                              +{entry.images!.length - 1}
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Expanded: full ingredients */}
                  {hasIngredients && isExpanded && !isEditing && (
                    <div style={{ marginTop: 8, marginLeft: 36 }}>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {confirmed.map((ing, j) => (
                          <span key={`c-${j}`} style={{
                            display: 'inline-block', padding: '2px 7px', fontSize: 11,
                            borderRadius: 6, background: 'var(--bg-surface-2)', color: 'var(--text-primary)',
                          }}>
                            {ing}
                          </span>
                        ))}
                        {likely.map((ing, j) => (
                          <span key={`l-${j}`} style={{
                            display: 'inline-block', padding: '2px 7px', fontSize: 11,
                            borderRadius: 6, color: 'var(--text-hint)',
                          }}>
                            {ing}?
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Expanded: full image gallery */}
                  {hasImages && isExpanded && !isEditing && (
                    <div style={{ display: 'flex', gap: 6, marginTop: 8, marginLeft: 36, flexWrap: 'wrap' }}>
                      {entry.images!.map((src, j) => (
                        <img
                          key={j}
                          src={src}
                          alt=""
                          style={{
                            width: 128, height: 128, objectFit: 'cover',
                            borderRadius: 10, border: '0.5px solid var(--border)',
                          }}
                        />
                      ))}
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
                    <div style={{ display: 'flex', gap: 8, marginTop: 8, marginLeft: 36 }} onClick={e => e.stopPropagation()}>
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

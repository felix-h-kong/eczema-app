import { useState, useCallback } from 'react';
import { startAnalysis, getAnalysisResult } from '../api';
import type { AnalysisResult } from '../api';

type AnalysisState =
  | { phase: 'idle' }
  | { phase: 'running'; jobId: string }
  | { phase: 'done'; result: AnalysisResult }
  | { phase: 'error'; message: string };

export function Analysis() {
  const [useLikely, setUseLikely] = useState(false);
  const [state, setState] = useState<AnalysisState>({ phase: 'idle' });

  const poll = useCallback(async (jobId: string) => {
    const MAX_ATTEMPTS = 60;
    for (let i = 0; i < MAX_ATTEMPTS; i++) {
      await new Promise(r => setTimeout(r, 2000));
      try {
        const res = await getAnalysisResult(jobId);
        if (res.status === 'done') {
          setState({ phase: 'done', result: res });
          return;
        }
        if (res.status === 'error') {
          setState({ phase: 'error', message: 'Analysis job failed on server.' });
          return;
        }
      } catch (err) {
        setState({ phase: 'error', message: err instanceof Error ? err.message : 'Polling failed' });
        return;
      }
    }
    setState({ phase: 'error', message: 'Analysis timed out after 2 minutes.' });
  }, []);

  async function handleRun() {
    setState({ phase: 'running', jobId: '' });
    try {
      const { job_id } = await startAnalysis(useLikely);
      setState({ phase: 'running', jobId: job_id });
      poll(job_id);
    } catch (err) {
      setState({ phase: 'error', message: err instanceof Error ? err.message : 'Failed to start' });
    }
  }

  const isRunning = state.phase === 'running';

  return (
    <div style={{ padding: '24px 16px 100px' }}>
      <h1 style={{ fontSize: 24, fontWeight: 600, marginBottom: 16 }}>Trigger Analysis</h1>

      <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={useLikely}
          onChange={e => setUseLikely(e.target.checked)}
          disabled={isRunning}
          style={{ width: 18, height: 18 }}
        />
        <span style={{ fontSize: 15 }}>Include likely ingredients (expand parsed lists)</span>
      </label>

      <button
        onClick={handleRun}
        disabled={isRunning}
        style={{
          width: '100%', padding: '12px 0',
          fontSize: 16, fontWeight: 600, borderRadius: 8,
          border: 'none', background: '#0ea5e9', color: '#fff',
          cursor: isRunning ? 'not-allowed' : 'pointer',
          opacity: isRunning ? 0.6 : 1,
          marginBottom: 24,
        }}
      >
        {isRunning ? 'Running analysis…' : 'Run Analysis'}
      </button>

      {isRunning && (
        <div style={{ textAlign: 'center', color: '#666', padding: 32 }}>
          <div style={{ fontSize: 32, marginBottom: 12 }}>⏳</div>
          <p>Analysing your logs…</p>
          <p style={{ fontSize: 13, marginTop: 4 }}>This may take up to a minute</p>
        </div>
      )}

      {state.phase === 'error' && (
        <div style={{
          background: '#fef2f2', border: '1px solid #fca5a5',
          borderRadius: 8, padding: 16, color: '#dc2626',
        }}>
          {state.message}
        </div>
      )}

      {state.phase === 'done' && (
        <>
          {state.result.warning && (
            <div style={{
              background: '#fffbeb', border: '1px solid #fcd34d',
              borderRadius: 8, padding: 16, marginBottom: 16, color: '#92400e',
            }}>
              <strong>Warning:</strong> {state.result.warning}
            </div>
          )}

          {state.result.summary && (
            <div style={{
              background: '#f0f9ff', border: '1px solid #bae6fd',
              borderRadius: 8, padding: 16, marginBottom: 16,
              fontSize: 15, lineHeight: 1.6,
            }}>
              <strong style={{ display: 'block', marginBottom: 8 }}>Summary</strong>
              {state.result.summary}
            </div>
          )}

          {state.result.stats.length === 0 ? (
            <p style={{ color: '#666', textAlign: 'center', padding: 32 }}>
              Not enough data yet. Keep logging meals and flares!
            </p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                <thead>
                  <tr style={{ borderBottom: '2px solid #e5e7eb' }}>
                    <th style={{ textAlign: 'left', padding: '8px 4px' }}>Ingredient</th>
                    <th style={{ textAlign: 'right', padding: '8px 4px' }}>Lift</th>
                    <th style={{ textAlign: 'right', padding: '8px 4px' }}>Flares</th>
                    <th style={{ textAlign: 'right', padding: '8px 4px' }}>Confounded</th>
                  </tr>
                </thead>
                <tbody>
                  {state.result.stats.map((row, i) => (
                    <tr key={i} style={{ borderBottom: '1px solid #f3f4f6' }}>
                      <td style={{ padding: '8px 4px', fontWeight: 500 }}>{row.ingredient}</td>
                      <td style={{
                        padding: '8px 4px', textAlign: 'right',
                        color: row.lift > 1.5 ? '#dc2626' : row.lift > 1 ? '#d97706' : '#059669',
                        fontWeight: 600,
                      }}>
                        {row.lift.toFixed(2)}x
                      </td>
                      <td style={{ padding: '8px 4px', textAlign: 'right' }}>{row.flare_appearances}</td>
                      <td style={{ padding: '8px 4px', textAlign: 'right', color: '#9ca3af' }}>
                        {row.confounded > 0 ? row.confounded : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <p style={{ marginTop: 12, fontSize: 12, color: '#9ca3af' }}>
                Lift = how much more often this ingredient appears before a flare vs. baseline.
                Higher = stronger association.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

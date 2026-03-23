import { useState, useEffect, useCallback } from 'react';
import { startAnalysis, getAnalysisResult, getLogEntries } from '../api';
import type { AnalysisResult } from '../api';

type AnalysisState =
  | { phase: 'idle' }
  | { phase: 'running'; jobId: string }
  | { phase: 'done'; result: AnalysisResult }
  | { phase: 'error'; message: string };

export function Analysis() {
  const [useLikely, setUseLikely] = useState(false);
  const [state, setState] = useState<AnalysisState>({ phase: 'idle' });
  const [flareCount, setFlareCount] = useState(0);

  useEffect(() => {
    const now = new Date();
    const from = new Date(now);
    from.setDate(now.getDate() - 30);
    getLogEntries({ type: 'flare', from: from.toISOString() })
      .then(entries => setFlareCount(entries.length))
      .catch(() => {});
  }, []);

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
  const maxLift = state.phase === 'done' && state.result.stats.length > 0
    ? Math.max(...state.result.stats.map(s => s.lift))
    : 1;

  return (
    <div style={{ padding: '16px 20px', paddingBottom: 80 }}>
      <div style={{
        fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
        textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: 4,
      }}>
        {flareCount} flare{flareCount !== 1 ? 's' : ''} in 30 days
      </div>
      <h1 style={{ fontSize: 24, fontWeight: 500, marginBottom: 16, color: 'var(--text-primary)' }}>Analyse</h1>

      {/* Toggle */}
      <label style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
        borderRadius: 14, padding: '12px 14px', marginBottom: 12,
        cursor: 'pointer',
      }}>
        <span style={{ fontSize: 14, color: 'var(--text-primary)' }}>Include likely ingredients</span>
        <input
          type="checkbox"
          checked={useLikely}
          onChange={e => setUseLikely(e.target.checked)}
          disabled={isRunning}
          style={{ width: 18, height: 18 }}
        />
      </label>

      <button
        onClick={handleRun}
        disabled={isRunning}
        style={{
          width: '100%', padding: '12px 0',
          fontSize: 15, fontWeight: 500, borderRadius: 14,
          border: 'none', background: 'var(--primary)', color: '#FDF8F3',
          cursor: isRunning ? 'not-allowed' : 'pointer',
          opacity: isRunning ? 0.6 : 1,
          marginBottom: 20,
        }}
      >
        {isRunning ? 'Running analysis\u2026' : 'Run Analysis'}
      </button>

      {isRunning && (
        <div style={{ textAlign: 'center', color: 'var(--text-hint)', padding: 32 }}>
          <p style={{ fontSize: 14 }}>Analysing your logs\u2026</p>
          <p style={{ fontSize: 12, marginTop: 4 }}>This may take up to a minute</p>
        </div>
      )}

      {state.phase === 'error' && (
        <div style={{
          background: 'var(--bg-surface-2)', border: '0.5px solid var(--border)',
          borderRadius: 14, padding: 14, color: 'var(--type-flare)', fontSize: 14,
        }}>
          {state.message}
        </div>
      )}

      {state.phase === 'done' && (
        <>
          {state.result.warning && (
            <div style={{
              background: 'var(--bg-surface-2)', border: '0.5px solid var(--border)',
              borderRadius: 14, padding: 14, marginBottom: 16,
              fontSize: 13, color: 'var(--text-secondary)',
            }}>
              {state.result.warning}
            </div>
          )}

          {/* Top suspects with horizontal lift bars */}
          {state.result.stats.length > 0 && (
            <div style={{
              background: 'var(--bg-surface)', border: '0.5px solid var(--border)',
              borderRadius: 14, padding: 14, marginBottom: 16,
            }}>
              <div style={{
                fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
                textTransform: 'uppercase', color: 'var(--text-secondary)',
                marginBottom: 10,
              }}>
                Top suspects
              </div>
              {state.result.stats.map((row, i) => (
                <div key={i} style={{ marginBottom: i < state.result.stats.length - 1 ? 10 : 0 }}>
                  <div style={{
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                    marginBottom: 4,
                  }}>
                    <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-primary)' }}>
                      {row.ingredient}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                      {row.lift.toFixed(1)}x lift
                    </span>
                  </div>
                  <div style={{
                    height: 6, borderRadius: 3,
                    background: 'var(--bg-surface-2)',
                    overflow: 'hidden',
                  }}>
                    <div style={{
                      height: '100%', borderRadius: 3,
                      background: row.lift > 1.5 ? 'var(--type-flare)' : 'var(--primary)',
                      width: `${Math.min((row.lift / maxLift) * 100, 100)}%`,
                    }} />
                  </div>
                </div>
              ))}
              <p style={{ marginTop: 10, fontSize: 11, color: 'var(--text-hint)' }}>
                Lift = how much more often an ingredient appears before a flare vs. baseline.
              </p>
            </div>
          )}

          {state.result.stats.length === 0 && (
            <p style={{ color: 'var(--text-hint)', textAlign: 'center', padding: 32, fontSize: 14 }}>
              Not enough data yet. Keep logging meals and flares!
            </p>
          )}

          {/* Claude summary */}
          {state.result.summary && (
            <div style={{
              background: 'var(--bg-surface-2)', border: '0.5px solid var(--border)',
              borderRadius: 14, padding: 14,
              fontSize: 14, lineHeight: 1.6, color: 'var(--text-primary)',
            }}>
              <div style={{
                fontSize: 11, fontWeight: 500, letterSpacing: '0.05em',
                textTransform: 'uppercase', color: 'var(--text-secondary)',
                marginBottom: 6,
              }}>
                Summary
              </div>
              {state.result.summary}
            </div>
          )}
        </>
      )}
    </div>
  );
}

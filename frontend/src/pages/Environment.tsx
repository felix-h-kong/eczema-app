import { useState, useEffect, useRef, useCallback } from 'react';
import {
  Chart as ChartJS,
  LineController,
  LineElement,
  PointElement,
  LinearScale,
  TimeScale,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import 'chartjs-adapter-date-fns';
import zoomPlugin from 'chartjs-plugin-zoom';
import annotationPlugin from 'chartjs-plugin-annotation';
import { getEnvironmentReadings } from '../api';
import { useSensorState } from '../useSensorState';
import { getDebugLog, onDebugLogChange, debugLogAppend } from '../govee-state';
import type { EnvironmentReading } from '../api';

ChartJS.register(
  LineController, LineElement, PointElement, LinearScale, TimeScale,
  Tooltip, Legend, Filler, zoomPlugin, annotationPlugin,
);

function timeAgo(isoString: string): string {
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export function Environment() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const chartRef = useRef<ChartJS | null>(null);
  const { lastReading, lastSeen, lastSyncError } = useSensorState();
  const [readings, setReadings] = useState<(EnvironmentReading & { source: string })[]>([]);
  const [loading, setLoading] = useState(true);
  const [logLines, setLogLines] = useState<string[]>(getDebugLog);
  const logEndRef = useRef<HTMLDivElement>(null);

  // Subscribe to debug log updates
  useEffect(() => {
    return onDebugLogChange((lines) => {
      setLogLines(lines);
      // Auto-scroll to bottom
      setTimeout(() => logEndRef.current?.scrollIntoView({ behavior: 'smooth' }), 50);
    });
  }, []);

  // Fetch last 24 hours of readings from backend
  useEffect(() => {
    const from = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
    getEnvironmentReadings({ from })
      .then(setReadings)
      .catch((err) => console.error('Failed to load environment readings:', err))
      .finally(() => setLoading(false));
  }, []);

  // Append new readings from live sensor state
  useEffect(() => {
    if (!lastReading) return;
    setReadings((prev) => {
      // Avoid duplicates (same timestamp)
      if (prev.length > 0 && prev[prev.length - 1].timestamp === lastReading.timestamp) {
        return prev;
      }
      return [...prev, { ...lastReading, source: 'govee_h5075' }];
    });
  }, [lastReading]);

  // Create / update chart
  const buildChart = useCallback(() => {
    if (!canvasRef.current || readings.length === 0) return;

    try {
    const timestamps = readings.map(r => new Date(r.timestamp).getTime());
    const temps = readings.map(r => r.temperature);
    const humids = readings.map(r => r.humidity);

    if (chartRef.current) {
      // Update existing chart data
      const chart = chartRef.current;
      chart.data.labels = timestamps;
      chart.data.datasets[0].data = temps;
      chart.data.datasets[1].data = humids;
      chart.update('none');
      return;
    }

    // Create new chart
    chartRef.current = new ChartJS(canvasRef.current, {
      type: 'line',
      data: {
        labels: timestamps,
        datasets: [
          {
            label: 'Temperature (°C)',
            data: temps,
            borderColor: '#E57373',
            backgroundColor: '#E5737320',
            borderWidth: 1.5,
            pointRadius: 0,
            pointHitRadius: 8,
            fill: false,
            tension: 0.3,
            yAxisID: 'yTemp',
          },
          {
            label: 'Humidity (%)',
            data: humids,
            borderColor: '#64B5F6',
            backgroundColor: '#64B5F620',
            borderWidth: 1.5,
            pointRadius: 0,
            pointHitRadius: 8,
            fill: false,
            tension: 0.3,
            yAxisID: 'yHumid',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false,
        },
        scales: {
          x: {
            type: 'time',
            time: {
              displayFormats: { hour: 'HH:mm', minute: 'HH:mm' },
              tooltipFormat: 'PPp',
            },
            ticks: {
              color: '#999',
              font: { size: 10 },
              maxRotation: 0,
            },
            grid: { display: false },
          },
          yTemp: {
            type: 'linear',
            position: 'left',
            title: { display: true, text: '°C', color: '#E57373', font: { size: 11 } },
            ticks: { color: '#E57373', font: { size: 10 } },
            grid: { color: '#ffffff15' },
          },
          yHumid: {
            type: 'linear',
            position: 'right',
            title: { display: true, text: '% RH', color: '#64B5F6', font: { size: 11 } },
            ticks: { color: '#64B5F6', font: { size: 10 } },
            grid: { display: false },
          },
        },
        plugins: {
          legend: {
            display: true,
            position: 'top',
            labels: { boxWidth: 12, font: { size: 11 }, color: '#aaa' },
          },
          tooltip: {
            backgroundColor: '#2a2a2a',
            titleColor: '#eee',
            bodyColor: '#ccc',
            borderColor: '#444',
            borderWidth: 0.5,
          },
          zoom: {
            pan: {
              enabled: true,
              mode: 'x',
            },
            zoom: {
              pinch: { enabled: true },
              wheel: { enabled: true },
              mode: 'x',
            },
          },
        },
      },
    });
    } catch (err) {
      console.error('[env] chart error:', err);
      debugLogAppend(`chart error: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [readings]);

  useEffect(() => {
    buildChart();
  }, [buildChart]);

  // Cleanup chart on unmount
  useEffect(() => {
    return () => {
      chartRef.current?.destroy();
      chartRef.current = null;
    };
  }, []);

  return (
    <div style={{ padding: '16px 16px 80px', maxWidth: 600, margin: '0 auto' }}>
      {/* Current reading hero */}
      <div style={{
        textAlign: 'center',
        padding: '20px 0 16px',
      }}>
        {lastReading ? (
          <>
            <div style={{
              fontSize: 36, fontWeight: 700,
              color: 'var(--text-primary)',
              letterSpacing: '-0.5px',
            }}>
              {lastReading.temperature.toFixed(1)}°C
            </div>
            <div style={{
              fontSize: 20, fontWeight: 500,
              color: 'var(--text-secondary)',
              marginTop: 2,
            }}>
              {lastReading.humidity.toFixed(0)}% RH
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-hint)', marginTop: 6 }}>
              Updated {timeAgo(lastReading.timestamp)}
            </div>
          </>
        ) : (
          <div style={{ fontSize: 14, color: 'var(--text-hint)', padding: '20px 0' }}>
            {loading ? 'Loading...' : 'No sensor readings yet'}
          </div>
        )}
      </div>

      {/* Chart */}
      <div style={{
        height: 260,
        background: 'var(--bg-surface)',
        borderRadius: 12,
        padding: '12px 8px 8px',
        border: '0.5px solid var(--border)',
      }}>
        {readings.length > 0 ? (
          <canvas ref={canvasRef} />
        ) : (
          <div style={{
            height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, color: 'var(--text-hint)',
          }}>
            {loading ? 'Loading chart data...' : 'No data in the last 24 hours'}
          </div>
        )}
      </div>

      {/* Sync status footer */}
      <div style={{
        marginTop: 16, textAlign: 'center',
        fontSize: 11, color: 'var(--text-hint)',
      }}>
        {lastSeen && `Last scan: ${timeAgo(lastSeen)}`}
        {lastSyncError && (
          <span style={{ color: '#E57373' }}> · {lastSyncError}</span>
        )}
      </div>

      {/* Debug log */}
      {logLines.length > 0 && (
        <div style={{
          marginTop: 16,
          background: '#1a1a1a',
          borderRadius: 8,
          padding: '8px 10px',
          maxHeight: 200,
          overflowY: 'auto',
          fontFamily: 'monospace',
          fontSize: 10,
          lineHeight: 1.6,
          color: '#aaa',
        }}>
          <div style={{ color: '#666', marginBottom: 4 }}>BLE debug log</div>
          {logLines.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
          <div ref={logEndRef} />
        </div>
      )}
    </div>
  );
}

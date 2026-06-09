import type { Manifest } from '../api';
import type { AppState } from '../state';

export function renderMetricsPanel(state: AppState): HTMLElement {
  const panel = document.createElement('section');
  panel.className = 'panel metrics-panel';
  const title = document.createElement('div');
  title.className = 'panel-title';
  title.textContent = 'Metrics';
  panel.append(title);
  if (!state.showMetrics) {
    const muted = document.createElement('p');
    muted.className = 'muted';
    muted.textContent = 'Metrics hidden.';
    panel.append(muted);
    return panel;
  }
  const manifest = state.manifest;
  const metrics = manifest?.colmap.metrics_summary ?? {};
  const rows = [
    ['selected frame count', manifest?.frames.selected_count],
    ['registered images', metrics.registered_images],
    ['sparse points', metrics.sparse_points],
    ['dense points', metrics.dense_points],
    ['reprojection error', metrics.reprojection_error_px],
    ['registered ratio', metrics.registered_ratio]
  ] as const;
  const table = document.createElement('div');
  table.className = 'metric-table';
  for (const [label, value] of rows) {
    const row = document.createElement('div');
    row.className = 'metric-row';
    row.append(text(label), strong(format(value)));
    table.append(row);
  }
  panel.append(table, renderChart(manifest));
  return panel;
}

function renderChart(manifest: Manifest | null): HTMLElement {
  const wrap = document.createElement('div');
  wrap.className = 'quality-chart';
  const data = manifest?.quality.summary.chart ?? [];
  if (!data.length) {
    wrap.textContent = 'Quality chart appears after scoring.';
    return wrap;
  }
  const canvas = document.createElement('canvas');
  canvas.width = 520;
  canvas.height = 150;
  wrap.append(canvas);
  requestAnimationFrame(() => {
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    const values = data.map((row) => row.quality_score ?? 0);
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = '#0b1118';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.strokeStyle = '#334454';
    ctx.lineWidth = 1;
    for (let y = 25; y < canvas.height; y += 32) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(canvas.width, y);
      ctx.stroke();
    }
    ctx.strokeStyle = '#63d6a5';
    ctx.lineWidth = 2;
    ctx.beginPath();
    values.forEach((value, index) => {
      const x = (index / Math.max(values.length - 1, 1)) * canvas.width;
      const y = canvas.height - 14 - ((value - min) / Math.max(max - min, 0.0001)) * (canvas.height - 28);
      if (index === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  });
  return wrap;
}

function text(value: string): HTMLElement {
  const el = document.createElement('span');
  el.textContent = value;
  return el;
}

function strong(value: string): HTMLElement {
  const el = document.createElement('strong');
  el.textContent = value;
  return el;
}

function format(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '-';
  if (Math.abs(value) < 1 && value !== 0) return value.toFixed(3);
  if (Math.abs(value) < 100) return value.toFixed(2);
  return Math.round(value).toLocaleString();
}

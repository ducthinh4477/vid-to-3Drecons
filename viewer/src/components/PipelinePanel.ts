import type { AppState } from '../state';

export function renderPipelinePanel(state: AppState): HTMLElement {
  const panel = document.createElement('section');
  panel.className = 'timeline-panel';
  const steps = state.job?.steps ?? [];
  for (const step of steps) {
    const item = document.createElement('div');
    item.className = 'timeline-step';
    item.dataset.status = step.status;
    const dot = document.createElement('span');
    dot.className = 'step-dot';
    const text = document.createElement('div');
    const label = document.createElement('strong');
    label.textContent = step.label;
    const message = document.createElement('span');
    message.textContent = step.message || step.status;
    text.append(label, message);
    item.append(dot, text);
    panel.append(item);
  }
  if (!steps.length) {
    panel.textContent = 'Pipeline is idle.';
  }
  return panel;
}

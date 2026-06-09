import type { AppState } from '../state';

export function renderVideoInputPanel(state: AppState, onChange: (patch: Partial<AppState>) => void, onStart: () => void): HTMLElement {
  const section = document.createElement('section');
  section.className = 'sidebar-section';
  const title = document.createElement('h2');
  title.className = 'sidebar-title';
  title.textContent = 'Video to Gaussian PLY';

  const preset = document.createElement('select');
  preset.className = 'field';
  preset.append(new Option('Manual path', ''));
  for (const scene of state.scenes) preset.append(new Option(scene.label, scene.video_path));
  preset.value = state.videoPath;
  preset.addEventListener('change', () => {
    const selected = state.scenes.find((item) => item.video_path === preset.value);
    onChange({ videoPath: preset.value, scene: selected?.scene || state.scene });
  });

  section.append(
    title,
    labeled('Video preset', preset),
    textField('Video path', state.videoPath, (videoPath) => onChange({ videoPath })),
    textField('Scene', state.scene, (scene) => onChange({ scene })),
    selectField('Policy', state.policy, ['no_filter', 'light_filter', 'medium_filter', 'strong_filter'], (policy) => onChange({ policy: policy as AppState['policy'] })),
    numberField('FPS', state.fps, (fps) => onChange({ fps })),
    numberField('GS iterations', state.iterations, (iterations) => onChange({ iterations: Math.max(1, Math.round(iterations)) })),
    numberField('Resolution', state.resolution, (resolution) => onChange({ resolution: Math.max(1, Math.round(resolution)) })),
    startButton(state, onStart)
  );
  return section;
}

function startButton(state: AppState, onStart: () => void): HTMLElement {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'primary-button';
  button.textContent = state.job?.status === 'running' ? 'Running...' : 'Start Demo';
  button.disabled = state.job?.status === 'running' || !state.videoPath.trim();
  button.addEventListener('click', onStart);
  return button;
}

function textField(label: string, value: string, onCommit: (value: string) => void): HTMLElement {
  const input = document.createElement('input');
  input.className = 'field';
  input.value = value;
  input.addEventListener('change', () => onCommit(input.value));
  return labeled(label, input);
}

function numberField(label: string, value: number, onCommit: (value: number) => void): HTMLElement {
  const input = document.createElement('input');
  input.className = 'field';
  input.type = 'text';
  input.inputMode = 'decimal';
  input.value = String(value);
  input.addEventListener('change', () => {
    const parsed = Number(input.value);
    if (Number.isFinite(parsed) && parsed > 0) onCommit(parsed);
    else input.value = String(value);
  });
  return labeled(label, input);
}

function selectField(label: string, value: string, options: string[], onCommit: (value: string) => void): HTMLElement {
  const select = document.createElement('select');
  select.className = 'field';
  for (const option of options) select.append(new Option(option, option));
  select.value = value;
  select.addEventListener('change', () => onCommit(select.value));
  return labeled(label, select);
}

function labeled(label: string, child: HTMLElement): HTMLElement {
  const wrap = document.createElement('label');
  wrap.className = 'field-label';
  const span = document.createElement('span');
  span.textContent = label;
  wrap.append(span, child);
  return wrap;
}

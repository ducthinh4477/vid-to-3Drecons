import type { AppState } from '../state';

export function renderVideoPanel(state: AppState, onChange: (patch: Partial<AppState>) => void, onStart: () => void): HTMLElement {
  const panel = document.createElement('section');
  panel.className = 'panel video-panel';

  const title = document.createElement('div');
  title.className = 'panel-title';
  title.textContent = 'Video input';

  const sceneSelect = document.createElement('select');
  sceneSelect.className = 'field';
  const empty = new Option('Manual path', '');
  sceneSelect.append(empty);
  for (const scene of state.scenes) {
    sceneSelect.append(new Option(scene.label, scene.video_path));
  }
  sceneSelect.value = state.videoPath;
  sceneSelect.addEventListener('change', () => {
    const selected = state.scenes.find((item) => item.video_path === sceneSelect.value);
    onChange({
      videoPath: sceneSelect.value,
      scene: selected?.scene || state.scene
    });
  });

  const pathInput = input('Video path', state.videoPath, (value) => onChange({ videoPath: value }));
  const sceneInput = input('Scene', state.scene, (value) => onChange({ scene: value }));
  const fpsInput = numberInput('FPS', state.fps, (value) => onChange({ fps: value }));
  const iterationsInput = numberInput('Iterations', state.iterations, (value) => onChange({ iterations: value }));
  const resolutionInput = numberInput('Resolution', state.resolution, (value) => onChange({ resolution: value }));

  const mode = select('Mode', state.mode, ['instant', 'cached', 'preview'], (value) => onChange({ mode: value as AppState['mode'] }));
  const policy = select(
    'Policy',
    state.policy,
    ['no_filter', 'light_filter', 'medium_filter', 'strong_filter'],
    (value) => onChange({ policy: value as AppState['policy'] })
  );

  const videoWrap = document.createElement('div');
  videoWrap.className = 'video-preview';
  if (state.manifest?.video.url) {
    const video = document.createElement('video');
    video.src = state.manifest.video.url;
    video.controls = true;
    video.muted = true;
    videoWrap.append(video);
  } else {
    videoWrap.textContent = 'No video loaded';
  }

  const start = document.createElement('button');
  start.className = 'primary-button';
  start.type = 'button';
  start.textContent = state.job?.status === 'running' ? 'Running...' : 'Start Demo';
  start.disabled = state.job?.status === 'running' || !state.videoPath.trim();
  start.addEventListener('click', onStart);

  panel.append(title, videoWrap, labeled('Scene preset', sceneSelect), pathInput, sceneInput, mode, policy, fpsInput, iterationsInput, resolutionInput, start);
  return panel;
}

function input(labelText: string, value: string, onInput: (value: string) => void): HTMLElement {
  const el = document.createElement('input');
  el.className = 'field';
  el.value = value;
  el.addEventListener('change', () => onInput(el.value));
  el.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      el.blur();
      onInput(el.value);
    }
  });
  return labeled(labelText, el);
}

function numberInput(labelText: string, value: number, onInput: (value: number) => void): HTMLElement {
  const el = document.createElement('input');
  el.className = 'field';
  el.type = 'text';
  el.inputMode = labelText === 'FPS' ? 'decimal' : 'numeric';
  el.value = String(value);
  const commit = () => {
    const parsed = Number(el.value);
    if (Number.isFinite(parsed) && parsed > 0) {
      onInput(parsed);
    } else {
      el.value = String(value);
    }
  };
  el.addEventListener('change', commit);
  el.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      el.blur();
      commit();
    }
  });
  return labeled(labelText, el);
}

function select(labelText: string, value: string, options: string[], onInput: (value: string) => void): HTMLElement {
  const el = document.createElement('select');
  el.className = 'field';
  for (const option of options) {
    el.append(new Option(option, option));
  }
  el.value = value;
  el.addEventListener('change', () => onInput(el.value));
  return labeled(labelText, el);
}

function labeled(labelText: string, child: HTMLElement): HTMLElement {
  const label = document.createElement('label');
  label.className = 'field-label';
  const span = document.createElement('span');
  span.textContent = labelText;
  label.append(span, child);
  return label;
}

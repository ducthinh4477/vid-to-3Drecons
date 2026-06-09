import type { AppState } from '../state';

export function renderFramePanel(state: AppState, onSelect: (url: string) => void): HTMLElement {
  const panel = document.createElement('section');
  panel.className = 'panel frame-panel';
  const title = document.createElement('div');
  title.className = 'panel-title';
  title.textContent = `Selected frames ${state.manifest ? `(${state.manifest.frames.selected_count})` : ''}`;
  panel.append(title);
  if (!state.showFrames) {
    const muted = document.createElement('p');
    muted.className = 'muted';
    muted.textContent = 'Frame strip hidden.';
    panel.append(muted);
    return panel;
  }
  const grid = document.createElement('div');
  grid.className = 'frame-grid';
  const thumbs = state.manifest?.frames.thumbnails ?? [];
  for (const thumb of thumbs) {
    const button = document.createElement('button');
    button.className = 'frame-thumb';
    button.type = 'button';
    const img = document.createElement('img');
    img.src = thumb.url;
    img.alt = thumb.name;
    button.title = thumb.name;
    button.addEventListener('click', () => onSelect(thumb.url));
    button.append(img);
    grid.append(button);
  }
  panel.append(grid);
  if (state.selectedFrameUrl) {
    const preview = document.createElement('div');
    preview.className = 'frame-large';
    const img = document.createElement('img');
    img.src = state.selectedFrameUrl;
    img.alt = 'Selected frame preview';
    preview.append(img);
    panel.append(preview);
  }
  if (!thumbs.length) {
    const muted = document.createElement('p');
    muted.className = 'muted';
    muted.textContent = 'Selected frames will appear after frame filtering.';
    panel.append(muted);
  }
  return panel;
}

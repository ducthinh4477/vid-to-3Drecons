import type { AppState } from '../state';

export function renderPlyLoadPanel(state: AppState, onFile: (file: File) => void, onPath: (path: string) => void): HTMLElement {
  const section = document.createElement('section');
  section.className = 'sidebar-section';
  section.append(title('PLY Viewer Test'));

  const file = document.createElement('input');
  file.type = 'file';
  file.accept = '.ply';
  file.className = 'field';
  file.addEventListener('change', () => {
    const selected = file.files?.[0];
    if (selected) onFile(selected);
  });

  const path = document.createElement('input');
  path.className = 'field';
  path.placeholder = 'outputs/demo/r2_medium_filter/point_cloud.ply';
  path.value = state.activeAsset?.path ?? '';
  const load = document.createElement('button');
  load.className = 'secondary-button';
  load.type = 'button';
  load.textContent = 'Load PLY Path';
  load.addEventListener('click', () => onPath(path.value.trim()));

  section.append(labeled('Upload .ply', file), labeled('Repo PLY path', path), load);
  return section;
}

function title(text: string): HTMLElement {
  const el = document.createElement('h2');
  el.className = 'sidebar-title';
  el.textContent = text;
  return el;
}

function labeled(label: string, child: HTMLElement): HTMLElement {
  const wrap = document.createElement('label');
  wrap.className = 'field-label';
  const span = document.createElement('span');
  span.textContent = label;
  wrap.append(span, child);
  return wrap;
}

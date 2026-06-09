import { saveViewerSettings } from '../api';
import type { AppState } from '../state';
import { resetTransform } from '../viewer/axisTransform';
import { renderPlyLoadPanel } from './PlyLoadPanel';
import { renderVideoInputPanel } from './VideoInputPanel';
import type { ViewerActions } from './ViewerPanel';

export function renderSidebar(
  state: AppState,
  actions: ViewerActions,
  onChange: (patch: Partial<AppState>) => void,
  onStart: () => void,
  onPlyFile: (file: File) => void,
  onPlyPath: (path: string) => void
): HTMLElement {
  const sidebar = document.createElement('aside');
  sidebar.className = 'sidebar';
  const brand = document.createElement('div');
  brand.className = 'sidebar-brand';
  brand.textContent = 'Vid-to-3D PLY Viewer';
  sidebar.append(
    brand,
    renderPlyLoadPanel(state, onPlyFile, onPlyPath),
    renderVideoInputPanel(state, onChange, onStart),
    renderControls(state, actions, onChange)
  );
  return sidebar;
}

function renderControls(state: AppState, actions: ViewerActions, onChange: (patch: Partial<AppState>) => void): HTMLElement {
  const section = document.createElement('section');
  section.className = 'sidebar-section';
  const title = document.createElement('h2');
  title.className = 'sidebar-title';
  title.textContent = 'View Transform';
  section.append(title);

  section.append(
    button('Reset Camera', () => actions.reset()),
    button('Auto Fit', () => actions.autoFit()),
    slider('Point Size', state.pointSize, 0.001, 0.12, 0.001, (pointSize) => {
      onChange({ pointSize });
      actions.setPointSize(pointSize);
    }),
    slider('Splat Scale', state.splatScale, 0.1, 5, 0.05, (splatScale) => {
      onChange({ splatScale });
      actions.setSplatScale(splatScale);
    }),
    slider('Move Speed', state.moveSpeed, 0.2, 12, 0.1, (moveSpeed) => {
      onChange({ moveSpeed });
      actions.setMoveSpeed(moveSpeed);
    }),
    toggle('Lock To Bounds', state.lockToBounds, (lockToBounds) => {
      onChange({ lockToBounds });
      actions.setLockToBounds(lockToBounds);
    }),
    transformButtons(state, actions, onChange),
    button('Save View Transform', async () => {
      await saveViewerSettings(state.scene, state.policy, state.transform);
      onChange({ statusMessage: 'Saved viewer_settings.json.' });
    })
  );
  return section;
}

function transformButtons(state: AppState, actions: ViewerActions, onChange: (patch: Partial<AppState>) => void): HTMLElement {
  const grid = document.createElement('div');
  grid.className = 'button-grid';
  const patchTransform = (patch: Partial<AppState['transform']>) => {
    const transform = { ...state.transform, ...patch };
    onChange({ transform });
    requestAnimationFrame(() => actions.applyTransform());
  };
  grid.append(
    button('Flip Y', () => patchTransform({ flipY: !state.transform.flipY })),
    button('Flip Z', () => patchTransform({ flipZ: !state.transform.flipZ })),
    button('Rotate X +90', () => patchTransform({ rotateX: 90 })),
    button('Rotate X -90', () => patchTransform({ rotateX: -90 })),
    button('Rotate Y 180', () => patchTransform({ rotateY: state.transform.rotateY === 180 ? 0 : 180 })),
    button('Reset Transform', () => onChange({ transform: resetTransform() }))
  );
  return grid;
}

function button(label: string, onClick: () => void): HTMLElement {
  const el = document.createElement('button');
  el.type = 'button';
  el.className = 'secondary-button';
  el.textContent = label;
  el.addEventListener('click', onClick);
  return el;
}

function slider(label: string, value: number, min: number, max: number, step: number, onInput: (value: number) => void): HTMLElement {
  const wrap = document.createElement('label');
  wrap.className = 'slider-row';
  const text = document.createElement('span');
  text.textContent = label;
  const input = document.createElement('input');
  input.type = 'range';
  input.min = String(min);
  input.max = String(max);
  input.step = String(step);
  input.value = String(value);
  const output = document.createElement('output');
  output.textContent = String(value);
  input.addEventListener('input', () => {
    const next = Number(input.value);
    output.textContent = next.toFixed(step < 0.01 ? 3 : 2);
    onInput(next);
  });
  wrap.append(text, input, output);
  return wrap;
}

function toggle(label: string, checked: boolean, onChange: (checked: boolean) => void): HTMLElement {
  const wrap = document.createElement('label');
  wrap.className = 'toggle-row';
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = checked;
  input.addEventListener('change', () => onChange(input.checked));
  const span = document.createElement('span');
  span.textContent = label;
  wrap.append(input, span);
  return wrap;
}

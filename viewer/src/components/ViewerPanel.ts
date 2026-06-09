import type { Manifest } from '../api';
import type { AppState } from '../state';
import { PointCloudViewer } from '../viewer/PointCloudViewer';
import { SplatViewer } from '../viewer/SplatViewer';

let activeViewer: PointCloudViewer | SplatViewer | null = null;
let loadedKey = '';

export function renderViewerPanel(
  state: AppState,
  onResetReady: (reset: () => void) => void,
  onToggleReferenceReady: (toggle: (visible: boolean) => void) => void
): HTMLElement {
  const panel = document.createElement('section');
  panel.className = 'viewer-panel';
  const canvasHost = document.createElement('div');
  canvasHost.className = 'viewer-canvas';
  const overlay = document.createElement('div');
  overlay.className = 'viewer-overlay';
  overlay.textContent = overlayText(state.manifest);
  panel.append(canvasHost, overlay);

  requestAnimationFrame(() => {
    const manifest = state.manifest;
    const url = manifest?.viewer.active_url;
    const type = manifest?.viewer.active_type;
    const key = `${type}:${url}`;
    if (!manifest || !url) return;
    if (key === loadedKey && activeViewer) {
      canvasHost.append(activeViewer.renderer.domElement);
      return;
    }
    loadedKey = key;
    activeViewer?.dispose();
    activeViewer = null;
    loadViewer(canvasHost, manifest, overlay).catch((error: unknown) => {
      overlay.textContent = error instanceof Error ? error.message : String(error);
    });
    onResetReady(() => activeViewer?.resetCamera());
    onToggleReferenceReady((visible: boolean) => activeViewer?.setReferenceVisible(visible));
  });
  return panel;
}

async function loadViewer(host: HTMLElement, manifest: Manifest, overlay: HTMLElement): Promise<void> {
  host.replaceChildren();
  const camera = manifest.viewer.camera;
  const url = manifest.viewer.active_url;
  if (!url) return;
  overlay.textContent = `Loading ${assetLabel(manifest)}...`;
  if (manifest.viewer.active_type === 'splat') {
    const viewer = new SplatViewer(host, camera);
    activeViewer = viewer;
    const count = await viewer.load(url);
    overlay.textContent = `${assetLabel(manifest)}${count ? ` · ${count.toLocaleString()} splats` : ''}`;
    return;
  }
  const viewer = new PointCloudViewer(host, camera);
  activeViewer = viewer;
  const count =
    manifest.viewer.active_type === 'preview_points' ? await viewer.loadPreviewPoints(url) : await viewer.loadPly(url);
  overlay.textContent = `${assetLabel(manifest)} · ${count.toLocaleString()} points`;
}

function overlayText(manifest: Manifest | null): string {
  if (!manifest) return 'Viewer waiting for a manifest.';
  const base = assetLabel(manifest);
  return manifest.message ? `${base} · ${manifest.message}` : base;
}

function assetLabel(manifest: Manifest): string {
  if (manifest.viewer.active_type === 'splat') {
    return manifest.status.has_3dgs_preview ? '3DGS preview' : '3DGS cached';
  }
  if (manifest.viewer.active_type === 'none') return 'No 3D asset';
  return 'COLMAP preview';
}

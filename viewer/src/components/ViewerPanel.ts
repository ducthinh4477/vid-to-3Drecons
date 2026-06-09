import type { PlyInfo } from '../api';
import type { AppState } from '../state';
import { inspectPlyAsset } from '../viewer/PlyAssetLoader';
import { PointCloudViewer } from '../viewer/PointCloudViewer';
import { SplatViewer } from '../viewer/SplatViewer';

type ViewerInstance = PointCloudViewer | SplatViewer;
let activeViewer: ViewerInstance | null = null;
let loadedKey = '';
let activeKind: 'point_cloud' | 'gaussian_splat' | 'unknown' = 'unknown';

export type ViewerActions = {
  reset: () => void;
  autoFit: () => void;
  applyTransform: () => void;
  setPointSize: (value: number) => void;
  setSplatScale: (value: number) => void;
  setMoveSpeed: (value: number) => void;
  setLockToBounds: (value: boolean) => void;
};

export function renderViewerPanel(state: AppState, onActions: (actions: ViewerActions) => void, onLoaded: (info: PlyInfo | null, message: string) => void): HTMLElement {
  const panel = document.createElement('section');
  panel.className = 'viewer-panel';
  const canvasHost = document.createElement('div');
  canvasHost.className = 'viewer-canvas';
  const overlay = document.createElement('div');
  overlay.className = 'viewer-overlay';
  overlay.textContent = state.activeAsset ? `Loading ${state.activeAsset.name}...` : 'Load a PLY or start the Gaussian PLY demo.';
  const help = document.createElement('div');
  help.className = 'viewer-help';
  help.textContent = 'WASD / Arrows move - Mouse drag locks look - Space up - Alt/Ctrl down - Shift slow - R reset';
  panel.append(canvasHost, overlay, help);

  requestAnimationFrame(() => {
    const asset = state.activeAsset;
    if (!asset) return;
    const key = `${asset.url}:${JSON.stringify(state.transform)}`;
    if (key === loadedKey && activeViewer) {
      canvasHost.append(activeViewer.renderer.domElement);
      activeViewer.setMoveSpeed(state.moveSpeed);
      activeViewer.setLockToBounds(state.lockToBounds);
      return;
    }
    loadedKey = key;
    activeViewer?.dispose();
    activeViewer = null;
    loadAsset(canvasHost, overlay, state).then(({ info, message }) => onLoaded(info, message)).catch((error: unknown) => {
      const message = error instanceof Error ? error.message : String(error);
      overlay.textContent = message;
      onLoaded(null, message);
    });
    onActions({
      reset: () => activeViewer?.resetCamera(),
      autoFit: () => activeViewer?.autoFit(),
      applyTransform: () => {
        if (activeViewer) activeViewer.applyTransform(state.transform);
      },
      setPointSize: (value: number) => {
        if (activeViewer instanceof PointCloudViewer) activeViewer.setPointSize(value);
      },
      setSplatScale: (value: number) => {
        if (activeViewer instanceof SplatViewer) activeViewer.setSplatScale(value);
      },
      setMoveSpeed: (value: number) => activeViewer?.setMoveSpeed(value),
      setLockToBounds: (value: boolean) => activeViewer?.setLockToBounds(value)
    });
  });
  return panel;
}

async function loadAsset(host: HTMLElement, overlay: HTMLElement, state: AppState): Promise<{ info: PlyInfo | null; message: string }> {
  const asset = state.activeAsset;
  if (!asset) return { info: null, message: 'No asset.' };
  host.replaceChildren();
  const info = await inspectPlyAsset(asset.url, asset.ply);
  const assetType = info?.asset_type ?? 'unknown';
  activeKind = assetType;
  const countText = info?.vertex_count ? info.vertex_count.toLocaleString() : 'unknown';
  overlay.textContent = `${asset.name} - ${assetType} - loading`;
  const camera = { position: [0, 1, 3] as [number, number, number], look_at: [0, 0, 0] as [number, number, number], fov: 60 };
  if (assetType === 'gaussian_splat') {
    const viewer = new SplatViewer(host, camera, state.moveSpeed, state.lockToBounds);
    activeViewer = viewer;
    const loaded = await viewer.load(asset.url, state.transform, info?.bounds ?? null, state.splatScale);
    const message = `${asset.name} - 3DGS PLY - ${(loaded ?? info?.vertex_count ?? 0).toLocaleString()} splats`;
    overlay.textContent = message;
    return { info, message };
  }
  const viewer = new PointCloudViewer(host, camera, state.moveSpeed, state.lockToBounds);
  activeViewer = viewer;
  const loaded = await viewer.loadPly(asset.url, state.transform, info?.bounds ?? null);
  viewer.setPointSize(state.pointSize);
  const message = `${asset.name} - point cloud PLY - ${loaded.toLocaleString()} points`;
  overlay.textContent = message || `${asset.name} - ${countText} points`;
  return { info, message };
}

export function currentViewerKind(): string {
  return activeKind;
}

import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';
import * as THREE from 'three';
import { FPSLockedControls, type Bounds } from './FPSLockedControls';
import './styles.css';

type ViewerScene = {
  splat?: string;
  splat_url?: string;
  preview_points_url?: string;
  bounds: Bounds & {
    center?: [number, number, number];
  };
  camera: {
    position: [number, number, number];
    look_at: [number, number, number];
    fov?: number;
    near?: number;
    far?: number;
  };
  controls?: {
    move_speed?: number;
  };
  render?: {
    splat_alpha_removal_threshold?: number;
    splat_scale?: number;
    point_cloud_mode?: boolean;
    preview_points?: boolean;
  };
  demo?: DemoInfo;
};

type DemoInfo = {
  scene?: string;
  policy?: string;
  metrics?: DemoMetrics;
  thumbnails?: string[];
  supersplat_url?: string;
  local_viewer_url?: string;
};

type DemoMetrics = {
  selected_frames?: number | null;
  registered_images?: number | null;
  sparse_points?: number | null;
  dense_points?: number | null;
  reprojection_error_px?: number | null;
  registered_ratio?: number | null;
};

type DemoManifest = {
  kind?: string;
  scene?: string;
  policy?: string;
  viewer_scene?: string;
  splat_file?: string;
  metrics_file?: string | null;
  metrics_summary?: DemoMetrics;
  thumbnails?: string[];
  supersplat_viewer?: string;
  local_viewer?: string;
};

type PreviewPoints = {
  count: number;
  positions: number[];
  colors: number[];
};

type LoadedScene = {
  scene: ViewerScene;
  sourceUrl: string;
  manifest?: DemoManifest;
};

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('Missing #app root.');

const root = document.createElement('main');
root.className = 'viewer-root';
const status = document.createElement('div');
status.className = 'status';
status.textContent = 'Loading scene...';
root.append(status);
app.append(root);

function setStatus(message: string, kind: 'info' | 'error' = 'info', hidden = false): void {
  status.textContent = message;
  status.dataset.kind = kind;
  status.dataset.hidden = String(hidden);
}

function getNumberParam(name: string): number | null {
  const value = new URLSearchParams(window.location.search).get(name);
  if (value === null || value.trim() === '') return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function getBooleanParam(name: string): boolean | null {
  const value = new URLSearchParams(window.location.search).get(name);
  if (value === null) return null;
  return ['1', 'true', 'yes', 'on'].includes(value.trim().toLowerCase());
}

function resolveUrl(path: string | undefined, baseUrl: string): string | undefined {
  if (!path) return undefined;
  return new URL(path, baseUrl).toString();
}

async function loadScene(): Promise<LoadedScene> {
  const params = new URLSearchParams(window.location.search);
  const sceneUrl = params.get('scene');
  if (!sceneUrl) {
    throw new Error('Missing scene URL.');
  }
  const response = await fetch(sceneUrl);
  if (!response.ok) {
    throw new Error(`Could not load scene JSON (${response.status}).`);
  }
  const data = await response.json() as ViewerScene | DemoManifest;
  const sourceUrl = response.url;
  if ('viewer_scene' in data && data.viewer_scene) {
    const manifest = data as DemoManifest;
    const viewerSceneUrl = resolveUrl(manifest.viewer_scene, sourceUrl);
    if (!viewerSceneUrl) throw new Error('Demo manifest does not contain a viewer scene.');
    const viewerSceneResponse = await fetch(viewerSceneUrl);
    if (!viewerSceneResponse.ok) {
      throw new Error(`Could not load viewer scene JSON (${viewerSceneResponse.status}).`);
    }
    const viewerScene = await viewerSceneResponse.json() as ViewerScene;
    viewerScene.demo = {
      scene: manifest.scene,
      policy: manifest.policy,
      metrics: manifest.metrics_summary,
      thumbnails: manifest.thumbnails,
      supersplat_url: manifest.supersplat_viewer,
      local_viewer_url: manifest.local_viewer,
      ...viewerScene.demo
    };
    return { scene: viewerScene, sourceUrl: viewerSceneResponse.url, manifest };
  }
  return { scene: data as ViewerScene, sourceUrl };
}

function resize(renderer: THREE.WebGLRenderer, camera: THREE.PerspectiveCamera): void {
  const width = window.innerWidth;
  const height = window.innerHeight;
  renderer.setSize(width, height, false);
  camera.aspect = width / Math.max(height, 1);
  camera.updateProjectionMatrix();
}

function createReferenceScene(bounds: Bounds): THREE.Scene {
  const scene = new THREE.Scene();
  const min = new THREE.Vector3(...bounds.min);
  const max = new THREE.Vector3(...bounds.max);
  const box = new THREE.Box3(min, max);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);

  const boxHelper = new THREE.Box3Helper(box, 0x9fb7c9);
  const boxMaterial = boxHelper.material as THREE.Material;
  boxMaterial.transparent = true;
  boxMaterial.opacity = 0.45;
  scene.add(boxHelper);

  const gridSize = Math.max(size.x, size.z, 1);
  const grid = new THREE.GridHelper(gridSize, 12, 0x34515f, 0x1c2a31);
  grid.position.set(center.x, min.y, center.z);
  scene.add(grid);

  const axes = new THREE.AxesHelper(Math.max(Math.min(size.x, size.y, size.z) * 0.18, 0.4));
  axes.position.copy(center);
  scene.add(axes);

  return scene;
}

async function addPreviewPoints(url: string | undefined, targetScene: THREE.Scene, bounds: Bounds): Promise<THREE.Points | null> {
  if (!url) return null;
  const response = await fetch(url);
  if (!response.ok) return null;

  const preview = (await response.json()) as PreviewPoints;
  if (!preview.positions.length || preview.positions.length !== preview.colors.length) return null;

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(preview.positions, 3));
  geometry.setAttribute('color', new THREE.Float32BufferAttribute(preview.colors, 3));

  const min = new THREE.Vector3(...bounds.min);
  const max = new THREE.Vector3(...bounds.max);
  const size = new THREE.Vector3().subVectors(max, min);
  const pointSize = Math.max(Math.min(size.x, size.y, size.z) * 0.008, 0.025);
  const material = new THREE.PointsMaterial({
    size: pointSize,
    vertexColors: true,
    transparent: true,
    opacity: 0.82,
    sizeAttenuation: true,
    depthWrite: false
  });

  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  targetScene.add(points);
  return points;
}

function makeSlider(
  labelText: string,
  value: number,
  min: number,
  max: number,
  step: number,
  onInput: (value: number) => void
): HTMLLabelElement {
  const label = document.createElement('label');
  const text = document.createElement('span');
  const output = document.createElement('output');
  const input = document.createElement('input');

  label.className = 'control-row';
  text.textContent = labelText;
  output.textContent = value.toFixed(step < 0.01 ? 4 : 2);
  input.type = 'range';
  input.min = String(min);
  input.max = String(max);
  input.step = String(step);
  input.value = String(value);
  input.addEventListener('input', () => {
    const nextValue = Number(input.value);
    output.textContent = nextValue.toFixed(step < 0.01 ? 4 : 2);
    onInput(nextValue);
  });

  label.append(text, input, output);
  return label;
}

function makeToggle(labelText: string, checked: boolean, onInput: (checked: boolean) => void): HTMLLabelElement {
  const label = document.createElement('label');
  const text = document.createElement('span');
  const input = document.createElement('input');

  label.className = 'toggle-row';
  text.textContent = labelText;
  input.type = 'checkbox';
  input.checked = checked;
  input.addEventListener('input', () => onInput(input.checked));

  label.append(text, input);
  return label;
}

function createControlPanel(): HTMLElement {
  const panel = document.createElement('aside');
  panel.className = 'control-panel';
  return panel;
}

function formatMetric(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '-';
  return digits > 0 ? value.toFixed(digits) : Math.round(value).toLocaleString();
}

function addMetric(panel: HTMLElement, label: string, value: string): void {
  const row = document.createElement('div');
  row.className = 'metric-row';
  const key = document.createElement('span');
  const val = document.createElement('strong');
  key.textContent = label;
  val.textContent = value;
  row.append(key, val);
  panel.append(row);
}

function createDemoPanel(scene: ViewerScene, sourceUrl: string): HTMLElement | null {
  const demo = scene.demo;
  if (!demo) return null;

  const panel = document.createElement('aside');
  panel.className = 'demo-panel';
  const title = document.createElement('div');
  title.className = 'demo-title';
  title.textContent = demo.scene || '3DGS Demo';
  const subtitle = document.createElement('div');
  subtitle.className = 'demo-subtitle';
  subtitle.textContent = demo.policy ? `Policy: ${demo.policy}` : 'Visual demo layer';
  panel.append(title, subtitle);

  const metrics = demo.metrics || {};
  addMetric(panel, 'Selected frames', formatMetric(metrics.selected_frames));
  addMetric(panel, 'Registered images', formatMetric(metrics.registered_images));
  addMetric(panel, 'Sparse points', formatMetric(metrics.sparse_points));
  addMetric(panel, 'Dense points', formatMetric(metrics.dense_points));
  addMetric(panel, 'Reproj. error', formatMetric(metrics.reprojection_error_px, 3));

  const actions = document.createElement('div');
  actions.className = 'demo-actions';
  const superSplatButton = document.createElement('button');
  superSplatButton.type = 'button';
  superSplatButton.textContent = 'Open SuperSplat';
  superSplatButton.addEventListener('click', () => {
    const url = resolveUrl(demo.supersplat_url, sourceUrl);
    if (url) window.open(url, '_blank', 'noopener,noreferrer');
  });

  const localButton = document.createElement('button');
  localButton.type = 'button';
  localButton.textContent = 'Open local viewer';
  localButton.addEventListener('click', () => {
    const url = resolveUrl(demo.local_viewer_url, sourceUrl);
    if (url) window.open(url, '_blank', 'noopener,noreferrer');
  });
  actions.append(superSplatButton, localButton);
  panel.append(actions);

  const controls = document.createElement('div');
  controls.className = 'demo-help';
  controls.textContent = 'WASD/arrows move, Space up, Left Alt down, Shift slow, mouse look after click.';
  panel.append(controls);
  return panel;
}

async function start(): Promise<void> {
  const loaded = await loadScene();
  const scene = loaded.scene;
  const splatUrl = resolveUrl(scene.splat_url || scene.splat, loaded.sourceUrl);
  if (!splatUrl) throw new Error('Scene JSON does not contain a splat URL.');

  const renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false });
  renderer.setClearColor(0x0b1014, 1);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  root.prepend(renderer.domElement);

  const camera = new THREE.PerspectiveCamera(
    scene.camera.fov ?? 70,
    window.innerWidth / Math.max(window.innerHeight, 1),
    scene.camera.near ?? 0.01,
    scene.camera.far ?? 500
  );
  camera.position.set(...scene.camera.position);

  const referenceScene = createReferenceScene(scene.bounds);
  const previewPoints = await addPreviewPoints(resolveUrl(scene.preview_points_url, loaded.sourceUrl), referenceScene, scene.bounds);
  const previewEnabled = getBooleanParam('preview') ?? scene.render?.preview_points ?? false;
  if (previewPoints) previewPoints.visible = previewEnabled;

  const viewer = new GaussianSplats3D.Viewer({
    selfDrivenMode: false,
    renderer,
    camera,
    rootElement: root,
    threeScene: referenceScene,
    useBuiltInControls: false,
    ignoreDevicePixelRatio: false,
    gpuAcceleratedSort: true,
    sharedMemoryForWorkers: true,
    integerBasedSort: true,
    halfPrecisionCovariancesOnGPU: true,
    dynamicScene: false,
    renderMode: GaussianSplats3D.RenderMode.Always,
    sceneRevealMode: GaussianSplats3D.SceneRevealMode.Instant,
    antialiased: false,
    sphericalHarmonicsDegree: 0,
    logLevel: GaussianSplats3D.LogLevel.Info
  });

  const alphaOverride = getNumberParam('alpha');
  const speedOverride = getNumberParam('speed');
  const sensitivityOverride = getNumberParam('sens');
  const dpiOverride = getNumberParam('dpi');
  const splatScaleOverride = getNumberParam('splatScale');
  const alphaThreshold = Math.round(
    alphaOverride ?? scene.render?.splat_alpha_removal_threshold ?? 1
  );
  const moveSpeed = speedOverride ?? scene.controls?.move_speed ?? 3.0;
  const sensitivity = sensitivityOverride ?? 0.0022;
  const dpiScale = dpiOverride ?? 1.0;
  const splatScale = splatScaleOverride ?? scene.render?.splat_scale ?? 2.5;

  const controls = new FPSLockedControls({
    camera,
    domElement: renderer.domElement,
    bounds: scene.bounds,
    moveSpeed,
    sensitivity,
    dpiScale,
    lookAt: scene.camera.look_at
  });

  resize(renderer, camera);
  window.addEventListener('resize', () => resize(renderer, camera));

  await viewer.addSplatScene(splatUrl, {
    splatAlphaRemovalThreshold: THREE.MathUtils.clamp(alphaThreshold, 0, 255),
    showLoadingUI: true,
    progressiveLoad: true
  });
  (viewer as unknown as { splatMesh?: { setSplatScale?: (scale: number) => void; setPointCloudModeEnabled?: (enabled: boolean) => void } })
    .splatMesh?.setSplatScale?.(Math.max(splatScale, 0.1));
  if (scene.render?.point_cloud_mode) {
    (viewer as unknown as { splatMesh?: { setPointCloudModeEnabled?: (enabled: boolean) => void } })
      .splatMesh?.setPointCloudModeEnabled?.(true);
  }

  const clock = new THREE.Clock();
  const splatCount = (viewer as unknown as { splatMesh?: { getSplatCount?: () => number } }).splatMesh?.getSplatCount?.();
  const splatMesh = (viewer as unknown as { splatMesh?: { setSplatScale?: (scale: number) => void } }).splatMesh;
  const panel = createControlPanel();
  panel.append(
    makeSlider('Speed', moveSpeed, 0.5, 12, 0.25, (value) => controls.setMoveSpeed(value)),
    makeSlider('Sensitivity', sensitivity, 0.0004, 0.008, 0.0001, (value) => controls.setSensitivity(value)),
    makeSlider('DPI', dpiScale, 0.25, 4, 0.05, (value) => controls.setDpiScale(value)),
    makeSlider('Splat', splatScale, 0.5, 10, 0.25, (value) => splatMesh?.setSplatScale?.(value))
  );
  if (previewPoints) {
    panel.append(makeToggle('Preview', previewEnabled, (checked) => {
      previewPoints.visible = checked;
    }));
  }
  root.append(panel);
  const demoPanel = createDemoPanel(scene, loaded.sourceUrl);
  if (demoPanel) root.append(demoPanel);

  setStatus(
    splatCount ? `Loaded ${splatCount.toLocaleString()} splats. Click the view to move.` : 'Scene loaded. Click the view to move.',
    'info',
    false
  );
  window.setTimeout(() => setStatus('', 'info', true), 4500);

  function frame(): void {
    requestAnimationFrame(frame);
    controls.update(clock.getDelta());
    viewer.update();
    viewer.render();
  }
  frame();
}

start().catch((error: unknown) => {
  const message = error instanceof Error ? error.message : String(error);
  setStatus(message, 'error');
});

import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';
import * as THREE from 'three';
import { applyAxisTransform, type AxisTransformState } from './axisTransform';
import { boundsCenter, boundsRadius, paddedBounds, type Bounds } from './bounds';
import { FPSRoomControls } from './FPSRoomControls';
import type { CameraConfig } from './PointCloudViewer';

export class SplatViewer {
  readonly renderer: THREE.WebGLRenderer;
  readonly camera: THREE.PerspectiveCamera;
  readonly scene: THREE.Scene;
  private viewer: any = null;
  private animation = 0;
  private clock = new THREE.Clock();
  private grid: THREE.GridHelper;
  private axes: THREE.AxesHelper;
  private controls: FPSRoomControls;
  private wrapper = new THREE.Group();
  private bounds: Bounds = { min: [-5, -2, -5], max: [5, 4, 5] };

  constructor(private host: HTMLElement, cameraConfig: CameraConfig, moveSpeed: number, lockToBounds: boolean) {
    this.renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(host.clientWidth || 900, host.clientHeight || 620);
    this.renderer.setClearColor(0x06080c, 1);
    host.append(this.renderer.domElement);
    this.camera = new THREE.PerspectiveCamera(cameraConfig.fov, 1, 0.01, 2000);
    this.scene = new THREE.Scene();
    this.grid = new THREE.GridHelper(20, 40, 0x3a4d5f, 0x17222c);
    this.axes = new THREE.AxesHelper(0.8);
    this.scene.add(this.grid, this.axes, this.wrapper);
    this.controls = new FPSRoomControls(this.camera, this.renderer.domElement, this.bounds, moveSpeed, lockToBounds);
    this.renderer.domElement.addEventListener('viewer-reset', () => this.resetCamera());
    window.addEventListener('resize', this.resize);
    this.resize();
  }

  async load(url: string, transform: AxisTransformState, sourceBounds?: Bounds | null, splatScale = 1): Promise<number | null> {
    this.viewer = new GaussianSplats3D.Viewer({
      selfDrivenMode: false,
      renderer: this.renderer,
      camera: this.camera,
      rootElement: this.host,
      threeScene: this.scene,
      useBuiltInControls: false,
      gpuAcceleratedSort: true,
      sharedMemoryForWorkers: true,
      integerBasedSort: true,
      halfPrecisionCovariancesOnGPU: true,
      sceneRevealMode: GaussianSplats3D.SceneRevealMode.Instant,
      renderMode: GaussianSplats3D.RenderMode.Always,
      sphericalHarmonicsDegree: 0
    });
    await this.viewer.addSplatScene(url, { showLoadingUI: true, progressiveLoad: true, splatAlphaRemovalThreshold: 1 });
    this.viewer?.splatMesh?.setSplatScale?.(splatScale);
    this.applyTransform(transform);
    this.setBounds(paddedBounds(sourceBounds ?? null, 0.2));
    this.autoFit();
    this.animate();
    return this.viewer?.splatMesh?.getSplatCount?.() ?? null;
  }

  applyTransform(transform: AxisTransformState): void {
    const mesh = this.viewer?.splatMesh as THREE.Object3D | undefined;
    if (mesh) applyAxisTransform(mesh, transform);
  }

  setSplatScale(scale: number): void {
    this.viewer?.splatMesh?.setSplatScale?.(Math.max(scale, 0.1));
  }

  setMoveSpeed(speed: number): void {
    this.controls.setMoveSpeed(speed);
  }

  setLockToBounds(lock: boolean): void {
    this.controls.setLockToBounds(lock);
  }

  resetCamera(): void {
    const center = boundsCenter(this.bounds);
    const radius = boundsRadius(this.bounds);
    this.camera.position.set(center.x + radius * 0.22, center.y + radius * 0.12, center.z + radius * 0.55);
    this.camera.near = Math.max(radius / 2000, 0.001);
    this.camera.far = radius * 24;
    this.camera.updateProjectionMatrix();
    this.controls.lookAt(center);
  }

  autoFit(): void {
    this.resetCamera();
  }

  dispose(): void {
    cancelAnimationFrame(this.animation);
    window.removeEventListener('resize', this.resize);
    this.controls.dispose();
    this.viewer?.dispose?.();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  private setBounds(bounds: Bounds): void {
    this.bounds = bounds;
    this.controls.setBounds(bounds);
    const center = boundsCenter(bounds);
    const radius = boundsRadius(bounds);
    this.grid.scale.setScalar(Math.max(radius / 10, 0.5));
    this.grid.position.set(center.x, bounds.min[1], center.z);
    this.axes.position.copy(center);
  }

  private resize = (): void => {
    const width = this.host.clientWidth || 900;
    const height = this.host.clientHeight || 620;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / Math.max(height, 1);
    this.camera.updateProjectionMatrix();
  };

  private animate = (): void => {
    this.animation = requestAnimationFrame(this.animate);
    this.controls.update(this.clock.getDelta());
    this.viewer?.update?.();
    this.viewer?.render?.();
  };
}

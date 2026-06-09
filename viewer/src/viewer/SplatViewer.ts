import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { CameraConfig } from './PointCloudViewer';

export class SplatViewer {
  readonly renderer: THREE.WebGLRenderer;
  readonly camera: THREE.PerspectiveCamera;
  readonly scene: THREE.Scene;
  readonly controls: OrbitControls;
  private viewer: any = null;
  private animation = 0;
  private grid: THREE.GridHelper;
  private axes: THREE.AxesHelper;

  constructor(private host: HTMLElement, private cameraConfig: CameraConfig) {
    this.renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(host.clientWidth || 640, host.clientHeight || 420);
    this.renderer.setClearColor(0x07090d, 1);
    host.append(this.renderer.domElement);

    this.camera = new THREE.PerspectiveCamera(cameraConfig.fov, 1, 0.01, 1000);
    this.scene = new THREE.Scene();
    this.grid = new THREE.GridHelper(4, 16, 0x385066, 0x1c2732);
    this.axes = new THREE.AxesHelper(0.8);
    this.scene.add(this.grid, this.axes);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.resetCamera();
    window.addEventListener('resize', this.resize);
    this.resize();
  }

  async load(url: string): Promise<number | null> {
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
    await this.viewer.addSplatScene(url, {
      showLoadingUI: true,
      progressiveLoad: true,
      splatAlphaRemovalThreshold: 1
    });
    this.animate();
    return this.viewer?.splatMesh?.getSplatCount?.() ?? null;
  }

  setReferenceVisible(visible: boolean): void {
    this.grid.visible = visible;
    this.axes.visible = visible;
  }

  resetCamera(): void {
    this.camera.position.set(...this.cameraConfig.position);
    this.controls.target.set(...this.cameraConfig.look_at);
    this.controls.update();
  }

  dispose(): void {
    cancelAnimationFrame(this.animation);
    window.removeEventListener('resize', this.resize);
    this.viewer?.dispose?.();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  private resize = (): void => {
    const width = this.host.clientWidth || 640;
    const height = this.host.clientHeight || 420;
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / Math.max(height, 1);
    this.camera.updateProjectionMatrix();
  };

  private animate = (): void => {
    this.animation = requestAnimationFrame(this.animate);
    this.controls.update();
    this.viewer?.update?.();
    this.viewer?.render?.();
  };
}

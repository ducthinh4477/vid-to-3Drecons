import * as THREE from 'three';
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js';
import { applyAxisTransform, type AxisTransformState } from './axisTransform';
import { boundsCenter, boundsRadius, paddedBounds, type Bounds } from './bounds';
import { FPSRoomControls } from './FPSRoomControls';

export type CameraConfig = {
  position: [number, number, number];
  look_at: [number, number, number];
  fov: number;
};

export class PointCloudViewer {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene: THREE.Scene;
  readonly camera: THREE.PerspectiveCamera;
  private controls: FPSRoomControls;
  private root = new THREE.Group();
  private points: THREE.Points | null = null;
  private grid: THREE.GridHelper;
  private axes: THREE.AxesHelper;
  private animation = 0;
  private clock = new THREE.Clock();
  private bounds: Bounds = { min: [-5, -2, -5], max: [5, 4, 5] };

  constructor(private host: HTMLElement, private cameraConfig: CameraConfig, moveSpeed: number, lockToBounds: boolean) {
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x06080c);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(host.clientWidth || 900, host.clientHeight || 620);
    host.append(this.renderer.domElement);

    this.camera = new THREE.PerspectiveCamera(cameraConfig.fov, 1, 0.01, 2000);
    this.controls = new FPSRoomControls(this.camera, this.renderer.domElement, this.bounds, moveSpeed, lockToBounds);
    this.grid = new THREE.GridHelper(20, 40, 0x3a4d5f, 0x17222c);
    this.axes = new THREE.AxesHelper(0.8);
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x1a2632, 1.4));
    this.scene.add(this.grid, this.axes, this.root);
    this.renderer.domElement.addEventListener('viewer-reset', () => this.resetCamera());
    window.addEventListener('resize', this.resize);
    this.resize();
    this.animate();
  }

  async loadPly(url: string, transform: AxisTransformState, sourceBounds?: Bounds | null): Promise<number> {
    const geometry = await new PLYLoader().loadAsync(url);
    this.ensureColors(geometry);
    const count = geometry.getAttribute('position')?.count ?? 0;
    geometry.computeBoundingBox();
    const material = new THREE.PointsMaterial({
      size: 0.025,
      vertexColors: true,
      transparent: true,
      opacity: 0.95,
      sizeAttenuation: true
    });
    this.points = new THREE.Points(geometry, material);
    this.points.frustumCulled = false;
    this.root.clear();
    this.root.add(this.points);
    this.applyTransform(transform);
    const box = sourceBounds ?? this.geometryBounds(geometry);
    this.setBounds(paddedBounds(box, 0.2));
    this.autoFit();
    return count;
  }

  applyTransform(transform: AxisTransformState): void {
    applyAxisTransform(this.root, transform);
  }

  setPointSize(size: number): void {
    const material = this.points?.material as THREE.PointsMaterial | undefined;
    if (material) material.size = Math.max(size, 0.001);
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

  private geometryBounds(geometry: THREE.BufferGeometry): Bounds | null {
    const box = geometry.boundingBox;
    if (!box) return null;
    return { min: [box.min.x, box.min.y, box.min.z], max: [box.max.x, box.max.y, box.max.z] };
  }

  private ensureColors(geometry: THREE.BufferGeometry): void {
    if (geometry.getAttribute('color')) return;
    const count = geometry.getAttribute('position')?.count ?? 0;
    const colors = new Float32Array(count * 3);
    for (let i = 0; i < count; i += 1) {
      colors[i * 3] = 0.75;
      colors[i * 3 + 1] = 0.83;
      colors[i * 3 + 2] = 0.92;
    }
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
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
    this.renderer.render(this.scene, this.camera);
  };
}

import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { PLYLoader } from 'three/examples/jsm/loaders/PLYLoader.js';

export type PreviewPoints = {
  count: number;
  positions: number[];
  colors: number[];
  bounds?: { min: [number, number, number]; max: [number, number, number] } | null;
};

export type CameraConfig = {
  position: [number, number, number];
  look_at: [number, number, number];
  fov: number;
};

export class PointCloudViewer {
  readonly renderer: THREE.WebGLRenderer;
  readonly scene: THREE.Scene;
  readonly camera: THREE.PerspectiveCamera;
  readonly controls: OrbitControls;
  private pointObject: THREE.Points | null = null;
  private grid: THREE.GridHelper;
  private axes: THREE.AxesHelper;
  private animation = 0;
  private cameraConfig: CameraConfig;

  constructor(private host: HTMLElement, cameraConfig: CameraConfig) {
    this.cameraConfig = cameraConfig;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x07090d);
    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(host.clientWidth || 640, host.clientHeight || 420);
    host.append(this.renderer.domElement);

    this.camera = new THREE.PerspectiveCamera(cameraConfig.fov, 1, 0.01, 1000);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.mouseButtons = {
      LEFT: THREE.MOUSE.ROTATE,
      MIDDLE: THREE.MOUSE.DOLLY,
      RIGHT: THREE.MOUSE.PAN
    };

    const light = new THREE.HemisphereLight(0xffffff, 0x1b2430, 1.3);
    this.scene.add(light);
    this.grid = new THREE.GridHelper(4, 16, 0x385066, 0x1c2732);
    this.axes = new THREE.AxesHelper(0.8);
    this.scene.add(this.grid, this.axes);
    this.resetCamera();
    window.addEventListener('resize', this.resize);
    this.resize();
    this.animate();
  }

  async loadPreviewPoints(url: string): Promise<number> {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`Could not load preview points (${response.status}).`);
    const preview = (await response.json()) as PreviewPoints;
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(preview.positions, 3));
    geometry.setAttribute('color', new THREE.Float32BufferAttribute(preview.colors, 3));
    this.setPoints(geometry, preview.count);
    return preview.count;
  }

  async loadPly(url: string): Promise<number> {
    const geometry = await new PLYLoader().loadAsync(url);
    if (!geometry.getAttribute('color')) {
      const count = geometry.getAttribute('position')?.count ?? 0;
      const colors = new Float32Array(count * 3);
      for (let i = 0; i < count; i += 1) {
        colors[i * 3] = 0.72;
        colors[i * 3 + 1] = 0.84;
        colors[i * 3 + 2] = 1.0;
      }
      geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    }
    const count = geometry.getAttribute('position')?.count ?? 0;
    this.setPoints(geometry, count);
    return count;
  }

  setPointSize(size: number): void {
    const material = this.pointObject?.material as THREE.PointsMaterial | undefined;
    if (material) {
      material.size = size;
      material.needsUpdate = true;
    }
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
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  private setPoints(geometry: THREE.BufferGeometry, count: number): void {
    if (this.pointObject) {
      this.scene.remove(this.pointObject);
      this.pointObject.geometry.dispose();
      (this.pointObject.material as THREE.Material).dispose();
    }
    geometry.computeBoundingBox();
    const size = this.sizeFromGeometry(geometry);
    const material = new THREE.PointsMaterial({
      size: Math.max(size * 0.004, 0.012),
      vertexColors: true,
      transparent: true,
      opacity: 0.92,
      sizeAttenuation: true
    });
    this.pointObject = new THREE.Points(geometry, material);
    this.pointObject.frustumCulled = false;
    this.scene.add(this.pointObject);
    this.frameGeometry(geometry, count);
  }

  private frameGeometry(geometry: THREE.BufferGeometry, count: number): void {
    const box = geometry.boundingBox;
    if (!box || count === 0) return;
    const center = new THREE.Vector3();
    const size = new THREE.Vector3();
    box.getCenter(center);
    box.getSize(size);
    const radius = Math.max(size.x, size.y, size.z, 1);
    this.controls.target.copy(center);
    this.camera.position.set(center.x + radius * 0.8, center.y + radius * 0.55, center.z + radius * 1.35);
    this.camera.near = Math.max(radius / 1000, 0.001);
    this.camera.far = radius * 20;
    this.camera.updateProjectionMatrix();
    this.grid.scale.setScalar(Math.max(radius, 1));
    this.grid.position.set(center.x, box.min.y, center.z);
    this.axes.position.copy(center);
    this.controls.update();
  }

  private sizeFromGeometry(geometry: THREE.BufferGeometry): number {
    const box = geometry.boundingBox;
    if (!box) return 1;
    const size = new THREE.Vector3();
    box.getSize(size);
    return Math.max(size.x, size.y, size.z, 1);
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
    this.renderer.render(this.scene, this.camera);
  };
}

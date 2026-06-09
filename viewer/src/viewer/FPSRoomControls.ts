import * as THREE from 'three';
import type { Bounds } from './bounds';

const FORWARD = new Set(['KeyW', 'ArrowUp']);
const BACKWARD = new Set(['KeyS', 'ArrowDown']);
const LEFT = new Set(['KeyA', 'ArrowLeft']);
const RIGHT = new Set(['KeyD', 'ArrowRight']);
const DOWN = new Set(['AltLeft', 'AltRight', 'ControlLeft', 'ControlRight']);

export class FPSRoomControls {
  private pressed = new Set<string>();
  private yaw = 0;
  private pitch = 0;
  private bounds: Bounds;

  constructor(
    private camera: THREE.PerspectiveCamera,
    private domElement: HTMLElement,
    bounds: Bounds,
    private moveSpeed = 3,
    private lockToBounds = true
  ) {
    this.bounds = bounds;
    this.bind();
  }

  setBounds(bounds: Bounds): void {
    this.bounds = bounds;
    this.clamp();
  }

  setMoveSpeed(speed: number): void {
    this.moveSpeed = Math.max(speed, 0.05);
  }

  setLockToBounds(lock: boolean): void {
    this.lockToBounds = lock;
  }

  lookAt(target: THREE.Vector3): void {
    const direction = target.clone().sub(this.camera.position).normalize();
    this.pitch = Math.asin(THREE.MathUtils.clamp(direction.y, -0.99, 0.99));
    this.yaw = Math.atan2(-direction.x, -direction.z);
    this.applyRotation();
  }

  update(delta: number): void {
    const local = new THREE.Vector3();
    if (this.has(FORWARD)) local.z -= 1;
    if (this.has(BACKWARD)) local.z += 1;
    if (this.has(LEFT)) local.x -= 1;
    if (this.has(RIGHT)) local.x += 1;
    if (this.pressed.has('Space')) local.y += 1;
    if (this.has(DOWN)) local.y -= 1;
    if (local.lengthSq() === 0) return;

    const speed = this.moveSpeed * (this.pressed.has('ShiftLeft') || this.pressed.has('ShiftRight') ? 0.35 : 1);
    local.normalize().multiplyScalar(speed * delta);
    const forward = new THREE.Vector3(0, 0, -1).applyQuaternion(this.camera.quaternion);
    forward.y = 0;
    forward.normalize();
    const right = new THREE.Vector3(1, 0, 0).applyQuaternion(this.camera.quaternion);
    right.y = 0;
    right.normalize();
    this.camera.position.addScaledVector(forward, -local.z);
    this.camera.position.addScaledVector(right, local.x);
    this.camera.position.y += local.y;
    this.clamp();
  }

  dispose(): void {
    document.removeEventListener('keydown', this.keyDown);
    document.removeEventListener('keyup', this.keyUp);
    document.removeEventListener('mousemove', this.mouseMove);
    this.domElement.removeEventListener('mousedown', this.mouseDown);
  }

  private bind(): void {
    document.addEventListener('keydown', this.keyDown);
    document.addEventListener('keyup', this.keyUp);
    document.addEventListener('mousemove', this.mouseMove);
    this.domElement.addEventListener('mousedown', this.mouseDown);
  }

  private has(keys: Set<string>): boolean {
    for (const key of keys) if (this.pressed.has(key)) return true;
    return false;
  }

  private applyRotation(): void {
    this.pitch = THREE.MathUtils.clamp(this.pitch, -Math.PI / 2 + 0.03, Math.PI / 2 - 0.03);
    this.camera.quaternion.setFromEuler(new THREE.Euler(this.pitch, this.yaw, 0, 'YXZ'));
  }

  private clamp(): void {
    if (!this.lockToBounds) return;
    const min = this.bounds.min;
    const max = this.bounds.max;
    this.camera.position.set(
      THREE.MathUtils.clamp(this.camera.position.x, min[0], max[0]),
      THREE.MathUtils.clamp(this.camera.position.y, min[1], max[1]),
      THREE.MathUtils.clamp(this.camera.position.z, min[2], max[2])
    );
  }

  private keyDown = (event: KeyboardEvent): void => {
    if (event.code === 'Space' || event.code.startsWith('Alt') || event.code.startsWith('Control')) event.preventDefault();
    if (event.code === 'KeyR') this.domElement.dispatchEvent(new CustomEvent('viewer-reset'));
    this.pressed.add(event.code);
  };

  private keyUp = (event: KeyboardEvent): void => {
    this.pressed.delete(event.code);
  };

  private mouseDown = (): void => {
    if (document.pointerLockElement !== this.domElement) void this.domElement.requestPointerLock();
  };

  private mouseMove = (event: MouseEvent): void => {
    if (document.pointerLockElement !== this.domElement) return;
    this.yaw -= event.movementX * 0.0022;
    this.pitch -= event.movementY * 0.0022;
    this.applyRotation();
  };
}

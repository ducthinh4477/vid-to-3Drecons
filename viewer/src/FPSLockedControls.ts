import * as THREE from 'three';

export type Bounds = {
  min: [number, number, number];
  max: [number, number, number];
};

export type FPSLockedControlsOptions = {
  camera: THREE.PerspectiveCamera;
  domElement: HTMLElement;
  bounds: Bounds;
  moveSpeed: number;
  sensitivity?: number;
  dpiScale?: number;
  lookAt?: [number, number, number];
};

const KEY_FORWARD = new Set(['KeyW', 'ArrowUp']);
const KEY_BACKWARD = new Set(['KeyS', 'ArrowDown']);
const KEY_LEFT = new Set(['KeyA', 'ArrowLeft']);
const KEY_RIGHT = new Set(['KeyD', 'ArrowRight']);
const KEY_UP = new Set(['Space']);
const KEY_DOWN = new Set(['AltLeft']);

export class FPSLockedControls {
  private readonly camera: THREE.PerspectiveCamera;
  private readonly domElement: HTMLElement;
  private readonly bounds: Bounds;
  private readonly pressed = new Set<string>();
  private readonly velocity = new THREE.Vector3();
  private readonly forward = new THREE.Vector3();
  private readonly right = new THREE.Vector3();
  private moveSpeed: number;
  private yaw = 0;
  private pitch = 0;
  private sensitivity = 0.0022;
  private dpiScale = 1.0;

  constructor(options: FPSLockedControlsOptions) {
    this.camera = options.camera;
    this.domElement = options.domElement;
    this.bounds = options.bounds;
    this.moveSpeed = options.moveSpeed;
    this.sensitivity = options.sensitivity ?? this.sensitivity;
    this.dpiScale = options.dpiScale ?? this.dpiScale;
    this.clampPosition();
    this.initializeAngles(options.lookAt);
    this.bindEvents();
    this.applyRotation();
    this.clampPosition();
  }

  update(deltaSeconds: number): void {
    this.velocity.set(0, 0, 0);

    if (this.hasAny(KEY_FORWARD)) this.velocity.z -= 1;
    if (this.hasAny(KEY_BACKWARD)) this.velocity.z += 1;
    if (this.hasAny(KEY_LEFT)) this.velocity.x -= 1;
    if (this.hasAny(KEY_RIGHT)) this.velocity.x += 1;
    if (this.hasAny(KEY_UP)) this.velocity.y += 1;
    if (this.hasAny(KEY_DOWN)) this.velocity.y -= 1;

    if (this.velocity.lengthSq() === 0) return;

    const speedMultiplier = this.pressed.has('ShiftLeft') ? 0.5 : 1.0;
    this.velocity.normalize().multiplyScalar(this.moveSpeed * speedMultiplier * deltaSeconds);
    this.forward.set(0, 0, -1).applyQuaternion(this.camera.quaternion);
    this.forward.y = 0;
    this.forward.normalize();
    this.right.set(1, 0, 0).applyQuaternion(this.camera.quaternion);
    this.right.y = 0;
    this.right.normalize();

    this.camera.position.addScaledVector(this.forward, -this.velocity.z);
    this.camera.position.addScaledVector(this.right, this.velocity.x);
    this.camera.position.y += this.velocity.y;
    this.clampPosition();
  }

  setMoveSpeed(moveSpeed: number): void {
    this.moveSpeed = Math.max(moveSpeed, 0.05);
  }

  setSensitivity(sensitivity: number): void {
    this.sensitivity = Math.max(sensitivity, 0.0001);
  }

  setDpiScale(dpiScale: number): void {
    this.dpiScale = Math.max(dpiScale, 0.1);
  }

  dispose(): void {
    document.removeEventListener('keydown', this.onKeyDown);
    document.removeEventListener('keyup', this.onKeyUp);
    document.removeEventListener('mousemove', this.onMouseMove);
    this.domElement.removeEventListener('click', this.onClick);
  }

  private bindEvents(): void {
    document.addEventListener('keydown', this.onKeyDown);
    document.addEventListener('keyup', this.onKeyUp);
    document.addEventListener('mousemove', this.onMouseMove);
    this.domElement.addEventListener('click', this.onClick);
  }

  private initializeAngles(lookAt?: [number, number, number]): void {
    if (!lookAt) return;

    const target = new THREE.Vector3(...lookAt);
    const direction = target.sub(this.camera.position).normalize();
    this.pitch = Math.asin(THREE.MathUtils.clamp(direction.y, -0.999, 0.999));
    this.yaw = Math.atan2(-direction.x, -direction.z);
  }

  private hasAny(keys: Set<string>): boolean {
    for (const key of keys) {
      if (this.pressed.has(key)) return true;
    }
    return false;
  }

  private applyRotation(): void {
    this.pitch = THREE.MathUtils.clamp(this.pitch, -Math.PI / 2 + 0.02, Math.PI / 2 - 0.02);
    this.camera.quaternion.setFromEuler(new THREE.Euler(this.pitch, this.yaw, 0, 'YXZ'));
  }

  private clampPosition(): void {
    const min = this.bounds.min;
    const max = this.bounds.max;
    this.camera.position.set(
      THREE.MathUtils.clamp(this.camera.position.x, min[0], max[0]),
      THREE.MathUtils.clamp(this.camera.position.y, min[1], max[1]),
      THREE.MathUtils.clamp(this.camera.position.z, min[2], max[2])
    );
  }

  private readonly onClick = (): void => {
    if (document.pointerLockElement !== this.domElement) {
      void this.domElement.requestPointerLock();
    }
  };

  private readonly onMouseMove = (event: MouseEvent): void => {
    if (document.pointerLockElement !== this.domElement) return;
    const effectiveSensitivity = this.sensitivity * this.dpiScale;
    this.yaw -= event.movementX * effectiveSensitivity;
    this.pitch -= event.movementY * effectiveSensitivity;
    this.applyRotation();
  };

  private readonly onKeyDown = (event: KeyboardEvent): void => {
    if (event.code === 'Space' || event.code === 'AltLeft') event.preventDefault();
    this.pressed.add(event.code);
  };

  private readonly onKeyUp = (event: KeyboardEvent): void => {
    this.pressed.delete(event.code);
  };
}

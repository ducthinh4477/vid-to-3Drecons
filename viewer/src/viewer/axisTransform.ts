import * as THREE from 'three';

export type AxisPreset =
  | 'original'
  | 'colmap_room'
  | 'colmap'
  | 'gaussian'
  | 'yUp'
  | 'zUp'
  | 'flipY'
  | 'flipZ'
  | 'rotateX90'
  | 'rotateXMinus90'
  | 'rotateY180';

export type AxisTransformState = {
  axisPreset: AxisPreset;
  flipY: boolean;
  flipZ: boolean;
  rotateX: -90 | 0 | 90;
  rotateY: 0 | 180;
};

export const defaultTransform: AxisTransformState = {
  axisPreset: 'colmap_room',
  flipY: false,
  flipZ: false,
  rotateX: -90,
  rotateY: 0
};

export function resetTransform(): AxisTransformState {
  return { ...defaultTransform };
}

export function applyAxisTransform(object: THREE.Object3D, state: AxisTransformState): void {
  object.position.set(0, 0, 0);
  object.rotation.set(0, 0, 0);
  object.scale.set(1, 1, 1);

  const matrix = new THREE.Matrix4();
  matrix.identity();
  matrix.multiply(presetMatrix(state.axisPreset));
  if (state.rotateX) matrix.multiply(new THREE.Matrix4().makeRotationX(THREE.MathUtils.degToRad(state.rotateX)));
  if (state.rotateY) matrix.multiply(new THREE.Matrix4().makeRotationY(THREE.MathUtils.degToRad(state.rotateY)));
  if (state.flipY || state.flipZ) {
    matrix.multiply(new THREE.Matrix4().makeScale(1, state.flipY ? -1 : 1, state.flipZ ? -1 : 1));
  }
  matrix.decompose(object.position, object.quaternion, object.scale);
}

export function transformBounds(bounds: { min: [number, number, number]; max: [number, number, number] } | null, state: AxisTransformState) {
  if (!bounds) return null;
  const box = new THREE.Box3(new THREE.Vector3(...bounds.min), new THREE.Vector3(...bounds.max));
  const points = [
    new THREE.Vector3(box.min.x, box.min.y, box.min.z),
    new THREE.Vector3(box.min.x, box.min.y, box.max.z),
    new THREE.Vector3(box.min.x, box.max.y, box.min.z),
    new THREE.Vector3(box.min.x, box.max.y, box.max.z),
    new THREE.Vector3(box.max.x, box.min.y, box.min.z),
    new THREE.Vector3(box.max.x, box.min.y, box.max.z),
    new THREE.Vector3(box.max.x, box.max.y, box.min.z),
    new THREE.Vector3(box.max.x, box.max.y, box.max.z)
  ];
  const temp = new THREE.Object3D();
  applyAxisTransform(temp, state);
  const matrix = temp.matrixWorld.compose(temp.position, temp.quaternion, temp.scale);
  const next = new THREE.Box3();
  for (const point of points) next.expandByPoint(point.applyMatrix4(matrix));
  return {
    min: [next.min.x, next.min.y, next.min.z] as [number, number, number],
    max: [next.max.x, next.max.y, next.max.z] as [number, number, number]
  };
}

function presetMatrix(preset: AxisPreset): THREE.Matrix4 {
  switch (preset) {
    case 'colmap_room':
    case 'rotateXMinus90':
      return new THREE.Matrix4().makeRotationX(-Math.PI / 2);
    case 'rotateX90':
      return new THREE.Matrix4().makeRotationX(Math.PI / 2);
    case 'rotateY180':
      return new THREE.Matrix4().makeRotationY(Math.PI);
    case 'flipY':
      return new THREE.Matrix4().makeScale(1, -1, 1);
    case 'flipZ':
      return new THREE.Matrix4().makeScale(1, 1, -1);
    case 'zUp':
    case 'colmap':
      return new THREE.Matrix4().identity();
    case 'gaussian':
    case 'yUp':
    case 'original':
    default:
      return new THREE.Matrix4().identity();
  }
}

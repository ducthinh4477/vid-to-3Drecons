import * as THREE from 'three';

export type Bounds = { min: [number, number, number]; max: [number, number, number] };

export function paddedBounds(bounds: Bounds | null, ratio = 0.18): Bounds {
  if (!bounds) return { min: [-5, -2, -5], max: [5, 4, 5] };
  const min = new THREE.Vector3(...bounds.min);
  const max = new THREE.Vector3(...bounds.max);
  const size = new THREE.Vector3().subVectors(max, min);
  const pad = Math.max(size.x, size.y, size.z, 1) * ratio;
  min.addScalar(-pad);
  max.addScalar(pad);
  return { min: [min.x, min.y, min.z], max: [max.x, max.y, max.z] };
}

export function boundsCenter(bounds: Bounds): THREE.Vector3 {
  return new THREE.Box3(new THREE.Vector3(...bounds.min), new THREE.Vector3(...bounds.max)).getCenter(new THREE.Vector3());
}

export function boundsRadius(bounds: Bounds): number {
  const box = new THREE.Box3(new THREE.Vector3(...bounds.min), new THREE.Vector3(...bounds.max));
  return Math.max(box.getSize(new THREE.Vector3()).length() * 0.5, 1);
}

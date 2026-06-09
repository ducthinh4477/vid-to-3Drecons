import type { JobStatus, Manifest, PlyInfo, Policy, SceneOption } from './api';
import type { AxisTransformState } from './viewer/axisTransform';

export type AppState = {
  scenes: SceneOption[];
  videoPath: string;
  scene: string;
  policy: Policy;
  fps: number;
  iterations: number;
  resolution: number;
  job: JobStatus | null;
  manifest: Manifest | null;
  activeAsset: {
    url: string;
    path?: string;
    name: string;
    kind: 'ply' | 'scene';
    ply?: PlyInfo;
  } | null;
  transform: AxisTransformState;
  pointSize: number;
  splatScale: number;
  moveSpeed: number;
  lockToBounds: boolean;
  selectedFrameUrl: string | null;
  error: string | null;
  statusMessage: string;
};

export const initialState: AppState = {
  scenes: [],
  videoPath: '',
  scene: 'scene01',
  policy: 'light_filter',
  fps: 5,
  iterations: 7000,
  resolution: 4,
  job: null,
  manifest: null,
  activeAsset: null,
  transform: {
    axisPreset: 'colmap_room',
    flipY: false,
    flipZ: false,
    rotateX: -90,
    rotateY: 0
  },
  pointSize: 0.025,
  splatScale: 1.0,
  moveSpeed: 3,
  lockToBounds: true,
  selectedFrameUrl: null,
  error: null,
  statusMessage: 'Ready.'
};

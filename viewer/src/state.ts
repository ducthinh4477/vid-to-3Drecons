import type { DemoMode, JobStatus, Manifest, Policy, SceneOption } from './api';

export type AppState = {
  scenes: SceneOption[];
  videoPath: string;
  scene: string;
  policy: Policy;
  mode: DemoMode;
  fps: number;
  quality: string;
  iterations: number;
  resolution: number;
  job: JobStatus | null;
  manifest: Manifest | null;
  selectedFrameUrl: string | null;
  error: string | null;
  showFrames: boolean;
  showMetrics: boolean;
  showPointCloud: boolean;
  showSplat: boolean;
};

export const initialState: AppState = {
  scenes: [],
  videoPath: '',
  scene: 'scene01',
  policy: 'light_filter',
  mode: 'instant',
  fps: 5,
  quality: 'medium',
  iterations: 1500,
  resolution: 4,
  job: null,
  manifest: null,
  selectedFrameUrl: null,
  error: null,
  showFrames: true,
  showMetrics: true,
  showPointCloud: true,
  showSplat: true
};

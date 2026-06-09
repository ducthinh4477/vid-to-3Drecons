export type DemoMode = 'instant' | 'cached' | 'preview';
export type Policy = 'no_filter' | 'light_filter' | 'medium_filter' | 'strong_filter';
export type StepStatus = 'idle' | 'running' | 'done' | 'error' | 'skipped' | 'available' | 'missing';

export type DemoStep = {
  name: string;
  label: string;
  status: StepStatus;
  message: string;
};

export type JobStatus = {
  job_id: string;
  status: 'queued' | 'running' | 'done' | 'error';
  current_step: string;
  steps: DemoStep[];
  logs: string[];
  artifact_manifest: string | null;
  error: string | null;
};

export type SceneOption = {
  scene: string;
  video_path: string;
  label: string;
};

export type Manifest = {
  version: number;
  scene: string;
  policy: Policy;
  mode: DemoMode;
  created_at: string;
  technical_note: string;
  message?: string | null;
  video: { path: string; url: string | null };
  frames: {
    raw_dir: string;
    selected_dir: string;
    selected_count: number;
    thumbnails: Array<{ path: string; url: string; name: string }>;
  };
  quality: {
    csv: string | null;
    url: string | null;
    summary: {
      frame_count?: number;
      quality_score_mean?: number | null;
      quality_score_min?: number | null;
      quality_score_max?: number | null;
      sharpness_mean?: number | null;
      keypoints_orb_mean?: number | null;
      chart?: Array<{ frame?: string; quality_score?: number | null; sharpness?: number | null; keypoints_orb?: number | null }>;
    };
  };
  colmap: {
    workspace: string;
    metrics_json: string | null;
    metrics_summary: {
      registered_images?: number | null;
      sparse_points?: number | null;
      dense_points?: number | null;
      reprojection_error_px?: number | null;
      registered_ratio?: number | null;
    };
    preview_ply: string | null;
    preview_points_json: string | null;
    preview_ply_url: string | null;
    preview_points_url: string | null;
  };
  viewer: {
    active_type: 'splat' | 'pointcloud' | 'preview_points' | 'none';
    active_asset: string | null;
    active_url: string | null;
    fallback_asset: string | null;
    fallback_url: string | null;
    camera: { position: [number, number, number]; look_at: [number, number, number]; fov: number };
    bounds: { min: [number, number, number]; max: [number, number, number] };
  };
  status: {
    has_colmap_preview: boolean;
    has_3dgs_cached: boolean;
    has_3dgs_preview: boolean;
  };
};

export type StartRequest = {
  video_path: string;
  scene: string;
  policy: Policy;
  mode: DemoMode;
  fps: number;
  quality: string;
  iterations: number;
  resolution: number;
};

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};
  if (!response.ok) {
    throw new Error(payload.detail || payload.error || `Request failed: ${response.status}`);
  }
  return payload as T;
}

export async function getScenes(): Promise<{ videos: SceneOption[]; demos: Array<{ scene: string; policy: string; manifest: string }> }> {
  return requestJson('/api/scenes');
}

export async function startDemo(body: StartRequest): Promise<{ job_id: string; status: string }> {
  return requestJson('/api/demo/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}

export async function getJob(jobId: string): Promise<JobStatus> {
  return requestJson(`/api/demo/status/${jobId}`);
}

export async function getManifest(url: string): Promise<Manifest> {
  return requestJson(url);
}

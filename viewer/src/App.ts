import { getJob, getManifest, getPlyInfo, getScenes, startDemo, uploadPly, type JobStatus, type PlyInfo } from './api';
import { renderSidebar } from './components/Sidebar';
import { renderViewerPanel, type ViewerActions } from './components/ViewerPanel';
import { initialState, type AppState } from './state';

const noopActions: ViewerActions = {
  reset: () => undefined,
  autoFit: () => undefined,
  applyTransform: () => undefined,
  setPointSize: () => undefined,
  setSplatScale: () => undefined,
  setMoveSpeed: () => undefined,
  setLockToBounds: () => undefined
};

export class App {
  private state: AppState = { ...initialState };
  private actions: ViewerActions = noopActions;

  constructor(private root: HTMLElement) {}

  async start(): Promise<void> {
    this.render();
    try {
      const scenes = await getScenes();
      const first = scenes.videos[0];
      this.patch({
        scenes: scenes.videos,
        videoPath: first?.video_path ?? this.state.videoPath,
        scene: first?.scene ?? this.state.scene
      });
    } catch (error) {
      this.patch({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private patch(patch: Partial<AppState>): void {
    this.state = { ...this.state, ...patch };
    this.render();
  }

  private async loadPlyFile(file: File): Promise<void> {
    this.patch({ error: null, statusMessage: `Uploading ${file.name}...` });
    try {
      const uploaded = await uploadPly(file);
      this.patch({
        activeAsset: { url: uploaded.asset_url, path: uploaded.path, name: uploaded.name, kind: 'ply', ply: uploaded.ply },
        statusMessage: `Loaded upload: ${uploaded.name}`
      });
    } catch (error) {
      this.patch({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async loadPlyPath(path: string): Promise<void> {
    if (!path) return;
    this.patch({ error: null, statusMessage: `Inspecting ${path}...` });
    try {
      const info = await getPlyInfo(path);
      this.patch({
        activeAsset: { url: info.url, path: info.path, name: info.name, kind: 'ply', ply: info },
        statusMessage: `Loaded path: ${info.name}`
      });
    } catch (error) {
      this.patch({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async startVideoDemo(): Promise<void> {
    this.patch({ error: null, job: null, manifest: null, statusMessage: 'Starting video -> selected frames -> Gaussian PLY demo...' });
    try {
      const started = await startDemo({
        video_path: this.state.videoPath,
        scene: this.state.scene,
        policy: this.state.policy,
        fps: this.state.fps,
        iterations: this.state.iterations,
        resolution: this.state.resolution
      });
      await this.watchJob(started.job_id);
    } catch (error) {
      this.patch({ error: error instanceof Error ? error.message : String(error) });
    }
  }

  private async watchJob(jobId: string): Promise<void> {
    const source = new EventSource(`/api/demo/events/${jobId}`);
    source.onmessage = (event: MessageEvent<string>) => {
      const job = JSON.parse(event.data) as JobStatus;
      void this.handleJob(job);
      if (job.status === 'done' || job.status === 'error') source.close();
    };
    source.onerror = () => {
      source.close();
      getJob(jobId).then((job) => this.handleJob(job)).catch((error: unknown) => {
        this.patch({ error: error instanceof Error ? error.message : String(error) });
      });
    };
  }

  private async handleJob(job: JobStatus): Promise<void> {
    this.patch({ job, statusMessage: this.shortJobMessage(job) });
    if (!job.artifact_manifest) return;
    const manifest = await getManifest(job.artifact_manifest);
    const url = manifest.viewer.active_url ?? manifest.viewer.fallback_url;
    const path = manifest.viewer.active_asset ?? manifest.viewer.fallback_asset ?? undefined;
    if (url) {
      let info: PlyInfo | undefined;
      if (path?.endsWith('.ply')) {
        try {
          info = await getPlyInfo(path);
        } catch {
          info = undefined;
        }
      }
      this.patch({
        manifest,
        activeAsset: { url, path, name: path?.split('/').pop() ?? 'pipeline-output.ply', kind: 'ply', ply: info },
        statusMessage: manifest.message || 'Pipeline finished. Loaded Gaussian PLY in viewer.'
      });
    }
  }

  private shortJobMessage(job: JobStatus): string {
    const last = [...job.steps].reverse().find((step) => step.status === 'running' || step.status === 'done' || step.status === 'missing' || step.status === 'available');
    return last ? `${job.status}: ${last.message || last.label}` : `Job ${job.job_id}: ${job.status}`;
  }

  private render(): void {
    this.root.replaceChildren();
    const shell = document.createElement('main');
    shell.className = 'demo-shell';
    shell.append(
      renderSidebar(
        this.state,
        this.actions,
        (patch) => this.patch(patch),
        () => void this.startVideoDemo(),
        (file) => void this.loadPlyFile(file),
        (path) => void this.loadPlyPath(path)
      ),
      renderViewerPanel(
        this.state,
        (actions) => {
          this.actions = actions;
        },
        (_info, message) => {
          this.state.statusMessage = message;
          this.renderStatusOnly();
        }
      ),
      this.statusBar()
    );
    this.root.append(shell);
  }

  private renderStatusOnly(): void {
    const status = this.root.querySelector('.status-bar');
    if (status) status.textContent = this.state.error || this.state.statusMessage;
  }

  private statusBar(): HTMLElement {
    const bar = document.createElement('div');
    bar.className = 'status-bar';
    if (this.state.error) bar.dataset.kind = 'error';
    bar.textContent = this.state.error || this.state.statusMessage;
    return bar;
  }
}

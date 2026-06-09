import { getJob, getManifest, getScenes, startDemo, type JobStatus } from '../api';
import { initialState, type AppState } from '../state';
import { renderFramePanel } from './FramePanel';
import { renderMetricsPanel } from './MetricsPanel';
import { renderPipelinePanel } from './PipelinePanel';
import { renderVideoPanel } from './VideoPanel';
import { renderViewerPanel } from './ViewerPanel';

export class App {
  private state: AppState = { ...initialState };
  private root: HTMLElement;
  private resetViewer: () => void = () => undefined;
  private toggleReference: (visible: boolean) => void = () => undefined;

  constructor(root: HTMLElement) {
    this.root = root;
  }

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

  private async startDemo(): Promise<void> {
    this.patch({ error: null, manifest: null, job: null });
    try {
      const started = await startDemo({
        video_path: this.state.videoPath,
        scene: this.state.scene,
        policy: this.state.policy,
        mode: this.state.mode,
        fps: this.state.fps,
        quality: this.state.quality,
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
    source.onmessage = async (event: MessageEvent<string>) => {
      const job = JSON.parse(event.data) as JobStatus;
      this.patch({ job });
      if (job.artifact_manifest) {
        try {
          const manifest = await getManifest(job.artifact_manifest);
          this.patch({ manifest, selectedFrameUrl: manifest.frames.thumbnails[0]?.url ?? null });
        } catch {
          // The manifest may appear at the same instant as the status update; polling below catches it.
        }
      }
      if (job.status === 'done' || job.status === 'error') source.close();
    };
    source.onerror = async () => {
      source.close();
      const job = await getJob(jobId);
      this.patch({ job });
      if (job.artifact_manifest) {
        const manifest = await getManifest(job.artifact_manifest);
        this.patch({ manifest, selectedFrameUrl: manifest.frames.thumbnails[0]?.url ?? null });
      }
    };
  }

  private render(): void {
    this.root.replaceChildren();
    const shell = document.createElement('main');
    shell.className = 'app-shell';
    shell.append(this.header(), this.body(), renderPipelinePanel(this.state));
    this.root.append(shell);
  }

  private header(): HTMLElement {
    const header = document.createElement('header');
    header.className = 'app-header';
    const title = document.createElement('div');
    title.className = 'brand';
    title.textContent = 'Vid-to-3D Reconstruction Demo';
    const note = document.createElement('div');
    note.className = 'technical-note';
    note.textContent = this.state.manifest?.technical_note ?? 'COLMAP SIFT baseline with optional cached 3DGS viewer.';
    header.append(title, note, this.toolbar());
    return header;
  }

  private toolbar(): HTMLElement {
    const bar = document.createElement('div');
    bar.className = 'toolbar';
    bar.append(
      button('Load COLMAP Preview', () => undefined, true),
      button('Load 3DGS Cached', () => undefined, !this.state.manifest?.status.has_3dgs_cached),
      button('Reset Camera', () => this.resetViewer()),
      toggle('Frames', this.state.showFrames, (checked) => this.patch({ showFrames: checked })),
      toggle('Metrics', this.state.showMetrics, (checked) => this.patch({ showMetrics: checked })),
      toggle('Grid', true, (checked) => this.toggleReference(checked))
    );
    return bar;
  }

  private body(): HTMLElement {
    const body = document.createElement('div');
    body.className = 'app-body';
    const left = document.createElement('div');
    left.className = 'left-column';
    left.append(
      renderVideoPanel(this.state, (patch) => this.patch(patch), () => void this.startDemo()),
      renderFramePanel(this.state, (url) => this.patch({ selectedFrameUrl: url })),
      renderMetricsPanel(this.state)
    );
    const right = document.createElement('div');
    right.className = 'right-column';
    right.append(
      renderViewerPanel(
        this.state,
        (reset) => {
          this.resetViewer = reset;
        },
        (toggleRef) => {
          this.toggleReference = toggleRef;
        }
      ),
      this.statusStrip()
    );
    body.append(left, right);
    return body;
  }

  private statusStrip(): HTMLElement {
    const strip = document.createElement('section');
    strip.className = 'status-strip';
    if (this.state.error) {
      strip.dataset.kind = 'error';
      strip.textContent = this.state.error;
      return strip;
    }
    const message = this.state.manifest?.message;
    if (message) {
      strip.textContent = message;
      return strip;
    }
    strip.textContent = this.state.job ? `Job ${this.state.job.job_id}: ${this.state.job.status}` : 'Ready.';
    return strip;
  }
}

function button(label: string, onClick: () => void, disabled = false): HTMLElement {
  const el = document.createElement('button');
  el.className = 'tool-button';
  el.type = 'button';
  el.textContent = label;
  el.disabled = disabled;
  el.addEventListener('click', onClick);
  return el;
}

function toggle(label: string, checked: boolean, onChange: (checked: boolean) => void): HTMLElement {
  const wrap = document.createElement('label');
  wrap.className = 'toggle-chip';
  const input = document.createElement('input');
  input.type = 'checkbox';
  input.checked = checked;
  input.addEventListener('change', () => onChange(input.checked));
  const text = document.createElement('span');
  text.textContent = label;
  wrap.append(input, text);
  return wrap;
}

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
import warnings
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

warnings.filterwarnings("ignore", message="'cgi' is deprecated.*", category=DeprecationWarning)
import cgi


ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = ROOT / "data" / "demo_uploads"
OUTPUT_DIR = ROOT / "outputs" / "3dgs" / "demo_uploads"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
PLY_EXTENSIONS = {".ply"}
PIPELINE_MODULES = ["cv2", "numpy", "pandas", "yaml", "plyfile"]
PYTHON_COMMAND: list[str] = [sys.executable]


@dataclass
class DemoJob:
    id: str
    kind: str
    status: str = "queued"
    logs: list[str] = field(default_factory=list)
    scene_json: str | None = None
    viewer_url: str | None = None
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None

    def log(self, message: str) -> None:
        self.logs.append(message.rstrip())
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]


jobs: dict[str, DemoJob] = {}
jobs_lock = threading.Lock()
viewer_processes: list[subprocess.Popen[str]] = []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch a drag-and-drop local demo app.")
    parser.add_argument("--host", default="127.0.0.1", help="Local host.")
    parser.add_argument("--port", default=7860, type=int, help="Preferred demo app port.")
    parser.add_argument("--python", type=Path, help="Python executable for the pipeline scripts.")
    parser.add_argument("--no-open", action="store_true", help="Do not open browser automatically.")
    return parser.parse_args()


def find_free_port(host: str, preferred_port: int) -> int:
    for port in range(preferred_port, preferred_port + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"Could not find a free port near {preferred_port}.")


def slugify(text: str) -> str:
    keep = []
    for char in text.lower():
        if char.isalnum():
            keep.append(char)
        elif char in {"-", "_", " "}:
            keep.append("_")
    slug = "".join(keep).strip("_")
    return slug or "demo_scene"


def dedupe_commands(commands: list[list[str]]) -> list[list[str]]:
    seen = set()
    unique = []
    for command in commands:
        key = tuple(command)
        if key in seen:
            continue
        seen.add(key)
        unique.append(command)
    return unique


def candidate_python_commands(explicit_python: Path | None) -> list[list[str]]:
    commands: list[list[str]] = []
    if explicit_python is not None:
        commands.append([str(explicit_python)])

    local_venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    if local_venv_python.exists():
        commands.append([str(local_venv_python)])

    conda_roots = [
        Path("C:/ProgramData/anaconda3"),
        Path("C:/ProgramData/miniconda3"),
        Path("C:/Anaconda3"),
        Path("C:/Miniconda3"),
        Path.home() / "anaconda3",
        Path.home() / "miniconda3",
    ]
    for env_name in ["gs", "gaussian_splatting"]:
        for conda_root in conda_roots:
            conda_python = conda_root / "envs" / env_name / "python.exe"
            if conda_python.exists():
                commands.append([str(conda_python)])

    commands.append([sys.executable])

    python_on_path = shutil.which("python")
    if python_on_path:
        commands.append([python_on_path])

    py_launcher = shutil.which("py")
    if py_launcher:
        commands.extend(
            [
                [py_launcher, "-3.12"],
                [py_launcher, "-3.11"],
                [py_launcher, "-3.10"],
            ]
        )

    return dedupe_commands(commands)


def check_python_command(command: list[str]) -> tuple[bool, str]:
    module_imports = "; ".join(f"import {name}" for name in PIPELINE_MODULES)
    code = "import sys; " + module_imports + "; print(sys.executable)"
    try:
        result = subprocess.run(
            command + ["-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)

    if result.returncode != 0:
        output = (result.stderr or result.stdout).strip()
        return False, output.splitlines()[-1] if output else "module check failed"

    executable = result.stdout.strip().splitlines()[-1]
    return True, executable


def select_pipeline_python(explicit_python: Path | None) -> tuple[list[str] | None, list[str]]:
    attempts = []
    for command in candidate_python_commands(explicit_python):
        ok, message = check_python_command(command)
        attempts.append(f"{subprocess.list2cmdline(command)} -> {'OK' if ok else 'FAIL'}: {message}")
        if ok:
            return command, attempts
    return None, attempts


def json_response(handler: BaseHTTPRequestHandler, payload: dict, status: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def read_upload(handler: BaseHTTPRequestHandler) -> tuple[Path, dict[str, str]]:
    content_type = handler.headers.get("Content-Type", "")
    if "multipart/form-data" not in content_type:
        raise ValueError("Expected multipart/form-data upload.")

    form = cgi.FieldStorage(
        fp=handler.rfile,
        headers=handler.headers,
        environ={
            "REQUEST_METHOD": "POST",
            "CONTENT_TYPE": content_type,
        },
    )
    file_item = form["file"] if "file" in form else None
    if file_item is None or not getattr(file_item, "filename", ""):
        raise ValueError("Upload field `file` is required.")

    original_name = Path(file_item.filename).name
    suffix = Path(original_name).suffix.lower()
    if suffix not in VIDEO_EXTENSIONS | PLY_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")

    upload_id = uuid.uuid4().hex[:8]
    upload_folder = UPLOAD_DIR / upload_id
    upload_folder.mkdir(parents=True, exist_ok=True)
    upload_path = upload_folder / original_name
    with upload_path.open("wb") as f:
        shutil.copyfileobj(file_item.file, f)

    fields: dict[str, str] = {}
    for key in ["scene", "policy", "fps", "iterations", "resolution", "auto_open_viewer"]:
        if key in form and getattr(form[key], "value", None) is not None:
            fields[key] = str(form[key].value)
    return upload_path, fields


def run_process(command: list[str], job: DemoJob) -> int:
    job.log("")
    job.log("Running:")
    job.log(subprocess.list2cmdline(command))
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        job.log(line)
    return process.wait()


def start_viewer(scene_json: Path, job: DemoJob) -> None:
    job.status = "viewer_starting"
    command = [
        *PYTHON_COMMAND,
        str(ROOT / "scripts" / "14_launch_3dgs_viewer.py"),
        "--scene-json",
        str(scene_json),
        "--install-viewer-deps",
    ]
    job.log("")
    job.log("Opening FPS viewer:")
    job.log(subprocess.list2cmdline(command))
    process = subprocess.Popen(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    viewer_processes.append(process)

    def read_viewer_output() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            text = line.rstrip()
            job.log(text)
            if text.startswith("Viewer URL:"):
                job.viewer_url = text.split(":", maxsplit=1)[1].strip()
                job.status = "viewer_ready"
        return_code = process.wait()
        if return_code != 0 and job.viewer_url is None:
            job.status = "failed"
            job.error = f"Viewer failed with exit code {return_code}."
            job.log(job.error)

    threading.Thread(target=read_viewer_output, daemon=True).start()


def run_video_job(job: DemoJob, upload_path: Path, fields: dict[str, str]) -> None:
    scene = slugify(fields.get("scene") or upload_path.stem)
    policy = fields.get("policy") or "light_filter"
    fps = fields.get("fps") or "5"
    iterations = fields.get("iterations") or "7000"
    resolution = fields.get("resolution") or "2"

    command = [
        *PYTHON_COMMAND,
        str(ROOT / "scripts" / "15_demo_video_to_3dgs.py"),
        "--video",
        str(upload_path),
        "--scene",
        scene,
        "--policy",
        policy,
        "--fps",
        fps,
        "--iterations",
        iterations,
        "--resolution",
        resolution,
    ]
    code = run_process(command, job)
    short_policy = policy.removesuffix("_filter") if policy.endswith("_filter") else policy
    scene_json = ROOT / "outputs" / "3dgs" / f"{scene}_{short_policy}" / "viewer_scene.json"
    if code != 0:
        raise RuntimeError(f"Video pipeline failed with exit code {code}.")
    if not scene_json.exists():
        raise RuntimeError(f"Pipeline finished but viewer scene was not found: {scene_json}")
    job.scene_json = str(scene_json)
    start_viewer(scene_json, job)


def run_ply_job(job: DemoJob, upload_path: Path, fields: dict[str, str]) -> None:
    scene = slugify(fields.get("scene") or upload_path.stem)
    out_dir = OUTPUT_DIR / f"{scene}_{uuid.uuid4().hex[:8]}"
    cleaned_ply = out_dir / "point_cloud.cleaned.ply"
    scene_json = out_dir / "viewer_scene.json"
    command = [
        *PYTHON_COMMAND,
        str(ROOT / "scripts" / "13_clean_3dgs_ply.py"),
        "--input",
        str(upload_path),
        "--out",
        str(cleaned_ply),
        "--scene-json",
        str(scene_json),
    ]
    code = run_process(command, job)
    if code != 0:
        raise RuntimeError(f"PLY cleaning failed with exit code {code}.")
    job.scene_json = str(scene_json)
    start_viewer(scene_json, job)


def run_job(job_id: str, upload_path: Path, fields: dict[str, str]) -> None:
    with jobs_lock:
        job = jobs[job_id]
        job.status = "running"
    try:
        suffix = upload_path.suffix.lower()
        if suffix in VIDEO_EXTENSIONS:
            run_video_job(job, upload_path, fields)
        elif suffix in PLY_EXTENSIONS:
            run_ply_job(job, upload_path, fields)
        else:
            raise RuntimeError(f"Unsupported file type: {suffix}")
        job.log("Viewer process started. If dependencies are ready, the browser will open automatically.")
    except Exception as exc:
        job.status = "failed"
        job.error = str(exc)
        job.log(f"Error: {exc}")
    finally:
        job.finished_at = time.time()


HTML = r"""<!doctype html>
<html lang="vi">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Video to 3DGS Demo</title>
    <style>
      * { box-sizing: border-box; }
      body {
        margin: 0;
        min-height: 100vh;
        background: #101214;
        color: #f5f7fb;
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }
      main {
        min-height: 100vh;
        display: grid;
        grid-template-columns: minmax(320px, 420px) 1fr;
      }
      .panel {
        padding: 24px;
        border-right: 1px solid #2c3137;
        background: #171a1f;
      }
      h1 {
        margin: 0 0 18px;
        font-size: 24px;
        font-weight: 720;
      }
      label {
        display: block;
        margin: 14px 0 6px;
        color: #c8d0dc;
        font-size: 13px;
      }
      input, select {
        width: 100%;
        height: 38px;
        border: 1px solid #3b424c;
        border-radius: 6px;
        background: #0f1115;
        color: #f5f7fb;
        padding: 0 10px;
        font-size: 14px;
      }
      .dropzone {
        display: grid;
        place-items: center;
        min-height: 170px;
        margin: 10px 0 16px;
        border: 2px dashed #56606d;
        border-radius: 8px;
        background: #11151a;
        text-align: center;
        cursor: pointer;
      }
      .dropzone[data-active="true"] {
        border-color: #48b3ff;
        background: #112333;
      }
      .dropzone strong {
        display: block;
        margin-bottom: 6px;
        font-size: 16px;
      }
      .dropzone span {
        color: #aab4c3;
        font-size: 13px;
      }
      button {
        width: 100%;
        height: 42px;
        margin-top: 18px;
        border: 0;
        border-radius: 6px;
        background: #48b3ff;
        color: #071018;
        font-size: 15px;
        font-weight: 700;
        cursor: pointer;
      }
      button:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }
      .content {
        display: grid;
        grid-template-rows: auto 1fr;
        min-width: 0;
      }
      .status {
        display: flex;
        gap: 12px;
        align-items: center;
        min-height: 58px;
        padding: 14px 18px;
        border-bottom: 1px solid #2c3137;
        background: #12161b;
      }
      .status a {
        color: #48b3ff;
      }
      pre {
        margin: 0;
        padding: 18px;
        overflow: auto;
        background: #080a0d;
        color: #c7f7d4;
        font-size: 12px;
        line-height: 1.45;
        white-space: pre-wrap;
      }
      @media (max-width: 820px) {
        main { grid-template-columns: 1fr; }
        .panel { border-right: 0; border-bottom: 1px solid #2c3137; }
      }
    </style>
  </head>
  <body>
    <main>
      <section class="panel">
        <h1>Video to 3DGS Demo</h1>
        <div id="dropzone" class="dropzone">
          <div>
            <strong>Kéo thả video hoặc PLY</strong>
            <span>Hỗ trợ .mp4/.mov/.avi/.mkv/.webm và .ply</span>
          </div>
        </div>
        <input id="file" type="file" accept=".mp4,.mov,.avi,.mkv,.webm,.ply" hidden />
        <label for="scene">Scene name</label>
        <input id="scene" value="demo_scene" />
        <label for="policy">Frame policy</label>
        <select id="policy">
          <option value="light_filter" selected>light_filter</option>
          <option value="no_filter">no_filter</option>
          <option value="medium_filter">medium_filter</option>
          <option value="strong_filter">strong_filter</option>
        </select>
        <label for="fps">Extract FPS</label>
        <input id="fps" value="5" />
        <label for="iterations">3DGS iterations</label>
        <input id="iterations" value="7000" />
        <label for="resolution">3DGS resolution</label>
        <input id="resolution" value="2" />
        <button id="run" disabled>Chạy demo</button>
      </section>
      <section class="content">
        <div class="status">
          <div id="state">Chọn file để bắt đầu.</div>
          <a id="viewer" href="#" target="_blank" rel="noreferrer" hidden>Mở viewer</a>
        </div>
        <pre id="logs"></pre>
      </section>
    </main>
    <script>
      const dropzone = document.getElementById('dropzone');
      const fileInput = document.getElementById('file');
      const runButton = document.getElementById('run');
      const state = document.getElementById('state');
      const logs = document.getElementById('logs');
      const viewer = document.getElementById('viewer');
      let selectedFile = null;
      let pollTimer = null;

      function setFile(file) {
        selectedFile = file;
        dropzone.querySelector('strong').textContent = file.name;
        dropzone.querySelector('span').textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB`;
        runButton.disabled = false;
        const baseName = file.name.replace(/\.[^.]+$/, '').replace(/[^a-zA-Z0-9_-]+/g, '_').toLowerCase();
        document.getElementById('scene').value = baseName || 'demo_scene';
      }

      dropzone.addEventListener('click', () => fileInput.click());
      fileInput.addEventListener('change', () => {
        if (fileInput.files && fileInput.files[0]) setFile(fileInput.files[0]);
      });
      for (const eventName of ['dragenter', 'dragover']) {
        dropzone.addEventListener(eventName, (event) => {
          event.preventDefault();
          dropzone.dataset.active = 'true';
        });
      }
      for (const eventName of ['dragleave', 'drop']) {
        dropzone.addEventListener(eventName, (event) => {
          event.preventDefault();
          dropzone.dataset.active = 'false';
        });
      }
      dropzone.addEventListener('drop', (event) => {
        const file = event.dataTransfer.files[0];
        if (file) setFile(file);
      });

      async function poll(jobId) {
        const response = await fetch(`/api/jobs/${jobId}`);
        const job = await response.json();
        state.textContent = `Trạng thái: ${job.status}`;
        logs.textContent = job.logs.join('\n');
        logs.scrollTop = logs.scrollHeight;
        if (job.viewer_url) {
          viewer.href = job.viewer_url;
          viewer.hidden = false;
        }
        if (job.status === 'failed') {
          clearInterval(pollTimer);
          runButton.disabled = false;
        }
      }

      runButton.addEventListener('click', async () => {
        if (!selectedFile) return;
        runButton.disabled = true;
        viewer.hidden = true;
        logs.textContent = '';
        state.textContent = 'Đang upload...';
        const form = new FormData();
        form.append('file', selectedFile);
        form.append('scene', document.getElementById('scene').value);
        form.append('policy', document.getElementById('policy').value);
        form.append('fps', document.getElementById('fps').value);
        form.append('iterations', document.getElementById('iterations').value);
        form.append('resolution', document.getElementById('resolution').value);
        const response = await fetch('/api/upload', { method: 'POST', body: form });
        const payload = await response.json();
        if (!response.ok) {
          state.textContent = payload.error || 'Upload failed.';
          runButton.disabled = false;
          return;
        }
        state.textContent = `Job: ${payload.job_id}`;
        pollTimer = setInterval(() => poll(payload.job_id), 1000);
        await poll(payload.job_id);
      });
    </script>
  </body>
</html>
"""


class DemoHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            data = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if parsed.path.startswith("/api/jobs/"):
            job_id = parsed.path.rsplit("/", maxsplit=1)[-1]
            with jobs_lock:
                job = jobs.get(job_id)
                if job is None:
                    json_response(self, {"error": "job not found"}, 404)
                    return
                payload = {
                    "id": job.id,
                    "kind": job.kind,
                    "status": job.status,
                    "logs": job.logs,
                    "scene_json": job.scene_json,
                    "viewer_url": job.viewer_url,
                    "error": job.error,
                }
            json_response(self, payload)
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/upload":
            self.send_error(404, "Not found")
            return

        try:
            upload_path, fields = read_upload(self)
            kind = "video" if upload_path.suffix.lower() in VIDEO_EXTENSIONS else "ply"
            job_id = uuid.uuid4().hex[:10]
            job = DemoJob(id=job_id, kind=kind)
            job.log(f"Uploaded: {upload_path}")
            job.log(f"Kind: {kind}")
            with jobs_lock:
                jobs[job_id] = job
            thread = threading.Thread(target=run_job, args=(job_id, upload_path, fields), daemon=True)
            thread.start()
            json_response(self, {"job_id": job_id, "kind": kind}, 202)
        except Exception as exc:
            json_response(self, {"error": str(exc)}, 400)

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    global PYTHON_COMMAND
    args = parse_args()
    selected_python, attempts = select_pipeline_python(args.python)
    print("Pipeline Python candidates:")
    for attempt in attempts:
        print(f"- {attempt}")
    if selected_python is None:
        print("\nError: no Python interpreter has all pipeline modules:")
        print(", ".join(PIPELINE_MODULES))
        print("Install dependencies with the Python you want to use, or pass --python C:\\path\\to\\python.exe")
        return 1
    PYTHON_COMMAND = selected_python
    print(f"\nUsing pipeline Python: {subprocess.list2cmdline(PYTHON_COMMAND)}")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    port = find_free_port(args.host, args.port)
    server = ThreadingHTTPServer((args.host, port), DemoHandler)
    url = f"http://{args.host}:{port}"
    print(f"Demo app: {url}")
    if not args.no_open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping demo app...")
        return 0
    finally:
        server.shutdown()
        for process in viewer_processes:
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    raise SystemExit(main())

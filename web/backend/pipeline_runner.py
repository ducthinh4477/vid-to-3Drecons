from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from src.reconstruction.colmap_utils import count_ply_vertices
from web.backend.artifact_service import (
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    artifact_url,
    list_media_files,
    project_rel,
    read_json,
    read_quality_summary,
    sample_evenly,
    write_json,
)
from web.backend.colmap_exporter import export_colmap_preview

ROOT = Path(__file__).resolve().parents[2]
Mode = Literal["instant", "cached", "preview"]
StepStatus = Literal["idle", "running", "done", "error", "skipped", "available", "missing"]


@dataclass
class DemoRequest:
    video_path: str
    scene: str
    policy: str
    mode: Mode = "instant"
    fps: float = 5.0
    quality: str = "medium"
    iterations: int = 1500
    resolution: int = 4


@dataclass
class Step:
    name: str
    label: str
    status: StepStatus = "idle"
    message: str = ""


@dataclass
class Job:
    id: str
    request: DemoRequest
    status: Literal["queued", "running", "done", "error"] = "queued"
    current_step: str = ""
    steps: list[Step] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    artifact_manifest: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    events: "queue.Queue[dict]" = field(default_factory=queue.Queue)

    def emit(self) -> None:
        self.updated_at = time.time()
        self.events.put(self.snapshot())

    def log(self, message: str) -> None:
        text = message.rstrip()
        if text:
            self.logs.append(text)
            self.logs = self.logs[-160:]
            self.emit()

    def snapshot(self) -> dict:
        return {
            "job_id": self.id,
            "status": self.status,
            "current_step": self.current_step,
            "steps": [step.__dict__ for step in self.steps],
            "logs": self.logs[-80:],
            "artifact_manifest": self.artifact_manifest,
            "error": self.error,
        }


class PipelineRunner:
    def __init__(self) -> None:
        self.jobs: dict[str, Job] = {}
        self.lock = threading.Lock()

    def start(self, request: DemoRequest) -> Job:
        job = Job(id=uuid.uuid4().hex[:10], request=request, steps=_default_steps(request.mode))
        with self.lock:
            self.jobs[job.id] = job
        threading.Thread(target=self._run_job, args=(job,), daemon=True).start()
        return job

    def get(self, job_id: str) -> Job | None:
        with self.lock:
            return self.jobs.get(job_id)

    def _run_job(self, job: Job) -> None:
        job.status = "running"
        job.emit()
        try:
            run_pipeline(job)
            job.status = "done"
        except Exception as exc:
            job.status = "error"
            job.error = str(exc)
            _set_step(job, job.current_step, "error", str(exc))
            job.log(f"Error: {exc}")
        finally:
            job.emit()


def _default_steps(mode: Mode) -> list[Step]:
    labels = [
        ("extract_frames", "Step 1 Extract frames"),
        ("quality_scoring", "Step 2 Quality scoring"),
        ("frame_selection", "Step 3 Frame selection"),
        ("colmap", "Step 4 COLMAP SIFT baseline"),
        ("preview", "Step 5 3D preview"),
        ("cached_3dgs", "Step 6 3DGS cached model"),
    ]
    if mode == "preview":
        labels.append(("preview_3dgs", "Step 7 3DGS preview training"))
    return [Step(name=name, label=label) for name, label in labels]


def run_pipeline(job: Job) -> None:
    request = job.request
    video = Path(request.video_path)
    if not video.is_absolute():
        video = ROOT / video
    if not video.exists() or video.suffix.lower() not in VIDEO_EXTENSIONS:
        raise FileNotFoundError(f"Video not found or unsupported: {video}")

    scene = _slug(request.scene or video.stem)
    policy = request.policy
    frames_raw = ROOT / "data" / "frames_raw" / scene
    quality_csv = ROOT / "outputs" / "frame_quality" / scene / "frame_quality.csv"
    selected_dir = ROOT / "data" / "frames_selected" / scene / policy
    workspace = ROOT / "outputs" / "reconstructions" / scene / policy / "colmap"
    metrics_json = ROOT / "outputs" / "reconstructions" / scene / policy / "metrics.json"

    _run_or_skip(
        job,
        "extract_frames",
        frames_raw.exists() and bool(list_media_files(frames_raw, IMAGE_EXTENSIONS)),
        f"Using cached frames in {project_rel(frames_raw)}",
        [sys.executable, "scripts/01_extract_frames.py", "--video", str(video), "--scene", scene, "--fps", str(request.fps)],
    )
    _run_or_skip(
        job,
        "quality_scoring",
        quality_csv.exists(),
        f"Using cached quality CSV {project_rel(quality_csv)}",
        [
            sys.executable,
            "scripts/02_compute_frame_quality.py",
            "--scene",
            scene,
            "--frames",
            str(frames_raw),
            "--out",
            str(quality_csv),
        ],
    )
    _run_or_skip(
        job,
        "frame_selection",
        selected_dir.exists() and (selected_dir / "selected_frames.csv").exists(),
        f"Using cached selected frames in {project_rel(selected_dir)}",
        [
            sys.executable,
            "scripts/03_select_frames.py",
            "--scene",
            scene,
            "--frames",
            str(frames_raw),
            "--quality",
            str(quality_csv),
            "--policy",
            policy,
            "--out",
            str(selected_dir),
        ],
    )

    colmap_ready = _workspace_has_colmap(workspace)
    _run_or_skip(
        job,
        "colmap",
        colmap_ready,
        f"Using cached COLMAP workspace {project_rel(workspace)}",
        [
            sys.executable,
            "scripts/05_run_hloc_colmap.py",
            "--scene",
            scene,
            "--policy",
            policy,
            "--images",
            str(selected_dir),
            "--workspace",
            str(workspace),
            "--quality",
            request.quality,
            "--camera-model",
            "SIMPLE_RADIAL",
            "--single-camera",
            "1",
        ],
    )

    _run_optional_evaluate(job, scene, policy, workspace, metrics_json)
    _set_step(job, "preview", "running", "Exporting COLMAP preview artifact.")
    preview_result = export_colmap_preview(scene, policy)
    _set_step(job, "preview", "done", f"Preview points: {preview_result.get('point_count') or 0}")

    preview_message = None
    if request.mode == "preview":
        preview_message = _run_preview_training(job, scene, policy, request.iterations, request.resolution)

    manifest = generate_manifest(
        scene=scene,
        policy=policy,
        mode=request.mode,
        video=video,
        quality_csv=quality_csv,
        selected_dir=selected_dir,
        workspace=workspace,
        metrics_json=metrics_json,
        preview_result=preview_result,
        preview_message=preview_message,
    )
    manifest_data = read_json(manifest)
    if manifest_data.get("status", {}).get("has_3dgs_cached"):
        _set_step(job, "cached_3dgs", "available", "3DGS cached model available.")
    else:
        _set_step(job, "cached_3dgs", "missing", "3DGS cached model not found, showing COLMAP preview.")
    job.artifact_manifest = f"/api/artifacts/{scene}/{policy}/manifest"
    job.log(f"Manifest: {project_rel(manifest)}")


def _run_optional_evaluate(job: Job, scene: str, policy: str, workspace: Path, metrics_json: Path) -> None:
    if metrics_json.exists():
        job.log(f"Using cached metrics {project_rel(metrics_json)}")
        return
    if not _workspace_has_colmap(workspace):
        job.log("COLMAP metrics skipped because no reconstruction workspace is available.")
        return
    command = [
        sys.executable,
        "scripts/07_evaluate_colmap.py",
        "--scene",
        scene,
        "--policy",
        policy,
        "--workspace",
        str(workspace),
        "--out",
        str(metrics_json),
    ]
    _run_background_metric_command(job, command)


def _run_preview_training(job: Job, scene: str, policy: str, iterations: int, resolution: int) -> str | None:
    _set_step(job, "preview_3dgs", "running", "Preparing 3DGS preview dataset.")
    dataset = ROOT / "data" / "3dgs" / f"{scene}_{policy.removesuffix('_filter') if policy.endswith('_filter') else policy}"
    code = _run_command(
        job,
        "preview_3dgs",
        [sys.executable, "scripts/11_prepare_3dgs_dataset.py", "--scene", scene, "--policy", policy, "--out", str(dataset), "--overwrite"],
        optional=True,
    )
    if code != 0:
        _set_step(job, "preview_3dgs", "error", "Could not prepare 3DGS dataset; showing COLMAP preview.")
        return "3DGS preview dataset preparation failed, showing COLMAP preview."

    gaussian_root = os.environ.get("GAUSSIAN_SPLATTING_PATH")
    if not gaussian_root:
        message = "GAUSSIAN_SPLATTING_PATH is not configured; showing COLMAP preview."
        _set_step(job, "preview_3dgs", "error", message)
        job.log(message)
        return message

    train_py = Path(gaussian_root) / "train.py"
    if not train_py.exists():
        message = f"train.py not found under GAUSSIAN_SPLATTING_PATH={gaussian_root}; showing COLMAP preview."
        _set_step(job, "preview_3dgs", "error", message)
        job.log(message)
        return message

    model_dir = ROOT / "outputs" / "3dgs" / f"{scene}_{policy}_preview"
    code = _run_command(
        job,
        "preview_3dgs",
        [
            sys.executable,
            str(train_py),
            "-s",
            str(dataset),
            "-m",
            str(model_dir),
            "--iterations",
            str(iterations),
            "--resolution",
            str(resolution),
        ],
        cwd=Path(gaussian_root),
        optional=True,
    )
    if code != 0:
        _set_step(job, "preview_3dgs", "error", "3DGS preview training failed; showing COLMAP preview.")
        return "3DGS preview training failed, showing COLMAP preview."

    source = model_dir / "point_cloud" / f"iteration_{iterations}" / "point_cloud.ply"
    target = ROOT / "outputs" / "demo" / f"{scene}_{policy}" / "point_cloud_3dgs_preview.ply"
    if source.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        _set_step(job, "preview_3dgs", "done", f"Preview model ready: {project_rel(target)}")
        return None
    _set_step(job, "preview_3dgs", "error", "Training finished but point_cloud.ply was not found.")
    return "3DGS preview output was not found, showing COLMAP preview."


def generate_manifest(
    scene: str,
    policy: str,
    mode: Mode,
    video: Path,
    quality_csv: Path,
    selected_dir: Path,
    workspace: Path,
    metrics_json: Path,
    preview_result: dict,
    preview_message: str | None,
) -> Path:
    demo_dir = ROOT / "outputs" / "demo" / f"{scene}_{policy}"
    demo_dir.mkdir(parents=True, exist_ok=True)
    cached_asset = _find_3dgs_cache(demo_dir)
    preview_ply = preview_result.get("preview_ply")
    preview_json = preview_result.get("preview_points_json")

    active_asset = cached_asset if cached_asset and mode in {"cached", "preview"} else preview_ply or preview_json
    active_type = _asset_type(active_asset, cached_asset is not None and active_asset == cached_asset)
    has_3dgs_cached = cached_asset is not None
    if mode == "cached" and not has_3dgs_cached:
        preview_message = "3DGS cached model not found, showing COLMAP preview."

    metrics = _metrics_summary(metrics_json)
    thumbnails = [
        {"path": project_rel(path), "url": artifact_url(path), "name": path.name}
        for path in sample_evenly(list_media_files(selected_dir, IMAGE_EXTENSIONS), 18)
    ]
    bounds = preview_result.get("bounds") or {"min": [-1, -1, -1], "max": [1, 1, 1]}
    manifest = {
        "version": 1,
        "scene": scene,
        "policy": policy,
        "mode": mode,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "technical_note": "COLMAP automatic_reconstructor with SIFT is used. 3DGS model is loaded from cache if available.",
        "message": preview_message,
        "video": {"path": project_rel(video), "url": artifact_url(video)},
        "frames": {
            "raw_dir": f"data/frames_raw/{scene}",
            "selected_dir": project_rel(selected_dir),
            "selected_count": len(list_media_files(selected_dir, IMAGE_EXTENSIONS)),
            "thumbnails": thumbnails,
        },
        "quality": {
            "csv": project_rel(quality_csv) if quality_csv.exists() else None,
            "url": artifact_url(quality_csv) if quality_csv.exists() else None,
            "summary": read_quality_summary(quality_csv),
        },
        "colmap": {
            "workspace": project_rel(workspace),
            "metrics_json": project_rel(metrics_json) if metrics_json.exists() else None,
            "metrics_summary": metrics,
            "preview_ply": project_rel(preview_ply) if preview_ply else None,
            "preview_points_json": project_rel(preview_json) if preview_json else None,
            "preview_ply_url": artifact_url(preview_ply) if preview_ply else None,
            "preview_points_url": artifact_url(preview_json) if preview_json else None,
        },
        "viewer": {
            "active_type": active_type,
            "active_asset": project_rel(active_asset) if active_asset else None,
            "active_url": artifact_url(active_asset) if active_asset else None,
            "fallback_asset": project_rel(preview_ply or preview_json) if (preview_ply or preview_json) else None,
            "fallback_url": artifact_url(preview_ply or preview_json) if (preview_ply or preview_json) else None,
            "camera": {"position": [0, 1, 3], "look_at": [0, 0, 0], "fov": 60},
            "bounds": bounds,
        },
        "status": {
            "has_colmap_preview": bool(preview_ply or preview_json),
            "has_3dgs_cached": has_3dgs_cached,
            "has_3dgs_preview": (demo_dir / "point_cloud_3dgs_preview.ply").exists(),
        },
    }
    manifest_path = demo_dir / "demo_manifest.json"
    write_json(manifest, manifest_path)
    return manifest_path


def _find_3dgs_cache(demo_dir: Path) -> Path | None:
    names = [
        "point_cloud_3dgs_30000.ply",
        "point_cloud_3dgs_7000.ply",
        "point_cloud_3dgs_preview.ply",
        "point_cloud.ply",
        "*.splat",
        "*.gsplat",
        "*.ksplat",
        "*.compressed.ply",
    ]
    for name in names:
        matches = sorted(demo_dir.glob(name))
        if matches:
            return matches[0]
    return None


def _asset_type(path: Path | None, is_splat: bool) -> str:
    if path is None:
        return "none"
    suffix = path.suffix.lower()
    if is_splat or suffix in {".splat", ".gsplat", ".ksplat"} or path.name.endswith(".compressed.ply"):
        return "splat"
    if suffix == ".json":
        return "preview_points"
    return "pointcloud"


def _metrics_summary(metrics_json: Path) -> dict:
    if not metrics_json.exists():
        return {
            "registered_images": None,
            "sparse_points": None,
            "dense_points": None,
            "reprojection_error_px": None,
            "registered_ratio": None,
        }
    data = read_json(metrics_json)
    best = data.get("best_sparse_model") or {}
    return {
        "registered_images": best.get("registered_images"),
        "sparse_points": best.get("points"),
        "dense_points": data.get("dense_fused_points"),
        "reprojection_error_px": best.get("mean_reprojection_error_px"),
        "registered_ratio": best.get("registered_ratio"),
    }


def _workspace_has_colmap(workspace: Path) -> bool:
    return (workspace / "dense").exists() or (workspace / "sparse").exists() or (workspace / "database.db").exists()


def _run_or_skip(job: Job, step_name: str, skip: bool, skip_message: str, command: list[str]) -> None:
    if skip:
        _set_step(job, step_name, "done", skip_message)
        job.log(skip_message)
        return
    code = _run_command(job, step_name, command)
    if code != 0:
        raise RuntimeError(f"{step_name} failed with exit code {code}")


def _run_command(
    job: Job,
    step_name: str,
    command: list[str],
    cwd: Path | None = None,
    optional: bool = False,
) -> int:
    _set_step(job, step_name, "running", "Running command.")
    job.log(subprocess.list2cmdline(command))
    process = subprocess.Popen(
        command,
        cwd=str(cwd or ROOT),
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
    code = process.wait()
    if code == 0:
        _set_step(job, step_name, "done", "Done.")
    elif optional:
        _set_step(job, step_name, "error", f"Optional command failed with exit code {code}.")
    return code


def _run_background_metric_command(job: Job, command: list[str]) -> int:
    job.log("Evaluating cached COLMAP metrics.")
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
    code = process.wait()
    if code != 0:
        job.log(f"COLMAP metric evaluation failed with exit code {code}.")
    return code


def _set_step(job: Job, name: str, status: StepStatus, message: str) -> None:
    job.current_step = name
    for step in job.steps:
        if step.name == name:
            step.status = status
            step.message = message
            break
    job.emit()


def _slug(text: str) -> str:
    cleaned = []
    for char in text.strip().lower():
        if char.isalnum():
            cleaned.append(char)
        elif char in {"-", "_", " "}:
            cleaned.append("_")
    return "".join(cleaned).strip("_") or "scene"


runner = PipelineRunner()

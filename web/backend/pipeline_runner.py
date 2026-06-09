from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

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
from web.backend.gaussian_bridge import (
    collect_point_cloud,
    gaussian_paths,
    has_converted_dataset,
    has_trained_point_cloud,
    prepare_dataset_from_selected_frames,
    resolve_gaussian_root,
    resolve_vis_root,
    run_subprocess_stream,
    run_convert_with_fallback,
    train_command,
    validate_external_repos,
)

ROOT = Path(__file__).resolve().parents[2]
StepStatus = Literal["idle", "running", "done", "error", "skipped", "available", "missing"]


@dataclass
class DemoRequest:
    video_path: str
    scene: str
    policy: str
    fps: float = 5.0
    quality: str = "medium"
    iterations: int = 7000
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
        job = Job(id=uuid.uuid4().hex[:10], request=request, steps=_default_steps())
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


def _default_steps() -> list[Step]:
    labels = [
        ("extract_frames", "Step 1 Extract frames"),
        ("quality_scoring", "Step 2 Quality scoring"),
        ("frame_selection", "Step 3 Frame selection"),
        ("gs_dataset", "Step 4 Prepare Gaussian dataset"),
        ("gs_convert", "Step 5 GraphDECO convert.py"),
        ("gs_train", "Step 6 GraphDECO train.py"),
        ("vis3dgs", "Step 7 PLY ready for ViS-3DGS"),
    ]
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
    gaussian_root = resolve_gaussian_root()
    vis_root = resolve_vis_root()
    gs_paths = gaussian_paths(scene, policy)

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

    validate_external_repos(gaussian_root, vis_root)
    _set_step(job, "gs_dataset", "running", "Copying selected frames into Gaussian Splatting dataset/input.")
    frame_count = prepare_dataset_from_selected_frames(selected_dir, gs_paths)
    _set_step(job, "gs_dataset", "done", f"Prepared {frame_count} selected frames at {project_rel(gs_paths.input_dir)}.")

    if has_converted_dataset(gs_paths.dataset_dir):
        _set_step(job, "gs_convert", "done", f"Using cached Gaussian dataset {project_rel(gs_paths.dataset_dir)}.")
        job.log(f"Using cached Gaussian dataset {project_rel(gs_paths.dataset_dir)}")
    else:
        _set_step(job, "gs_convert", "running", "Running gaussian-splatting convert.py. This runs COLMAP feature matching and mapper inside GraphDECO.")
        code = run_convert_with_fallback(gaussian_root, gs_paths.dataset_dir, job.log)
        if code != 0:
            raise RuntimeError(f"gaussian-splatting convert.py failed with exit code {code}")
        _set_step(job, "gs_convert", "done", "Gaussian Splatting dataset converted.")

    if has_trained_point_cloud(gs_paths.model_dir, request.iterations):
        _set_step(job, "gs_train", "done", f"Using cached Gaussian Splatting model at {project_rel(gs_paths.model_dir)}.")
        job.log(f"Using cached Gaussian Splatting model {project_rel(gs_paths.model_dir)}")
    else:
        _set_step(job, "gs_train", "running", f"Training Gaussian Splatting for {request.iterations} iterations.")
        code = run_subprocess_stream(
            train_command(gaussian_root, gs_paths.dataset_dir, gs_paths.model_dir, request.iterations, request.resolution),
            gaussian_root,
            job.log,
        )
        if code != 0:
            raise RuntimeError(f"gaussian-splatting train.py failed with exit code {code}")
        _set_step(job, "gs_train", "done", "Gaussian Splatting training finished.")

    result = collect_point_cloud(scene, policy, gs_paths, vis_root, gaussian_root)
    vis_message = f"PLY ready: {project_rel(result.output_ply)}"
    if vis_root:
        vis_message += f" | ViS-3DGS repo detected at {vis_root}"
    else:
        vis_message += " | ViS-3DGS repo not found; web viewer still loads the PLY."
    _set_step(job, "vis3dgs", "done", vis_message)

    manifest = generate_manifest(
        scene=scene,
        policy=policy,
        video=video,
        quality_csv=quality_csv,
        selected_dir=selected_dir,
        gaussian_result=result,
        preview_message="Loaded Gaussian Splatting point_cloud.ply generated from selected frames.",
    )
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


def generate_manifest(
    scene: str,
    policy: str,
    video: Path,
    quality_csv: Path,
    selected_dir: Path,
    gaussian_result,
    preview_message: str | None,
) -> Path:
    demo_dir = ROOT / "outputs" / "demo" / f"{scene}_{policy}"
    demo_dir.mkdir(parents=True, exist_ok=True)

    active_asset = gaussian_result.output_ply
    active_type = _asset_type(active_asset, True)
    thumbnails = [
        {"path": project_rel(path), "url": artifact_url(path), "name": path.name}
        for path in sample_evenly(list_media_files(selected_dir, IMAGE_EXTENSIONS), 18)
    ]
    bounds = {"min": [-1, -1, -1], "max": [1, 1, 1]}
    manifest = {
        "version": 1,
        "scene": scene,
        "policy": policy,
        "mode": "video_to_gaussian_splatting_ply",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "technical_note": (
            "This path extracts and selects frames in vid-to-3Drecons, then calls GraphDECO gaussian-splatting "
            "convert.py and train.py to produce point_cloud.ply. convert.py runs COLMAP internally for poses; "
            "scripts/05_run_hloc_colmap.py is not used by this web pipeline."
        ),
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
        "gaussian_splatting": {
            "dataset_dir": project_rel(gaussian_result.dataset_dir),
            "model_dir": project_rel(gaussian_result.model_dir),
            "source_ply": str(gaussian_result.source_ply),
            "output_ply": project_rel(gaussian_result.output_ply),
            "output_ply_url": artifact_url(gaussian_result.output_ply),
            "iteration": gaussian_result.iteration,
        },
        "vis3dgs": {
            "repo": str(gaussian_result.vis_root) if gaussian_result.vis_root else None,
            "target_manifest": project_rel(gaussian_result.vis_manifest),
            "note": "ViS-3DGS is optional external inspection for the generated PLY; the one-page web app stays self-contained.",
        },
        "colmap": {
            "workspace": None,
            "metrics_json": None,
            "metrics_summary": _empty_metrics_summary(),
            "preview_ply": None,
            "preview_points_json": None,
            "preview_ply_url": None,
            "preview_points_url": None,
            "note": "Legacy COLMAP preview is disabled for this path. GraphDECO convert.py performs its own COLMAP pose stage.",
        },
        "viewer": {
            "active_type": active_type,
            "active_asset": project_rel(active_asset) if active_asset else None,
            "active_url": artifact_url(active_asset) if active_asset else None,
            "fallback_asset": None,
            "fallback_url": None,
            "camera": {"position": [0, 1, 3], "look_at": [0, 0, 0], "fov": 60},
            "bounds": bounds,
        },
        "status": {
            "has_colmap_preview": False,
            "has_3dgs_cached": False,
            "has_3dgs_preview": True,
            "has_gaussian_point_cloud": active_asset.exists() if active_asset else False,
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
        return _empty_metrics_summary()
    data = read_json(metrics_json)
    best = data.get("best_sparse_model") or {}
    return {
        "registered_images": best.get("registered_images"),
        "sparse_points": best.get("points"),
        "dense_points": data.get("dense_fused_points"),
        "reprojection_error_px": best.get("mean_reprojection_error_px"),
        "registered_ratio": best.get("registered_ratio"),
    }


def _empty_metrics_summary() -> dict:
    return {
        "registered_images": None,
        "sparse_points": None,
        "dense_points": None,
        "reprojection_error_px": None,
        "registered_ratio": None,
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

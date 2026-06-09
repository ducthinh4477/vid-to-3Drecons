from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from src.reconstruction.colmap_utils import find_colmap_executable
from web.backend.artifact_service import IMAGE_EXTENSIONS, list_media_files, project_rel

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GAUSSIAN_ROOT = Path(os.environ.get("GAUSSIAN_SPLATTING_PATH", r"C:\GitHub\gaussian-splatting"))
DEFAULT_VIS_ROOT = Path(os.environ.get("VIS_3DGS_PATH", r"C:\GitHub\ViS-3DGS-main"))


@dataclass
class GaussianPaths:
    dataset_dir: Path
    input_dir: Path
    model_dir: Path
    demo_dir: Path
    output_ply: Path
    vis_manifest: Path


@dataclass
class GaussianResult:
    dataset_dir: Path
    model_dir: Path
    source_ply: Path
    output_ply: Path
    iteration: int
    vis_root: Path | None
    vis_manifest: Path


def resolve_gaussian_root(path: str | Path | None = None) -> Path:
    root = Path(path) if path else DEFAULT_GAUSSIAN_ROOT
    return root.resolve()


def resolve_vis_root(path: str | Path | None = None) -> Path | None:
    root = Path(path) if path else DEFAULT_VIS_ROOT
    root = root.resolve()
    return root if root.exists() else None


def gaussian_paths(scene: str, policy: str) -> GaussianPaths:
    key = f"{scene}_{policy}"
    dataset_dir = ROOT / "outputs" / "gaussian_splatting" / key / "dataset"
    model_dir = ROOT / "outputs" / "gaussian_splatting" / key / "model"
    demo_dir = ROOT / "outputs" / "demo" / key
    return GaussianPaths(
        dataset_dir=dataset_dir,
        input_dir=dataset_dir / "input",
        model_dir=model_dir,
        demo_dir=demo_dir,
        output_ply=demo_dir / "point_cloud.ply",
        vis_manifest=demo_dir / "vis3dgs_target.json",
    )


def validate_external_repos(gaussian_root: Path, vis_root: Path | None) -> None:
    missing = []
    if not (gaussian_root / "convert.py").exists():
        missing.append(f"missing convert.py in {gaussian_root}")
    if not (gaussian_root / "train.py").exists():
        missing.append(f"missing train.py in {gaussian_root}")
    if vis_root is not None and not (vis_root / "package.json").exists():
        missing.append(f"missing package.json in {vis_root}")
    if missing:
        raise FileNotFoundError("; ".join(missing))


def prepare_dataset_from_selected_frames(selected_dir: Path, paths: GaussianPaths, force: bool = False) -> int:
    frames = list_media_files(selected_dir, IMAGE_EXTENSIONS)
    if not frames:
        raise FileNotFoundError(f"No selected frames found in {selected_dir}")

    if force and paths.input_dir.exists():
        shutil.rmtree(paths.input_dir)
    paths.input_dir.mkdir(parents=True, exist_ok=True)

    existing = list_media_files(paths.input_dir, IMAGE_EXTENSIONS)
    if len(existing) == len(frames) and all((paths.input_dir / frame.name).exists() for frame in frames):
        return len(frames)

    for old in existing:
        old.unlink()
    for frame in frames:
        shutil.copy2(frame, paths.input_dir / frame.name)
    return len(frames)


def has_converted_dataset(dataset_dir: Path) -> bool:
    sparse = dataset_dir / "sparse" / "0"
    return (dataset_dir / "images").exists() and all((sparse / name).exists() for name in ("cameras.bin", "images.bin", "points3D.bin"))


def convert_command(gaussian_root: Path, dataset_dir: Path) -> list[str]:
    command = [sys.executable, str(gaussian_root / "convert.py"), "-s", str(dataset_dir)]
    colmap = find_colmap_executable()
    if colmap:
        command.extend(["--colmap_executable", colmap])
    return command


def run_convert_with_fallback(gaussian_root: Path, dataset_dir: Path, on_line) -> int:
    code = run_subprocess_stream(convert_command(gaussian_root, dataset_dir), gaussian_root, on_line)
    if code == 0:
        return 0
    on_line(
        "GraphDECO convert.py failed. Retrying with vid-to-3Drecons COLMAP 4.x-compatible converter "
        "(FeatureExtraction.use_gpu / FeatureMatching.use_gpu).\n"
    )
    _clean_convert_outputs(dataset_dir)
    return run_compatible_colmap_convert(dataset_dir, on_line)


def run_compatible_colmap_convert(dataset_dir: Path, on_line) -> int:
    colmap = find_colmap_executable()
    if colmap is None:
        on_line("COLMAP executable was not found on PATH or C:/colmap/bin/colmap.exe.\n")
        return 1

    distorted = dataset_dir / "distorted"
    sparse_distorted = distorted / "sparse"
    sparse_distorted.mkdir(parents=True, exist_ok=True)
    database = distorted / "database.db"
    input_dir = dataset_dir / "input"

    commands = [
        [
            colmap,
            "feature_extractor",
            "--database_path",
            str(database),
            "--image_path",
            str(input_dir),
            "--ImageReader.single_camera",
            "1",
            "--ImageReader.camera_model",
            "OPENCV",
            "--FeatureExtraction.use_gpu",
            "1",
        ],
        [
            colmap,
            "exhaustive_matcher",
            "--database_path",
            str(database),
            "--FeatureMatching.use_gpu",
            "1",
        ],
        [
            colmap,
            "mapper",
            "--database_path",
            str(database),
            "--image_path",
            str(input_dir),
            "--output_path",
            str(sparse_distorted),
            "--Mapper.ba_global_function_tolerance=0.000001",
        ],
        [
            colmap,
            "image_undistorter",
            "--image_path",
            str(input_dir),
            "--input_path",
            str(sparse_distorted / "0"),
            "--output_path",
            str(dataset_dir),
            "--output_type",
            "COLMAP",
        ],
    ]
    for command in commands:
        code = run_subprocess_stream(command, ROOT, on_line)
        if code != 0:
            return code
    _normalize_sparse_folder(dataset_dir)
    return 0


def train_command(gaussian_root: Path, dataset_dir: Path, model_dir: Path, iterations: int, resolution: int) -> list[str]:
    return [
        sys.executable,
        str(gaussian_root / "train.py"),
        "-s",
        str(dataset_dir),
        "-m",
        str(model_dir),
        "--iterations",
        str(iterations),
        "--resolution",
        str(resolution),
    ]


def _clean_convert_outputs(dataset_dir: Path) -> None:
    for name in ("distorted", "images", "sparse", "stereo"):
        path = dataset_dir / name
        if path.exists():
            shutil.rmtree(path)


def _normalize_sparse_folder(dataset_dir: Path) -> None:
    sparse = dataset_dir / "sparse"
    target = sparse / "0"
    target.mkdir(parents=True, exist_ok=True)
    for path in list(sparse.iterdir()):
        if path.name == "0":
            continue
        shutil.move(str(path), str(target / path.name))


def latest_point_cloud(model_dir: Path) -> tuple[Path | None, int]:
    point_root = model_dir / "point_cloud"
    if not point_root.exists():
        return None, 0
    best_path: Path | None = None
    best_iteration = 0
    for ply in point_root.glob("iteration_*/point_cloud.ply"):
        match = re.search(r"iteration_(\d+)", ply.as_posix())
        iteration = int(match.group(1)) if match else 0
        if iteration >= best_iteration:
            best_iteration = iteration
            best_path = ply
    return best_path, best_iteration


def has_trained_point_cloud(model_dir: Path, required_iterations: int) -> bool:
    path, iteration = latest_point_cloud(model_dir)
    return path is not None and iteration >= required_iterations


def collect_point_cloud(scene: str, policy: str, paths: GaussianPaths, vis_root: Path | None, gaussian_root: Path | None = None) -> GaussianResult:
    source_ply, iteration = latest_point_cloud(paths.model_dir)
    if source_ply is None:
        raise FileNotFoundError(f"No Gaussian Splatting point_cloud.ply found under {paths.model_dir}")

    paths.demo_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_ply, paths.output_ply)
    if iteration:
        shutil.copy2(source_ply, paths.demo_dir / f"point_cloud_3dgs_{iteration}.ply")

    payload = {
        "scene": scene,
        "policy": policy,
        "ply": project_rel(paths.output_ply),
        "source_ply": str(source_ply),
        "gaussian_splatting_root": str((gaussian_root or resolve_gaussian_root()).resolve()),
        "vis_3dgs_root": str(vis_root) if vis_root else None,
        "note": "ViS-3DGS is a VSCode custom editor for the produced PLY; the one-page web app still renders this PLY in its own canvas.",
    }
    from web.backend.artifact_service import write_json

    write_json(payload, paths.vis_manifest)
    return GaussianResult(
        dataset_dir=paths.dataset_dir,
        model_dir=paths.model_dir,
        source_ply=source_ply,
        output_ply=paths.output_ply,
        iteration=iteration,
        vis_root=vis_root,
        vis_manifest=paths.vis_manifest,
    )


def run_subprocess_stream(command: list[str], cwd: Path, on_line) -> int:
    on_line(subprocess.list2cmdline(command))
    process = subprocess.Popen(
        command,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert process.stdout is not None
    for line in process.stdout:
        on_line(line)
    return process.wait()

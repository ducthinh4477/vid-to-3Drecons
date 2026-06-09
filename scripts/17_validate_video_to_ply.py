from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.backend.artifact_service import inspect_ply
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate video -> selected frames -> GraphDECO Gaussian Splatting PLY.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--policy", default="medium_filter")
    parser.add_argument("--fps", default=1.0, type=float)
    parser.add_argument("--iterations", default=7000, type=int)
    parser.add_argument("--resolution", default=4, type=int)
    parser.add_argument("--gaussian-root", type=Path, default=None)
    parser.add_argument("--vis-root", type=Path, default=None)
    parser.add_argument("--skip-train", action="store_true", help="Validate setup and collect an existing PLY without running train.py.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    failures: list[str] = []

    video = _resolve(args.video)
    _check(video.exists(), "video exists", failures, str(video))

    frames = ROOT / "data" / "frames_raw" / args.scene
    quality_csv = ROOT / "outputs" / "frame_quality" / args.scene / "frame_quality.csv"
    selected = ROOT / "data" / "frames_selected" / args.scene / args.policy
    gaussian_root = resolve_gaussian_root(args.gaussian_root)
    vis_root = resolve_vis_root(args.vis_root)
    paths = gaussian_paths(args.scene, args.policy)

    try:
        validate_external_repos(gaussian_root, vis_root)
        print(f"PASS: gaussian-splatting repo ({gaussian_root})")
        print(f"INFO: ViS-3DGS repo ({vis_root})" if vis_root else "INFO: ViS-3DGS repo not found; optional viewer step only.")
    except Exception as exc:
        failures.append(str(exc))

    if not _has_images(frames):
        _run([sys.executable, "scripts/01_extract_frames.py", "--video", str(video), "--scene", args.scene, "--fps", str(args.fps)], failures, "extract frames")
    _check(_has_images(frames), "frames extracted", failures, str(frames))

    if not quality_csv.exists():
        _run(
            [
                sys.executable,
                "scripts/02_compute_frame_quality.py",
                "--scene",
                args.scene,
                "--frames",
                str(frames),
                "--out",
                str(quality_csv),
            ],
            failures,
            "compute quality",
        )
    _check(_csv_non_empty(quality_csv), "frame_quality.csv non-empty", failures, str(quality_csv))

    if not _has_images(selected):
        _run(
            [
                sys.executable,
                "scripts/03_select_frames.py",
                "--scene",
                args.scene,
                "--frames",
                str(frames),
                "--quality",
                str(quality_csv),
                "--policy",
                args.policy,
                "--out",
                str(selected),
            ],
            failures,
            "select frames",
        )
    _check(_has_images(selected), "selected frames non-empty", failures, str(selected))

    if not failures:
        try:
            count = prepare_dataset_from_selected_frames(selected, paths)
            print(f"PASS: prepared Gaussian dataset input ({count} frames)")
        except Exception as exc:
            failures.append(f"prepare Gaussian dataset failed: {exc}")

    if not failures and not has_converted_dataset(paths.dataset_dir):
        code = run_convert_with_fallback(gaussian_root, paths.dataset_dir, lambda line: print(line, end="" if line.endswith("\n") else "\n"))
        if code != 0:
            failures.append(f"gaussian-splatting convert.py failed with exit code {code}")
    _check(has_converted_dataset(paths.dataset_dir), "GraphDECO converted dataset exists", failures, str(paths.dataset_dir))

    if args.skip_train:
        print("INFO: skipping train.py; will validate an existing model PLY if present.")
    elif not failures and not has_trained_point_cloud(paths.model_dir, args.iterations):
        code = run_subprocess_stream(
            train_command(gaussian_root, paths.dataset_dir, paths.model_dir, args.iterations, args.resolution),
            gaussian_root,
            lambda line: print(line, end="" if line.endswith("\n") else "\n"),
        )
        if code != 0:
            failures.append(f"gaussian-splatting train.py failed with exit code {code}")

    if not failures:
        try:
            result = collect_point_cloud(args.scene, args.policy, paths, vis_root, gaussian_root)
            info = inspect_ply(result.output_ply)
            props = set(info["properties"])
            _check({"x", "y", "z"}.issubset(props), "PLY has x/y/z", failures, str(result.output_ply))
            _check(info["asset_type"] in {"gaussian_splat", "point_cloud"}, "PLY readable by web viewer", failures, info["asset_type"])
            print(f"PASS: output PLY vertices={info['vertex_count']} type={info['asset_type']}")
        except Exception as exc:
            failures.append(f"collect/inspect output PLY failed: {exc}")

    if failures:
        print("\nFAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("\nPASS: video -> Gaussian Splatting PLY validation succeeded.")
    return 0


def _resolve(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def _has_images(path: Path) -> bool:
    return path.exists() and any(child.suffix.lower() in {".jpg", ".jpeg", ".png"} for child in path.iterdir() if child.is_file())


def _csv_non_empty(path: Path) -> bool:
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.reader(f)) > 1


def _run(command: list[str], failures: list[str], label: str) -> None:
    print(f"RUN: {label}")
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        failures.append(f"{label} failed with exit code {result.returncode}")
    else:
        print(f"PASS: {label}")


def _check(ok: bool, label: str, failures: list[str], detail: str = "") -> None:
    if ok:
        print(f"PASS: {label}{f' ({detail})' if detail else ''}")
    else:
        failures.append(f"{label} failed{f': {detail}' if detail else ''}")


if __name__ == "__main__":
    raise SystemExit(main())

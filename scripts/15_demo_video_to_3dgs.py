from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def policy_short_name(policy: str) -> str:
    if policy.endswith("_filter"):
        return policy.removesuffix("_filter")
    return policy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local demo pipeline from video to FPS 3DGS viewer.")
    parser.add_argument("--video", required=True, type=Path, help="Input video.")
    parser.add_argument("--scene", required=True, help="Scene name.")
    parser.add_argument("--policy", default="light_filter", help="Frame filtering policy.")
    parser.add_argument("--fps", default=5.0, type=float, help="Frame extraction FPS.")
    parser.add_argument("--quality", default="medium", help="COLMAP quality.")
    parser.add_argument("--iterations", default=7000, type=int, help="Speedy-Splat iterations.")
    parser.add_argument("--resolution", default=2, type=int, help="Speedy-Splat resolution.")
    parser.add_argument("--open-viewer", action="store_true", help="Open the viewer after cleaning the PLY.")
    parser.add_argument("--reuse-existing", action="store_true", default=True, help="Reuse existing outputs when present.")
    parser.add_argument("--overwrite", action="store_true", help="Re-run stages even when outputs exist.")
    return parser.parse_args()


def run(command: list[str]) -> int:
    print("\nRunning:")
    print(subprocess.list2cmdline(command))
    return subprocess.run(command, cwd=str(ROOT)).returncode


def has_images(path: Path) -> bool:
    return path.exists() and any(p.suffix.lower() in {".jpg", ".jpeg", ".png"} for p in path.iterdir() if p.is_file())


def has_sparse_dataset(path: Path) -> bool:
    sparse = path / "sparse" / "0"
    return (path / "images").exists() and all((sparse / name).exists() for name in ["cameras.bin", "images.bin", "points3D.bin"])


def find_latest_ply(model_out: Path) -> Path | None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src.reconstruction.gsplat_utils import find_latest_speedy_splat_ply

    return find_latest_speedy_splat_ply(model_out)


def ply_iteration(ply_path: Path | None) -> int:
    if ply_path is None:
        return -1
    suffix = ply_path.parent.name.removeprefix("iteration_")
    return int(suffix) if suffix.isdigit() else -1


def check_speedy_splat_training_ready() -> list[str]:
    errors = []
    train_py = ROOT / "third_party" / "speedy-splat" / "train.py"
    if not train_py.exists():
        errors.append(
            "Speedy-Splat is missing. Run: python scripts/00_bootstrap_3dgs_deps.py --install-speedy-splat"
        )

    try:
        import torch
    except ImportError:
        errors.append("PyTorch is not installed.")
    else:
        if not torch.cuda.is_available():
            errors.append(f"PyTorch CUDA is not available: torch {torch.__version__}.")

    missing_extensions = []
    if importlib.util.find_spec("diff_gaussian_rasterization") is None:
        missing_extensions.append("diff_gaussian_rasterization")
        errors.append("diff_gaussian_rasterization is not installed.")
    if importlib.util.find_spec("simple_knn") is None:
        missing_extensions.append("simple_knn")
        errors.append("simple_knn is not installed.")
    if missing_extensions and shutil.which("cl") is None:
        errors.append("cl.exe is not available. Install Visual Studio Build Tools C++ before building missing extensions.")
    return errors


def main() -> int:
    args = parse_args()
    if not args.video.exists():
        print(f"Error: input video not found: {args.video}")
        return 1

    scene = args.scene
    policy = args.policy
    short_policy = policy_short_name(policy)
    frames_raw = ROOT / "data" / "frames_raw" / scene
    quality_csv = ROOT / "outputs" / "frame_quality" / scene / "frame_quality.csv"
    selected = ROOT / "data" / "frames_selected" / scene / policy
    colmap_workspace = ROOT / "outputs" / "reconstructions" / scene / policy / "colmap"
    metrics_json = ROOT / "outputs" / "reconstructions" / scene / policy / "metrics.json"
    dataset = ROOT / "data" / "3dgs" / f"{scene}_{short_policy}"
    model_out = ROOT / "outputs" / "3dgs" / f"{scene}_{short_policy}"
    cleaned_ply = model_out / "point_cloud.cleaned.ply"
    scene_json = model_out / "viewer_scene.json"

    if args.overwrite:
        args.reuse_existing = False

    latest_ply = find_latest_ply(model_out)
    if latest_ply is None or ply_iteration(latest_ply) < args.iterations:
        training_errors = check_speedy_splat_training_ready()
        if training_errors:
            print("Error: cannot run full video -> 3DGS demo because training is not ready.")
            for error in training_errors:
                print(f"- {error}")
            print("\nSetup commands after installing CUDA-enabled PyTorch:")
            print("python scripts/00_bootstrap_3dgs_deps.py --install-speedy-splat")
            print("pip install third_party/speedy-splat/submodules/diff-gaussian-rasterization")
            print("pip install third_party/speedy-splat/submodules/simple-knn")
            print("\nTip: you can still drag a finished 3DGS point_cloud.ply into the demo app to open the viewer.")
            return 1

    if not args.reuse_existing or not has_images(frames_raw):
        code = run([sys.executable, "scripts/01_extract_frames.py", "--video", str(args.video), "--scene", scene, "--fps", str(args.fps)])
        if code:
            return code
    else:
        print(f"Reusing extracted frames: {frames_raw}")

    if not args.reuse_existing or not quality_csv.exists():
        code = run([sys.executable, "scripts/02_compute_frame_quality.py", "--scene", scene, "--frames", str(frames_raw), "--out", str(quality_csv)])
        if code:
            return code
    else:
        print(f"Reusing frame quality CSV: {quality_csv}")

    if not args.reuse_existing or not has_images(selected):
        code = run(
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
                str(selected),
            ]
        )
        if code:
            return code
    else:
        print(f"Reusing selected frames: {selected}")

    if args.reuse_existing and (colmap_workspace / "sparse").exists():
        print(f"Reusing COLMAP workspace: {colmap_workspace}")
    else:
        code = run(
            [
                sys.executable,
                "scripts/05_run_hloc_colmap.py",
                "--scene",
                scene,
                "--policy",
                policy,
                "--images",
                str(selected),
                "--workspace",
                str(colmap_workspace),
                "--quality",
                args.quality,
                "--camera-model",
                "SIMPLE_RADIAL",
                "--single-camera",
                "1",
            ]
            + ([] if args.reuse_existing else ["--overwrite"])
        )
        if code:
            return code

    if not args.reuse_existing or not metrics_json.exists():
        code = run(
            [
                sys.executable,
                "scripts/07_evaluate_colmap.py",
                "--scene",
                scene,
                "--policy",
                policy,
                "--workspace",
                str(colmap_workspace),
                "--out",
                str(metrics_json),
            ]
        )
        if code:
            return code
    else:
        print(f"Reusing COLMAP metrics: {metrics_json}")

    if not args.reuse_existing or not has_sparse_dataset(dataset):
        prepare_command = [
            sys.executable,
            "scripts/11_prepare_3dgs_dataset.py",
            "--scene",
            scene,
            "--policy",
            policy,
            "--out",
            str(dataset),
        ]
        if not args.reuse_existing:
            prepare_command.append("--overwrite")
        code = run(prepare_command)
        if code:
            return code
    else:
        print(f"Reusing prepared 3DGS dataset: {dataset}")

    if not args.reuse_existing or latest_ply is None or ply_iteration(latest_ply) < args.iterations:
        train_command = [
            sys.executable,
            "scripts/12_train_speedy_splat.py",
            "--scene",
            scene,
            "--policy",
            policy,
            "--dataset",
            str(dataset),
            "--model-out",
            str(model_out),
            "--iterations",
            str(args.iterations),
            "--resolution",
            str(args.resolution),
        ]
        if not args.reuse_existing:
            train_command.append("--overwrite")
        code = run(train_command)
        if code:
            return code
        latest_ply = find_latest_ply(model_out)

    if latest_ply is None:
        print(f"Error: no Speedy-Splat point_cloud.ply found in {model_out}")
        return 1

    needs_clean = not args.reuse_existing or not cleaned_ply.exists() or not scene_json.exists()
    if not needs_clean:
        source_mtime = latest_ply.stat().st_mtime
        cleaned_mtime = min(cleaned_ply.stat().st_mtime, scene_json.stat().st_mtime)
        needs_clean = source_mtime > cleaned_mtime

    if needs_clean:
        code = run([sys.executable, "scripts/13_clean_3dgs_ply.py", "--input", str(latest_ply), "--out", str(cleaned_ply), "--scene-json", str(scene_json)])
        if code:
            return code
    else:
        print(f"Reusing cleaned PLY: {cleaned_ply}")

    print("\nDemo artifact ready:")
    print(f"Cleaned PLY: {cleaned_ply}")
    print(f"Viewer scene JSON: {scene_json}")

    if args.open_viewer:
        return run([sys.executable, "scripts/14_launch_3dgs_viewer.py", "--scene-json", str(scene_json), "--install-viewer-deps"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

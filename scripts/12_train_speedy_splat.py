from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEEDY_SPLAT_DIR = ROOT / "third_party" / "speedy-splat"


def policy_short_name(policy: str) -> str:
    if policy.endswith("_filter"):
        return policy.removesuffix("_filter")
    return policy


def default_dataset_path(scene: str, policy: str) -> Path:
    return ROOT / "data" / "3dgs" / f"{scene}_{policy_short_name(policy)}"


def default_model_path(scene: str, policy: str) -> Path:
    return ROOT / "outputs" / "3dgs" / f"{scene}_{policy_short_name(policy)}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train a Speedy-Splat model from a prepared COLMAP dataset.")
    parser.add_argument("--scene", required=True, help="Scene name, for example scene01.")
    parser.add_argument("--policy", required=True, help="Frame filtering policy, for example light_filter.")
    parser.add_argument("--dataset", type=Path, help="Prepared 3DGS dataset path.")
    parser.add_argument("--model-out", type=Path, help="Output Speedy-Splat model directory.")
    parser.add_argument("--iterations", default=7000, type=int, help="Training iterations.")
    parser.add_argument("--resolution", default=2, type=int, help="Speedy-Splat resolution setting.")
    parser.add_argument("--overwrite", action="store_true", help="Run even if model output already has point clouds.")
    return parser.parse_args()


def model_has_point_cloud(model_out: Path) -> bool:
    return any(model_out.glob("point_cloud/iteration_*/point_cloud.ply"))


def point_cloud_iteration(ply_path: Path) -> int:
    suffix = ply_path.parent.name.removeprefix("iteration_")
    return int(suffix) if suffix.isdigit() else -1


def model_has_required_point_cloud(model_out: Path, required_iterations: int) -> bool:
    return any(
        point_cloud_iteration(path) >= required_iterations
        for path in model_out.glob("point_cloud/iteration_*/point_cloud.ply")
    )


def check_training_dependencies() -> list[str]:
    errors = []
    try:
        import torch
    except ImportError:
        errors.append("PyTorch is not installed.")
    else:
        if not torch.cuda.is_available():
            errors.append(
                f"PyTorch is installed but CUDA is not available: torch {torch.__version__}."
            )

    missing_extensions = []
    if importlib.util.find_spec("diff_gaussian_rasterization") is None:
        missing_extensions.append("diff_gaussian_rasterization")
        errors.append(
            "diff_gaussian_rasterization is not installed. "
            "Install third_party/speedy-splat/submodules/diff-gaussian-rasterization."
        )
    if importlib.util.find_spec("simple_knn") is None:
        missing_extensions.append("simple_knn")
        errors.append(
            "simple_knn is not installed. Install third_party/speedy-splat/submodules/simple-knn."
        )
    if missing_extensions and shutil.which("cl") is None:
        errors.append("cl.exe was not found. Install Visual Studio Build Tools C++ before building missing extensions.")
    return errors


def main() -> int:
    args = parse_args()
    dataset = (args.dataset or default_dataset_path(args.scene, args.policy)).resolve()
    model_out = (args.model_out or default_model_path(args.scene, args.policy)).resolve()
    train_py = SPEEDY_SPLAT_DIR / "train.py"

    if not train_py.exists():
        print(f"Error: Speedy-Splat train.py not found: {train_py}")
        print("Run: python scripts/00_bootstrap_3dgs_deps.py --install-speedy-splat")
        return 1
    if not dataset.exists():
        print(f"Error: prepared 3DGS dataset not found: {dataset}")
        print("Run scripts/11_prepare_3dgs_dataset.py first.")
        return 1
    if model_has_required_point_cloud(model_out, args.iterations) and not args.overwrite:
        print(f"Reusing existing Speedy-Splat model: {model_out}")
        print("Use --overwrite to train again.")
        return 0

    dependency_errors = check_training_dependencies()
    if dependency_errors:
        print("Error: Speedy-Splat training dependencies are not ready.")
        for error in dependency_errors:
            print(f"- {error}")
        print("\nExpected setup:")
        print("1. Install a CUDA-enabled PyTorch build for your Python environment.")
        print("2. Run: git -C third_party/speedy-splat submodule update --init --recursive")
        print("3. Run: pip install third_party/speedy-splat/submodules/diff-gaussian-rasterization")
        print("4. Run: pip install third_party/speedy-splat/submodules/simple-knn")
        return 1

    model_out.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(train_py),
        "--source_path",
        str(dataset),
        "--model_path",
        str(model_out),
        "--resolution",
        str(args.resolution),
        "--iterations",
        str(args.iterations),
        "--position_lr_init",
        "0.001",
        "--position_lr_final",
        "0.0001",
        "--feature_lr",
        "0.0001",
        "--scaling_lr",
        "0.0001",
        "--rotation_lr",
        "0.0001",
        "--percent_dense",
        "0.8",
        "--lambda_dssim",
        "0.5",
        "--densification_interval",
        "1000",
        "--checkpoint_iterations",
        "500",
        "--save_iterations",
        str(args.iterations),
    ]

    print("Running Speedy-Splat training:")
    print(subprocess.list2cmdline(command))
    result = subprocess.run(command, cwd=str(SPEEDY_SPLAT_DIR))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

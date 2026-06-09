from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEEDY_SPLAT_REPO = "https://github.com/j-alex-hanson/speedy-splat.git"
SPEEDY_SPLAT_DIR = ROOT / "third_party" / "speedy-splat"
DIFF_RASTER_DIR = SPEEDY_SPLAT_DIR / "submodules" / "diff-gaussian-rasterization"
SIMPLE_KNN_DIR = SPEEDY_SPLAT_DIR / "submodules" / "simple-knn"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check and optionally install 3DGS demo dependencies.")
    parser.add_argument(
        "--install-speedy-splat",
        action="store_true",
        help="Clone Speedy-Splat into third_party/speedy-splat if it is missing.",
    )
    parser.add_argument(
        "--install-cuda-torch",
        action="store_true",
        help="Install CUDA-enabled PyTorch wheels for this Python environment.",
    )
    parser.add_argument(
        "--torch-cuda-index",
        default="https://download.pytorch.org/whl/cu121",
        help="PyTorch wheel index URL used by --install-cuda-torch.",
    )
    parser.add_argument(
        "--install-speedy-splat-extensions",
        action="store_true",
        help="Build/install Speedy-Splat CUDA extensions after submodules are initialized.",
    )
    return parser.parse_args()


def command_exists(name: str) -> bool:
    if shutil.which(name):
        return True
    if name == "colmap" and Path("C:/colmap/bin/colmap.exe").exists():
        return True
    return False


def check_python_module(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def submodules_ready() -> bool:
    required_paths = [
        DIFF_RASTER_DIR / "setup.py",
        SIMPLE_KNN_DIR / "setup.py",
    ]
    return all(path.exists() for path in required_paths)


def check_node() -> tuple[bool, str]:
    node = shutil.which("node")
    if not node:
        return False, "node not found"

    result = subprocess.run([node, "--version"], capture_output=True, text=True)
    version_text = result.stdout.strip().lstrip("v")
    major_text = version_text.split(".", maxsplit=1)[0]
    try:
        major = int(major_text)
    except ValueError:
        return False, f"could not parse Node version: {version_text}"
    return major >= 18, f"node v{version_text}"


def check_torch_cuda() -> tuple[bool, str]:
    try:
        import torch
    except ImportError:
        return False, "torch not installed"

    if torch.cuda.is_available():
        return True, f"torch {torch.__version__}, CUDA available"
    return False, f"torch {torch.__version__}, CUDA not available"


def clone_speedy_splat() -> bool:
    git = shutil.which("git")
    if not git:
        print("FAIL git: git not found; cannot clone Speedy-Splat.")
        return False

    SPEEDY_SPLAT_DIR.parent.mkdir(parents=True, exist_ok=True)
    if not SPEEDY_SPLAT_DIR.exists():
        result = subprocess.run([git, "clone", "--recursive", SPEEDY_SPLAT_REPO, str(SPEEDY_SPLAT_DIR)])
        if result.returncode != 0:
            return False

    result = subprocess.run([git, "-C", str(SPEEDY_SPLAT_DIR), "submodule", "update", "--init", "--recursive"])
    return result.returncode == 0


def install_cuda_torch(index_url: str) -> bool:
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--force-reinstall",
        "torch",
        "torchvision",
        "torchaudio",
        "--index-url",
        index_url,
    ]
    result = subprocess.run(command)
    return result.returncode == 0


def install_speedy_splat_extensions() -> bool:
    if not submodules_ready():
        print("FAIL speedy-splat-submodules: run --install-speedy-splat first.")
        return False

    commands = [
        [sys.executable, "-m", "pip", "install", "ninja", "cmake"],
        [sys.executable, "-m", "pip", "install", str(DIFF_RASTER_DIR)],
        [sys.executable, "-m", "pip", "install", str(SIMPLE_KNN_DIR)],
    ]
    for command in commands:
        result = subprocess.run(command)
        if result.returncode != 0:
            return False
    return True


def main() -> int:
    args = parse_args()
    checks: list[tuple[str, bool, str]] = []

    if args.install_cuda_torch and not install_cuda_torch(args.torch_cuda_index):
        return 1

    required_checks: set[str] = {"colmap", "git"}
    optional_checks: set[str] = {"ffmpeg", "npm", "node>=18", "torch+cuda"}

    for command in ["ffmpeg", "colmap", "git", "npm", "cl", "cmake", "ninja"]:
        checks.append((command, command_exists(command), "found" if command_exists(command) else "not found"))

    node_ok, node_message = check_node()
    checks.append(("node>=18", node_ok, node_message))

    for module_name in ["cv2", "numpy", "pandas", "yaml", "plyfile"]:
        checks.append((f"python:{module_name}", check_python_module(module_name), "importable"))

    cuda_ok, cuda_message = check_torch_cuda()
    checks.append(("torch+cuda", cuda_ok, cuda_message))

    if args.install_speedy_splat:
        speedy_ok = clone_speedy_splat()
        checks.append(("speedy-splat", speedy_ok, str(SPEEDY_SPLAT_DIR)))
    else:
        checks.append(("speedy-splat", SPEEDY_SPLAT_DIR.exists(), str(SPEEDY_SPLAT_DIR)))

    if args.install_speedy_splat_extensions and not install_speedy_splat_extensions():
        return 1

    checks.append(("speedy-splat-submodules", submodules_ready(), "initialized" if submodules_ready() else "missing"))
    checks.append(
        (
            "diff_gaussian_rasterization",
            check_python_module("diff_gaussian_rasterization"),
            "importable",
        )
    )
    checks.append(("simple_knn", check_python_module("simple_knn"), "importable"))
    required_checks.update(
        {
            "speedy-splat",
            "speedy-splat-submodules",
            "diff_gaussian_rasterization",
            "simple_knn",
        }
    )

    failed_required = []
    for name, ok, message in checks:
        status = "OK" if ok else "FAIL"
        print(f"{status:4} {name}: {message}")
        if not ok and name in required_checks:
            failed_required.append(name)

    if not cuda_ok:
        print("Warning: CUDA is required for practical Speedy-Splat training; CPU training is not a demo path.")
    if not node_ok or not command_exists("npm"):
        print("Warning: Node.js/npm is required to launch the local web viewer.")
    if not command_exists("ffmpeg"):
        print("Warning: ffmpeg is optional for this pipeline because frame extraction uses OpenCV.")
    if not command_exists("cl"):
        print("Warning: cl.exe was not found. Install Visual Studio Build Tools C++ before building Speedy-Splat extensions.")

    if failed_required:
        print("\nMissing required dependencies:", ", ".join(failed_required))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

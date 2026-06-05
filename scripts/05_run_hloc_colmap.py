from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.reconstruction.colmap_utils import find_colmap_executable
from src.utils.io import list_images


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run plain COLMAP automatic reconstruction for selected frames."
    )
    parser.add_argument("--scene", required=True, help="Scene name.")
    parser.add_argument("--policy", required=True, help="Frame filtering policy name.")
    parser.add_argument("--images", required=True, type=Path, help="Selected image folder.")
    parser.add_argument("--workspace", required=True, type=Path, help="COLMAP workspace folder.")
    parser.add_argument("--quality", default="medium", help="COLMAP quality setting.")
    parser.add_argument("--camera-model", default="SIMPLE_RADIAL", help="COLMAP camera model.")
    parser.add_argument("--single-camera", default=1, type=int, help="Use one shared camera.")
    parser.add_argument("--use-gpu", default=1, type=int, help="Use GPU if available.")
    parser.add_argument("--overwrite", action="store_true", help="Allow existing workspace output.")
    return parser.parse_args()


def workspace_has_reconstruction(workspace: Path) -> bool:
    sparse_root = workspace / "sparse"
    dense_root = workspace / "dense"
    database_path = workspace / "database.db"
    return sparse_root.exists() or dense_root.exists() or database_path.exists()


def main() -> int:
    args = parse_args()

    colmap = find_colmap_executable()
    if colmap is None:
        print("Error: COLMAP command was not found on PATH.")
        print("Also checked: C:\\colmap\\bin\\colmap.exe")
        return 1
    print(f"Using COLMAP: {colmap}")

    if not args.images.exists():
        print(f"Error: image folder not found: {args.images}")
        return 1
    image_paths = list_images(args.images)
    if not image_paths:
        print(f"Error: no images found in: {args.images}")
        return 1

    args.workspace.mkdir(parents=True, exist_ok=True)
    if workspace_has_reconstruction(args.workspace) and not args.overwrite:
        print(f"Warning: workspace already contains COLMAP output: {args.workspace}")
        print("Use --overwrite to run COLMAP in this workspace anyway.")
        return 1

    log_path = args.workspace / "colmap_run.log"
    command = [
        colmap,
        "automatic_reconstructor",
        "--workspace_path",
        str(args.workspace),
        "--image_path",
        str(args.images),
        "--camera_model",
        args.camera_model,
        "--single_camera",
        str(args.single_camera),
        "--quality",
        args.quality,
    ]
    if args.use_gpu == 0:
        command.extend(["--use_gpu", "0"])

    print(f"Scene: {args.scene}")
    print(f"Policy: {args.policy}")
    print(f"Images: {args.images} ({len(image_paths)} files)")
    print(f"Workspace: {args.workspace}")
    print("Running COLMAP automatic_reconstructor...")

    result = subprocess.run(command, capture_output=True, text=True)
    with log_path.open("w", encoding="utf-8") as f:
        f.write("Command:\n")
        f.write(subprocess.list2cmdline(command))
        f.write("\n\nSTDOUT:\n")
        f.write(result.stdout)
        f.write("\n\nSTDERR:\n")
        f.write(result.stderr)

    print(f"Saved COLMAP log: {log_path}")
    if result.returncode != 0:
        print(f"Error: COLMAP failed with exit code {result.returncode}.")
        return result.returncode

    print("COLMAP reconstruction finished successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

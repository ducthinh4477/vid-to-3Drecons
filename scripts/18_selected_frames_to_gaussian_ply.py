from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    parser = argparse.ArgumentParser(description="Run selected frames through GraphDECO gaussian-splatting and collect point_cloud.ply.")
    parser.add_argument("--scene", required=True)
    parser.add_argument("--policy", default="medium_filter")
    parser.add_argument("--iterations", default=7000, type=int)
    parser.add_argument("--resolution", default=4, type=int)
    parser.add_argument("--gaussian-root", type=Path, default=None)
    parser.add_argument("--vis-root", type=Path, default=None)
    parser.add_argument("--skip-train", action="store_true", help="Prepare/convert only, then collect an existing trained PLY if present.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_dir = ROOT / "data" / "frames_selected" / args.scene / args.policy
    gaussian_root = resolve_gaussian_root(args.gaussian_root)
    vis_root = resolve_vis_root(args.vis_root)
    paths = gaussian_paths(args.scene, args.policy)

    validate_external_repos(gaussian_root, vis_root)
    count = prepare_dataset_from_selected_frames(selected_dir, paths)
    print(f"Prepared {count} frames: {paths.input_dir}")

    if has_converted_dataset(paths.dataset_dir):
        print(f"Using cached converted dataset: {paths.dataset_dir}")
    else:
        code = run_convert_with_fallback(gaussian_root, paths.dataset_dir, lambda line: print(line, end="" if line.endswith("\n") else "\n"))
        if code != 0:
            return code

    if args.skip_train:
        print("Skipping train.py by request.")
    elif has_trained_point_cloud(paths.model_dir, args.iterations):
        print(f"Using cached trained model: {paths.model_dir}")
    else:
        code = run_subprocess_stream(
            train_command(gaussian_root, paths.dataset_dir, paths.model_dir, args.iterations, args.resolution),
            gaussian_root,
            lambda line: print(line, end="" if line.endswith("\n") else "\n"),
        )
        if code != 0:
            return code

    result = collect_point_cloud(args.scene, args.policy, paths, vis_root, gaussian_root)
    print(f"Collected PLY: {result.output_ply}")
    print(f"ViS-3DGS target manifest: {result.vis_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

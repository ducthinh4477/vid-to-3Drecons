from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect a trained 3DGS PLY into an outputs/demo package.")
    parser.add_argument("--scene", required=True, help="Scene name, for example scene01.")
    parser.add_argument("--policy", required=True, help="Frame filtering policy, for example light_filter.")
    parser.add_argument("--model-dir", required=True, type=Path, help="3DGS output model directory.")
    parser.add_argument("--iteration", type=int, help="Iteration number to collect. Uses latest if omitted.")
    parser.add_argument("--out", type=Path, help="Demo output directory.")
    return parser.parse_args()


def default_demo_dir(scene: str, policy: str) -> Path:
    return ROOT / "outputs" / "demo" / f"{scene}_{policy}"


def find_point_cloud(model_dir: Path, iteration: int | None) -> Path | None:
    point_cloud_root = model_dir / "point_cloud"
    if iteration is not None:
        candidate = point_cloud_root / f"iteration_{iteration}" / "point_cloud.ply"
        return candidate if candidate.exists() else None

    candidates = sorted(point_cloud_root.glob("iteration_*/point_cloud.ply"))
    if not candidates:
        return None

    def key(path: Path) -> int:
        suffix = path.parent.name.removeprefix("iteration_")
        return int(suffix) if suffix.isdigit() else -1

    return max(candidates, key=key)


def iteration_from_path(path: Path) -> int | None:
    suffix = path.parent.name.removeprefix("iteration_")
    return int(suffix) if suffix.isdigit() else None


def copy_metrics(scene: str, policy: str, demo_dir: Path) -> str | None:
    metrics_source = ROOT / "outputs" / "reconstructions" / scene / policy / "metrics.json"
    if not metrics_source.exists():
        return None
    metrics_target = demo_dir / "metrics.json"
    shutil.copy2(metrics_source, metrics_target)
    return metrics_target.name


def main() -> int:
    args = parse_args()
    model_dir = args.model_dir.resolve()
    demo_dir = args.out or default_demo_dir(args.scene, args.policy)

    if not model_dir.exists():
        print(f"Error: model directory not found: {model_dir}")
        return 1

    source_ply = find_point_cloud(model_dir, args.iteration)
    if source_ply is None:
        print("Error: 3DGS output not found; train 3DGS first.")
        print(f"Looked under: {model_dir / 'point_cloud'}")
        if args.iteration is not None:
            print(f"Requested iteration: {args.iteration}")
        return 1

    demo_dir.mkdir(parents=True, exist_ok=True)
    splat_target = demo_dir / "point_cloud.ply"
    shutil.copy2(source_ply, splat_target)
    metrics_file = copy_metrics(args.scene, args.policy, demo_dir)

    manifest = {
        "version": 1,
        "kind": "vid_to_3drecons_demo",
        "scene": args.scene,
        "policy": args.policy,
        "splat_file": splat_target.name,
        "metrics_file": metrics_file,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_model_dir": str(model_dir).replace("\\", "/"),
        "source_point_cloud": str(source_ply.resolve()).replace("\\", "/"),
        "iteration": args.iteration if args.iteration is not None else iteration_from_path(source_ply),
    }
    with (demo_dir / "demo_manifest.json").open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("3DGS demo output collected.")
    print(f"Source PLY: {source_ply}")
    print(f"Demo folder: {demo_dir}")
    print(f"Splat file: {splat_target}")
    if metrics_file:
        print(f"Metrics copied: {demo_dir / metrics_file}")
    else:
        print("Metrics copied: no metrics.json found for this scene/policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

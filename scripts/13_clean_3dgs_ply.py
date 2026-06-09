from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.reconstruction.gsplat_utils import CleanConfig, clean_ply
from web.backend.artifact_service import inspect_ply


def parse_quantile(text: str) -> tuple[float, float]:
    parts = [part.strip() for part in text.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("expected two comma-separated numbers, for example 0.01,0.99")
    return float(parts[0]), float(parts[1])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean noisy splats from a 3DGS PLY and write viewer metadata.")
    parser.add_argument("--input", required=True, type=Path, help="Input point_cloud.ply.")
    parser.add_argument("--out", required=True, type=Path, help="Output cleaned PLY.")
    parser.add_argument("--scene-json", type=Path, help="Output viewer_scene.json path.")
    parser.add_argument("--opacity-min", default=0.03, type=float, help="Minimum opacity probability to keep.")
    parser.add_argument("--scale-percentile-max", default=99.5, type=float, help="Maximum scale percentile to keep.")
    parser.add_argument(
        "--position-quantile",
        default=(0.01, 0.99),
        type=parse_quantile,
        help="Spatial quantile crop as low,high.",
    )
    parser.add_argument("--bounds-padding-ratio", default=0.10, type=float, help="Bounds padding ratio.")
    parser.add_argument("--viewer-alpha-threshold", default=1, type=int, help="Viewer alpha threshold 0-255.")
    parser.add_argument("--move-speed", default=3.0, type=float, help="Viewer FPS movement speed.")
    parser.add_argument("--no-clean", action="store_true", help="Copy the original PLY without filtering.")
    parser.add_argument("--no-crop", action="store_true", help="Disable spatial quantile crop while cleaning.")
    parser.add_argument("--axis-preset", default="colmap_room", help="Viewer axis preset metadata.")
    parser.add_argument("--keep-original", action="store_true", help="Also keep a copy of the original PLY next to --out.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.input.exists():
        print(f"Error: input PLY not found: {args.input}")
        return 1

    scene_json = args.scene_json or (args.out.parent / "viewer_scene.json")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    scene_json.parent.mkdir(parents=True, exist_ok=True)

    if args.keep_original:
        shutil.copy2(args.input, args.out.parent / f"{args.input.stem}.original{args.input.suffix}")

    if args.no_clean:
        shutil.copy2(args.input, args.out)
        try:
            info = inspect_ply(args.out)
        except Exception as exc:
            print(f"Error: failed to inspect copied PLY: {exc}")
            return 1
        scene = {
            "version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "splat": args.out.name,
            "splat_url": args.out.name,
            "asset_type": info.get("asset_type"),
            "bounds": info.get("bounds") or {"min": [-1, -1, -1], "max": [1, 1, 1]},
            "camera": {"position": [0, 1, 3], "look_at": [0, 0, 0], "fov": 60},
            "transform": {"axisPreset": args.axis_preset},
            "cleaning": {"enabled": False, "count_before": info.get("vertex_count"), "count_after": info.get("vertex_count"), "removed": 0},
        }
        with scene_json.open("w", encoding="utf-8") as f:
            json.dump(scene, f, indent=2)
        print("PLY copied without cleaning.")
        print(f"Input: {args.input}")
        print(f"Output: {args.out}")
        print(f"Viewer scene JSON: {scene_json}")
        return 0

    position_quantile = (0.0, 1.0) if args.no_crop else args.position_quantile
    config = CleanConfig(
        opacity_min=args.opacity_min,
        scale_percentile_max=args.scale_percentile_max,
        position_quantile=position_quantile,
        bounds_padding_ratio=args.bounds_padding_ratio,
        viewer_alpha_threshold=args.viewer_alpha_threshold,
        move_speed=args.move_speed,
    )

    try:
        scene = clean_ply(args.input, args.out, scene_json, config)
    except Exception as exc:
        print(f"Error: failed to clean PLY: {exc}")
        return 1

    cleaning = scene["cleaning"]
    print("3DGS PLY cleaned.")
    print(f"Input: {args.input}")
    print(f"Output: {args.out}")
    print(f"Viewer scene JSON: {scene_json}")
    print(f"Splats: {cleaning['count_before']} -> {cleaning['count_after']} ({cleaning['removed']} removed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

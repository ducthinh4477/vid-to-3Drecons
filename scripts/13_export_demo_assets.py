from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from plyfile import PlyData


ROOT = Path(__file__).resolve().parents[1]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export static assets for the 3DGS visual demo layer.")
    parser.add_argument("--scene", required=True, help="Scene name, for example scene01.")
    parser.add_argument("--policy", required=True, help="Frame filtering policy, for example light_filter.")
    parser.add_argument("--demo-dir", type=Path, help="Existing outputs/demo/<scene>_<policy> folder.")
    parser.add_argument("--thumbnail-count", default=18, type=int, help="Representative selected-frame thumbnails to copy.")
    return parser.parse_args()


def demo_dir(scene: str, policy: str) -> Path:
    return ROOT / "outputs" / "demo" / f"{scene}_{policy}"


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def ply_points(path: Path) -> np.ndarray:
    ply = PlyData.read(str(path))
    if "vertex" not in ply:
        raise ValueError(f"PLY does not contain vertex data: {path}")
    vertex = ply["vertex"].data
    names = set(vertex.dtype.names or [])
    if not {"x", "y", "z"}.issubset(names):
        raise ValueError(f"PLY vertex data must contain x, y, z: {path}")
    return np.column_stack(
        [
            np.asarray(vertex["x"], dtype=np.float64),
            np.asarray(vertex["y"], dtype=np.float64),
            np.asarray(vertex["z"], dtype=np.float64),
        ]
    )


def bounds_and_camera(points: np.ndarray) -> tuple[dict[str, list[float]], dict[str, Any]]:
    if points.size == 0:
        min_xyz = np.array([-1.0, -1.0, -1.0], dtype=np.float64)
        max_xyz = np.array([1.0, 1.0, 1.0], dtype=np.float64)
        focus = np.zeros(3, dtype=np.float64)
    else:
        min_xyz = np.min(points, axis=0)
        max_xyz = np.max(points, axis=0)
        focus = np.median(points, axis=0)

    extent = np.maximum(max_xyz - min_xyz, 1e-6)
    padding = extent * 0.10
    min_xyz = min_xyz - padding
    max_xyz = max_xyz + padding
    center = (min_xyz + max_xyz) * 0.5
    size = max_xyz - min_xyz
    focus = np.minimum(np.maximum(focus, min_xyz + size * 0.02), max_xyz - size * 0.02)
    position = focus.copy()
    position[1] = min_xyz[1] + size[1] * 0.12
    position = np.minimum(np.maximum(position, min_xyz + size * 0.02), max_xyz - size * 0.02)
    if float(np.linalg.norm(focus - position)) < 1e-3:
        focus[1] = min(max_xyz[1], position[1] + max(size[1] * 0.25, 1.0))

    radius = max(float(np.linalg.norm(size)), 1.0)
    bounds = {
        "min": min_xyz.astype(float).tolist(),
        "max": max_xyz.astype(float).tolist(),
        "center": center.astype(float).tolist(),
        "size": size.astype(float).tolist(),
    }
    camera = {
        "position": position.astype(float).tolist(),
        "look_at": focus.astype(float).tolist(),
        "fov": 70,
        "near": 0.01,
        "far": max(radius * 5.0, 100.0),
    }
    return bounds, camera


def supersplat_settings(camera: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": 2,
        "tonemapping": "none",
        "highPrecisionRendering": False,
        "background": {"color": [0.02, 0.025, 0.03]},
        "postEffectSettings": {
            "sharpness": {"enabled": False, "amount": 0},
            "bloom": {"enabled": False, "intensity": 1, "blurLevel": 2},
            "grading": {"enabled": False, "brightness": 0, "contrast": 1, "saturation": 1, "tint": [1, 1, 1]},
            "vignette": {"enabled": False, "intensity": 0.5, "inner": 0.3, "outer": 0.75, "curvature": 1},
            "fringing": {"enabled": False, "intensity": 0.5},
        },
        "animTracks": [],
        "cameras": [
            {
                "initial": {
                    "position": camera["position"],
                    "target": camera["look_at"],
                    "fov": camera["fov"],
                }
            }
        ],
        "annotations": [],
        "startMode": "default",
    }


def selected_frames(scene: str, policy: str) -> list[Path]:
    source = ROOT / "data" / "frames_selected" / scene / policy
    if not source.exists():
        return []
    return sorted(path for path in source.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)


def representative_subset(paths: list[Path], count: int) -> list[Path]:
    if count <= 0 or len(paths) <= count:
        return paths
    indexes = np.linspace(0, len(paths) - 1, count, dtype=int)
    return [paths[int(index)] for index in indexes]


def copy_thumbnails(scene: str, policy: str, output_dir: Path, count: int) -> list[str]:
    thumbs_dir = output_dir / "thumbnails"
    if thumbs_dir.exists():
        shutil.rmtree(thumbs_dir)
    thumbs_dir.mkdir(parents=True, exist_ok=True)

    copied = []
    for index, source in enumerate(representative_subset(selected_frames(scene, policy), count), start=1):
        target_name = f"{index:02d}_{source.name}"
        shutil.copy2(source, thumbs_dir / target_name)
        copied.append(f"thumbnails/{target_name}")
    return copied


def copy_tree(source: Path, target: Path) -> bool:
    if not source.exists():
        return False
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    return True


def copy_supersplat_viewer(output_dir: Path) -> bool:
    source = ROOT / "viewer" / "node_modules" / "@playcanvas" / "supersplat-viewer" / "public"
    return copy_tree(source, output_dir / "viewer")


def copy_local_viewer(output_dir: Path) -> bool:
    source = ROOT / "viewer" / "dist"
    if not source.exists():
        return False

    for item in source.iterdir():
        target = output_dir / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
    return True


def metrics_summary(metrics: dict[str, Any]) -> dict[str, Any]:
    best = metrics.get("best_sparse_model") or {}
    dense_models = metrics.get("dense_models") or []
    selected_frames = best.get("images") or best.get("registered_images")
    return {
        "selected_frames": selected_frames,
        "registered_images": best.get("registered_images"),
        "sparse_points": best.get("points"),
        "dense_points": metrics.get("dense_fused_points") or (dense_models[0].get("fused_points") if dense_models else None),
        "reprojection_error_px": best.get("mean_reprojection_error_px"),
        "registered_ratio": best.get("registered_ratio"),
    }


def main() -> int:
    args = parse_args()
    output_dir = args.demo_dir or demo_dir(args.scene, args.policy)
    manifest_path = output_dir / "demo_manifest.json"
    splat_path = output_dir / "point_cloud.ply"

    if not output_dir.exists():
        print(f"Error: demo folder not found: {output_dir}")
        print("Run scripts/12_collect_3dgs_output.py first.")
        return 1
    if not splat_path.exists():
        print("Error: 3DGS output not found; train 3DGS first.")
        print(f"Missing demo PLY: {splat_path}")
        return 1

    manifest = read_json(manifest_path)
    points = ply_points(splat_path)
    bounds, camera = bounds_and_camera(points)
    metrics_file = manifest.get("metrics_file")
    metrics = read_json(output_dir / metrics_file) if metrics_file else {}
    thumbnails = copy_thumbnails(args.scene, args.policy, output_dir, args.thumbnail_count)
    supersplat_copied = copy_supersplat_viewer(output_dir)
    local_viewer_copied = copy_local_viewer(output_dir)

    settings = supersplat_settings(camera)
    write_json(output_dir / "settings.json", settings)

    scene_json = {
        "version": 1,
        "kind": "vid_to_3drecons_viewer_scene",
        "splat": "point_cloud.ply",
        "splat_url": "/point_cloud.ply",
        "bounds": bounds,
        "camera": camera,
        "controls": {"mode": "fps_locked", "move_speed": 3.0},
        "render": {"splat_alpha_removal_threshold": 1, "splat_scale": 2.5, "preview_points": False},
        "demo": {
            "scene": args.scene,
            "policy": args.policy,
            "metrics": metrics_summary(metrics),
            "thumbnails": thumbnails,
            "supersplat_url": "/viewer/index.html?content=/point_cloud.ply&settings=/settings.json",
            "local_viewer_url": "/?scene=/scene.json",
        },
    }
    write_json(output_dir / "scene.json", scene_json)

    manifest.update(
        {
            "version": 1,
            "kind": "vid_to_3drecons_demo",
            "scene": args.scene,
            "policy": args.policy,
            "splat_file": "point_cloud.ply",
            "metrics_file": metrics_file if metrics_file else None,
            "settings_file": "settings.json",
            "viewer_scene": "scene.json",
            "thumbnails": thumbnails,
            "metrics_summary": metrics_summary(metrics),
            "supersplat_viewer": "viewer/index.html?content=/point_cloud.ply&settings=/settings.json",
            "local_viewer": "?scene=/demo_manifest.json",
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_json(manifest_path, manifest)

    print("3DGS demo assets exported.")
    print(f"Demo folder: {output_dir}")
    print(f"Settings: {output_dir / 'settings.json'}")
    print(f"Viewer scene: {output_dir / 'scene.json'}")
    print(f"Thumbnails copied: {len(thumbnails)}")
    print(f"SuperSplat viewer copied: {supersplat_copied}")
    print(f"Local viewer copied: {local_viewer_copied}")
    if not supersplat_copied:
        print("Tip: run `npm install` in viewer/ to install @playcanvas/supersplat-viewer.")
    if not local_viewer_copied:
        print("Tip: run `npm run build` in viewer/ before exporting for a self-contained local viewer.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

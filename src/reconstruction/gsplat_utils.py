from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from plyfile import PlyData, PlyElement


@dataclass(frozen=True)
class CleanConfig:
    opacity_min: float = 0.03
    scale_percentile_max: float = 99.5
    position_quantile: tuple[float, float] = (0.01, 0.99)
    bounds_padding_ratio: float = 0.10
    viewer_alpha_threshold: int = 1
    move_speed: float = 3.0


def sigmoid(values: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-values))


def opacity_to_probability(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    if float(np.nanmin(values)) < 0.0 or float(np.nanmax(values)) > 1.0:
        return sigmoid(values)
    return values


def scale_magnitude(vertex: np.ndarray) -> np.ndarray:
    names = set(vertex.dtype.names or [])
    scale_names = sorted(name for name in names if name.startswith("scale_"))
    if scale_names:
        stacked = np.column_stack([np.asarray(vertex[name], dtype=np.float64) for name in scale_names])
        return np.linalg.norm(stacked, axis=1)

    if {"sx", "sy", "sz"}.issubset(names):
        stacked = np.column_stack(
            [
                np.asarray(vertex["sx"], dtype=np.float64),
                np.asarray(vertex["sy"], dtype=np.float64),
                np.asarray(vertex["sz"], dtype=np.float64),
            ]
        )
        return np.linalg.norm(stacked, axis=1)

    return np.zeros(len(vertex), dtype=np.float64)


def compute_bounds(points: np.ndarray, padding_ratio: float) -> dict[str, list[float]]:
    if points.size == 0:
        min_xyz = np.array([-1.0, -1.0, -1.0], dtype=np.float64)
        max_xyz = np.array([1.0, 1.0, 1.0], dtype=np.float64)
    else:
        min_xyz = np.min(points, axis=0)
        max_xyz = np.max(points, axis=0)

    extent = np.maximum(max_xyz - min_xyz, 1e-6)
    padding = extent * float(max(0.0, padding_ratio))
    min_xyz = min_xyz - padding
    max_xyz = max_xyz + padding
    center = (min_xyz + max_xyz) * 0.5
    size = max_xyz - min_xyz

    return {
        "min": min_xyz.astype(float).tolist(),
        "max": max_xyz.astype(float).tolist(),
        "center": center.astype(float).tolist(),
        "size": size.astype(float).tolist(),
    }


def default_camera(bounds: dict[str, list[float]], focus: np.ndarray | None = None) -> dict[str, Any]:
    center = np.asarray(bounds["center"], dtype=np.float64)
    size = np.asarray(bounds["size"], dtype=np.float64)
    min_xyz = np.asarray(bounds["min"], dtype=np.float64)
    max_xyz = np.asarray(bounds["max"], dtype=np.float64)
    radius = max(float(np.linalg.norm(size)), 1.0)
    look_at = np.asarray(focus, dtype=np.float64) if focus is not None else center.copy()
    look_at = np.minimum(np.maximum(look_at, min_xyz + size * 0.02), max_xyz - size * 0.02)

    position = look_at.copy()
    position[1] = min_xyz[1] + size[1] * 0.12
    position = np.minimum(np.maximum(position, min_xyz + size * 0.02), max_xyz - size * 0.02)

    if float(np.linalg.norm(look_at - position)) < 1e-3:
        look_at[1] = min(max_xyz[1], position[1] + max(size[1] * 0.25, 1.0))

    return {
        "position": position.astype(float).tolist(),
        "look_at": look_at.astype(float).tolist(),
        "fov": 70,
        "near": 0.01,
        "far": max(radius * 5.0, 100.0),
    }


def build_clean_mask(vertex: np.ndarray, config: CleanConfig) -> tuple[np.ndarray, dict[str, Any]]:
    names = set(vertex.dtype.names or [])
    if not {"x", "y", "z"}.issubset(names):
        raise ValueError("PLY vertex element must contain x, y, and z properties.")

    count_before = len(vertex)
    points = np.column_stack(
        [
            np.asarray(vertex["x"], dtype=np.float64),
            np.asarray(vertex["y"], dtype=np.float64),
            np.asarray(vertex["z"], dtype=np.float64),
        ]
    )

    mask = np.ones(count_before, dtype=bool)
    opacity_removed = 0
    if "opacity" in names:
        opacity = opacity_to_probability(np.asarray(vertex["opacity"], dtype=np.float64))
        opacity_mask = opacity >= float(config.opacity_min)
        opacity_removed = int(np.count_nonzero(mask & ~opacity_mask))
        mask &= opacity_mask

    scale_removed = 0
    scales = scale_magnitude(vertex)
    if scales.size and np.any(scales > 0):
        scale_limit = float(np.percentile(scales, config.scale_percentile_max))
        scale_mask = scales <= scale_limit
        scale_removed = int(np.count_nonzero(mask & ~scale_mask))
        mask &= scale_mask

    low_q, high_q = config.position_quantile
    low_q = min(max(float(low_q), 0.0), 0.49)
    high_q = min(max(float(high_q), 0.51), 1.0)
    lower = np.quantile(points, low_q, axis=0)
    upper = np.quantile(points, high_q, axis=0)
    spatial_mask = np.all((points >= lower) & (points <= upper), axis=1)
    spatial_removed = int(np.count_nonzero(mask & ~spatial_mask))
    mask &= spatial_mask

    stats = {
        "count_before": int(count_before),
        "count_after": int(np.count_nonzero(mask)),
        "removed": int(count_before - np.count_nonzero(mask)),
        "removed_by_opacity": opacity_removed,
        "removed_by_scale": scale_removed,
        "removed_by_space": spatial_removed,
        "opacity_min": config.opacity_min,
        "scale_percentile_max": config.scale_percentile_max,
        "position_quantile": [low_q, high_q],
    }
    return mask, stats


def clean_ply(input_path: Path, output_path: Path, scene_json_path: Path, config: CleanConfig) -> dict[str, Any]:
    ply = PlyData.read(str(input_path))
    if "vertex" not in ply:
        raise ValueError(f"PLY does not contain a vertex element: {input_path}")

    vertex = ply["vertex"].data
    mask, stats = build_clean_mask(vertex, config)
    cleaned_vertex = vertex[mask]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    elements = []
    for element in ply.elements:
        if element.name == "vertex":
            elements.append(PlyElement.describe(cleaned_vertex, "vertex"))
        else:
            elements.append(element)
    PlyData(elements, text=ply.text, byte_order=ply.byte_order).write(str(output_path))

    points = np.column_stack(
        [
            np.asarray(cleaned_vertex["x"], dtype=np.float64),
            np.asarray(cleaned_vertex["y"], dtype=np.float64),
            np.asarray(cleaned_vertex["z"], dtype=np.float64),
        ]
    )
    bounds = compute_bounds(points, config.bounds_padding_ratio)
    focus = np.median(points, axis=0) if points.size else None
    scene = {
        "version": 1,
        "splat": str(output_path.resolve()).replace("\\", "/"),
        "splat_url": None,
        "bounds": bounds,
        "camera": default_camera(bounds, focus),
        "controls": {
            "mode": "fps_locked",
            "move_speed": config.move_speed,
        },
        "render": {
            "splat_alpha_removal_threshold": int(config.viewer_alpha_threshold),
            "splat_scale": 2.5,
            "preview_points": False,
        },
        "cleaning": stats,
    }

    scene_json_path.parent.mkdir(parents=True, exist_ok=True)
    with scene_json_path.open("w", encoding="utf-8") as f:
        json.dump(scene, f, indent=2)

    return scene


def find_latest_speedy_splat_ply(model_dir: Path) -> Path | None:
    point_cloud_root = model_dir / "point_cloud"
    if not point_cloud_root.exists():
        return None

    candidates = sorted(point_cloud_root.glob("iteration_*/point_cloud.ply"))
    if not candidates:
        return None

    def iteration_number(path: Path) -> int:
        name = path.parent.name
        suffix = name.removeprefix("iteration_")
        if suffix.isdigit():
            return int(suffix)
        if suffix == "final":
            return math.inf  # type: ignore[return-value]
        return -1

    return max(candidates, key=iteration_number)

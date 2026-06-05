from __future__ import annotations

import re
import shutil
from pathlib import Path


def find_colmap_executable() -> str | None:
    colmap = shutil.which("colmap")
    if colmap is not None:
        return colmap

    common_windows_path = Path("C:/colmap/bin/colmap.exe")
    if common_windows_path.exists():
        return str(common_windows_path)

    return None


def find_sparse_models(workspace: Path) -> list[Path]:
    sparse_root = Path(workspace) / "sparse"
    if not sparse_root.exists():
        return []

    required_files = {"cameras.bin", "images.bin", "points3D.bin"}
    models = []
    for folder in sorted(path for path in sparse_root.iterdir() if path.is_dir()):
        folder_files = {path.name for path in folder.iterdir() if path.is_file()}
        if required_files.issubset(folder_files):
            models.append(folder)
    return models


def find_dense_models(workspace: Path) -> list[Path]:
    dense_root = Path(workspace) / "dense"
    if not dense_root.exists():
        return []

    return sorted(
        folder
        for folder in dense_root.iterdir()
        if folder.is_dir() and (folder / "fused.ply").exists()
    )


def count_ply_vertices(ply_path: Path) -> int | None:
    try:
        with Path(ply_path).open("rb") as f:
            for raw_line in f:
                line = raw_line.decode("ascii", errors="ignore").strip()
                if line.startswith("element vertex"):
                    parts = line.split()
                    if len(parts) >= 3:
                        return int(parts[2])
                if line == "end_header":
                    break
    except (OSError, ValueError):
        return None
    return None


def parse_model_analyzer_output(text: str) -> dict:
    line_prefix = r"^(?:.*\]\s*)?"
    patterns = {
        "rigs": line_prefix + r"Rigs:\s*([0-9]+)",
        "cameras": line_prefix + r"Cameras:\s*([0-9]+)",
        "frames": line_prefix + r"Frames:\s*([0-9]+)",
        "registered_frames": line_prefix + r"Registered frames:\s*([0-9]+)",
        "images": line_prefix + r"Images:\s*([0-9]+)",
        "registered_images": line_prefix + r"Registered images:\s*([0-9]+)",
        "points": line_prefix + r"Points:\s*([0-9]+)",
        "observations": line_prefix + r"Observations:\s*([0-9]+)",
        "mean_track_length": line_prefix + r"Mean track length:\s*([0-9.]+)",
        "mean_observations_per_image": line_prefix + r"Mean observations per image:\s*([0-9.]+)",
        "mean_reprojection_error_px": line_prefix + r"Mean reprojection error:\s*([0-9.]+)\s*px",
    }
    integer_keys = {
        "rigs",
        "cameras",
        "frames",
        "registered_frames",
        "images",
        "registered_images",
        "points",
        "observations",
    }

    metrics = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if not match:
            metrics[key] = None
            continue

        value = match.group(1)
        metrics[key] = int(value) if key in integer_keys else float(value)

    return metrics


def choose_best_sparse_model(metrics_list: list[dict]) -> dict:
    if not metrics_list:
        return {}

    def sort_key(metrics: dict) -> tuple[int, int]:
        registered_images = metrics.get("registered_images") or 0
        points = metrics.get("points") or 0
        return int(registered_images), int(points)

    return max(metrics_list, key=sort_key)

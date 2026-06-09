from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.reconstruction.colmap_utils import count_ply_vertices, find_colmap_executable

ROOT = Path(__file__).resolve().parents[2]


def export_colmap_preview(scene: str, policy: str) -> dict:
    workspace = ROOT / "outputs" / "reconstructions" / scene / policy / "colmap"
    demo_dir = ROOT / "outputs" / "demo" / f"{scene}_{policy}"
    demo_dir.mkdir(parents=True, exist_ok=True)
    preview_ply = demo_dir / "colmap_preview.ply"
    preview_json = demo_dir / "preview_points.json"

    fused = workspace / "dense" / "0" / "fused.ply"
    if fused.exists():
        shutil.copy2(fused, preview_ply)
        preview = _ply_to_preview_json(preview_ply, preview_json)
        return {
            "preview_ply": preview_ply,
            "preview_points_json": preview_json if preview_json.exists() else None,
            "point_count": count_ply_vertices(preview_ply),
            "source": fused,
            "bounds": preview.get("bounds"),
        }

    points_txt = _find_points3d_txt(workspace)
    if points_txt is None:
        points_txt = _convert_sparse_bin_to_txt(workspace)

    if points_txt is not None and points_txt.exists():
        preview = _points3d_txt_to_preview(points_txt, preview_json)
        _write_ascii_ply(preview["points"], preview_ply)
        return {
            "preview_ply": preview_ply,
            "preview_points_json": preview_json,
            "point_count": preview["count"],
            "source": points_txt,
            "bounds": preview.get("bounds"),
        }

    _write_preview_json([], preview_json)
    return {
        "preview_ply": None,
        "preview_points_json": preview_json,
        "point_count": 0,
        "source": None,
        "bounds": None,
    }


def _find_points3d_txt(workspace: Path) -> Path | None:
    candidates = [
        workspace / "sparse" / "0" / "points3D.txt",
        workspace / "dense" / "0" / "sparse" / "points3D.txt",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return next(workspace.glob("sparse/*/points3D.txt"), None) if workspace.exists() else None


def _convert_sparse_bin_to_txt(workspace: Path) -> Path | None:
    colmap = find_colmap_executable()
    sparse = workspace / "sparse" / "0"
    if colmap is None or not sparse.exists():
        return None
    out_dir = Path(tempfile.mkdtemp(prefix="colmap_txt_", dir=str(workspace)))
    result = subprocess.run(
        [colmap, "model_converter", "--input_path", str(sparse), "--output_path", str(out_dir), "--output_type", "TXT"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    points = out_dir / "points3D.txt"
    return points if result.returncode == 0 and points.exists() else None


def _points3d_txt_to_preview(points_txt: Path, out_json: Path, limit: int = 120_000) -> dict:
    points = []
    with points_txt.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 7:
                continue
            try:
                xyz = [float(parts[1]), float(parts[2]), float(parts[3])]
                rgb = [int(parts[4]), int(parts[5]), int(parts[6])]
            except ValueError:
                continue
            points.append({"xyz": xyz, "rgb": rgb})
            if len(points) >= limit:
                break
    return _write_preview_json(points, out_json)


def _ply_to_preview_json(ply_path: Path, out_json: Path, limit: int = 120_000) -> dict:
    try:
        from plyfile import PlyData

        ply = PlyData.read(str(ply_path))
        vertex = ply["vertex"].data
        stride = max(len(vertex) // limit, 1)
        points = []
        names = set(vertex.dtype.names or [])
        has_color = {"red", "green", "blue"}.issubset(names)
        for row in vertex[::stride]:
            rgb = [210, 226, 245]
            if has_color:
                rgb = [int(row["red"]), int(row["green"]), int(row["blue"])]
            points.append({"xyz": [float(row["x"]), float(row["y"]), float(row["z"])], "rgb": rgb})
        return _write_preview_json(points, out_json)
    except Exception:
        return {}


def _write_preview_json(points: list[dict], out_json: Path) -> dict:
    positions: list[float] = []
    colors: list[float] = []
    mins = [float("inf"), float("inf"), float("inf")]
    maxs = [float("-inf"), float("-inf"), float("-inf")]
    for point in points:
        xyz = point["xyz"]
        rgb = point["rgb"]
        positions.extend(xyz)
        colors.extend([channel / 255.0 for channel in rgb])
        for index, value in enumerate(xyz):
            mins[index] = min(mins[index], value)
            maxs[index] = max(maxs[index], value)

    bounds = None
    if points:
        bounds = {"min": mins, "max": maxs}
    payload = {"count": len(points), "positions": positions, "colors": colors, "bounds": bounds}
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(payload, f)
    return {"count": len(points), "points": points, "bounds": bounds}


def _write_ascii_ply(points: list[dict], out_ply: Path) -> None:
    out_ply.parent.mkdir(parents=True, exist_ok=True)
    with out_ply.open("w", encoding="ascii") as f:
        f.write("ply\nformat ascii 1.0\n")
        f.write(f"element vertex {len(points)}\n")
        f.write("property float x\nproperty float y\nproperty float z\n")
        f.write("property uchar red\nproperty uchar green\nproperty uchar blue\n")
        f.write("end_header\n")
        for point in points:
            x, y, z = point["xyz"]
            r, g, b = point["rgb"]
            f.write(f"{x} {y} {z} {r} {g} {b}\n")

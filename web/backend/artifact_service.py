from __future__ import annotations

import csv
import json
import mimetypes
import shutil
import uuid
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException, UploadFile
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[2]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MODEL_EXTENSIONS = {".ply", ".splat", ".gsplat", ".ksplat", ".compressed.ply"}
ALLOWED_ROOTS = [
    ROOT / "data",
    ROOT / "outputs",
]
UPLOAD_PLY_ROOT = ROOT / "data" / "demo_uploads" / "ply"


def to_project_path(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = ROOT / candidate
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid path: {path}") from exc

    allowed = [ROOT.resolve(), *(root.resolve() for root in ALLOWED_ROOTS)]
    if not any(resolved == root or root in resolved.parents for root in allowed):
        raise HTTPException(status_code=403, detail="Path is outside the project workspace.")
    return resolved


def project_rel(path: str | Path) -> str:
    resolved = to_project_path(path)
    return resolved.relative_to(ROOT.resolve()).as_posix()


def artifact_url(path: str | Path | None) -> str | None:
    if not path:
        return None
    return f"/api/artifacts/file?path={quote(project_rel(path))}"


def serve_artifact(path: str) -> FileResponse:
    resolved = to_project_path(path)
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Artifact file not found.")

    media_type = mimetypes.guess_type(resolved.name)[0]
    if resolved.suffix.lower() in {".splat", ".gsplat", ".ksplat"}:
        media_type = "application/octet-stream"
    return FileResponse(resolved, media_type=media_type)


def upload_ply(file: UploadFile) -> dict:
    name = Path(file.filename or "upload.ply").name
    if Path(name).suffix.lower() != ".ply":
        raise HTTPException(status_code=400, detail="Only .ply files are supported.")
    upload_id = uuid.uuid4().hex[:10]
    folder = UPLOAD_PLY_ROOT / upload_id
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / name
    with target.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    info = inspect_ply(target)
    return {
        "asset_url": artifact_url(target),
        "path": project_rel(target),
        "name": name,
        "type": "ply",
        "ply": info,
    }


def inspect_ply(path: str | Path) -> dict:
    resolved = to_project_path(path)
    if not resolved.exists() or resolved.suffix.lower() != ".ply":
        raise HTTPException(status_code=404, detail="PLY file not found.")
    header = _read_ply_header(resolved)
    props = header["properties"]
    prop_names = {prop["name"] for prop in props}
    ply_type = "unknown"
    if {"x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity"}.issubset(prop_names):
        ply_type = "gaussian_splat"
    elif {"x", "y", "z"}.issubset(prop_names):
        ply_type = "point_cloud"

    bounds = None
    color = "none"
    if {"red", "green", "blue"}.issubset(prop_names):
        color = "rgb"
    elif {"f_dc_0", "f_dc_1", "f_dc_2"}.issubset(prop_names):
        color = "f_dc"
    try:
        from plyfile import PlyData

        ply = PlyData.read(str(resolved))
        vertex = ply["vertex"].data
        if len(vertex) and {"x", "y", "z"}.issubset(prop_names):
            bounds = {
                "min": [float(vertex["x"].min()), float(vertex["y"].min()), float(vertex["z"].min())],
                "max": [float(vertex["x"].max()), float(vertex["y"].max()), float(vertex["z"].max())],
            }
    except Exception:
        bounds = None
    return {
        "name": resolved.name,
        "path": project_rel(resolved),
        "url": artifact_url(resolved),
        "format": header["format"],
        "vertex_count": header["vertex_count"],
        "properties": [prop["name"] for prop in props],
        "asset_type": ply_type,
        "color": color,
        "bounds": bounds,
    }


def _read_ply_header(path: Path) -> dict:
    properties: list[dict[str, str]] = []
    vertex_count = 0
    ply_format = "unknown"
    in_vertex = False
    with path.open("rb") as f:
        for raw in f:
            line = raw.decode("ascii", errors="ignore").strip()
            if line.startswith("format "):
                ply_format = line
            elif line.startswith("element "):
                parts = line.split()
                in_vertex = len(parts) >= 3 and parts[1] == "vertex"
                if in_vertex:
                    try:
                        vertex_count = int(parts[2])
                    except ValueError:
                        vertex_count = 0
            elif in_vertex and line.startswith("property "):
                parts = line.split()
                if len(parts) >= 3:
                    properties.append({"type": parts[-2], "name": parts[-1]})
            elif line == "end_header":
                break
    if not properties:
        raise HTTPException(status_code=400, detail="Invalid or unsupported PLY header.")
    return {"format": ply_format, "vertex_count": vertex_count, "properties": properties}


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(payload: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def list_media_files(folder: Path, extensions: set[str]) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in extensions
    )


def sample_evenly(paths: list[Path], limit: int = 18) -> list[Path]:
    if len(paths) <= limit:
        return paths
    step = (len(paths) - 1) / max(limit - 1, 1)
    return [paths[round(index * step)] for index in range(limit)]


def read_quality_summary(csv_path: Path) -> dict:
    if not csv_path.exists():
        return {}
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    if not rows:
        return {}

    def values(key: str) -> list[float]:
        parsed = []
        for row in rows:
            try:
                parsed.append(float(row.get(key) or "nan"))
            except ValueError:
                continue
        return [value for value in parsed if value == value]

    scores = values("quality_score")
    sharpness = values("sharpness")
    keypoints = values("keypoints_orb")
    chart_rows = []
    for row in sample_evenly(rows, 80):
        chart_rows.append(
            {
                "frame": row.get("frame_name") or row.get("frame_index"),
                "quality_score": _float_or_none(row.get("quality_score")),
                "sharpness": _float_or_none(row.get("sharpness")),
                "keypoints_orb": _float_or_none(row.get("keypoints_orb")),
            }
        )
    return {
        "frame_count": len(rows),
        "quality_score_mean": sum(scores) / len(scores) if scores else None,
        "quality_score_min": min(scores) if scores else None,
        "quality_score_max": max(scores) if scores else None,
        "sharpness_mean": sum(sharpness) / len(sharpness) if sharpness else None,
        "keypoints_orb_mean": sum(keypoints) / len(keypoints) if keypoints else None,
        "chart": chart_rows,
    }


def _float_or_none(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None

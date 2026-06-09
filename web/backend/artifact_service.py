from __future__ import annotations

import csv
import json
import mimetypes
from pathlib import Path
from urllib.parse import quote

from fastapi import HTTPException
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parents[2]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
MODEL_EXTENSIONS = {".ply", ".splat", ".gsplat", ".ksplat", ".compressed.ply"}
ALLOWED_ROOTS = [
    ROOT / "data",
    ROOT / "outputs",
]


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

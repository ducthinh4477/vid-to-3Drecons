from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def ensure_dir(path: str | Path) -> Path:
    """Create a directory if needed and return it as a Path."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def load_yaml(path: str | Path) -> dict[str, Any]:
    yaml_path = Path(path)
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def save_json(obj: Any, path: str | Path) -> Path:
    json_path = Path(path)
    ensure_dir(json_path.parent)
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    return json_path


def list_images(directory: str | Path) -> list[Path]:
    image_dir = Path(directory)
    if not image_dir.exists():
        return []
    return sorted(
        path
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def copy_image(src: str | Path, dst: str | Path) -> Path:
    src_path = Path(src)
    dst_path = Path(dst)
    ensure_dir(dst_path.parent)
    shutil.copy2(src_path, dst_path)
    return dst_path

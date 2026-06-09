from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.backend.colmap_exporter import export_colmap_preview


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export a lightweight COLMAP preview for the one-page demo.")
    parser.add_argument("--scene", required=True)
    parser.add_argument("--policy", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = export_colmap_preview(args.scene, args.policy)
    print(f"Preview PLY: {result.get('preview_ply')}")
    print(f"Preview JSON: {result.get('preview_points_json')}")
    print(f"Point count: {result.get('point_count')}")
    print(f"Source: {result.get('source')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

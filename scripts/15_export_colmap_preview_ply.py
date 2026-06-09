from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from web.backend.colmap_exporter import export_colmap_preview


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export COLMAP fused/sparse points to a preview PLY.")
    parser.add_argument("--scene", required=True)
    parser.add_argument("--policy", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = export_colmap_preview(args.scene, args.policy)
    preview_ply = result.get("preview_ply")
    if not preview_ply:
        print("FAIL: no COLMAP preview PLY could be exported.")
        return 1
    print("PASS: COLMAP preview PLY exported.")
    print(f"PLY: {preview_ply}")
    print(f"Points: {result.get('point_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

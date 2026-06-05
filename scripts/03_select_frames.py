from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.io import copy_image, ensure_dir


POLICIES = {
    "no_filter": {"quality_percentile": None, "max_ssim": None},
    "light_filter": {"quality_percentile": 20, "max_ssim": 0.98},
    "medium_filter": {"quality_percentile": 40, "max_ssim": 0.95},
    "strong_filter": {"quality_percentile": 60, "max_ssim": 0.92},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select frames using quality and redundancy filters.")
    parser.add_argument("--scene", required=True, help="Scene name.")
    parser.add_argument("--frames", required=True, type=Path, help="Input frame directory.")
    parser.add_argument("--quality", required=True, type=Path, help="Frame quality CSV path.")
    parser.add_argument("--policy", required=True, choices=POLICIES.keys(), help="Selection policy.")
    parser.add_argument("--out", required=True, type=Path, help="Output selected-frame directory.")
    return parser.parse_args()


def resolve_frame_path(row: pd.Series, frames_dir: Path) -> Path:
    frame_name = str(row["frame_name"])
    return frames_dir / frame_name


def main() -> int:
    args = parse_args()
    if not args.frames.exists():
        print(f"Error: frame directory not found: {args.frames}")
        return 1
    if not args.quality.exists():
        print(f"Error: quality CSV not found: {args.quality}")
        return 1

    df = pd.read_csv(args.quality)
    if df.empty:
        print(f"Error: quality CSV has no rows: {args.quality}")
        return 1

    policy = POLICIES[args.policy]
    if args.policy == "no_filter":
        selected = df.copy()
        quality_threshold = None
    else:
        quality_threshold = float(df["quality_score"].quantile(policy["quality_percentile"] / 100.0))
        ssim = df["redundancy_ssim_to_prev"]
        selected = df[
            (df["quality_score"] >= quality_threshold)
            & (ssim.isna() | (ssim <= policy["max_ssim"]))
        ].copy()

    out_dir = ensure_dir(args.out)
    copied_paths = []
    for _, row in selected.iterrows():
        src_path = resolve_frame_path(row, args.frames)
        if not src_path.exists():
            print(f"Warning: selected frame missing, skipping copy: {src_path}")
            copied_paths.append("")
            continue
        copied_paths.append(str(copy_image(src_path, out_dir / src_path.name)))

    selected["selected_path"] = copied_paths
    selected_csv = out_dir / "selected_frames.csv"
    selected.to_csv(selected_csv, index=False)

    selected_count = int((selected["selected_path"] != "").sum())
    total_count = int(len(df))
    removal_ratio = 1.0 - (selected_count / total_count)

    print(f"Policy: {args.policy}")
    if quality_threshold is not None:
        print(f"Quality threshold: {quality_threshold:.6f}")
        print(f"Max SSIM to previous: {policy['max_ssim']}")
    print(f"Selected frames: {selected_count} / {total_count}")
    print(f"Removal ratio: {removal_ratio:.2%}")
    print(f"Output folder: {out_dir}")
    print(f"Saved selected CSV: {selected_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

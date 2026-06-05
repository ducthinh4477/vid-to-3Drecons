from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import pandas as pd
from tqdm import tqdm

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.frame_quality.brightness import brightness_metrics
from src.frame_quality.keypoints import orb_keypoint_count
from src.frame_quality.redundancy import ssim_similarity
from src.frame_quality.scoring import compute_quality_scores
from src.frame_quality.sharpness import laplacian_sharpness
from src.utils.io import ensure_dir, list_images, save_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compute frame quality metrics.")
    parser.add_argument("--scene", required=True, help="Scene name.")
    parser.add_argument("--frames", required=True, type=Path, help="Input frame directory.")
    parser.add_argument("--out", required=True, type=Path, help="Output CSV path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame_paths = list_images(args.frames)
    if not args.frames.exists():
        print(f"Error: frame directory not found: {args.frames}")
        return 1
    if not frame_paths:
        print(f"Error: no image files found in: {args.frames}")
        return 1

    rows = []
    prev_image = None
    for frame_index, frame_path in enumerate(tqdm(frame_paths, desc="Frame quality"), start=1):
        image = cv2.imread(str(frame_path), cv2.IMREAD_COLOR)
        if image is None:
            print(f"Warning: skipping unreadable image: {frame_path}")
            continue

        metrics = brightness_metrics(image)
        redundancy = None if prev_image is None else ssim_similarity(prev_image, image)

        rows.append(
            {
                "scene": args.scene,
                "frame_index": frame_index,
                "frame_name": frame_path.name,
                "frame_path": str(frame_path),
                "sharpness": laplacian_sharpness(image),
                **metrics,
                "keypoints_orb": orb_keypoint_count(image),
                "redundancy_ssim_to_prev": redundancy,
            }
        )
        prev_image = image

    if not rows:
        print("Error: no readable images were processed.")
        return 1

    df = compute_quality_scores(pd.DataFrame(rows))
    out_path = args.out
    ensure_dir(out_path.parent)
    df.to_csv(out_path, index=False)

    summary_path = ROOT / "outputs" / "frame_quality" / args.scene / "frame_quality_summary.json"
    summary = {
        "scene": args.scene,
        "frames_dir": str(args.frames),
        "csv": str(out_path),
        "frame_count": int(len(df)),
        "quality_score_mean": float(df["quality_score"].mean()),
        "quality_score_median": float(df["quality_score"].median()),
        "quality_score_min": float(df["quality_score"].min()),
        "quality_score_max": float(df["quality_score"].max()),
        "sharpness_mean": float(df["sharpness"].mean()),
        "keypoints_orb_mean": float(df["keypoints_orb"].mean()),
    }
    save_json(summary, summary_path)

    print(f"Saved quality CSV: {out_path}")
    print(f"Saved summary JSON: {summary_path}")
    print(f"Processed frames: {len(df)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

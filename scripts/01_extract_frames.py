from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.io import ensure_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract sampled frames from a video.")
    parser.add_argument("--video", required=True, type=Path, help="Input video path.")
    parser.add_argument("--scene", required=True, help="Scene name used for output folder.")
    parser.add_argument("--fps", required=True, type=float, help="Target sampling FPS.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    video_path = args.video
    if not video_path.exists():
        print(f"Error: video file not found: {video_path}")
        return 1
    if args.fps <= 0:
        print("Error: --fps must be greater than 0.")
        return 1

    out_dir = ensure_dir(ROOT / "data" / "frames_raw" / args.scene)
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        print(f"Error: OpenCV could not open video: {video_path}")
        return 1

    source_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    saved = 0
    frame_index = 0
    next_sample_time = 0.0
    sample_period = 1.0 / args.fps

    while True:
        ok, frame = capture.read()
        if not ok:
            break

        should_save = False
        if source_fps > 0:
            timestamp = frame_index / source_fps
            if timestamp + 1e-9 >= next_sample_time:
                should_save = True
                next_sample_time += sample_period
        else:
            should_save = True

        if should_save:
            saved += 1
            out_path = out_dir / f"frame_{saved:06d}.jpg"
            cv2.imwrite(str(out_path), frame)

        frame_index += 1

    capture.release()

    print(f"Source FPS: {source_fps:.3f}" if source_fps > 0 else "Source FPS: unknown")
    print(f"Target FPS: {args.fps:g}")
    print(f"Source frames: {total_frames}")
    print(f"Total saved frames: {saved}")
    print(f"Output folder: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

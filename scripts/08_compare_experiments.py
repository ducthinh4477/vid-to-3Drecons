from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
EXPECTED_COLUMNS = [
    "policy",
    "total_frames",
    "selected_frames",
    "removal_ratio",
    "mean_quality_score",
    "mean_sharpness",
    "mean_brightness",
    "mean_keypoints_orb",
    "mean_redundancy_ssim_to_prev",
]
COLMAP_COLUMNS = [
    "policy",
    "images",
    "registered_images",
    "registered_ratio",
    "sparse_points",
    "observations",
    "mean_track_length",
    "mean_observations_per_image",
    "mean_reprojection_error_px",
    "dense_fused_points",
    "sparse_model_path",
    "dense_model_path",
    "success",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare frame filtering or COLMAP policies.")
    parser.add_argument("--scene", required=True, help="Scene name.")
    parser.add_argument("--quality", type=Path, help="Full frame quality CSV.")
    parser.add_argument(
        "--selected-root",
        type=Path,
        help="Folder containing policy subfolders, for example data/frames_selected/scene01.",
    )
    parser.add_argument(
        "--recon-root",
        type=Path,
        help="Folder containing reconstruction policy subfolders, for example outputs/reconstructions/scene01.",
    )
    parser.add_argument("--out", required=True, type=Path, help="Output summary CSV path.")
    return parser.parse_args()


def list_policy_folders(selected_root: Path) -> list[Path]:
    return sorted(path for path in selected_root.iterdir() if path.is_dir())


def list_selected_image_names(policy_folder: Path) -> list[str]:
    selected_csv = policy_folder / "selected_frames.csv"
    if selected_csv.exists():
        selected_df = pd.read_csv(selected_csv)
        if "selected_path" in selected_df.columns:
            selected_df = selected_df[selected_df["selected_path"].fillna("") != ""]
        if "frame_name" in selected_df.columns:
            return sorted(selected_df["frame_name"].dropna().astype(str).tolist())

    return sorted(
        path.name
        for path in policy_folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def mean_or_none(values: pd.Series) -> float | None:
    if values.dropna().empty:
        return None
    return float(values.mean())


def build_policy_summary(
    policy_folder: Path,
    quality_df: pd.DataFrame,
    total_frames: int,
) -> dict[str, object]:
    selected_names = list_selected_image_names(policy_folder)
    selected_df = quality_df[quality_df["frame_name"].isin(selected_names)].copy()
    selected_count = len(selected_names)
    removal_ratio = 1.0 - (selected_count / total_frames) if total_frames else 0.0

    return {
        "policy": policy_folder.name,
        "total_frames": total_frames,
        "selected_frames": selected_count,
        "removal_ratio": removal_ratio,
        "mean_quality_score": mean_or_none(selected_df["quality_score"]),
        "mean_sharpness": mean_or_none(selected_df["sharpness"]),
        "mean_brightness": mean_or_none(selected_df["brightness"]),
        "mean_keypoints_orb": mean_or_none(selected_df["keypoints_orb"]),
        "mean_redundancy_ssim_to_prev": mean_or_none(selected_df["redundancy_ssim_to_prev"]),
    }


def validate_quality_csv(quality_df: pd.DataFrame) -> bool:
    required_columns = {
        "frame_name",
        "quality_score",
        "sharpness",
        "brightness",
        "keypoints_orb",
        "redundancy_ssim_to_prev",
    }
    missing_columns = sorted(required_columns - set(quality_df.columns))
    if missing_columns:
        print(f"Error: quality CSV is missing columns: {', '.join(missing_columns)}")
        return False
    return True


def run_frame_filtering_comparison(args: argparse.Namespace) -> int:
    if args.quality is None:
        print("Error: --quality is required unless --recon-root is provided.")
        return 1
    if args.selected_root is None:
        print("Error: --selected-root is required unless --recon-root is provided.")
        return 1

    if not args.quality.exists():
        print(f"Error: quality CSV not found: {args.quality}")
        return 1
    if not args.selected_root.exists():
        print(f"Error: selected-root folder not found: {args.selected_root}")
        return 1

    quality_df = pd.read_csv(args.quality)
    if quality_df.empty:
        print(f"Error: quality CSV has no rows: {args.quality}")
        return 1
    if not validate_quality_csv(quality_df):
        return 1

    policy_folders = list_policy_folders(args.selected_root)
    if not policy_folders:
        print(f"Error: no policy folders found under: {args.selected_root}")
        return 1

    total_frames = len(quality_df)
    rows = [
        build_policy_summary(policy_folder, quality_df, total_frames)
        for policy_folder in policy_folders
    ]
    summary_df = pd.DataFrame(rows, columns=EXPECTED_COLUMNS)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(args.out, index=False)

    json_path = args.out.parent / f"{args.scene}_frame_filtering_summary.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scene": args.scene,
                "quality_csv": str(args.quality),
                "selected_root": str(args.selected_root),
                "summary_csv": str(args.out),
                "policies": rows,
            },
            f,
            indent=2,
        )

    print(summary_df.to_string(index=False))
    print(f"\nSaved summary CSV: {args.out}")
    print(f"Saved summary JSON: {json_path}")
    return 0


def read_colmap_metrics(policy_folder: Path) -> dict[str, object]:
    metrics_path = policy_folder / "metrics.json"
    if not metrics_path.exists():
        return {
            "policy": policy_folder.name,
            "images": None,
            "registered_images": None,
            "registered_ratio": None,
            "sparse_points": None,
            "observations": None,
            "mean_track_length": None,
            "mean_observations_per_image": None,
            "mean_reprojection_error_px": None,
            "dense_fused_points": None,
            "sparse_model_path": None,
            "dense_model_path": None,
            "success": False,
        }

    with metrics_path.open("r", encoding="utf-8-sig") as f:
        metrics = json.load(f)

    best_sparse = metrics.get("best_sparse_model") or {}
    return {
        "policy": policy_folder.name,
        "images": best_sparse.get("images"),
        "registered_images": best_sparse.get("registered_images"),
        "registered_ratio": best_sparse.get("registered_ratio"),
        "sparse_points": best_sparse.get("points"),
        "observations": best_sparse.get("observations"),
        "mean_track_length": best_sparse.get("mean_track_length"),
        "mean_observations_per_image": best_sparse.get("mean_observations_per_image"),
        "mean_reprojection_error_px": best_sparse.get("mean_reprojection_error_px"),
        "dense_fused_points": metrics.get("dense_fused_points"),
        "sparse_model_path": best_sparse.get("sparse_model_path"),
        "dense_model_path": metrics.get("selected_dense_model"),
        "success": bool(metrics.get("success")),
    }


def run_colmap_comparison(args: argparse.Namespace) -> int:
    if not args.recon_root.exists():
        print(f"Error: recon-root folder not found: {args.recon_root}")
        return 1

    policy_folders = list_policy_folders(args.recon_root)
    if not policy_folders:
        print(f"Error: no policy folders found under: {args.recon_root}")
        return 1

    rows = [read_colmap_metrics(policy_folder) for policy_folder in policy_folders]
    summary_df = pd.DataFrame(rows, columns=COLMAP_COLUMNS)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    summary_df.to_csv(args.out, index=False)

    json_path = args.out.with_suffix(".json")
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            {
                "scene": args.scene,
                "recon_root": str(args.recon_root),
                "summary_csv": str(args.out),
                "policies": rows,
            },
            f,
            indent=2,
        )

    print(summary_df.to_string(index=False))
    print(f"\nSaved COLMAP summary CSV: {args.out}")
    print(f"Saved COLMAP summary JSON: {json_path}")
    return 0


def main() -> int:
    args = parse_args()
    if args.recon_root is not None:
        return run_colmap_comparison(args)
    return run_frame_filtering_comparison(args)


if __name__ == "__main__":
    raise SystemExit(main())

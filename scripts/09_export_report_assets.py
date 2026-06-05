from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export frame filtering and COLMAP figures.")
    parser.add_argument("--scene", required=True, help="Scene name.")
    parser.add_argument("--quality", type=Path, help="Full frame quality CSV.")
    parser.add_argument("--comparison", type=Path, help="Frame filtering comparison CSV.")
    parser.add_argument("--colmap-comparison", type=Path, help="COLMAP comparison CSV.")
    parser.add_argument("--out-dir", required=True, type=Path, help="Output figure directory.")
    return parser.parse_args()


def validate_columns(df: pd.DataFrame, required_columns: set[str], csv_path: Path) -> bool:
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        print(f"Error: {csv_path} is missing columns: {', '.join(missing_columns)}")
        return False
    return True


def save_histogram(df: pd.DataFrame, column: str, title: str, xlabel: str, path: Path) -> None:
    plt.figure(figsize=(8, 5))
    plt.hist(df[column].dropna(), bins=30)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel("Frame count")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def save_bar_chart(df: pd.DataFrame, value_column: str, title: str, ylabel: str, path: Path) -> None:
    plt.figure(figsize=(9, 5))
    plt.bar(df["policy"], df[value_column])
    plt.title(title)
    plt.xlabel("Policy")
    plt.ylabel(ylabel)
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.savefig(path, dpi=150)
    plt.close()


def export_frame_filtering_figures(args: argparse.Namespace) -> list[Path] | None:
    if args.quality is None or args.comparison is None:
        return []
    if not args.quality.exists():
        print(f"Error: quality CSV not found: {args.quality}")
        return None
    if not args.comparison.exists():
        print(f"Error: comparison CSV not found: {args.comparison}")
        return None

    quality_df = pd.read_csv(args.quality)
    comparison_df = pd.read_csv(args.comparison)

    if quality_df.empty:
        print(f"Error: quality CSV has no rows: {args.quality}")
        return None
    if comparison_df.empty:
        print(f"Error: comparison CSV has no rows: {args.comparison}")
        return None

    quality_columns = {"quality_score", "sharpness"}
    comparison_columns = {
        "policy",
        "selected_frames",
        "mean_quality_score",
        "mean_sharpness",
        "mean_keypoints_orb",
    }
    if not validate_columns(quality_df, quality_columns, args.quality):
        return None
    if not validate_columns(comparison_df, comparison_columns, args.comparison):
        return None

    figure_paths = [
        args.out_dir / f"{args.scene}_quality_score_hist.png",
        args.out_dir / f"{args.scene}_sharpness_hist.png",
        args.out_dir / f"{args.scene}_selected_count_by_policy.png",
        args.out_dir / f"{args.scene}_mean_quality_by_policy.png",
        args.out_dir / f"{args.scene}_mean_sharpness_by_policy.png",
        args.out_dir / f"{args.scene}_mean_keypoints_by_policy.png",
    ]

    save_histogram(
        quality_df,
        "quality_score",
        f"{args.scene} quality score distribution",
        "Quality score",
        figure_paths[0],
    )
    save_histogram(
        quality_df,
        "sharpness",
        f"{args.scene} sharpness distribution",
        "Laplacian sharpness",
        figure_paths[1],
    )
    save_bar_chart(
        comparison_df,
        "selected_frames",
        f"{args.scene} selected frame count by policy",
        "Selected frames",
        figure_paths[2],
    )
    save_bar_chart(
        comparison_df,
        "mean_quality_score",
        f"{args.scene} mean quality score by policy",
        "Mean quality score",
        figure_paths[3],
    )
    save_bar_chart(
        comparison_df,
        "mean_sharpness",
        f"{args.scene} mean sharpness by policy",
        "Mean sharpness",
        figure_paths[4],
    )
    save_bar_chart(
        comparison_df,
        "mean_keypoints_orb",
        f"{args.scene} mean ORB keypoints by policy",
        "Mean ORB keypoints",
        figure_paths[5],
    )

    return figure_paths


def export_colmap_figures(args: argparse.Namespace) -> list[Path] | None:
    if args.colmap_comparison is None:
        return []
    if not args.colmap_comparison.exists():
        print(f"Error: COLMAP comparison CSV not found: {args.colmap_comparison}")
        return None

    colmap_df = pd.read_csv(args.colmap_comparison)
    if colmap_df.empty:
        print(f"Error: COLMAP comparison CSV has no rows: {args.colmap_comparison}")
        return None

    required_columns = {
        "policy",
        "registered_ratio",
        "sparse_points",
        "mean_reprojection_error_px",
        "dense_fused_points",
    }
    if not validate_columns(colmap_df, required_columns, args.colmap_comparison):
        return None

    figure_paths = [
        args.out_dir / f"{args.scene}_registered_ratio_by_policy.png",
        args.out_dir / f"{args.scene}_sparse_points_by_policy.png",
        args.out_dir / f"{args.scene}_reprojection_error_by_policy.png",
        args.out_dir / f"{args.scene}_dense_points_by_policy.png",
    ]

    save_bar_chart(
        colmap_df,
        "registered_ratio",
        f"{args.scene} registered image ratio by policy",
        "Registered ratio",
        figure_paths[0],
    )
    save_bar_chart(
        colmap_df,
        "sparse_points",
        f"{args.scene} sparse points by policy",
        "Sparse points",
        figure_paths[1],
    )
    save_bar_chart(
        colmap_df,
        "mean_reprojection_error_px",
        f"{args.scene} mean reprojection error by policy",
        "Mean reprojection error (px)",
        figure_paths[2],
    )
    save_bar_chart(
        colmap_df,
        "dense_fused_points",
        f"{args.scene} dense fused points by policy",
        "Dense fused points",
        figure_paths[3],
    )

    return figure_paths


def main() -> int:
    args = parse_args()

    if args.quality is None and args.comparison is None and args.colmap_comparison is None:
        print("Error: provide --quality and --comparison, or provide --colmap-comparison.")
        return 1
    if (args.quality is None) != (args.comparison is None):
        print("Error: --quality and --comparison must be provided together.")
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)
    figure_paths = []

    frame_figures = export_frame_filtering_figures(args)
    if frame_figures is None:
        return 1
    figure_paths.extend(frame_figures)

    colmap_figures = export_colmap_figures(args)
    if colmap_figures is None:
        return 1
    figure_paths.extend(colmap_figures)

    print("Saved report figures:")
    for figure_path in figure_paths:
        print(f"- {figure_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

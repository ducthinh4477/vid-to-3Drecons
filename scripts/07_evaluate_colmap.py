from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.reconstruction.colmap_utils import (
    choose_best_sparse_model,
    count_ply_vertices,
    find_colmap_executable,
    find_dense_models,
    find_sparse_models,
    parse_model_analyzer_output,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate COLMAP reconstruction metrics.")
    parser.add_argument("--scene", required=True, help="Scene name.")
    parser.add_argument("--policy", required=True, help="Frame filtering policy name.")
    parser.add_argument("--workspace", required=True, type=Path, help="COLMAP workspace folder.")
    parser.add_argument("--out", required=True, type=Path, help="Output metrics JSON path.")
    return parser.parse_args()


def add_registered_ratio(metrics: dict) -> dict:
    images = metrics.get("images") or 0
    registered_images = metrics.get("registered_images") or 0
    metrics["registered_ratio"] = float(registered_images / images) if images else None
    return metrics


def analyze_sparse_model(colmap: str, sparse_model_path: Path) -> dict:
    result = subprocess.run(
        [colmap, "model_analyzer", "--path", str(sparse_model_path)],
        capture_output=True,
        text=True,
    )
    output = f"{result.stdout}\n{result.stderr}"
    metrics = parse_model_analyzer_output(output)
    metrics["sparse_model_path"] = str(sparse_model_path)
    metrics["model_analyzer_returncode"] = result.returncode
    if result.returncode != 0:
        metrics["model_analyzer_error"] = result.stderr.strip()
    return add_registered_ratio(metrics)


def choose_dense_model(dense_models: list[Path], best_sparse_model: dict) -> Path | None:
    if not dense_models:
        return None

    sparse_path_text = best_sparse_model.get("sparse_model_path")
    if sparse_path_text:
        sparse_index = Path(sparse_path_text).name
        for dense_model in dense_models:
            if dense_model.name == sparse_index:
                return dense_model

    return dense_models[0]


def main() -> int:
    args = parse_args()

    colmap = find_colmap_executable()
    if colmap is None:
        print("Error: COLMAP command was not found on PATH.")
        print("Install COLMAP and make sure `colmap` is available in this terminal.")
        return 1
    if not args.workspace.exists():
        print(f"Error: workspace folder not found: {args.workspace}")
        return 1

    sparse_models = find_sparse_models(args.workspace)
    if not sparse_models:
        print(f"Error: no valid sparse COLMAP models found under: {args.workspace / 'sparse'}")
        return 1

    all_sparse_metrics = [analyze_sparse_model(colmap, path) for path in sparse_models]
    successful_sparse_metrics = [
        metrics
        for metrics in all_sparse_metrics
        if metrics.get("model_analyzer_returncode") == 0
    ]
    best_sparse_model = choose_best_sparse_model(successful_sparse_metrics)
    if not best_sparse_model:
        print("Error: model_analyzer failed for all sparse models.")
        return 1

    dense_model_paths = find_dense_models(args.workspace)
    dense_models = [
        {
            "dense_model_path": str(path),
            "fused_ply_path": str(path / "fused.ply"),
            "fused_points": count_ply_vertices(path / "fused.ply"),
        }
        for path in dense_model_paths
    ]
    selected_dense_model = choose_dense_model(dense_model_paths, best_sparse_model)
    dense_fused_points = None
    if selected_dense_model is not None:
        dense_fused_points = count_ply_vertices(selected_dense_model / "fused.ply")

    result = {
        "scene": args.scene,
        "policy": args.policy,
        "workspace": str(args.workspace),
        "best_sparse_model": best_sparse_model,
        "all_sparse_models": all_sparse_metrics,
        "dense_models": dense_models,
        "selected_dense_model": str(selected_dense_model) if selected_dense_model else None,
        "dense_fused_points": dense_fused_points,
        "success": True,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    csv_path = args.out.with_suffix(".csv")
    csv_row = {
        "scene": args.scene,
        "policy": args.policy,
        "images": best_sparse_model.get("images"),
        "registered_images": best_sparse_model.get("registered_images"),
        "registered_ratio": best_sparse_model.get("registered_ratio"),
        "points": best_sparse_model.get("points"),
        "observations": best_sparse_model.get("observations"),
        "mean_track_length": best_sparse_model.get("mean_track_length"),
        "mean_observations_per_image": best_sparse_model.get("mean_observations_per_image"),
        "mean_reprojection_error_px": best_sparse_model.get("mean_reprojection_error_px"),
        "dense_fused_points": dense_fused_points,
        "sparse_model_path": best_sparse_model.get("sparse_model_path"),
        "dense_model_path": str(selected_dense_model) if selected_dense_model else None,
        "success": True,
    }
    pd.DataFrame([csv_row]).to_csv(csv_path, index=False)

    print(
        pd.DataFrame(
            [
                {
                    "policy": args.policy,
                    "images": csv_row["images"],
                    "registered_images": csv_row["registered_images"],
                    "registered_ratio": csv_row["registered_ratio"],
                    "points": csv_row["points"],
                    "mean_reprojection_error_px": csv_row["mean_reprojection_error_px"],
                    "dense_fused_points": csv_row["dense_fused_points"],
                }
            ]
        ).to_string(index=False)
    )
    print(f"\nSaved metrics JSON: {args.out}")
    print(f"Saved metrics CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

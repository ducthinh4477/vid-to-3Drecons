from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.reconstruction.colmap_utils import find_sparse_models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run COLMAP reconstruction and evaluation for policies.")
    parser.add_argument("--scene", required=True, help="Scene name.")
    parser.add_argument("--policies", nargs="+", required=True, help="Policy names to run.")
    parser.add_argument("--quality", default="medium", help="COLMAP automatic_reconstructor quality.")
    parser.add_argument("--camera-model", default="SIMPLE_RADIAL", help="COLMAP camera model.")
    parser.add_argument("--single-camera", default=1, type=int, help="Use one shared camera.")
    parser.add_argument("--use-gpu", default=1, type=int, help="Use GPU if available.")
    parser.add_argument("--overwrite", action="store_true", help="Pass --overwrite to script 05.")
    return parser.parse_args()


def run_command(command: list[str]) -> int:
    print("\nRunning:", flush=True)
    print(" ".join(command), flush=True)
    result = subprocess.run(command)
    return result.returncode


def run_evaluation(scene: str, policy: str, workspace: Path, metrics_json: Path) -> int:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "07_evaluate_colmap.py"),
        "--scene",
        scene,
        "--policy",
        policy,
        "--workspace",
        str(workspace),
        "--out",
        str(metrics_json),
    ]
    return run_command(command)


def main() -> int:
    args = parse_args()
    rows = []

    for policy in args.policies:
        images = ROOT / "data" / "frames_selected" / args.scene / policy
        workspace = ROOT / "outputs" / "reconstructions" / args.scene / policy / "colmap"
        metrics_json = ROOT / "outputs" / "reconstructions" / args.scene / policy / "metrics.json"

        run_command_05 = [
            sys.executable,
            str(ROOT / "scripts" / "05_run_hloc_colmap.py"),
            "--scene",
            args.scene,
            "--policy",
            policy,
            "--images",
            str(images),
            "--workspace",
            str(workspace),
            "--quality",
            args.quality,
            "--camera-model",
            args.camera_model,
            "--single-camera",
            str(args.single_camera),
            "--use-gpu",
            str(args.use_gpu),
        ]
        if args.overwrite:
            run_command_05.append("--overwrite")

        reused_existing = False
        if not args.overwrite and find_sparse_models(workspace):
            print(f"\nReusing existing COLMAP reconstruction for {policy}: {workspace}", flush=True)
            print("Use --overwrite if you want to run COLMAP again in this workspace.", flush=True)
            reconstruction_code = 0
            reused_existing = True
        else:
            reconstruction_code = run_command(run_command_05)

        evaluation_code = None
        if reconstruction_code == 0:
            evaluation_code = run_evaluation(args.scene, policy, workspace, metrics_json)
        else:
            print(f"Skipping evaluation for {policy} because reconstruction failed.", flush=True)

        rows.append(
            {
                "policy": policy,
                "images": str(images),
                "workspace": str(workspace),
                "metrics_json": str(metrics_json),
                "reconstruction_exit_code": reconstruction_code,
                "evaluation_exit_code": evaluation_code,
                "reused_existing_reconstruction": reused_existing,
                "success": reconstruction_code == 0 and evaluation_code == 0,
            }
        )

    summary_path = ROOT / "outputs" / "reconstructions" / args.scene / "colmap_batch_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump({"scene": args.scene, "policies": rows}, f, indent=2)

    print(f"\nSaved batch summary: {summary_path}", flush=True)
    failed = [row for row in rows if not row["success"]]
    if failed:
        print(f"Finished with {len(failed)} failed policy run(s).", flush=True)
        return 1

    print("All policy runs finished successfully.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

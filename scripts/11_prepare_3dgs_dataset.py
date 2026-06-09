from __future__ import annotations

import argparse
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
REQUIRED_SPARSE_FILES = ["cameras.bin", "images.bin", "points3D.bin"]
OPTIONAL_SPARSE_FILES = ["rigs.bin", "frames.bin"]


def policy_short_name(policy: str) -> str:
    if policy.endswith("_filter"):
        return policy.removesuffix("_filter")
    return policy


def default_output_path(scene: str, policy: str) -> Path:
    return ROOT / "data" / "3dgs" / f"{scene}_{policy_short_name(policy)}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a 3DGS dataset from COLMAP output.")
    parser.add_argument("--scene", required=True, help="Scene name, for example scene01.")
    parser.add_argument("--policy", required=True, help="Frame filtering policy, for example light_filter.")
    parser.add_argument("--images-src", type=Path, help="Source folder containing images.")
    parser.add_argument("--sparse-src", type=Path, help="Source COLMAP sparse model folder.")
    parser.add_argument("--out", type=Path, help="Output 3DGS dataset folder.")
    parser.add_argument("--overwrite", action="store_true", help="Delete and recreate the output folder.")
    return parser.parse_args()


def list_images(images_src: Path) -> list[Path]:
    return sorted(
        path
        for path in images_src.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def validate_sparse_source(sparse_src: Path) -> bool:
    missing_files = [name for name in REQUIRED_SPARSE_FILES if not (sparse_src / name).exists()]
    if missing_files:
        print(f"Error: missing required COLMAP sparse file(s): {', '.join(missing_files)}")
        print(f"Sparse source: {sparse_src}")
        return False
    return True


def prepare_output_folder(out_dir: Path, overwrite: bool) -> bool:
    if out_dir.exists() and any(out_dir.iterdir()):
        if not overwrite:
            print(f"Error: output folder already exists and is not empty: {out_dir}")
            print("Use --overwrite to delete and recreate only this output folder.")
            return False

        resolved_out = out_dir.resolve()
        protected_paths = {
            ROOT.resolve(),
            (ROOT / "data").resolve(),
            (ROOT / "outputs").resolve(),
        }
        if resolved_out in protected_paths:
            print(f"Error: refusing to delete protected folder: {out_dir}")
            return False
        shutil.rmtree(out_dir)

    (out_dir / "images").mkdir(parents=True, exist_ok=True)
    (out_dir / "sparse" / "0").mkdir(parents=True, exist_ok=True)
    return True


def copy_images(image_paths: list[Path], images_out: Path) -> int:
    copied = 0
    for image_path in image_paths:
        shutil.copy2(image_path, images_out / image_path.name)
        copied += 1
    return copied


def copy_sparse_files(sparse_src: Path, sparse_out: Path) -> list[str]:
    copied_files = []
    for file_name in REQUIRED_SPARSE_FILES + OPTIONAL_SPARSE_FILES:
        source_file = sparse_src / file_name
        if source_file.exists():
            shutil.copy2(source_file, sparse_out / file_name)
            copied_files.append(file_name)
    return copied_files


def default_sources(scene: str, policy: str) -> tuple[Path, Path, str]:
    colmap_root = ROOT / "outputs" / "reconstructions" / scene / policy / "colmap"
    dense_images = colmap_root / "dense" / "0" / "images"
    dense_sparse = colmap_root / "dense" / "0" / "sparse"

    if dense_images.exists() and dense_sparse.exists():
        return dense_images, dense_sparse, "COLMAP dense/0 undistorted dataset"

    selected_images = ROOT / "data" / "frames_selected" / scene / policy
    sparse_model = colmap_root / "sparse" / "0"
    return selected_images, sparse_model, "selected images with original sparse/0 model"


def print_3dgs_commands(dataset_path: Path) -> None:
    absolute_dataset_path = dataset_path.resolve()
    model_name = f"{dataset_path.name}_3dgs_7k"

    print("\nSuggested 3DGS command:")
    print(
        f"python train.py -s {absolute_dataset_path} "
        f"-m output\\{model_name} --iterations 7000 --resolution 2"
    )

    print("\nCleaner relative command:")
    print(
        f"python train.py -s <path-to-vid-to-3Drecons>\\data\\3dgs\\{dataset_path.name} "
        f"-m output\\{model_name} --iterations 7000 --resolution 2"
    )


def main() -> int:
    args = parse_args()

    default_images_src, default_sparse_src, source_mode = default_sources(args.scene, args.policy)
    images_src = args.images_src or default_images_src
    sparse_src = args.sparse_src or default_sparse_src
    out_dir = args.out or default_output_path(args.scene, args.policy)

    if not images_src.exists():
        print(f"Error: images source folder not found: {images_src}")
        return 1
    if not sparse_src.exists():
        print(f"Error: COLMAP sparse source folder not found: {sparse_src}")
        return 1
    if not validate_sparse_source(sparse_src):
        return 1

    image_paths = list_images(images_src)
    if not image_paths:
        print(f"Error: no supported image files found in: {images_src}")
        return 1

    if not prepare_output_folder(out_dir, args.overwrite):
        return 1

    images_out = out_dir / "images"
    sparse_out = out_dir / "sparse" / "0"
    image_count = copy_images(image_paths, images_out)
    sparse_files = copy_sparse_files(sparse_src, sparse_out)

    print("3DGS dataset prepared.")
    print(f"Source mode: {source_mode}")
    print(f"Images source: {images_src}")
    print(f"Sparse source: {sparse_src}")
    print(f"Images copied: {image_count}")
    print(f"Sparse files copied: {', '.join(sparse_files)}")
    print(f"Output dataset path: {out_dir.resolve()}")

    print_3dgs_commands(out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

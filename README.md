# vid-to-3Drecons

Minimal computer vision pipeline for a university Image Processing course. The current focus is frame quality assessment and frame filtering before future 3D reconstruction experiments.

Implemented pipeline:

```text
video -> extract frames -> compute frame quality -> select frames
```

COLMAP, hloc, DUST3R, RIFE, TecoGAN, and 3D Gaussian Splatting integration are intentionally left for later stages.

## Windows VSCode Setup

Open this repository folder in VSCode on Windows:

```powershell
cd C:\GitHub\vid-to-3Drecons
code .
```

Create and activate the Conda environment:

```powershell
conda create -n vid3d python=3.10 -y
conda activate vid3d
pip install -r requirements.txt
```

All scripts are designed to run from the repository root with Windows-compatible paths.

## Folder Structure

```text
vid-to-3Drecons/
  configs/
    default.yaml
    experiments.yaml
  data/
    raw_videos/          # input videos
    frames_raw/          # extracted video frames
    frames_selected/     # selected frame subsets
    masks/               # future masks
  outputs/
    frame_quality/       # CSV metrics and JSON summaries
    reconstructions/     # future reconstruction outputs
    comparisons/         # future experiment comparisons
    figures/             # future report figures
    reports/             # future report assets
  scripts/
    01_extract_frames.py
    02_compute_frame_quality.py
    03_select_frames.py
    04_generate_masks.py
    05_run_hloc_colmap.py
    06_run_dust3r.py
    07_evaluate_colmap.py
    08_compare_experiments.py
    09_export_report_assets.py
  src/
    frame_quality/
    reconstruction/
    evaluation/
    utils/
```

## Run The Minimum Pipeline

Put a video at `data/raw_videos/scene01.mp4`, then run:

```powershell
python scripts/01_extract_frames.py --video data/raw_videos/scene01.mp4 --scene scene01 --fps 5
```

This saves sampled frames to:

```text
data/frames_raw/scene01/frame_000001.jpg
```

Compute frame quality metrics:

```powershell
python scripts/02_compute_frame_quality.py --scene scene01 --frames data/frames_raw/scene01 --out outputs/frame_quality/scene01/frame_quality.csv
```

This writes:

```text
outputs/frame_quality/scene01/frame_quality.csv
outputs/frame_quality/scene01/frame_quality_summary.json
```

Select frames using one of the filtering policies:

```powershell
python scripts/03_select_frames.py --scene scene01 --frames data/frames_raw/scene01 --quality outputs/frame_quality/scene01/frame_quality.csv --policy medium_filter --out data/frames_selected/scene01/medium_filter
```

Available policies:

```text
no_filter      copy all frames
light_filter   quality percentile 20, max_ssim 0.98
medium_filter  quality percentile 40, max_ssim 0.95
strong_filter  quality percentile 60, max_ssim 0.92
```

The selected images and `selected_frames.csv` are saved in the output folder.

## Frame Quality Metrics

The current quality score combines:

```text
0.35 * sharpness_score
+ 0.20 * brightness_score
+ 0.25 * keypoint_score
+ 0.10 * dynamic_range_score
- 0.05 * clipping_penalty
- 0.05 * redundancy_penalty
```

The final score is clamped to `[0, 1]`. ORB keypoint count is used as a lightweight temporary proxy before future SuperPoint integration.

## Later Stages

Scripts `04` through `09` are placeholders. They currently print TODO messages and expected input/output locations only. Full masking, hloc/COLMAP, DUST3R, reconstruction evaluation, experiment comparison, and report export will be added later.

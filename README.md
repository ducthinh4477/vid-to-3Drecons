# vid-to-3Drecons

Du an xu ly anh / thi giac may tinh cho mon Image Processing. Dong gop chinh hien tai la danh gia chat luong frame va loc frame truoc khi chay tai tao 3D.

## Current Implementation Status

Implemented:

- frame extraction
- frame quality computation
- frame selection policies
- frame filtering comparison
- COLMAP automatic reconstruction
- COLMAP model evaluation
- comparison charts

Not yet implemented:

- hloc + SuperPoint + LightGlue
- DUST3R
- RIFE
- TecoGAN
- 3D Gaussian Splatting training/evaluation as a reported result

## Technical Honesty Note

The project originally planned hloc + SuperPoint + LightGlue, but the current experimental results are generated using COLMAP automatic_reconstructor with SIFT. Therefore, all current reported metrics must be attributed to COLMAP SIFT, not hloc.

Current experiment summary:
The current scene01 results were obtained using COLMAP automatic_reconstructor. COLMAP performed SIFT feature extraction and matching internally, followed by sparse reconstruction and dense fusion. hloc, SuperPoint, and LightGlue were not used in the current run. They remain planned as a future comparison branch.

## Current Implemented Pipeline

```text
Video input
-> Extract frames
-> Compute frame quality metrics:
   - Laplacian variance sharpness
   - brightness / exposure / clipping / dynamic range
   - SSIM redundancy
   - ORB keypoint count as texture proxy
-> Compute weighted quality score
-> Select frames using no_filter / light_filter / medium_filter / strong_filter
-> Run COLMAP automatic_reconstructor
-> COLMAP SIFT feature extraction and matching
-> COLMAP sparse reconstruction
-> COLMAP dense fusion
-> Evaluate sparse and dense metrics
```

Feature extraction and matching in Phase 3 are performed by COLMAP's built-in SIFT pipeline. ORB keypoint count is used during preprocessing as a lightweight proxy for texture richness.

## Planned Extension Pipeline

Future Phase 4:

```text
hloc + SuperPoint + LightGlue + COLMAP
-> compare against COLMAP SIFT baseline
```

In a future phase, hloc with SuperPoint and LightGlue can be integrated to replace or compare against COLMAP's built-in SIFT feature extraction and matching.

Future fallback branch:

```text
DUST3R for low-quality or difficult image sets
```

DUST3R is planned as a fallback branch for low-quality data or cases where COLMAP fails, but it has not been integrated in the current Phase 3 experiments.

Optional future video enhancement:

- RIFE for low-FPS videos
- TecoGAN or other super-resolution for low-resolution videos
- 3D Gaussian Splatting after reliable camera poses are available

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
    raw_videos/
    frames_raw/
    frames_selected/
    masks/
  outputs/
    frame_quality/
    reconstructions/
    comparisons/
    figures/
    reports/
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
    10_run_all_colmap_policies.py
    11_prepare_3dgs_dataset.py
    12_collect_3dgs_output.py
    13_export_demo_assets.py
    14_launch_demo.py
  src/
    frame_quality/
    reconstruction/
    evaluation/
    utils/
```

Note: `05_run_hloc_colmap.py` keeps a historical filename, but currently runs plain COLMAP automatic_reconstructor only.

## Phase 1: Frame Preprocessing

Extract frames:

```powershell
python scripts/01_extract_frames.py --video data/raw_videos/scene01.mp4 --scene scene01 --fps 5
```

Compute frame quality metrics:

```powershell
python scripts/02_compute_frame_quality.py --scene scene01 --frames data/frames_raw/scene01 --out outputs/frame_quality/scene01/frame_quality.csv
```

Select frames:

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

## Phase 2: Compare Frame Filtering Policies

Compare selected frame sets:

```powershell
python scripts/08_compare_experiments.py --scene scene01 --quality outputs/frame_quality/scene01/frame_quality.csv --selected-root data/frames_selected/scene01 --out outputs/comparisons/scene01_frame_filtering_summary.csv
```

Export frame filtering figures:

```powershell
python scripts/09_export_report_assets.py --scene scene01 --quality outputs/frame_quality/scene01/frame_quality.csv --comparison outputs/comparisons/scene01_frame_filtering_summary.csv --out-dir outputs/figures
```

## Phase 3: Run COLMAP automatic_reconstructor

Run COLMAP automatic_reconstructor for one filtering policy:

```powershell
python scripts/05_run_hloc_colmap.py --scene scene01 --policy medium_filter --images data/frames_selected/scene01/medium_filter --workspace outputs/reconstructions/scene01/medium_filter/colmap --quality medium --camera-model SIMPLE_RADIAL --single-camera 1
```

Evaluate one COLMAP reconstruction:

```powershell
python scripts/07_evaluate_colmap.py --scene scene01 --policy medium_filter --workspace outputs/reconstructions/scene01/medium_filter/colmap --out outputs/reconstructions/scene01/medium_filter/metrics.json
```

Run COLMAP evaluation/reconstruction flow for all frame filtering policies:

```powershell
python scripts/10_run_all_colmap_policies.py --scene scene01 --policies no_filter light_filter medium_filter strong_filter --quality medium
```

Compare COLMAP metrics across policies:

```powershell
python scripts/08_compare_experiments.py --scene scene01 --recon-root outputs/reconstructions/scene01 --out outputs/comparisons/scene01_colmap_summary.csv
```

Export COLMAP report figures:

```powershell
python scripts/09_export_report_assets.py --scene scene01 --colmap-comparison outputs/comparisons/scene01_colmap_summary.csv --out-dir outputs/figures
```

Expected outputs:

```text
outputs/reconstructions/scene01/<policy>/colmap/colmap_run.log
outputs/reconstructions/scene01/<policy>/metrics.json
outputs/reconstructions/scene01/<policy>/metrics.csv
outputs/reconstructions/scene01/colmap_batch_summary.json
outputs/comparisons/scene01_colmap_summary.csv
outputs/comparisons/scene01_colmap_summary.json
outputs/figures/scene01_registered_ratio_by_policy.png
outputs/figures/scene01_sparse_points_by_policy.png
outputs/figures/scene01_reprojection_error_by_policy.png
outputs/figures/scene01_dense_points_by_policy.png
```

## Scene01 Result Interpretation

- `light_filter` is the best balanced policy for scene01.
- `no_filter` gives the most points but uses the most frames.
- `light_filter` reduces the input from 635 to 508 frames while keeping strong reconstruction quality.
- `medium_filter` and `strong_filter` produce higher-quality selected frames but reduce coverage and model completeness because they remove too many intermediate views.
- This supports the main Image Processing contribution: frame quality assessment and filtering can reduce redundancy, but filtering must preserve geometric overlap.

## Prepare Dataset for 3D Gaussian Splatting

3D Gaussian Splatting is an optional visualization/demo stage after COLMAP. The current COLMAP result uses COLMAP automatic_reconstructor with built-in SIFT, not hloc/SuperPoint/LightGlue.

3DGS expects an undistorted COLMAP dataset with `PINHOLE` or `SIMPLE_PINHOLE` cameras. For this reason, the preparation script uses `outputs/reconstructions/<scene>/<policy>/colmap/dense/0/images` and `outputs/reconstructions/<scene>/<policy>/colmap/dense/0/sparse` when they exist. These are the undistorted images and sparse model produced by COLMAP.

Prepare the `light_filter` dataset for manual 3DGS training:

```powershell
python scripts/11_prepare_3dgs_dataset.py --scene scene01 --policy light_filter --out data/3dgs/scene01_light --overwrite
```

Expected output folder:

```text
data/3dgs/scene01_light/
  images/
    frame_000001.jpg
    frame_000002.jpg
    ...
  sparse/
    0/
      cameras.bin
      images.bin
      points3D.bin
      rigs.bin
      frames.bin
```

Suggested 3DGS command:

```powershell
python train.py -s C:\GitHub\vid-to-3Drecons\data\3dgs\scene01_light -m output\scene01_light_3dgs_7k --iterations 7000 --resolution 2
```

## Visual Demo Layer

The visual demo layer packages trained 3DGS output for browser inspection after COLMAP poses are available. It is not part of the current quantitative report pipeline.

Supported viewers:

- local web viewer in `viewer/`, using `@mkkellogg/gaussian-splats-3d`
- SuperSplat Viewer static web app from `@playcanvas/supersplat-viewer`
- ViS-3DGS in VSCode as an optional external inspection tool

These tools are only used to view trained 3DGS results. The current project metrics remain COLMAP automatic_reconstructor metrics unless a separate trained 3DGS experiment is explicitly documented.

Install/build viewer assets:

```powershell
cd viewer
npm install
npm run build
cd ..
```

Collect trained 3DGS output:

```powershell
python scripts/12_collect_3dgs_output.py --scene scene01 --policy light_filter --model-dir <path-to-gaussian-splatting>\output\scene01_light_3dgs_7k --iteration 7000
```

Export demo assets:

```powershell
python scripts/13_export_demo_assets.py --scene scene01 --policy light_filter
```

Launch the local viewer:

```powershell
python scripts/14_launch_demo.py --scene scene01 --policy light_filter
```

Launch SuperSplat Viewer:

```powershell
python scripts/14_launch_demo.py --scene scene01 --policy light_filter --viewer supersplat
```

See [docs/DEMO_3DGS_VIEWER.md](docs/DEMO_3DGS_VIEWER.md) for the full demo workflow.

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

The final score is clamped to `[0, 1]`.

## TODO Phase 4 hloc Integration

- install hloc
- extract SuperPoint features
- generate image pairs
- match with LightGlue
- import matches into COLMAP / run hloc reconstruction
- compare hloc result against current COLMAP SIFT baseline
- compare metrics: registered images, sparse points, reprojection error, dense points, runtime

## TODO DUST3R Fallback

- prepare low-quality image set
- run COLMAP baseline
- run DUST3R
- compare point cloud completeness and visual distortion
- do not claim DUST3R results until actual outputs exist

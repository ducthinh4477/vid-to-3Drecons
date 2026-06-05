# Pipeline

Tai lieu nay phan biet ro pipeline da cai dat hien tai va cac nhanh mo rong du kien. Ket qua hien tai khong su dung hloc, SuperPoint, LightGlue hay DUST3R.

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
- 3D Gaussian Splatting

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

Trong Phase 3, feature extraction va matching duoc thuc hien bang SIFT tich hop trong COLMAP. ORB keypoint count chi duoc dung o buoc tien xu ly nhu mot proxy nhe de uoc luong texture richness cua frame.

## Planned Extension Pipeline

### Future Phase 4: hloc Comparison Branch

```text
hloc + SuperPoint + LightGlue + COLMAP
-> compare against COLMAP SIFT baseline
```

Trong phase tuong lai, hloc voi SuperPoint va LightGlue co the duoc tich hop de thay the hoac so sanh voi feature extraction / matching SIFT tich hop trong COLMAP.

TODO Phase 4 hloc integration:

- install hloc
- extract SuperPoint features
- generate image pairs
- match with LightGlue
- import matches into COLMAP / run hloc reconstruction
- compare hloc result against current COLMAP SIFT baseline
- compare metrics: registered images, sparse points, reprojection error, dense points, runtime

### Future Fallback Branch: DUST3R

DUST3R is planned as a fallback branch for low-quality data or cases where COLMAP fails, but it has not been integrated in the current Phase 3 experiments.

TODO DUST3R fallback:

- prepare low-quality image set
- run COLMAP baseline
- run DUST3R
- compare point cloud completeness and visual distortion
- do not claim DUST3R results until actual outputs exist

### Optional Future Video Enhancement

- RIFE for low-FPS videos
- TecoGAN or other super-resolution for low-resolution videos
- 3D Gaussian Splatting after reliable camera poses are available

## Scene01 Interpretation

- `light_filter` is the best balanced policy for scene01.
- `no_filter` gives the most points but uses the most frames.
- `light_filter` reduces the input from 635 to 508 frames while keeping strong reconstruction quality.
- `medium_filter` and `strong_filter` produce higher-quality selected frames but reduce coverage and model completeness because they remove too many intermediate views.
- This supports the main Image Processing contribution: frame quality assessment and filtering can reduce redundancy, but filtering must preserve geometric overlap.

# Report Outline

## 1. Giới thiệu

- Bài toán: tái tạo 3D từ video do người dùng quay.
- Vấn đề xử lý ảnh: video có frame mờ, thiếu sáng, cháy sáng, trùng lặp cao và không phải frame nào cũng có ích cho SfM.
- Đóng góp chính: frame quality assessment và frame filtering trước reconstruction.

## 2. Current Implementation Status

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

## 3. Technical Honesty Note

The project originally planned hloc + SuperPoint + LightGlue, but the current experimental results are generated using COLMAP automatic_reconstructor with SIFT. Therefore, all current reported metrics must be attributed to COLMAP SIFT, not hloc.

Current experiment summary:
The current scene01 results were obtained using COLMAP automatic_reconstructor. COLMAP performed SIFT feature extraction and matching internally, followed by sparse reconstruction and dense fusion. hloc, SuperPoint, and LightGlue were not used in the current run. They remain planned as a future comparison branch.

## 4. Current Implemented Pipeline

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

## 5. Frame Quality Metrics

- Laplacian variance sharpness: đo độ sắc nét / mờ của frame.
- Brightness / exposure / clipping / dynamic range: đo độ sáng và mức độ mất thông tin vùng tối/sáng.
- SSIM redundancy: đo mức trùng lặp với frame trước.
- ORB keypoint count as texture proxy: ước lượng texture richness nhẹ, không phải SuperPoint.
- Weighted quality score: tổng hợp các metric để xếp hạng frame.

## 6. Frame Filtering Policies

- `no_filter`: giữ tất cả frame.
- `light_filter`: lọc nhẹ, percentile 20, max_ssim 0.98.
- `medium_filter`: lọc vừa, percentile 40, max_ssim 0.95.
- `strong_filter`: lọc mạnh, percentile 60, max_ssim 0.92.

## 7. Reconstruction Backend

Current backend:

- COLMAP automatic_reconstructor
- COLMAP built-in SIFT feature extraction / matching
- COLMAP sparse reconstruction
- COLMAP dense fusion

Không viết rằng hloc, SuperPoint hay LightGlue đã được dùng cho các kết quả hiện tại.

## 8. Scene01 Results

### Key Result Interpretation

- `light_filter` is the best balanced policy for scene01.
- `no_filter` gives the most points but uses the most frames.
- `light_filter` reduces the input from 635 to 508 frames while keeping strong reconstruction quality.
- `medium_filter` and `strong_filter` produce higher-quality selected frames but reduce coverage and model completeness because they remove too many intermediate views.
- This supports the main Image Processing contribution: frame quality assessment and filtering can reduce redundancy, but filtering must preserve geometric overlap.

### Suggested Tables

- Frame filtering summary table from `outputs/comparisons/scene01_frame_filtering_summary.csv`.
- COLMAP automatic_reconstructor summary table from `outputs/comparisons/scene01_colmap_summary.csv`.

### Suggested Figures

- `outputs/figures/scene01_quality_score_hist.png`
- `outputs/figures/scene01_sharpness_hist.png`
- `outputs/figures/scene01_selected_count_by_policy.png`
- `outputs/figures/scene01_mean_quality_by_policy.png`
- `outputs/figures/scene01_registered_ratio_by_policy.png`
- `outputs/figures/scene01_sparse_points_by_policy.png`
- `outputs/figures/scene01_reprojection_error_by_policy.png`
- `outputs/figures/scene01_dense_points_by_policy.png`

## 9. Planned Extension Pipeline

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

## 10. TODO Phase 4 hloc Integration

- install hloc
- extract SuperPoint features
- generate image pairs
- match with LightGlue
- import matches into COLMAP / run hloc reconstruction
- compare hloc result against current COLMAP SIFT baseline
- compare metrics: registered images, sparse points, reprojection error, dense points, runtime

## 11. TODO DUST3R Fallback

- prepare low-quality image set
- run COLMAP baseline
- run DUST3R
- compare point cloud completeness and visual distortion
- do not claim DUST3R results until actual outputs exist

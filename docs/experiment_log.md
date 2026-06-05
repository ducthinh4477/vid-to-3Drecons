# Experiment Log

## Technical Honesty Note

The project originally planned hloc + SuperPoint + LightGlue, but the current experimental results are generated using COLMAP automatic_reconstructor with SIFT. Therefore, all current reported metrics must be attributed to COLMAP SIFT, not hloc.

Current experiment summary:
The current scene01 results were obtained using COLMAP automatic_reconstructor. COLMAP performed SIFT feature extraction and matching internally, followed by sparse reconstruction and dense fusion. hloc, SuperPoint, and LightGlue were not used in the current run. They remain planned as a future comparison branch.

## Scene01 - COLMAP automatic_reconstructor Results by Frame Filtering Policy

### Cấu hình chung

- Scene: `scene01`
- SfM pipeline: COLMAP automatic_reconstructor with COLMAP SIFT features
- Feature extraction and matching: COLMAP built-in SIFT
- Sparse reconstruction: COLMAP
- Dense fusion: COLMAP
- hloc / SuperPoint / LightGlue: không dùng trong lần chạy hiện tại
- Input video FPS sau khi tách frame: 5 FPS
- Policies: `no_filter`, `light_filter`, `medium_filter`, `strong_filter`

## Tóm tắt frame filtering

| Policy | Total Frames | Selected Frames | Removal Ratio | Mean Quality Score | Notes |
| ------ | -----------: | --------------: | ------------: | -----------------: | ----- |
| no_filter | 635 | 635 | 0% | 0.4071 | Baseline, giữ tất cả frame |
| light_filter | 635 | 508 | 20% | 0.4695 | Lọc nhẹ, giữ overlap tốt |
| medium_filter | 635 | 381 | 40% | 0.5324 | Chất lượng frame cao hơn nhưng coverage giảm |
| strong_filter | 635 | 254 | 60% | 0.6091 | Lọc mạnh, mất nhiều view trung gian |

## COLMAP automatic_reconstructor Results

| Policy | Selected Frames | Images in Model | Registered Images | Registered Ratio | Sparse Points | Observations | Mean Track Length | Mean Observations / Image | Reproj Error | Dense Points | Notes |
| ------ | --------------: | --------------: | ----------------: | ---------------: | ------------: | -----------: | ----------------: | ------------------------: | -----------: | -----------: | ----- |
| no_filter | 635 | 583 | 583 | 100% | 41,441 | 280,504 | 6.768756 | 481.138937 | 1.064571 px | 1,950,803 | Nhiều points nhất nhưng dùng nhiều frame nhất |
| light_filter | 508 | 490 | 490 | 100% | 38,946 | 263,636 | 6.769270 | 538.032653 | 1.051125 px | 1,803,143 | Cân bằng tốt nhất giữa giảm frame và giữ reconstruction |
| medium_filter | 381 | 217 | 217 | 100% | 17,902 | 130,720 | 7.301977 | 602.396313 | 1.071107 px | 804,850 | Frame được lọc tốt hơn nhưng coverage giảm mạnh |
| strong_filter | 254 | 143 | 143 | 100% | 16,995 | 102,571 | 6.035363 | 717.279720 | 0.977788 px | 397,382 | Reprojection error thấp nhưng model nhỏ, kém đầy đủ |

Ghi chú: `Images in Model` là số ảnh nằm trong sparse model tốt nhất do COLMAP báo cáo. `Selected Frames` là số ảnh trong folder sau bước frame filtering.

## Nhận xét theo policy

### no_filter

`no_filter` là baseline không lọc frame. Chính sách này tạo nhiều sparse points và dense points nhất, nhưng dùng nhiều frame nhất nên redundancy và thời gian xử lý cao hơn. Kết quả này hữu ích làm baseline COLMAP SIFT.

### light_filter

`light_filter` giảm input từ 635 xuống 508 frame, tức giảm khoảng 20%, nhưng vẫn giữ 490 ảnh trong model chính và tạo 38,946 sparse points. Reprojection error thấp hơn `no_filter` một chút. Đây là policy cân bằng nhất cho `scene01`.

### medium_filter

`medium_filter` chọn frame có quality score trung bình cao hơn, nhưng chỉ còn 381 frame và model chính chỉ có 217 ảnh. Sparse points và dense points giảm mạnh, cho thấy việc lọc quá nhiều frame trung gian làm giảm coverage hình học.

### strong_filter

`strong_filter` cho reprojection error thấp nhất, nhưng chỉ còn 143 ảnh trong model chính và 16,995 sparse points. Chỉ số nội bộ có vẻ sạch hơn, nhưng model kém đầy đủ hơn vì mất overlap và view trung gian.

## Diễn giải chính

- `light_filter` is the best balanced policy for scene01.
- `no_filter` gives the most points but uses the most frames.
- `light_filter` reduces the input from 635 to 508 frames while keeping strong reconstruction quality.
- `medium_filter` and `strong_filter` produce higher-quality selected frames but reduce coverage and model completeness because they remove too many intermediate views.
- This supports the main Image Processing contribution: frame quality assessment and filtering can reduce redundancy, but filtering must preserve geometric overlap.

## Planned Future Extensions

### TODO Phase 4 hloc Integration

- install hloc
- extract SuperPoint features
- generate image pairs
- match with LightGlue
- import matches into COLMAP / run hloc reconstruction
- compare hloc result against current COLMAP SIFT baseline
- compare metrics: registered images, sparse points, reprojection error, dense points, runtime

### TODO DUST3R Fallback

- prepare low-quality image set
- run COLMAP baseline
- run DUST3R
- compare point cloud completeness and visual distortion
- do not claim DUST3R results until actual outputs exist

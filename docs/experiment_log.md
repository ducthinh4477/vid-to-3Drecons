## Scene01 — COLMAP results by frame filtering policy

### Common configuration

- Scene: scene01
- SfM pipeline: hloc (SuperPoint + LightGlue) + COLMAP
- Input video FPS (sau khi tách): 5 FPS
- Policies: `no_filter`, `light_filter`, `medium_filter`, `strong_filter`

---

## Scene01 — no_filter COLMAP result

### Input

- Policy: `no_filter`
- Frames after selection: 635
- Sparse path: `outputs/reconstructions/scene01/no_filter/colmap/sparse/0`
- (Dense chưa chạy / chưa ghi log)

### Sparse reconstruction metrics

| Metric                    | Value       |
|---------------------------|------------:|
| Images                    | 583         |
| Registered images         | 583         |
| Registered ratio          | 91.8%       |
| Sparse points             | 41,441      |
| Observations              | 280,504     |
| Mean track length         | 6.768756    |
| Mean observations / image | 481.138937  |
| Mean reprojection error   | 1.064571 px |

### Dense reconstruction metrics

Chưa chạy dense reconstruction cho cấu hình `no_filter` (có thể bổ sung sau nếu cần so sánh chi tiết hơn).

### Nhận xét

Pipeline với `no_filter` đăng ký được 583/635 ảnh (≈ 91.8%), tạo ra 41,441 điểm 3D và lỗi tái chiếu trung bình khoảng 1.06 px. Đây là baseline “không lọc” với nhiều frame dư thừa, thời gian matching lớn và không kiểm soát chất lượng từng frame.

---

## Scene01 — light_filter COLMAP result

### Input

- Policy: `light_filter`
- Frames after selection: 508
- Sparse path: `outputs/reconstructions/scene01/light_filter/colmap/sparse/0`
- (Dense chưa chạy / chưa ghi log)

### Sparse reconstruction metrics

| Metric                    | Value       |
|---------------------------|------------:|
| Images                    | 490         |
| Registered images         | 490         |
| Registered ratio          | 96.5%       |
| Sparse points             | 38,946      |
| Observations              | 263,636     |
| Mean track length         | 6.769270    |
| Mean observations / image | 538.032653  |
| Mean reprojection error   | 1.051125 px |

### Dense reconstruction metrics

Chưa chạy dense reconstruction cho cấu hình `light_filter`.

### Nhận xét

So với `no_filter`, `light_filter` giảm số frame đầu vào từ 635 xuống 508 (giảm khoảng 20%) nhưng số ảnh được register vẫn đạt 490, tương đương 96.5%. Reprojection error giảm nhẹ (1.0646 → 1.0511 px), trong khi số quan sát trung bình trên mỗi ảnh tăng (481.14 → 538.03), còn số điểm 3D chỉ giảm nhẹ (41,441 → 38,946). Điều này cho thấy lọc nhẹ loại bỏ được frame mờ/dư mà vẫn giữ đủ overlap để COLMAP tái tạo cảnh ổn định.

---

## Scene01 — medium_filter COLMAP result

### Input

- Policy: `medium_filter`
- Frames after selection: 381
- Sparse path: `outputs/reconstructions/scene01/medium_filter/colmap/sparse/0`
- Dense path: `outputs/reconstructions/scene01/medium_filter/colmap/dense/1/fused.ply`

### Sparse reconstruction metrics

| Metric                    | Value       |
|---------------------------|------------:|
| Images                    | 217         |
| Registered images         | 217         |
| Registered ratio          | 100%        |
| Sparse points             | 17,902      |
| Observations              | 130,720     |
| Mean track length         | 7.301977    |
| Mean observations / image | 602.396313  |
| Mean reprojection error   | 1.071107 px |

### Dense reconstruction metrics

| Metric           | Value        |
|------------------|-------------:|
| Fused points     | 743,392      |
| Dense fusion time| 0.855 minutes|
| Output file      | `dense/1/fused.ply` |

### Nhận xét

COLMAP đăng ký thành công toàn bộ 217 ảnh sau khi lọc bằng `medium_filter` (ratio 100%), với mean track length và observations/image cao hơn so với `no_filter` và `light_filter`, cho thấy các ảnh còn lại liên kết tốt với nhau. Tuy nhiên, số ảnh trong model chính giảm mạnh (từ 490 xuống 217) và số điểm 3D cũng giảm còn 17,902, phản ánh coverage cảnh bị thu hẹp đáng kể. Dense fusion vẫn tạo được 743k điểm cho visualization, nhưng mức lọc medium đã bắt đầu làm mất nhiều frame trung gian quan trọng cho overlap.

---

## Scene01 — strong_filter COLMAP result

### Input

- Policy: `strong_filter`
- Frames after selection: 254
- Sparse path: `outputs/reconstructions/scene01/strong_filter/colmap/sparse/0`
- (Dense chưa chạy / chưa ghi log)

### Sparse reconstruction metrics

| Metric                    | Value       |
|---------------------------|------------:|
| Images                    | 143         |
| Registered images         | 143         |
| Registered ratio          | 100%        |
| Sparse points             | 16,995      |
| Observations              | 102,571     |
| Mean track length         | 6.035363    |
| Mean observations / image | 717.279720  |
| Mean reprojection error   | 0.977788 px |

### Dense reconstruction metrics

Chưa chạy dense reconstruction cho cấu hình `strong_filter`.

### Nhận xét

`strong_filter` cho reprojection error thấp nhất (≈ 0.98 px) và số quan sát trung bình trên mỗi ảnh cao nhất, nhưng số ảnh và số điểm 3D giảm rất mạnh (143 ảnh, 16,995 điểm). Mô hình sparse trở nên nhỏ và tập trung vào một phần cảnh dễ tái tạo hơn, dẫn tới lỗi tái chiếu thấp nhưng coverage toàn cảnh kém hơn. Đây là minh họa điển hình cho việc lọc quá mạnh: mô hình nội bộ “sạch” nhưng không còn phù hợp cho mục tiêu tái tạo đầy đủ cảnh 3D từ video đầu vào.

---

## Scene01 — summary table

### COLMAP Reconstruction Results (scene01)

| Policy        | Images in folder | Registered images | Registered ratio | Sparse points | Mean reproj. error | Dense points | Notes                                      |
|--------------|-----------------:|------------------:|-----------------:|--------------:|--------------------:|------------:|--------------------------------------------|
| no_filter    | 635              | 583               | 91.8%            | 41,441        | 1.0646 px           | N/A         | Baseline, nhiều frame dư, thời gian lớn    |
| light_filter | 508              | 490               | 96.5%            | 38,946        | 1.0511 px           | N/A         | Giảm ~20% frame, giữ coverage rất tốt      |
| medium_filter| 381              | 217               | 100%             | 17,902        | 1.0711 px           | 743,392     | Mô hình thu hẹp, vẫn xem được dạng dense   |
| strong_filter| 254              | 143               | 100%             | 16,995        | 0.9778 px           | N/A         | Lỗi thấp nhưng coverage kém, model rất nhỏ |

### Tổng kết Scene01

- `light_filter` cho kết quả cân bằng nhất: giảm số frame đầu vào khoảng 20% nhưng vẫn giữ được gần như toàn bộ ảnh trong model chính, reprojection error giảm nhẹ và số quan sát trên mỗi ảnh tăng.[file:59]  
- `medium_filter` và `strong_filter` cho thấy lọc quá mạnh có thể làm giảm đáng kể coverage cảnh: số ảnh và số điểm 3D giảm nhiều dù các chỉ số nội bộ như reprojection error hoặc observations/image có thể trông “đẹp” hơn.[file:59]  
- Những quan sát này phù hợp với mục tiêu đề tài: lọc frame ở mức hợp lý (light\_filter) giúp giảm dữ liệu dư thừa mà vẫn duy trì chất lượng tái tạo 3D từ video chất lượng trung bình do người dùng không chuyên quay.[file:59]  
Đồ án này không đặt trọng tâm là dùng nhiều mô hình 3D mạnh, mà đặt trọng tâm là **xử lý ảnh/video trước khi tái tạo 3D**.

Pipeline chính:

```text
Video đầu vào
→ Tách frame
→ Đánh giá chất lượng frame:
   - độ nét / blur
   - độ sáng / exposure
   - độ trùng lặp
   - motion blur
   - số lượng keypoint
→ Tính quality score tổng hợp
→ Lọc frame theo nhiều ngưỡng
→ Nhánh A: frame tốt → hloc: SuperPoint + LightGlue → COLMAP SfM
→ Nhánh B: frame xấu / COLMAP thất bại → DUST3R
→ Đánh giá kết quả:
   - số frame được register
   - số điểm 3D
   - reprojection error
   - thời gian xử lý
   - chất lượng point cloud trực quan

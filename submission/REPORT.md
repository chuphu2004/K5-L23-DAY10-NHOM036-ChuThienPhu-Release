# Báo cáo nhóm 036

## 1. Số liệu luyện tập

- F1 theo seed (rule / cross_check / overall): seed 36007 đo trên lô kiểm tra Linux đúng ID nhóm: ≈ 1,0 / 0,4 / 0,7. Seed 36011: rule ≈ 1,0 theo nhật ký nhóm; chưa lưu cross_check và overall.
- Lô sạch: 0 lỗi luật, 19 ứng viên trên 8 ảnh. Seed 36007: 55 ứng viên trên 32 ảnh, review 20 confirmed và 12 rejected. Seed 36011: 55 ứng viên trên 30 ảnh.
- Ngưỡng đối chiếu: ghép cùng lớp ≥ 0,1; khác lớp ≥ 0,2 và mức khớp cùng lớp < 50% mức khớp khác lớp. Box lệch: segment vượt ≥ 8% cạnh box và < 95% pixel nằm trong box. Thiếu box: segment ≥ 0,5% diện tích ảnh. Gộp vật: segment phủ ≥ 15% mỗi box và IoU hai box < 0,5.
- Cách chọn: thử trên lô sạch, sửa cách ghép để giảm ứng viên từ 70 xuống 19 theo nhật ký nhóm; không đọc đáp án riêng.

## 2. Vì sao báo hết ứng viên làm F1 giảm?

Lô sạch vẫn có 19 ứng viên dù không có lỗi gài. Seed 36007 có 12/32 dòng review bị bác bỏ. Báo hết ứng viên sẽ tăng báo thừa, giảm precision và F1.

## 3. Quyết định và lineage

V1 có 34/250 ảnh lỗi = 13,6% > 2% nên Hold. Lineage ghi HOLD cho lab250_20c49a5c6d97 và release v2 có parent là v1. R-021 đã train trên v1 nên cần đánh giá lại hoặc train lại; đổi dataset không sửa trọng số đã học.

V2 giữ 228 ảnh, 1.517 box; tách 22 ảnh rework và giữ 8 ảnh chỉ lỗi panoptic. Cảnh scene_378 giữ lại 4 ảnh cùng split train, trong đó 1 ảnh được đổi từ val sang train.

## 4. Hash chứng minh gì, không chứng minh gì?

SHA-256 chứng minh nội dung file khớp bản đã lập manifest, không chứng minh nhãn đúng. Manifest v2 có 456 file: 228 ảnh và 228 nhãn. Hai ảnh sai hash được nhóm kiểm tra, giữ nguyên ảnh và cập nhật hash ở v2; v1 giữ nguyên.

## 5. Truy vết

Chọn ảnh thuộc job guideline v1.2 và có box wine glass (lớp 40). Lấy guideline theo jobs.csv vì guideline ghi trên ảnh có thể sai.

Tier_a có 3 ảnh trong scene_324 và scene_690; tier_b có 4 ảnh khác trong scene_219 và scene_378. Notify gồm A02, Q02, A04, Q01. Theo kết quả nhóm đã ghi, F1 tier_a, tier_b và notify đều làm tròn 1,0.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)

Nhóm ghi nhận cùng seed có release ID khác giữa các môi trường; ZIP đóng trên Windows/Python 3.13 và Linux/Python 3.10 cũng có hash khác. Bài nộp dùng bản của nhóm lab250_20c49a5c6d97, đóng và kiểm trên Linux/Python 3.10; nhóm đã ghi H1–H15 PASS trong môi trường này. Kiểm tra lại ngày 20/11/2026 trên WSL Ubuntu/Python 3.12.3: H1–H17 đều PASS.

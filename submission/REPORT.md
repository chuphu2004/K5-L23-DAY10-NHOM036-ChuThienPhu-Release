# Báo cáo nhóm <<XX>>

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall): <<seed: ... / ... / ...>>
- Số ứng viên trên lô sạch (`--no-faults`): <<...>>; hàng đợi trên seed luyện tập: <<... ảnh>>
- Ngưỡng đã chọn và cách chọn (không dùng `_private`): <<...>>

## 2. Vì sao báo hết ứng viên làm F1 giảm?
<<Trả lời bằng số của nhóm.>>

## 3. Quyết định và lineage
Seed 36007 có 34 mục lỗi trên 250 ảnh (13,6%), vượt ngưỡng 2%. Nhóm đã ghi HOLD cho v1 `lab250_20c49a5c6d97`. Run `R-021` đã dùng v1 để train. Thay dataset sau đó không thay đổi trọng số đã học, nên đội AI cần đánh giá lại run và cân nhắc train lại bằng v2.

Lô detection `lab250_20c49a5c6d97_v2` có 228 ảnh và 1.517 box. Nhóm đã tách 22 ảnh để rework và giữ 8 ảnh chỉ lỗi panoptic, có ghi mã trong README bàn giao. Cụm “5 scene_leak corrected” ở trường detail của lineage cần đọc theo dữ liệu thực tế: chỉ có **một cảnh rò split**, gồm 5 ảnh ở v1. Trong v2, 1 ảnh của cảnh đã vào rework, 1 ảnh đổi split và cả 4 ảnh giữ lại thuộc train.

## 4. Hash chứng minh gì, không chứng minh gì?
Manifest v2 ghi SHA-256 cho 228 JPG và 228 file nhãn YOLO. Đối chiếu với manifest cho biết các file có giữ nguyên nội dung byte so với thời điểm lập bảng hay không. Một box gán sai vẫn có hash hợp lệ, nên việc đánh giá nhãn cần dựa vào xem ảnh. Nhóm đã kiểm hai JPG sai hash ở v1, giữ ảnh và nhãn gốc, rồi ghi hash thực vào manifest v2.

## 5. Truy vết
Ticket nêu hai cảnh `scene_324` và `scene_690`. Từ v1.3, ly rượu bị che trên 50% hoặc bị cắt ở mép ảnh vẫn phải có box. Để tìm ảnh cần mở lại, nhóm dùng nhãn detection của lô v1 mà R-021 đã train. Nhóm nối mỗi ảnh với job qua metadata, lấy phiên bản guideline từ jobs.csv vì phiên bản ghi trên từng ảnh có thể sai. Trong các job dùng v1.2, nhóm chọn ảnh có ít nhất một box lớp 40 (`wine glass`).

Ba ảnh trong hai cảnh được báo thuộc tier_a. Bốn ảnh còn lại thuộc tier_b, nằm ở scene_219 và scene_378. Hai job liên quan là J02 (A02, Q02) và J04 (A04, Q01). Đây là bảy ảnh cần mở lại để kiểm tra ticket. Công cụ tự đo trả về F1 làm tròn 1,0 cho từng danh sách tier_a, tier_b và notify.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
Khi dùng script gốc trên cùng thư mục v2, bản ZIP tạo bằng Windows/Python 3.13 có SHA-256 khác bản tạo bằng Linux/Python 3.10. Gói nộp được đóng và kiểm bằng Linux/Python 3.10. H1–H15 đều PASS trong môi trường này. Trên Windows có thể dùng `Get-FileHash` để đối chiếu trực tiếp bản ZIP đã giao với file `.sha256`.

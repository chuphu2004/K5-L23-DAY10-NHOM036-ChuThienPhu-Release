Release: lab250_20c49a5c6d97_v2
Parent: lab250_20c49a5c6d97
Số ảnh: 228
Số nhãn: 1517
Guideline: v1.2 cho J01–J04, v1.3 cho J05–J10.
QC v1: 34/250 = 13,6%
Kết luận v1: Hold vì tỷ lệ lỗi vượt ngưỡng 2%.
Kết luận v2: Release cho detection. Trong 228 ảnh bàn giao, còn 0/228 ảnh có lỗi detection hoặc lỗi file đã biết cần rework. 22 ảnh còn lại của v1 được tách ra để xử lý riêng.
Ghi chú: 000000008021 (wrong_hash) — Ảnh mở đầy đủ. Hai box person ở tiền cảnh bao quanh hai khán giả. Box person ở giữa và box tie tương ứng với người thuyết trình và cà vạt hiển thị trên màn hình sân khấu. Giữ ảnh và nhãn YOLO gốc. SHA-256 đã ghi trong manifest v2: 235537407867a7b894e78b3aecb55b33b14b64cbb23ca376a00d34c62a1a63a6.
000000025139 (wrong_hash) — Sau khi xem lại ảnh và hai box zebra, người review xác nhận giữ ảnh cùng nhãn YOLO gốc cho v2. SHA-256 đã ghi trong manifest v2: 9c1c256049d80c05aec424d06263b1e0f204c3e5c20352a76b9897fa3ae581f3.

Rework: 22 ảnh gồm 6 bbox_drift, 5 class_swap, 5 missing_box, 2 duplicate_box, 2 invalid_class, 1 bbox_out_of_bounds và 1 missing_image. Mỗi dòng trong rework_queue.csv ghi mã ảnh, người gán, người kiểm của job gốc và việc phải làm. Đội AI dùng 228 cặp JPG/TXT còn lại, sao nguyên từ v1.
Truy vết: ảnh 000000024027 thuộc J10, đổi guideline từ v1.2 sang v1.3 theo jobs.csv. Cảnh scene_378 có 5 ảnh ở v1 (4 train, 1 val). Trong v2, ảnh 000000007574 vào rework vì thiếu box. Chuyển 000000007816 từ val sang train để cả 4 ảnh giữ lại thuộc train.
Chuyển đội panoptic kiểm lại 8 ảnh. Nhãn detection của các ảnh sau được giữ nguyên trong v2:
- category_swap: 000000000139, 000000018380, 000000020553.
- instance_merge: 000000013729.
- invalid_category_id: 000000007795, 000000015597.
- thing_overlap: 000000001584, 000000017899.

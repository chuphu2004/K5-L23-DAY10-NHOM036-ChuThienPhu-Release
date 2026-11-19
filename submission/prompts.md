# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Chu Thiên Phú | Claude Code (Claude Opus 5.5) | "viết validator luật" theo GUIDE Pha 1 và DELIVERY.md mục 2: 9 loại lỗi, chỉ thư viện chuẩn, chỉ đọc delivery | Lần đầu dùng `pkill -f` để dừng tiến trình chờ tải dữ liệu, lệnh tự giết chính shell của nó (không ảnh hưởng validator). Ngưỡng `duplicate_box`/`bbox_out_of_bounds` do AI tự chọn, chưa thử trên đề đã lật/nén lại | Chạy `score_findings.py`: lỗi luật F1 ≈ 1.0 trên seed 36007 và 36011; lô sạch `runs/clean` báo 0 lỗi luật |

# Nhóm 036

- Seed luyện tập: **36007** (release_id v1: `lab250_20c49a5c6d97`)
- Repo: <https://github.com/chuphu2004/K5-L23-DAY10-NHOM036-ChuThienPhu-Release>

## Tạo lô trên máy mình (mỗi người chạy một lần, từ thư mục gốc repo)

```bash
python scripts/download_public.py                                          # ~1 GB
python scripts/run_lab.py --seeds 36007                                    # lô luyện tập + R-021 vào lineage
python scripts/inject_release.py --seed 5 --no-faults --out runs/clean     # lô sạch (đo lệch tự nhiên)
python scripts/inject_release.py --seed 36011 --out runs/r36011            # seed phụ để thử validator
```

Cùng seed thì ra cùng lô, nên `release_id` phải là `lab250_20c49a5c6d97`. Không chạy lại `run_lab.py`, không mở `runs/*/_private/`.

| Họ và tên | MSHV | Tài khoản GitHub | Phần chính |
| --- | --- | --- | --- |
| Chu Thiên Phú | 2A202603114 | chuphu2004 | <<>> |
| Lưu Nhật Nam | 2A202603243 | <<>> | <<>> |
| Hoàng Thu Hương | 2A202603143 | borisbrjch | P3, P4 |
| Nguyễn Việt Anh | 2A202603095 | vietanhngx | P6 |

Phần chính: validator luật / đối chiếu / review / bàn giao / truy vết / bảo mật. Ai cũng phải xem ảnh ở Pha 2.

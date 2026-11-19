#!/usr/bin/env python3
"""Công cụ xem ảnh cho Pha 2 (không phải validator, nên được dùng Pillow + numpy: pip install pillow numpy).

  python validator/review_tool.py runs/r36007/delivery runs/r36007/candidates.json --out runs/r36007/review

Mỗi ứng viên vẽ 3 ô cùng một vùng cắt (phóng to):
  1. ảnh gốc, không vẽ gì: để nhìn vật thật
  2. box detection (đỏ = box của ứng viên, vàng = box khác) + tên lớp
  3. viền segment panoptic (mỗi segment một màu) + tên lớp
Ghi ra <out>/index.html (mở bằng trình duyệt) và <out>/review_log_todo.csv để điền verdict/note.

Trang điền review cho từng người (chọn dòng theo thứ tự trong review_log_todo.csv):
  python validator/review_tool.py runs/r36007/delivery runs/r36007/candidates.json --out runs/r36007/review --reviewer "Lưu Nhật Nam" --rows 9-16
-> <out>/review_<tên>.html: chọn verdict/type, ghi note, bấm tải về review_<tên>.csv (image,type,verdict,note).
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:  # font có dấu tiếng Việt; máy không có thì dùng font mặc định và chữ không dấu
    FONT = ImageFont.truetype("DejaVuSans.ttf", 13)
    TITLES = ["ảnh gốc", "detection", "panoptic"]
except OSError:
    FONT = ImageFont.load_default()
    TITLES = ["anh goc", "detection", "panoptic"]

PANEL = 420  # cạnh dài của mỗi ô sau khi phóng to
PALETTE = [(0, 200, 255), (0, 255, 120), (255, 120, 0), (200, 0, 255), (255, 0, 120), (120, 255, 0), (0, 120, 255)]


def region(c, width, height):
    """Vùng cắt: hợp các box/segment của ứng viên, nới thêm 40% mỗi phía."""
    rects = []
    if "box" in c:
        rects.append(c["box"])
    for b in c.get("boxes", []):
        rects.append(b)
    if "segment_bbox" in c:
        rects.append(c["segment_bbox"])  # [x1, y1, x2, y2] đo từ mask
    x1 = min(r[0] for r in rects); y1 = min(r[1] for r in rects)
    x2 = max(r[2] for r in rects); y2 = max(r[3] for r in rects)
    pad = 0.4 * max(x2 - x1, y2 - y1, 40)
    return (max(0, int(x1 - pad)), max(0, int(y1 - pad)), min(width, int(x2 + pad)), min(height, int(y2 + pad)))


def render(d: Path, c: dict, classes: dict, cats: dict, ann: dict) -> Image.Image:
    name = c["image"]
    img = Image.open(d / "images" / f"{name}.jpg").convert("RGB")
    W, H = img.size
    x1, y1, x2, y2 = region(c, W, H)
    scale = PANEL / max(x2 - x1, y2 - y1)
    size = (max(1, round((x2 - x1) * scale)), max(1, round((y2 - y1) * scale)))

    def crop(im):
        return im.crop((x1, y1, x2, y2)).resize(size, Image.LANCZOS)

    def to_panel(px, py):
        return (px - x1) * scale, (py - y1) * scale

    raw = crop(img)

    det = crop(img)
    dd = ImageDraw.Draw(det)
    marked = [c["box"]] if "box" in c else c.get("boxes", [])
    for line in (d / "labels" / f"{name}.txt").read_text().splitlines():
        p = line.split()
        if len(p) != 5:
            continue
        k, x, y, w, h = int(p[0]), *map(float, p[1:])
        b = [(x - w / 2) * W, (y - h / 2) * H, (x + w / 2) * W, (y + h / 2) * H]
        hot = any(all(abs(b[t] - m[t]) <= 1.5 for t in range(4)) for m in marked)
        a, bb = to_panel(b[0], b[1]), to_panel(b[2], b[3])
        dd.rectangle([a, bb], outline=(255, 0, 0) if hot else (255, 220, 0), width=3 if hot else 1)
        dd.text((a[0] + 3, a[1] + 2), classes.get(k, f"?{k}"), fill=(255, 0, 0) if hot else (255, 220, 0), font=FONT)

    pan = crop(img)
    m_img = Image.open(d / "masks" / f"{name}.png").convert("RGB").crop((x1, y1, x2, y2)).resize(size, Image.NEAREST)
    mask = np.asarray(m_img, dtype=np.int64)
    ids = mask[..., 0] + mask[..., 1] * 256 + mask[..., 2] * 65536
    edge = np.zeros(ids.shape, bool)
    edge[1:, :] |= ids[1:, :] != ids[:-1, :]
    edge[:, 1:] |= ids[:, 1:] != ids[:, :-1]
    arr = np.asarray(pan).copy()
    pd = []
    for n, s in enumerate(ann["segments_info"]):
        if not cats.get(s["category_id"], {}).get("isthing"):
            continue
        m = ids == s["id"]
        if not m.any():
            continue
        color = PALETTE[n % len(PALETTE)]
        arr[m & edge] = color
        arr[m] = (arr[m] * 0.75 + np.array(color) * 0.25).astype(np.uint8)
        ys, xs = np.nonzero(m)
        label = cats[s["category_id"]]["name"] + (" (crowd)" if s.get("iscrowd") else "")
        # đặt chữ trên pixel của chính segment gần tâm nhất: segment hình vành (vd giường bao quanh)
        # có tâm rơi vào vật khác, đặt ở tâm sẽ gán nhầm tên cho vật đó
        k = int(np.argmin((xs - xs.mean()) ** 2 + (ys - ys.mean()) ** 2))
        pd.append((int(xs[k]), int(ys[k]), label, color))
    pan = Image.fromarray(arr)
    dp = ImageDraw.Draw(pan)
    for x, y, label, color in pd:
        dp.text((x - 10, y), label, fill=(255, 255, 255), font=FONT, **({"stroke_width": 2, "stroke_fill": (0, 0, 0)} if TITLES[0] == "ảnh gốc" else {}))

    gap, head = 8, 22
    sheet = Image.new("RGB", (size[0] * 3 + gap * 2, size[1] + head), (255, 255, 255))
    d2 = ImageDraw.Draw(sheet)
    for k, (im, title) in enumerate(zip([raw, det, pan], TITLES)):
        sheet.paste(im, (k * (size[0] + gap), head))
        d2.text((k * (size[0] + gap) + 4, 4), title, fill=(0, 0, 0), font=FONT)
    return sheet


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("delivery", type=Path)
    ap.add_argument("candidates", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--reviewer", help="tên người xem: tạo thêm trang điền review riêng")
    ap.add_argument("--rows", default="1-999", help="dòng của người đó trong review_log_todo.csv, vd 9-16")
    args = ap.parse_args()
    d = args.delivery
    classes = {int(l.split()[0]): l.split(maxsplit=1)[1] for l in (d / "classes.txt").read_text().splitlines() if l.strip()}
    pan = json.loads((d / "panoptic.json").read_text())
    cats = {c["id"]: c for c in pan["categories"]}
    anns = {Path(a["file_name"]).stem: a for a in pan["annotations"]}
    cands = json.loads(args.candidates.read_text())["candidates"]
    args.out.mkdir(parents=True, exist_ok=True)

    by_image: dict[str, list[dict]] = {}
    for c in cands:
        by_image.setdefault(c["image"], []).append(c)

    rows, parts = [], []
    for name, cs in by_image.items():
        parts.append(f"<h2 id='{name}'>{name}</h2>")
        for k, c in enumerate(cs):
            png = f"{name}_{k}.png"
            render(d, c, classes, cats, anns[name]).save(args.out / png)
            info = html.escape(f"{c['type']}: {c.get('hint', '')}")
            parts.append(f"<p><b>{info}</b></p><img src='{png}' loading='lazy'>")
        # mỗi ảnh mang nhiều nhất một lỗi: một dòng cho mỗi ảnh, loại gợi ý là ứng viên đầu
        rows.append({"image": name, "type": cs[0]["type"], "verdict": "", "note": "",
                     "reviewer": "", "goi_y": " | ".join(c["type"] for c in cs)})

    (args.out / "index.html").write_text(
        "<meta charset='utf-8'><title>Review</title><style>body{font-family:sans-serif;margin:16px}"
        "img{max-width:100%;border:1px solid #ccc}h2{border-top:2px solid #333;padding-top:8px}</style>"
        f"<h1>{len(by_image)} ảnh, {len(cands)} ứng viên</h1>"
        "<p>Mỗi ảnh có nhiều nhất một lỗi. Với class_swap|category_swap: nhìn ô ảnh gốc, nguồn nào ghi đúng vật thì nguồn kia sai.</p>"
        + "\n".join(parts), encoding="utf-8")
    with (args.out / "review_log_todo.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["image", "type", "verdict", "note", "reviewer", "goi_y"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(by_image)} ảnh, {len(cands)} ứng viên -> {args.out}/index.html, review_log_todo.csv")
    if args.reviewer:
        a, _, b = args.rows.partition("-")
        mine = rows[int(a) - 1:int(b or a)]
        page = reviewer_page(args.out, args.reviewer, args.rows, mine, by_image, args.delivery.parent.name)
        print(f"{len(mine)} ảnh cho {args.reviewer} -> {page}")
    return 0


def reviewer_page(out: Path, name: str, rows_label: str, mine: list[dict], by_image: dict, run: str) -> Path:
    """Trang điền review cho một người; bản nháp lưu trong trình duyệt, kết quả tải về dạng CSV."""
    slug = re.sub(r"[^a-z0-9]+", "_", unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D"))
                  .encode("ascii", "ignore").decode().lower()).strip("_")
    data = [{"image": r["image"], "cands": [{"png": f"{r['image']}_{k}.png", "type": c["type"], "hint": c.get("hint", "")}
                                             for k, c in enumerate(by_image[r["image"]])]} for r in mine]
    tpl = (Path(__file__).with_name("review_form.html")).read_text(encoding="utf-8")
    fill = {"__DATA__": json.dumps(data, ensure_ascii=False), "__NAME__": html.escape(name), "__ROWS__": rows_label,
            "__RUN__": run, "__KEY__": f"review_{slug}_{run.lstrip('r')}", "__FILE__": f"review_{slug}.csv"}
    for k, v in fill.items():
        tpl = tpl.replace(k, v)
    page = out / f"review_{slug}.html"
    page.write_text(tpl, encoding="utf-8")
    return page


if __name__ == "__main__":
    raise SystemExit(main())

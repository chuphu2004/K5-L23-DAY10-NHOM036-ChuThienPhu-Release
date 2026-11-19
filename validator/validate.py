#!/usr/bin/env python3
"""Validator lỗi luật cho lô Day 10. Chỉ thư viện chuẩn, chỉ đọc thư mục delivery được truyền vào.

  python validator/validate.py <delivery> --out errors.json [--candidates candidates.json]

Lỗi luật (DELIVERY.md mục 2): missing_image, wrong_hash, invalid_class, bbox_out_of_bounds,
duplicate_box, scene_leak, guideline_mismatch, invalid_category_id, thing_overlap.
Phần ứng viên gán nhãn (--candidates) làm ở Pha 2.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Chỉ import pngutil (đọc PNG, thư viện chuẩn) theo RULES; không đọc gì khác ngoài delivery.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pngutil import read_rgb  # noqa: E402

OOB_EPS = 1e-4      # toạ độ chuẩn hoá; nhãn YOLO gốc làm tròn 6 chữ số nên không bao giờ vượt quá 1e-4
DUP_SIZE_PX = 1.0   # box lặp: cùng kích thước (sai số làm tròn)
DUP_SHIFT_PX = 3.0  # box lặp: tâm lệch 1–2 pixel; cặp tự nhiên chồng nhau thường khác kích thước

# Ngưỡng Pha 2, chọn bằng cách đo trên lô sạch runs/clean (xem REPORT.md).
SAMPLE = 2               # lấy mẫu pixel mask mỗi 2 px theo mỗi chiều
OWN_MATCH = 0.1          # box "nhận" segment cùng lớp khi "IoU pixel" >= mức này
SWAP_MATCH = 0.2         # box trùng một segment khác lớp ở mức này trở lên
SWAP_SAME_RATIO = 0.5    # ... và segment cùng lớp tốt nhất khớp kém hơn một nửa
DRIFT_MIN_PX = 400       # vật nhỏ hơn: làm tròn toạ độ đủ làm lệch vài pixel, không xét
DRIFT_OVERHANG = 0.08    # segment thò ra ngoài box >= 8% cạnh box
DRIFT_FRAC_IN = 0.95     # ... và có pixel segment thật sự rơi ra ngoài box
MISSING_MIN_FRAC = 0.005 # segment chiếm >= 0.5% ảnh mới coi là "vật đáng kể"
MERGE_FILL = 0.15        # mỗi box có >= 15% diện tích phủ bởi segment
MERGE_BOX_IOU_MAX = 0.5  # hai box đó không trùng nhau


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    boxes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        try:
            boxes.append((int(float(parts[0])), *map(float, parts[1:])))
        except ValueError:
            continue
    return boxes


def check_files(delivery: Path, items: dict) -> dict[str, str]:
    found = {}
    for name, item in items.items():
        image = delivery / item["image"]
        if not image.is_file():
            found[name] = "missing_image"
            continue
        for key in ("image", "label", "mask"):
            path = delivery / item.get(key, "")
            expected = item.get(f"{key}_sha256")
            if expected and path.is_file() and sha256(path) != expected.lower():
                found[name] = "wrong_hash"
                break
    return found


def check_labels(delivery: Path, items: dict, class_ids: set[int], sizes: dict) -> dict[str, str]:
    found = {}
    for name, item in items.items():
        path = delivery / item.get("label", f"labels/{name}.txt")
        if not path.is_file():
            continue
        boxes = read_labels(path)
        if any(c not in class_ids for c, *_ in boxes):
            found[name] = "invalid_class"
        elif any(x - w / 2 < -OOB_EPS or y - h / 2 < -OOB_EPS or x + w / 2 > 1 + OOB_EPS or y + h / 2 > 1 + OOB_EPS
                 for _, x, y, w, h in boxes):
            found[name] = "bbox_out_of_bounds"
        elif name in sizes and has_duplicate(boxes, *sizes[name]):
            found[name] = "duplicate_box"
    return found


def has_duplicate(boxes, width: int, height: int) -> bool:
    px = [(c, x * width, y * height, w * width, h * height) for c, x, y, w, h in boxes]
    for i, (c1, x1, y1, w1, h1) in enumerate(px):
        for c2, x2, y2, w2, h2 in px[i + 1:]:
            if (c1 == c2 and abs(w1 - w2) <= DUP_SIZE_PX and abs(h1 - h2) <= DUP_SIZE_PX
                    and abs(x1 - x2) <= DUP_SHIFT_PX and abs(y1 - y2) <= DUP_SHIFT_PX):
                return True
    return False


def check_metadata(delivery: Path, meta: list[dict]) -> tuple[dict[str, str], list[str]]:
    with (delivery / "jobs.csv").open(encoding="utf-8", newline="") as f:
        job_guideline = {row["job_id"].strip(): row["guideline"].strip() for row in csv.DictReader(f)}
    found = {}
    for m in meta:
        expected = job_guideline.get(m.get("job_id", ""))
        if expected and m.get("guideline_version", "").strip() != expected:
            found[m["image"]] = "guideline_mismatch"
    splits = defaultdict(set)
    for m in meta:
        splits[m["scene_id"]].add(m["split"])
    leaks = sorted(scene for scene, s in splits.items() if len(s) > 1)
    return found, leaks


def read_mask(path: Path) -> tuple[Counter, dict[int, list[tuple[int, int]]]]:
    """Đếm pixel thật của từng segment, và lấy mẫu toạ độ (bước SAMPLE) để đo pixel nằm trong box."""
    width, height, pixels = read_rgb(path)
    counts = Counter(pixels[i] + pixels[i + 1] * 256 + pixels[i + 2] * 65536 for i in range(0, len(pixels), 3))
    points: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for y in range(0, height, SAMPLE):
        row = y * width * 3
        for x in range(0, width, SAMPLE):
            i = row + x * 3
            points[pixels[i] + pixels[i + 1] * 256 + pixels[i + 2] * 65536].append((x, y))
    return counts, points


def check_panoptic(delivery: Path, panoptic: dict, masks: dict) -> dict[str, str]:
    valid = {c["id"] for c in panoptic["categories"]}
    found = {}
    for ann in panoptic["annotations"]:
        name = Path(ann["file_name"]).stem
        segments = ann.get("segments_info", [])
        if any(s["category_id"] not in valid for s in segments):
            found[name] = "invalid_category_id"
            continue
        mask = delivery / "masks" / ann["file_name"]
        if not mask.is_file():
            continue
        masks[name] = read_mask(mask)
        counts = masks[name][0]
        # area khai nhiều hơn số pixel thật => segment bị vật khác đè
        if any(s["area"] > counts.get(s["id"], 0) for s in segments):
            found[name] = "thing_overlap"
    return found


# ---------------- Pha 2: ứng viên lỗi gán nhãn (đối chiếu detection ↔ panoptic) ----------------

def inside(points, box) -> int:
    x1, y1, x2, y2 = box
    return sum(1 for x, y in points if x1 <= x <= x2 and y1 <= y <= y2)


def image_candidates(name, boxes, segments, cat_name, points, width, height) -> list[dict]:
    """boxes: [(tên lớp, (x1,y1,x2,y2) pixel)]; segments: segment thing của ảnh (kể cả crowd).

    Segment crowd (đám đông) vẫn dùng để ghép box, nhưng không sinh ứng viên từ nó: COCO không có box riêng cho crowd.
    """
    segs = [(s, cat_name[s["category_id"]], points.get(s["id"], [])) for s in segments]
    segs = [(s, n, p) for s, n, p in segs if p]
    if not segs:
        return []
    # cover[i][j] = số pixel mẫu của segment j nằm trong box i
    cover = [[inside(p, b) for _, _, p in segs] for _, b in boxes]
    box_px = [max(1.0, (b[2] - b[0]) * (b[3] - b[1]) / SAMPLE ** 2) for _, b in boxes]
    # bbox thật của segment, đo từ pixel mask (không tin bbox khai trong json)
    seg_box = [(min(x for x, _ in p), min(y for _, y in p), max(x for x, _ in p) + SAMPLE, max(y for _, y in p) + SAMPLE)
               for _, _, p in segs]

    def score(i, j):  # "IoU pixel" giữa box i và segment j
        c = cover[i][j]
        return c / (len(segs[j][2]) + box_px[i] - c)

    def crowd(j):
        return bool(segs[j][0].get("iscrowd"))

    out = []
    owner: dict[int, int] = {}   # box i -> segment cùng lớp khớp nhất
    swapped: set[int] = set()    # segment đã bị một box khác lớp nhận (ứng viên đổi lớp)
    for i, (cls, box) in enumerate(boxes):
        best = max(range(len(segs)), key=lambda j: score(i, j))
        same = [j for j in range(len(segs)) if segs[j][1] == cls]
        best_same = max(same, key=lambda j: score(i, j)) if same else None
        s_same = score(i, best_same) if best_same is not None else 0.0
        if best_same is not None and s_same >= OWN_MATCH:
            owner[i] = best_same
        if crowd(best):
            continue
        # box nằm đúng chỗ một segment khác lớp, và không segment cùng lớp nào khớp tương đương
        if segs[best][1] != cls and score(i, best) >= SWAP_MATCH and s_same < SWAP_SAME_RATIO * score(i, best):
            swapped.add(best)
            out.append({"image": name, "type": "class_swap|category_swap", "box": [round(v) for v in box],
                        "detection": cls, "panoptic": segs[best][1], "score": round(score(i, best), 2),
                        "hint": f"box {cls} trùng segment {segs[best][1]}: mở ảnh xem vật là gì"})
            continue
        if i in owner and not crowd(owner[i]) and segs[owner[i]][0]["area"] >= DRIFT_MIN_PX:
            j = owner[i]
            # COCO: box bao trọn vật nên segment nằm gọn trong box; segment thò ra ngoài box => box lệch
            sx1, sy1, sx2, sy2 = seg_box[j]
            x1, y1, x2, y2 = box
            bw, bh = max(1.0, x2 - x1), max(1.0, y2 - y1)
            over = max((x1 - sx1) / bw, (sx2 - x2) / bw, (y1 - sy1) / bh, (sy2 - y2) / bh)
            frac_in = cover[i][j] / len(segs[j][2])
            if over >= DRIFT_OVERHANG and frac_in < DRIFT_FRAC_IN:
                out.append({"image": name, "type": "bbox_drift", "box": [round(v) for v in box], "detection": cls,
                            "segment_bbox": [round(v) for v in seg_box[j]], "overhang": round(over, 2),
                            "frac_in": round(frac_in, 2),
                            "hint": f"segment {cls} thò ra ngoài box {over:.0%} cạnh box, {frac_in:.0%} pixel nằm trong"})

    min_px = MISSING_MIN_FRAC * width * height / SAMPLE ** 2
    owned = defaultdict(list)
    for i, j in owner.items():
        owned[j].append(i)
    for j, (s, cls, pts) in enumerate(segs):
        if crowd(j) or j in swapped:
            continue
        # vật lớn không có box cùng lớp nào nhận, cũng không bị box khác lớp nhận => thiếu box
        if not owned[j] and len(pts) >= min_px:
            out.append({"image": name, "type": "missing_box", "panoptic": cls, "segment_bbox": [round(v) for v in seg_box[j]],
                        "hint": f"segment {cls} {s['area']} px không có box {cls} nào"})
            continue
        # hai box cùng lớp cùng nhận segment này (segment riêng của vật thứ hai đã mất), mỗi box phủ
        # phần đáng kể pixel của segment trong vùng box, hai box không trùng nhau => hai vật bị gộp
        mine = [i for i in owned[j] if cover[i][j] / box_px[i] >= MERGE_FILL]
        pair = next(((a, b) for a in mine for b in mine if a < b and iou(boxes[a][1], boxes[b][1]) < MERGE_BOX_IOU_MAX), None)
        if pair:
            out.append({"image": name, "type": "instance_merge", "panoptic": cls, "segment_bbox": [round(v) for v in seg_box[j]],
                        "boxes": [[round(v) for v in boxes[k][1]] for k in pair],
                        "hint": f"một segment {cls} phủ hai box {cls} tách nhau"})
    return out


def iou(a, b) -> float:
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter)


def find_candidates(delivery, items, panoptic, class_names, sizes, masks, skip) -> list[dict]:
    cat_name = {c["id"]: c["name"] for c in panoptic["categories"]}
    is_thing = {c["id"] for c in panoptic["categories"] if c.get("isthing")}
    out = []
    for ann in panoptic["annotations"]:
        name = Path(ann["file_name"]).stem
        if name in skip or name not in masks or name not in sizes:
            continue  # mỗi ảnh mang nhiều nhất một lỗi: ảnh đã có lỗi luật thì không xét
        width, height = sizes[name]
        label = delivery / items.get(name, {}).get("label", f"labels/{name}.txt")
        boxes = [(class_names[c], ((x - w / 2) * width, (y - h / 2) * height, (x + w / 2) * width, (y + h / 2) * height))
                 for c, x, y, w, h in (read_labels(label) if label.is_file() else []) if c in class_names]
        segments = [s for s in ann.get("segments_info", []) if s["category_id"] in is_thing]
        out += image_candidates(name, boxes, segments, cat_name, masks[name][1], width, height)
    return out



def main() -> int:
    ap = argparse.ArgumentParser(description="Validator lỗi luật Day 10")
    ap.add_argument("delivery", type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--candidates", type=Path)
    args = ap.parse_args()
    d = args.delivery

    items = read_json(d / "manifest.json")["items"]
    meta = read_json(d / "metadata.json")["items"]
    panoptic = read_json(d / "panoptic.json")
    class_names = {int(line.split()[0]): line.split(maxsplit=1)[1].strip()
                   for line in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if line.strip()}
    class_ids = set(class_names)
    sizes = {Path(im["file_name"]).stem: (im["width"], im["height"]) for im in panoptic["images"]}

    found: dict[str, str] = {}
    masks: dict = {}
    # Mỗi ảnh mang nhiều nhất một lỗi; lỗi file ưu tiên trước, các tầng sau không ghi đè.
    for part in (check_files(d, items), check_labels(d, items, class_ids, sizes), check_panoptic(d, panoptic, masks)):
        for name, kind in part.items():
            found.setdefault(name, kind)
    guideline, leaks = check_metadata(d, meta)
    for name, kind in guideline.items():
        found.setdefault(name, kind)

    errors = [{"type": t, "target": n} for n, t in sorted(found.items())]
    errors += [{"type": "scene_leak", "target": s} for s in leaks]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"errors": errors}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(errors)} lỗi luật -> {args.out}", dict(Counter(e["type"] for e in errors)))
    if args.candidates:
        # ảnh thuộc cảnh bị scene_leak vẫn xét: lỗi đó gắn với cảnh, không phải ảnh
        cands = find_candidates(d, items, panoptic, class_names, sizes, masks, skip=set(found))
        args.candidates.parent.mkdir(parents=True, exist_ok=True)
        args.candidates.write_text(json.dumps({"candidates": cands}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{len(cands)} ứng viên gán nhãn -> {args.candidates}", dict(Counter(c["type"] for c in cands)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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


def check_panoptic(delivery: Path, panoptic: dict) -> dict[str, str]:
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
        _, _, pixels = read_rgb(mask)
        counts = Counter(pixels[i] + pixels[i + 1] * 256 + pixels[i + 2] * 65536 for i in range(0, len(pixels), 3))
        # area khai nhiều hơn số pixel thật => segment bị vật khác đè
        if any(s["area"] > counts.get(s["id"], 0) for s in segments):
            found[name] = "thing_overlap"
    return found


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
    class_ids = {int(line.split()[0]) for line in (d / "classes.txt").read_text(encoding="utf-8").splitlines() if line.strip()}
    sizes = {Path(im["file_name"]).stem: (im["width"], im["height"]) for im in panoptic["images"]}

    found: dict[str, str] = {}
    # Mỗi ảnh mang nhiều nhất một lỗi; lỗi file ưu tiên trước, các tầng sau không ghi đè.
    for part in (check_files(d, items), check_labels(d, items, class_ids, sizes), check_panoptic(d, panoptic)):
        for name, kind in part.items():
            found.setdefault(name, kind)
    guideline, leaks = check_metadata(d, meta)
    for name, kind in guideline.items():
        found.setdefault(name, kind)

    errors = [{"type": t, "target": n} for n, t in sorted(found.items())]
    errors += [{"type": "scene_leak", "target": s} for s in leaks]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"errors": errors}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.candidates:
        # shortcut: chưa sinh ứng viên gán nhãn, Pha 2 sẽ thay bằng phần đối chiếu det ↔ panoptic.
        args.candidates.parent.mkdir(parents=True, exist_ok=True)
        args.candidates.write_text(json.dumps({"candidates": []}, indent=1) + "\n", encoding="utf-8")
    print(f"{len(errors)} lỗi luật -> {args.out}", dict(Counter(e["type"] for e in errors)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

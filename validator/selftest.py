#!/usr/bin/env python3
"""Tự kiểm phần ứng viên gán nhãn: tự gài lỗi lên lô SẠCH (biết đáp án vì tự gài), chạy validator, đo recall.

  python validator/selftest.py runs/clean/delivery --seeds 1,2,3

Mỗi seed: chép lô sạch sang thư mục tạm, gài mỗi loại lỗi vào vài ảnh khác nhau, rồi đếm validator
có đưa ảnh đó vào candidates không (đúng loại; class_swap/category_swap tính chung một ứng viên).
Không đọc _private hay đáp án của lô luyện tập.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import pngutil  # noqa: E402

KINDS = ["class_swap", "bbox_drift", "missing_box", "category_swap", "instance_merge"]


def inject(d: Path, rng: random.Random, per_kind: int) -> list[tuple[str, str]]:
    pan = json.loads((d / "panoptic.json").read_text())
    things = [c["id"] for c in pan["categories"] if c["isthing"]]
    sizes = {Path(i["file_name"]).stem: (i["width"], i["height"]) for i in pan["images"]}
    anns = {Path(a["file_name"]).stem: a for a in pan["annotations"]}
    names = sorted(anns)
    rng.shuffle(names)
    truth = []

    def rows(n):
        return [line.split() for line in (d / "labels" / f"{n}.txt").read_text().splitlines() if line.strip()]

    def save(n, rs):
        (d / "labels" / f"{n}.txt").write_text("".join(" ".join(r) + "\n" for r in rs))

    def segs(n):
        return [s for s in anns[n]["segments_info"] if s["category_id"] in things and not s.get("iscrowd")]

    for kind in KINDS:
        done = 0
        while done < per_kind and names:
            n = names.pop()
            rs = rows(n)
            if kind == "class_swap":
                big = [r for r in rs if float(r[3]) * float(r[4]) >= 0.005]
                if not big:
                    continue
                r = rng.choice(big)
                r[0] = str(rng.choice([c for c in range(80) if c != int(r[0])]))
                save(n, rs)
            elif kind == "bbox_drift":
                ok = [r for r in rs if float(r[3]) > 0.08 and float(r[4]) > 0.08 and float(r[3]) * float(r[4]) >= 0.005]
                if not ok:
                    continue
                r = rng.choice(ok)
                x, y, w, h = map(float, r[1:5])
                ang, mag = rng.uniform(0, 2 * math.pi), rng.uniform(0.12, 0.3)
                if rng.random() < 0.5:
                    s = 1 + rng.uniform(-0.2, 0.2)
                    w, h = min(1.0, w * s), min(1.0, h * s)
                x = min(1 - w / 2, max(w / 2, x + math.cos(ang) * mag * w))
                y = min(1 - h / 2, max(h / 2, y + math.sin(ang) * mag * h))
                r[1:5] = [f"{x:.6f}", f"{y:.6f}", f"{w:.6f}", f"{h:.6f}"]
                save(n, rs)
            elif kind == "missing_box":
                big = [r for r in rs if float(r[3]) * float(r[4]) > 0.01]
                if len(rs) < 2 or not big:
                    continue
                rs.remove(rng.choice(big))
                save(n, rs)
            elif kind == "category_swap":
                ok = [s for s in segs(n) if s["area"] >= 1024]
                if not ok:
                    continue
                s = rng.choice(ok)
                s["category_id"] = rng.choice([c for c in things if c != s["category_id"]])
            elif kind == "instance_merge":
                groups = {}
                for s in segs(n):
                    groups.setdefault(s["category_id"], []).append(s)
                groups = [g for g in groups.values() if len(g) >= 2 and min(s["area"] for s in g) >= 512]
                if not groups:
                    continue
                pair = sorted(rng.choice(groups), key=lambda s: s["area"])
                small, big = pair[0], pair[-1]
                w, h, px = pngutil.read_rgb(d / "masks" / f"{n}.png")
                rgb = bytes(pngutil.segment_rgb(big["id"]))
                for i in range(0, len(px), 3):
                    if pngutil.segment_id(px, i) == small["id"]:
                        px[i:i + 3] = rgb
                pngutil.write_rgb(d / "masks" / f"{n}.png", w, h, bytes(px))
                big["area"] += small["area"]
                anns[n]["segments_info"].remove(small)
            truth.append((kind, n))
            done += 1
    (d / "panoptic.json").write_text(json.dumps(pan))
    # manifest: ghi lại hash để validator không báo wrong_hash cho file vừa sửa
    man = json.loads((d / "manifest.json").read_text())
    from hashlib import sha256
    for n, it in man["items"].items():
        for k in ("label", "mask"):
            it[f"{k}_sha256"] = sha256((d / it[k]).read_bytes()).hexdigest()
    (d / "manifest.json").write_text(json.dumps(man))
    return truth


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("clean", type=Path)
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--per-kind", type=int, default=2)
    args = ap.parse_args()
    hit, total, extra, rule_fp = Counter(), Counter(), 0, 0
    for seed in [int(s) for s in args.seeds.split(",")]:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "delivery"
            shutil.copytree(args.clean, d)
            truth = inject(d, random.Random(seed), args.per_kind)
            subprocess.run([sys.executable, str(Path(__file__).with_name("validate.py")), str(d), "--out", f"{tmp}/e.json",
                            "--candidates", f"{tmp}/c.json"], check=True, capture_output=True)
            cands = json.loads(Path(f"{tmp}/c.json").read_text())["candidates"]
            rule_fp += len(json.loads(Path(f"{tmp}/e.json").read_text())["errors"])
            got = {(t, c["image"]) for c in cands for t in c["type"].split("|")}
            for kind, n in truth:
                total[kind] += 1
                hit[kind] += (kind, n) in got
            bad = {n for _, n in truth}
            extra += len({c["image"] for c in cands} - bad)
    for k in KINDS:
        print(f"{k:15s} bắt {hit[k]}/{total[k]}")
    print(f"ảnh ứng viên không bị gài lỗi (lệch tự nhiên): {extra} trên {len(args.seeds.split(','))} lần chạy")
    print(f"lỗi luật báo nhầm: {rule_fp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

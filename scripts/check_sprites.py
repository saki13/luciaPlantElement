# -*- coding: utf-8 -*-
"""精灵表体检：找出"看起来正常、其实已经坏掉"的图（fast/giant 那类）。

背景：`build_spritesheet.py` 对每个单位用**一个全局 scale**（取所有帧的最紧边），
所以只要有一帧是"多姿态拼图"，整张表 11 格会被一起压扁。自动化的帧齐全性/表结构
检查都发现不了——它们看到的是"每格非空"，而压扁的角色当然也是非空的。

本脚本补上两层只有跨单位/跨帧才看得出来的判据：

1. **宽高比离群**：同一批单位的角色宽高比应该聚在一起。被压扁的单位会明显偏细。
2. **多角色帧**：敌人的源帧里本该只有一个角色。按行投影切成"内容条带"，
   若存在 2 个以上面积相当的条带，说明模型返回了拼图。

（植物不做条带判据：frostbell 这类植物本身就是分段的，会误报。）

用法：
    python scripts/check_sprites.py
    python scripts/check_sprites.py --assets-root _artfix/backup_before_install
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FRAME = 64
COLS = 4
ROW_FRAMES = [2, 4, 3, 2]      # idle / walk / attack / hurt
REQUIRED_FRAMES = ["idle_0", "idle_1", "walk_0", "walk_1", "walk_2", "walk_3",
                   "attack_0", "attack_1", "attack_2", "hurt_0", "hurt_1"]
LO, HI = 12, 48                # 与 build_spritesheet.remove_white_bg 同一组阈值


# --------------------------------------------------------------------- 图像
def alpha_of(path: Path) -> np.ndarray:
    """复刻管线自己的去背公式，返回 alpha 通道。"""
    rgb = np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)
    dist = np.maximum.reduce([255 - rgb[:, :, 0], 255 - rgb[:, :, 1], 255 - rgb[:, :, 2]])
    a = np.where(dist <= LO, 0,
                 np.where(dist >= HI, 255, (dist - LO) * 255 // (HI - LO)))
    return a.astype(np.uint8)


def content_bands(path: Path, ink_thresh: int = 40, min_gap: int = 2) -> List[Tuple[int, int, int]]:
    """按行投影切出互不相连的内容条带，返回 [(y0, y1, 墨迹像素数), ...]。"""
    ink = alpha_of(path) > ink_thresh
    row_has = ink.any(axis=1)
    idx = np.flatnonzero(row_has)
    if idx.size == 0:
        return []
    splits = np.flatnonzero(np.diff(idx) > min_gap)
    starts = np.concatenate(([idx[0]], idx[splits + 1]))
    ends = np.concatenate((idx[splits], [idx[-1]]))
    return [(int(s), int(e), int(ink[s:e + 1].sum())) for s, e in zip(starts, ends)]


# --------------------------------------------------------------------- 表结构
def sheet_problems(path: Path) -> List[str]:
    problems: List[str] = []
    im = Image.open(path)
    if im.size != (FRAME * COLS, FRAME * len(ROW_FRAMES)):
        problems.append(f"尺寸 {im.size} != {(FRAME * COLS, FRAME * len(ROW_FRAMES))}")
    if im.mode != "RGBA":
        problems.append(f"非 RGBA（{im.mode}）")
    im = im.convert("RGBA")
    for row, count in enumerate(ROW_FRAMES):
        for col in range(COLS):
            cell = im.crop((col * FRAME, row * FRAME, (col + 1) * FRAME, (row + 1) * FRAME))
            empty = cell.getbbox() is None
            if col < count and empty:
                problems.append(f"有效格 r{row}c{col} 为空")
            if col >= count and not empty:
                problems.append(f"留白格 r{row}c{col} 不透明")
    if im.getpixel((0, 0))[3] != 0:
        problems.append("左上角不透明")
    return problems


def cell_aspect(sheet_path: Path) -> Tuple[float, float, float]:
    """返回 (mean_w, mean_h, aspect)，只统计有效格。"""
    im = Image.open(sheet_path).convert("RGBA")
    ws, hs = [], []
    for row, count in enumerate(ROW_FRAMES):
        for col in range(count):
            bb = im.crop((col * FRAME, row * FRAME, (col + 1) * FRAME, (row + 1) * FRAME)).getbbox()
            if bb:
                ws.append(bb[2] - bb[0])
                hs.append(bb[3] - bb[1])
    if not ws:
        return 0.0, 0.0, 0.0
    mw, mh = sum(ws) / len(ws), sum(hs) / len(hs)
    return mw, mh, mw / max(mh, 1e-9)


# --------------------------------------------------------------------- 主逻辑
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--assets-root", default=str(ROOT / "anim_demo" / "assets"),
                    help="assets 目录（含 sprites/、enemies/、plants/）")
    ap.add_argument("--sig-ratio", type=float, default=0.10,
                    help="条带面积达到最大条带的比例才算'第二个角色'")
    ap.add_argument("--aspect-lo", type=float, default=0.35)
    ap.add_argument("--aspect-hi", type=float, default=1.30)
    args = ap.parse_args(argv)

    root = Path(args.assets_root)
    sprites = root / "sprites"
    enemy_sheets = sprites / "enemies"
    enemy_src = root / "enemies"

    if not sprites.exists():
        print(f"找不到 sprites 目录：{sprites}", file=sys.stderr)
        return 2

    failures: List[str] = []
    warnings: List[str] = []

    plant_sheets = sorted(p for p in sprites.glob("*.png"))
    enemy_list = sorted(enemy_sheets.glob("*.png")) if enemy_sheets.exists() else []

    print(f"assets root : {root}")
    print(f"plant sheets: {len(plant_sheets)}   enemy sheets: {len(enemy_list)}")
    print()

    # ---- 1. 表结构
    print("== 1. 表结构 ==")
    for p in plant_sheets + enemy_list:
        probs = sheet_problems(p)
        if probs:
            failures.append(f"{p.name}: " + "；".join(probs[:3]))
            print(f"  FAIL {p.name:<24} {probs[:3]}")
    print(f"  {len(plant_sheets) + len(enemy_list)} 张表检查完毕")

    # ---- 2. 宽高比离群
    print("\n== 2. 角色宽高比 ==")
    rows = []
    for p in plant_sheets:
        rows.append(("plant", p.stem, *cell_aspect(p)))
    for p in enemy_list:
        rows.append(("enemy", p.stem, *cell_aspect(p)))
    for kind, key, mw, mh, asp in sorted(rows, key=lambda r: r[4]):
        flag = ""
        if kind == "enemy" and (asp < args.aspect_lo or asp > args.aspect_hi):
            flag = "  <-- 离群"
            failures.append(f"{key}: 宽高比 {asp:.2f} 超出 [{args.aspect_lo}, {args.aspect_hi}]")
        print(f"  {kind:<6}{key:<24}{mw:6.1f}{mh:6.1f}   {asp:5.2f}{flag}")

    # ---- 3. 多角色帧（仅敌人）
    print("\n== 3. 敌人源帧：每帧应只有一个角色 ==")
    if not enemy_src.exists():
        print("  跳过：没有 enemies/ 源帧目录（只带了成品表）")
    else:
        for unit_dir in sorted(d for d in enemy_src.iterdir() if d.is_dir()):
            srcs = []
            base = unit_dir / "base.png"
            if base.exists():
                srcs.append(base)
            frames_dir = unit_dir / "frames"
            if frames_dir.exists():
                srcs += [frames_dir / f"{n}.png" for n in REQUIRED_FRAMES
                         if (frames_dir / f"{n}.png").exists()]
            if not srcs:
                continue
            worst = []
            for p in srcs:
                bs = content_bands(p)
                if len(bs) <= 1:
                    continue
                biggest = max(b[2] for b in bs)
                sig = [b for b in bs if b[2] >= biggest * args.sig_ratio]
                if len(sig) > 1:
                    worst.append((p.name, len(bs), len(sig)))
            if worst:
                failures.append(f"{unit_dir.name}: {len(worst)} 帧含多个角色"
                                f"（例：{worst[0][0]} 条带 {worst[0][1]} 个，显著 {worst[0][2]} 个）")
                print(f"  FAIL {unit_dir.name:<14} {len(worst)}/{len(srcs)} 帧是多角色拼图"
                      f"  例: {worst[0][0]} -> {worst[0][1]} 条带")
            else:
                print(f"  ok   {unit_dir.name:<14} {len(srcs)} 帧均为单角色")

    # ---- 汇总
    print("\n" + "=" * 60)
    if warnings:
        print(f"警告 {len(warnings)} 条")
    if failures:
        print(f"RESULT: FAIL（{len(failures)} 项）")
        for f in failures:
            print("  - " + f)
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

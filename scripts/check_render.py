# -*- coding: utf-8 -*-
"""渲染层断言：`app_pygame` 之前完全没有测试引用，改坏了只能靠人眼发现。

本脚本在 SDL dummy 下真实构造 `GameApp`，断言：

1. 21 张精灵表全部加载（0 missing / 0 failed）
2. 13 植物 + 8 敌人都在展示场景里拿到了 sprite
3. 动画时钟真的在推进（有单位换过帧）
4. 截图能落盘，且画面不是纯色（说明棋盘/精灵真的画上去了）
5. `--no-sprites` 降级模式仍能跑（工程"永远可跑"的底线）

用法：
    python scripts/check_render.py
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "libs"))
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

FAILS = []


def check(cond: bool, msg: str) -> None:
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def distinct_colors(png: Path) -> int:
    from PIL import Image
    im = Image.open(png).convert("RGB")
    im = im.resize((im.width // 2, im.height // 2))
    return len(set(im.getdata()))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shot-dir", default="", help="截图目录，默认系统临时目录")
    args = ap.parse_args(argv)

    from tdgame.app_pygame import GameApp

    shot_dir = Path(args.shot_dir) if args.shot_dir else Path(tempfile.gettempdir())

    print("== 1. 精灵表加载 ==")
    app = GameApp(use_sprites=True)
    lib = app.sprites
    check(lib.enabled, "animation 模块可用")
    check(lib.loaded_count() == 21, f"加载 {lib.loaded_count()}/21 张表")
    check(not lib.missing, f"无缺失（missing={lib.missing[:3]}）")
    check(not lib.failed, f"无加载失败（failed={lib.failed[:3]}）")

    print("\n== 2. 展示场景拿到 sprite ==")
    plants = app.scene_plants
    enemies = app.scene_enemies
    check(len(plants) == 15, f"植物摆位 {len(plants)} 个")
    check(len(enemies) == 8, f"敌人摆位 {len(enemies)} 个")
    check(all(p["sprite"] is not None for p in plants), "所有植物都有 sprite")
    check(all(e["sprite"] is not None for e in enemies), "所有敌人都有 sprite")
    keys_p = {p["key"] for p in plants}
    keys_e = {e["key"] for e in enemies}
    check(len(keys_p) == 13, f"覆盖 {len(keys_p)}/13 种植物")
    check(len(keys_e) == 8, f"覆盖 {len(keys_e)}/8 种敌人")

    print("\n== 3. 动画推进 ==")
    seen = set()
    for _ in range(200):
        app.advance(16)
        for p in plants:
            if p["sprite"] is not None:
                seen.add((p["key"], p["sprite"].frame_idx))
        for e in enemies:
            if e["sprite"] is not None:
                seen.add((e["key"] + "@enemy", e["sprite"].frame_idx))
    animated = {k for k, _ in seen}
    check(len(animated) >= 20, f"{len(animated)} 个单位出现过 ≥1 帧（换帧观测点 {len(seen)} 个）")
    multi = sum(1 for k in animated if len({f for kk, f in seen if kk == k}) > 1)
    check(multi >= 15, f"{multi} 个单位实际切过多帧")

    print("\n== 4. 截图非空且非纯色 ==")
    shot = shot_dir / "check_render_sprites.png"
    app.save_snapshot(shot)
    check(shot.exists(), f"截图落盘 {shot}")
    if shot.exists():
        size = shot.stat().st_size
        colors = distinct_colors(shot)
        check(size > 8000, f"文件大小 {size} 字节 > 8000")
        check(colors > 20, f"画面含 {colors} 种颜色（>20 说明不是纯色底）")

    print("\n== 5. --no-sprites 降级模式 ==")
    app2 = GameApp(use_sprites=False)
    check(not app2.sprites.enabled, "精灵模式已关闭")
    check(app2.sprites.loaded_count() == 0, "没有加载任何表")
    shot2 = shot_dir / "check_render_fallback.png"
    app2.advance(320)
    app2.save_snapshot(shot2)
    check(shot2.exists(), "降级模式也能截图")

    print()
    if FAILS:
        print(f"RESULT: FAIL（{len(FAILS)} 项）")
        for f in FAILS:
            print("  - " + f)
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

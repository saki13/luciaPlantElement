# -*- coding: utf-8 -*-
"""渲染层断言：`app_pygame` 现在是可玩客户端，改坏了必须能被自动发现。

断言：
1. 21 张精灵表全部可加载（逐 key 强制取一遍）
2. 会话可用：卡栏数量与卡池一致，能种下植物并被 entities() 反映
3. 自动对局 20 秒不崩，且棋盘上确实存在植物
4. 截图落盘且画面不是纯色
5. `--no-sprites` 降级模式仍能跑

用法：
    python scripts/check_render.py [--shot-dir DIR]
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# pygame 的来源因平台而异：
#   Windows 本机 -> 项目自带的 libs/（那是 win_amd64 的 .pyd）
#   CI (Linux)   -> pip 安装的 pygame
# 所以**不能**无条件把 libs 插到 sys.path 最前面，否则 Linux 上会优先加载
# Windows 二进制并直接 ImportError（CI 的 "Render assertions" 就是这么红的）。
try:
    import pygame  # noqa: F401
except ImportError:  # 本机没有全局 pygame，退回项目自带的 libs/
    sys.path.insert(0, str(ROOT / "libs"))

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
    ap.add_argument("--shot-dir", default="")
    args = ap.parse_args(argv)
    shot_dir = Path(args.shot_dir) if args.shot_dir else Path(tempfile.gettempdir())

    from tdgame.app_pygame import GameApp
    from tdgame.engine.loader import load_registry

    reg = load_registry(ROOT / "tdgame" / "data")

    print("== 1. 全部精灵表可加载 ==")
    app = GameApp(use_sprites=True)
    lib = app.sprites
    check(lib.enabled, "animation 模块可用")
    bad = []
    for key in reg.plants:
        if lib.sheet(key, "plant") is None:
            bad.append(f"plant:{key}")
    for key in reg.enemies:
        if lib.sheet(key, "enemy") is None:
            bad.append(f"enemy:{key}")
    expected = len(reg.plants) + len(reg.enemies)
    check(not bad, f"{len(reg.plants)} 植物 + {len(reg.enemies)} 敌人全部可加载（失败 {bad}）")
    check(lib.loaded_count() == expected, f"loaded={lib.loaded_count()}/{expected}")

    print("\n== 2. 会话与卡栏 ==")
    cards = app.session.cards()
    pool = app.level["card_pool"]
    check(len(cards) == len(pool), f"卡栏 {len(cards)} 张 = 卡池 {len(pool)} 张")
    check(all("sun" in c and "cd" in c for c in cards), "卡片带阳光价与冷却字段")

    first_key = cards[0]["key"]
    app.session.select(first_key)
    ok, reason = app.session.place(0, 0)
    check(ok, f"在第 0 行第 0 列种下 {first_key}（{reason}）")
    ents = app.session.entities()
    check(any(p["row"] == 0 and p["col"] == 0 for p in ents["plants"]),
          "entities() 反映出这株植物")

    print("\n== 3. 自动对局 20 秒 ==")
    app2 = GameApp(use_sprites=True, autoplay=True)
    for _ in range(20 * 60):
        app2.advance(1 / 60)
    st = app2.session.status()
    check(st["time"] >= 19.0, f"推进到 t={st['time']}s")
    check(st["plants"] > 0, f"自动对局中有 {st['plants']} 株植物")
    app2.draw()

    print("\n== 4. 截图非空且非纯色 ==")
    shot = shot_dir / "check_render_play.png"
    app2.save_snapshot(shot, warmup_frames=1)
    check(shot.exists(), f"截图落盘 {shot}")
    if shot.exists():
        size = shot.stat().st_size
        colors = distinct_colors(shot)
        check(size > 8000, f"文件大小 {size} 字节 > 8000")
        check(colors > 20, f"画面含 {colors} 种颜色（>20 说明不是纯色底）")

    print("\n== 5. --no-sprites 降级模式 ==")
    app3 = GameApp(use_sprites=False)
    check(not app3.sprites.enabled, "精灵模式已关闭")
    check(app3.sprites.sheet("peashooter", "plant") is None, "sheet() 返回 None")
    shot2 = shot_dir / "check_render_fallback.png"
    for _ in range(120):
        app3.advance(1 / 60)
    app3.draw()
    app3.save_snapshot(shot2, warmup_frames=1)
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

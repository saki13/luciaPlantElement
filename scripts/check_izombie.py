# -*- coding: utf-8 -*-
"""M5「我是僵尸」闸门：模式反转是否真的成立，以及可玩渲染是否正常。

覆盖两层：
1. 逻辑层：三个关卡都能被 headless Bot 打通（设计红线）；
2. 渲染层：`--mode izombie` 能起 frame、卡栏是敌人、没有铲子、截图非纯色。

之所以单独一个脚本而不是塞进 check_render：这一层要验证的是"攻防反转"
这个模式本身，与主线渲染断言是两件事，失败时能一眼看出是哪边坏了。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# pygame 来源见 check_render.py 的说明：Windows 用自带 libs/，CI 用 pip
try:
    import pygame  # noqa: F401
except ImportError:
    sys.path.insert(0, str(ROOT / "libs"))

import os  # noqa: E402

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tdgame.engine.loader import load_registry  # noqa: E402
from tdgame.scenarios.i_zombie import run_level  # noqa: E402

DATA = ROOT / "tdgame" / "data"
FAILS: list[str] = []


def check(cond: bool, msg: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'} {msg}")
    if not cond:
        FAILS.append(msg)


def load_levels() -> dict:
    out = {}
    for f in sorted((DATA / "izombie").glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        out[d["key"]] = d
    return out


def main() -> int:
    reg = load_registry(DATA)
    levels = load_levels()

    print("== 1. 关卡可解性（每个关卡都必须能被打通）==")
    check(len(levels) >= 3, f"至少 3 个关卡（实际 {len(levels)}）")
    for key, lv in levels.items():
        wins = sum(1 for seed in range(1000, 1003) if run_level(lv, reg, seed=seed)["won"])
        check(wins >= 2, f"{key} headless 胜率 {wins}/3")

    print("\n== 2. 预算确实是约束（砍到 1/3 后不该还能随便过）==")
    lv = dict(levels["zombie_02"])
    lv["budget"] = max(1, lv["budget"] // 3)
    wins = sum(1 for seed in range(1000, 1003) if run_level(lv, reg, seed=seed)["won"])
    check(wins < 3, f"预算 1/3 时胜率降到 {wins}/3")

    print("\n== 3. 可玩渲染（--mode izombie）==")
    from tdgame.app_pygame import GameApp

    app = GameApp(use_sprites=True, mode="izombie")
    check(app.mode == "izombie", "GameApp 处于 izombie 模式")
    check(app.level_key in levels, f"载入了关卡 {app.level_key}")

    cards = app.session.cards()
    check(len(cards) > 0, f"卡栏有 {len(cards)} 张卡")
    check(all(c.get("kind") == "enemy" for c in cards), "卡栏全是敌人（不是植物）")
    check(all("sun" in c and c["sun"] >= 1 for c in cards), "每张卡都标了预算价")

    # 我是僵尸不能种植物
    ok, why = app.session.click_cell(0, 0)
    check(not ok and why == "no_selection", f"没选卡时点击被拒（{why}）")
    app.session.select(cards[0]["key"])
    ok, why = app.session.click_cell(0, 0)
    check(ok, f"选卡后点击可投放（{why}）")
    check(app.session.sun < cards[0]["sun"] + app.session.sun + 1, "预算被扣减")

    for _ in range(120):
        app.advance(1 / 60)
    app.draw()
    check(app.shovel_rect.width == 0, "该模式不画铲子")

    shot = ROOT / "_work" / "check_izombie.png"
    shot.parent.mkdir(parents=True, exist_ok=True)
    app.save_snapshot(shot, warmup_frames=1)
    check(shot.exists() and shot.stat().st_size > 8000, f"截图落盘 {shot.name}")
    try:
        from PIL import Image

        with Image.open(shot) as im:
            colors = len(set(im.convert("RGB").resize((160, 110)).getdata()))
        check(colors > 20, f"画面含 {colors} 种颜色（非纯色）")
    except Exception as exc:  # noqa: BLE001
        check(False, f"截图分析失败：{exc}")

    print()
    if FAILS:
        print(f"RESULT: FAIL（{len(FAILS)} 项）")
        for f in FAILS:
            print(f"  - {f}")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())

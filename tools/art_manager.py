# -*- coding: utf-8 -*-
"""素材管理器：让人随时替换/重建任意单位的精灵表。

用法：
    python tools/art_manager.py list
    python tools/art_manager.py rebuild snow_pea
    python tools/art_manager.py import  snow_pea  D:\我的图\snow_pea.png
    python tools/art_manager.py import  snow_pea  D:\我的帧目录\          (目录=多帧)
    python tools/art_manager.py gen     custom_xxx      (用自带 art_prompt 出图)
    python tools/art_manager.py verify

设计原则：
- 不改数据 JSON，只动 PNG。
- 单图 -> build_spritesheet 单立绘模式（复制到所有格）
- 目录 -> build_spritesheet 目录模式（逐帧、全局统一缩放、底部锚点对齐）
- 每次替换后自动跑 check_sprites，不达标直接告诉你，不静默失败。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANIM = ROOT / "anim_demo"
SPR = ANIM / "assets" / "sprites"
DATA = ROOT / "tdgame" / "data"
BUILD = ANIM / "build_spritesheet.py"
CHECK = ROOT / "scripts" / "check_sprites.py"


def all_units() -> dict:
    """返回 {key: (kind, cn)}，kind 是 plant / enemy。"""
    out = {}
    for sub, kind in (("plants", "plant"), ("enemies", "enemy")):
        for f in sorted((DATA / sub).glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            out[d.get("key") or f.stem] = (kind, d.get("cn", ""))
    return out


def sheet_path(key: str) -> Path:
    units = all_units()
    kind = units.get(key, ("plant", ""))[0]
    return (SPR / "enemies" / f"{key}.png") if kind == "enemy" else (SPR / f"{key}.png")


def cmd_list() -> int:
    units = all_units()
    have = missing = 0
    print(f"{'key':<20}{'类型':<8}{'中文名':<14}精灵表")
    print("-" * 62)
    for key, (kind, cn) in units.items():
        p = sheet_path(key)
        ok = p.exists()
        have += ok
        missing += (not ok)
        size = f"{p.stat().st_size // 1024}KB" if ok else "缺"
        print(f"{key:<20}{kind:<8}{cn:<14}{size}")
    print("-" * 62)
    print(f"合计 {len(units)}：有 {have}，缺 {missing}")
    return 0


def _run(cmd: list[str]) -> int:
    r = subprocess.run(cmd, cwd=str(ANIM), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print((r.stderr or r.stdout)[-500:])
    return r.returncode


def cmd_rebuild(key: str) -> int:
    frames = ANIM / "assets" / "plants" / key / "frames"
    if frames.is_dir() and any(frames.glob("*.png")):
        src = frames
    else:
        base = ANIM / "assets" / "plants" / key / "base.png"
        if not base.exists():
            print(f"没有可用的源：{frames} 或 {base} 都不存在")
            return 1
        src = base
    out = sheet_path(key)
    print(f"拼表：{src} -> {out.relative_to(ROOT)}")
    if _run([sys.executable, str(BUILD), str(src), str(out)]) != 0:
        return 1
    return cmd_verify()


def cmd_import(key: str, source: str) -> int:
    src = Path(source).expanduser().resolve()   # 子进程在 anim_demo 下跑，必须转绝对路径
    if not src.exists():
        print(f"源不存在：{src}")
        return 1
    units = all_units()
    if key not in units:
        print(f"未知单位 {key}（用 list 查看可选 key）")
        return 1
    out = sheet_path(key)
    print(f"导入：{src} -> {out.relative_to(ROOT)}")
    if _run([sys.executable, str(BUILD), str(src), str(out)]) != 0:
        return 1
    return cmd_verify()


STYLE_TAIL = ("，2D游戏精灵立绘，Q版圆润卡通，粗深色描边，明快平涂，"
              "**一定要有一双又大又亮的卡通眼睛**（黑色大眼珠+白色高光），表情生动，"
              "正面平视，全身居中，站在画面底部中央，纯白色干净背景，无阴影，无文字，无边框")


def _defn(key: str) -> dict:
    for sub in ("plants", "enemies"):
        f = DATA / sub / f"{key}.json"
        if f.exists():
            return json.loads(f.read_text(encoding="utf-8"))
    raise SystemExit(f"未知单位 {key}")


def cmd_gen(key: str) -> int:
    """用该单位 JSON 里的 art_prompt（没有就用中文名）调千问出立绘，再拼表。"""
    import os
    d = _defn(key)
    prompt = d.get("art_prompt") or (d.get("cn", key) + "，一株原创塔防植物")
    prompt = prompt + STYLE_TAIL

    token = os.environ.get("MODELSCOPE_TOKEN") or os.environ.get("MS_TOKEN")
    if not token:
        f = ANIM / ".ms_token"
        if f.exists():
            token = f.read_text(encoding="utf-8").strip()
    if not token:
        print("没有 token：设置 MODELSCOPE_TOKEN 或写入 anim_demo/.ms_token")
        return 1

    stage = ROOT / "_work" / "art_gen"
    stage.mkdir(parents=True, exist_ok=True)
    raw = stage / f"{key}.png"
    env = dict(os.environ, MODELSCOPE_TOKEN=token, PYTHONIOENCODING="utf-8")
    if raw.exists():
        print(f"复用已有立绘 {raw}")
    else:
        print(f"出图：{key} ...")
        r = subprocess.run([sys.executable, str(ANIM / "gen_image_qwen.py"),
                            "--out", str(raw), "--prompt", prompt],
                           cwd=str(ANIM), env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0 or not raw.exists():
            print((r.stderr or r.stdout)[-400:])
            return 1
        print(f"立绘 OK：{raw.stat().st_size // 1024}KB")

    out = sheet_path(key)
    print(f"拼表 -> {out.relative_to(ROOT)}")
    if _run([sys.executable, str(BUILD), str(raw), str(out)]) != 0:
        return 1
    return cmd_verify()


def cmd_verify() -> int:
    print("校验 check_sprites ...")
    r = subprocess.run([sys.executable, str(CHECK)], cwd=str(ROOT),
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    tail = [ln for ln in (r.stdout or "").splitlines() if ln.strip()][-3:]
    print("\n".join(tail) or (r.stderr or "")[-300:])
    return r.returncode


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "list":
        return cmd_list()
    if cmd == "gen" and len(argv) >= 2:
        return cmd_gen(argv[1])
    if cmd == "verify":
        return cmd_verify()
    if cmd == "rebuild" and len(argv) >= 2:
        return cmd_rebuild(argv[1])
    if cmd == "import" and len(argv) >= 3:
        return cmd_import(argv[1], argv[2])
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# -*- coding: utf-8 -*-
"""存档持久化：把 `PlayerProgress` 落到 JSON，并能安全读回来。

三条原则：

1. **不信任文件内容**。`unlocked` 一律从 `cleared` 重新推导，而不是从存档里读
   —— 否则手改一行 JSON 就能解锁全部阶段。
2. **坏档不炸游戏**。文件缺失/损坏/字段类型不对，都退化成"新档 + 一条 warning"，
   调用方永远拿到一个可用的 `PlayerProgress`。
3. **原子写入**。先写 `.tmp` 再 `os.replace`，避免写一半断电留下半截文件。
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .progression import PHASES, PlayerProgress, phase_of_level

FORMAT = "pvz-save/1"


def snapshot(progress: PlayerProgress) -> Dict[str, Any]:
    """内存态 -> 可 JSON 化的纯数据（不含 unlocked，它是推导出来的）。"""
    return {
        "format": FORMAT,
        "cleared": list(progress.cleared),
        "design_tokens": int(progress.design_tokens),
    }


def restore(data: Any, levels: Optional[Dict[str, Dict]] = None) -> Tuple[PlayerProgress, Optional[str]]:
    """纯数据 -> PlayerProgress。返回 (进度, warning 或 None)。"""
    prog = PlayerProgress(levels)
    warn: Optional[str] = None

    if not isinstance(data, dict):
        return prog, "存档不是 JSON 对象，已按新档处理"

    fmt = data.get("format")
    if fmt != FORMAT:
        warn = f"存档格式 {fmt!r} 与当前 {FORMAT!r} 不一致，已尽力兼容读取"

    cleared = data.get("cleared")
    if isinstance(cleared, list):
        # 只收字符串；重复的按首次出现算（顺序影响"首通奖励"，所以保序去重）
        seen = set()
        for key in cleared:
            if isinstance(key, str) and key not in seen:
                seen.add(key)
                prog.cleared.append(key)
    elif cleared is not None:
        warn = (warn + "；" if warn else "") + "cleared 字段类型不对，已忽略"

    tokens = data.get("design_tokens", 0)
    if isinstance(tokens, bool) or not isinstance(tokens, int):
        warn = (warn + "；" if warn else "") + "design_tokens 字段类型不对，已归零"
        tokens = 0
    prog.design_tokens = max(0, int(tokens))

    # 关键：解锁状态从已通关列表重新推导，绝不从文件读
    prog.unlocked = set(PHASES["P1"].unlocks)
    for key in prog.cleared:
        phase = phase_of_level(key)
        if phase:
            prog.unlocked.update(PHASES[phase].unlocks)

    return prog, warn


def save_to(path: str | Path, progress: PlayerProgress) -> Path:
    """原子写入存档，返回最终路径。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    payload = json.dumps(snapshot(progress), ensure_ascii=False, indent=2, sort_keys=True)
    # encoding='utf-8' 明确不写 BOM：PowerShell 的 Set-Content -Encoding UTF8 会写 BOM，
    # 那种文件 json.loads 会直接报 "Unexpected UTF-8 BOM"。
    tmp.write_text(payload + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return path


def load_from(path: str | Path,
              levels: Optional[Dict[str, Dict]] = None) -> Tuple[PlayerProgress, Optional[str]]:
    """读存档。文件不存在 -> 新档（不算 error）。"""
    path = Path(path)
    if not path.exists():
        return PlayerProgress(levels), None
    try:
        raw = path.read_text(encoding="utf-8-sig")   # 容忍别人手写时带了 BOM
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 - 任何解析失败都降级成新档
        return PlayerProgress(levels), f"存档读取失败（{exc.__class__.__name__}），已按新档处理"
    return restore(data, levels)


def default_save_path() -> Path:
    """默认存档位置：仓库内 saves/ （已在 .gitignore 里）。"""
    return Path(__file__).resolve().parents[2] / "saves" / "progress.json"


# ---------------------------------------------------------------------- 命令行
def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="savegame", description="查看/重置玩家存档")
    ap.add_argument("--path", default="", help="存档路径，默认 saves/progress.json")
    ap.add_argument("--reset", action="store_true", help="删除存档")
    args = ap.parse_args(argv)

    path = Path(args.path) if args.path else default_save_path()
    if args.reset:
        if path.exists():
            path.unlink()
            print(f"已删除 {path}")
        else:
            print(f"没有存档 {path}")
        return 0

    prog, warn = load_from(path)
    if warn:
        print(f"[warn] {warn}")
    print(f"path: {path}")
    print(f"exists: {path.exists()}")
    print(f"design_tokens: {prog.design_tokens}")
    print(f"cleared ({len(prog.cleared)}): {', '.join(prog.cleared) or '-'}")
    print(f"phase: {prog.reached_phase()}")
    print(f"unlocked: {', '.join(sorted(prog.unlocked))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

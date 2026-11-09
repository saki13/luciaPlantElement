# -*- coding: utf-8 -*-
"""工程卫生检查：把几条"只会复发"的陷阱变成机器可查。

这个脚本存在的理由很直接：下面这些坑我都踩过，而且都只是"改好了 + 写进文档"，
没有任何东西阻止下一个人（或下一个我）再犯。文档拦不住人，门禁可以。

覆盖：
1. **UTF-8 BOM** —— PowerShell 的 `Set-Content -Encoding UTF8` 会写 BOM，
   而 `json.loads` 遇到 BOM 直接抛 `Unexpected UTF-8 BOM`。仓库里的
   json/py/ps1/md 一律不许带 BOM。
2. **GDScript 的 `x or {}`** —— GDScript 的 `or` 返回 bool（Python 返回操作数），
   `(d.get("k") or {}).get(...)` 会得到 true 然后崩。禁止这个写法。
3. **trace 场景与门禁 ONLY 列表不同步** —— `check_board_trace.py` 只比对
   `run_board_trace.gd` 里 `ONLY` 列出的场景。若 baseline 里新增了场景却没加进
   ONLY，门禁会"通过"但其实没验 —— 这是最危险的一种绿。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAILS: list[str] = []

TEXT_SUFFIXES = {".json", ".py", ".ps1", ".gd", ".md", ".yml", ".yaml", ".txt", ".cfg"}
SKIP_DIRS = {".git", ".godot", "_work", "_artfix", "_artfix2", "_artfix3",
             "unpacked", "ghidra-project", "libs", "logs", "unpacked_raw",
             "anim_demo/assets", "saves"}


def check(cond: bool, msg: str) -> None:
    print(f"  {'PASS' if cond else 'FAIL'} {msg}")
    if not cond:
        FAILS.append(msg)


def iter_text_files():
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(d + "/") or f"/{d}/" in f"/{rel}" for d in SKIP_DIRS):
            continue
        yield p


def check_bom() -> None:
    print("== 1. 文本文件不得带 UTF-8 BOM ==")
    bad = []
    for p in iter_text_files():
        try:
            head = p.read_bytes()[:3]
        except OSError:
            continue
        if head == b"\xef\xbb\xbf":
            bad.append(p.relative_to(ROOT).as_posix())
    check(not bad, f"检查完成（带 BOM 的文件：{bad[:5]}{' …' if len(bad) > 5 else ''}）")


def check_gdscript_or() -> None:
    print("\n== 2. GDScript 不得使用 `x or {}` / `x or []` ==")
    # GDScript 的 or 返回 bool，这个写法会静默得到 true 再崩
    pattern = re.compile(r"\bor\s+(\{\}|\[\])\s*\)")
    bad = []
    for p in ROOT.rglob("*.gd"):
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(d + "/") for d in SKIP_DIRS):
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            code = line.split("#", 1)[0]
            if pattern.search(code):
                bad.append(f"{rel}:{i}")
    check(not bad, f"检查完成（违规：{bad[:5]}）")


def check_ps1_ascii() -> None:
    print("\n== 3. .ps1 必须纯 ASCII ==")
    # Windows PowerShell 5.1 会把"无 BOM 的 UTF-8"当 ANSI 读，中文注释会变乱码；
    # 而我们又要求文件不带 BOM，所以唯一自洽的约定是：.ps1 一律纯 ASCII。
    bad = []
    for p in ROOT.rglob("*.ps1"):
        rel = p.relative_to(ROOT).as_posix()
        if any(rel.startswith(d + "/") for d in SKIP_DIRS):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), 1):
            if any(ord(c) > 127 for c in line):
                bad.append(f"{rel}:{i}")
                break
    check(not bad, f"检查完成（含非 ASCII 的文件：{bad[:5]}）")


def check_trace_only_sync() -> None:
    print("\n== 4. trace 场景必须与门禁 ONLY 列表同步 ==")
    baseline = ROOT / "reports" / "board_trace_baseline.json"
    runner = ROOT / "godot" / "tests" / "run_board_trace.gd"
    if not baseline.exists() or not runner.exists():
        check(False, "缺少 baseline 或 runner")
        return
    data = json.loads(baseline.read_text(encoding="utf-8"))
    scenarios = set(data.get("scenarios", {}))
    src = runner.read_text(encoding="utf-8")
    m = re.search(r"const\s+ONLY\s*:=\s*\[(.*?)\]", src, re.S)
    if m is None:
        check(False, "在 run_board_trace.gd 里找不到 ONLY 列表")
        return
    only = set(re.findall(r'"([^"]+)"', m.group(1)))
    missing = sorted(scenarios - only)
    extra = sorted(only - scenarios)
    check(not missing,
          f"baseline 里 {len(scenarios)} 个场景都在 ONLY 里（未纳入：{missing}）")
    check(not extra, f"ONLY 里没有 baseline 不存在的场景（多余：{extra}）")



# ---------------------------------------------------------------- 检查: 测试专用植物不得进卡池
def check_test_only_not_in_pools(root: Path) -> List[str]:
    """`_test_only` 的植物只供 headless 校准/单测使用，绝不能出现在关卡卡池里。"""
    import json as _json
    data = root / "tdgame" / "data"
    test_keys = set()
    for f in (data / "plants").glob("*.json"):
        d = _json.loads(f.read_text(encoding="utf-8"))
        if d.get("_test_only"):
            test_keys.add(d.get("key") or f.stem)
    bad = []
    if not test_keys:
        return bad
    for f in (data / "levels").glob("*.json"):
        d = _json.loads(f.read_text(encoding="utf-8"))
        for key in (d.get("card_pool") or []):
            if key in test_keys:
                bad.append(f"{d.get('key')} 的卡池含测试专用植物 {key}")
    return bad

def main() -> int:
    check_bom()
    check_gdscript_or()
    check_ps1_ascii()
    check_trace_only_sync()
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

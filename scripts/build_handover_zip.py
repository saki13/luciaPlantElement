# -*- coding: utf-8 -*-
"""
交接打包脚本：生成两个自包含 zip，并做机密/目录排除自检。

输出（项目根）：
  pvz_tdgame_runtime_<date>.zip       轻量运行包：代码 + libs + 成品精灵表 + 文档
  pvz_tdgame_art_sources_<date>.zip   美术源材包：AI 原始立绘/逐帧 + 管线脚本

硬性排除（任何包都不得包含）：
  .ms_token 等机密、.git、__pycache__、*.pyc/*.pyo、ghidra-project、unpacked、logs
"""
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATE = "20261104"

# 任何命中即禁止入包的路径片段（机密 / 版本控制 / 缓存 / 逆向版权目录 / 过程日志）
FORBIDDEN_PARTS = {
    ".ms_token", ".git", "__pycache__", "ghidra-project", "unpacked", "logs",
}
FORBIDDEN_SUFFIX = (".pyc", ".pyo", ".token")

ROOT_DOCS = [
    "README.md", "game_balance_design.md", "pvz-architecture.html", "HANDOVER.md",
    "tower_defense_prototype.py", "tower_defense_pygame.py",
]
# 运行包整目录递归收录（代码/测试/报告/自包含依赖）
RUNTIME_DIRS = ["tdgame", "scripts", "tests", "reports", "libs"]
# anim_demo 顶层只收脚本；成品精灵表单独递归
ANIM_PY_DIR = "anim_demo"
ANIM_SPRITES = Path("anim_demo/assets/sprites")
# 美术源材包收原始竖图目录 + 管线脚本 + 状态文件
ART_RAW_DIRS = [Path("anim_demo/assets/plants"), Path("anim_demo/assets/enemies")]
ART_STATUS = Path("anim_demo/assets/art_build_status.json")


def forbidden(rel: Path) -> bool:
    parts = set(rel.parts)
    if parts & FORBIDDEN_PARTS:
        return True
    name = rel.name
    if name == ".ms_token" or name.endswith(FORBIDDEN_SUFFIX):
        return True
    return False


def iter_files(base: Path, rel_prefix: Path):
    """递归枚举 base 下文件，产出 (绝对路径, 相对项目根路径)。"""
    for p in base.rglob("*"):
        if p.is_file():
            rel = rel_prefix / p.relative_to(base)
            if not forbidden(rel):
                yield p, rel


def collect_runtime():
    files = []
    for d in RUNTIME_DIRS:
        base = ROOT / d
        if base.exists():
            files.extend(iter_files(base, Path(d)))
    # anim_demo 顶层脚本（不递归 assets）
    anim = ROOT / ANIM_PY_DIR
    for p in sorted(anim.glob("*.py")):
        rel = Path(ANIM_PY_DIR) / p.name
        if not forbidden(rel):
            files.append((p, rel))
    # 成品精灵表递归
    sp = ROOT / ANIM_SPRITES
    if sp.exists():
        files.extend(iter_files(sp, ANIM_SPRITES))
    # 根文档/原型
    for name in ROOT_DOCS:
        p = ROOT / name
        if p.exists():
            files.append((p, Path(name)))
    return files


def collect_art():
    files = []
    for d in ART_RAW_DIRS:
        base = ROOT / d
        if base.exists():
            files.extend(iter_files(base, d))
    # 管线脚本，保证源材包可独立重跑管线
    anim = ROOT / ANIM_PY_DIR
    for p in sorted(anim.glob("*.py")):
        rel = Path(ANIM_PY_DIR) / p.name
        if not forbidden(rel):
            files.append((p, rel))
    st = ROOT / ART_STATUS
    if st.exists():
        files.append((st, ART_STATUS))
    hand = ROOT / "HANDOVER.md"
    if hand.exists():
        files.append((hand, Path("HANDOVER.md")))
    return files


def build(zip_name: str, prefix: str, files):
    out = ROOT / zip_name
    seen = set()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for abs_p, rel in sorted(files, key=lambda t: str(t[1]).lower()):
            if forbidden(rel):
                raise SystemExit(f"安全拦截：禁入文件出现在列表 {rel}")
            arc = f"{prefix}/{rel.as_posix()}"
            if arc in seen:
                continue
            seen.add(arc)
            z.write(abs_p, arc)
    # 打包后回读自检
    with zipfile.ZipFile(out, "r") as z:
        names = z.namelist()
        bad = [n for n in names if any(tok in n for tok in
               (".ms_token", ".git/", "__pycache__", "ghidra-project", "unpacked", "/logs/"))]
        if bad:
            raise SystemExit("打包自检失败，发现禁入条目：" + ", ".join(bad[:5]))
        size_mb = round(out.stat().st_size / 1024 / 1024, 2)
        print(f"{zip_name}: files={len(names)} size={size_mb}MB selfcheck=OK")


def main():
    build(f"pvz_tdgame_runtime_{DATE}.zip", "pvz_tdgame_handover", collect_runtime())
    build(f"pvz_tdgame_art_sources_{DATE}.zip", "pvz_tdgame_art_sources", collect_art())
    print("HANDOVER ZIP BUILD DONE")


if __name__ == "__main__":
    sys.exit(main())

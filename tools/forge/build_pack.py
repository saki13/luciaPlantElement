# -*- coding: utf-8 -*-
"""把植物工坊（HTML + Node）打包成可以发给别人的 zip。

用法:
    python tools/forge/build_pack.py

产物:
    dist/PlantForgeWeb/          文件夹
    dist/PlantForgeWeb.zip       发出去这个

包含:
    server.js                    零依赖服务
    public/index.html            界面
    anim_demo/assets/sprites/    现有 54 个角色的精灵表（供参考/改造）
    anim_demo/assets/plants/     空目录，改出来的帧落在这里
    start.command / start.bat    双击启动
    README.md                    说明

不含:
    令牌（.ms_token）、我们已有的项目帧、候选图、历史帧
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORGE = Path(__file__).resolve().parent
SPRITES = ROOT / "anim_demo" / "assets" / "sprites"
OUT = ROOT / "dist" / "PlantForgeWeb"
ZIP = ROOT / "dist" / "PlantForgeWeb.zip"


def build() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "anim_demo" / "assets" / "plants").mkdir(parents=True)

    shutil.copy2(FORGE / "server.js", OUT / "server.js")
    shutil.copy2(FORGE / "server.py", OUT / "server.py")
    shutil.copytree(FORGE / "public", OUT / "public")
    for name in ("start.command", "start.bat", "README.md"):
        shutil.copy2(FORGE / name, OUT / name)

    if SPRITES.is_dir():
        shutil.copytree(SPRITES, OUT / "anim_demo" / "assets" / "sprites")

    # 说明：数据目录（cn 显示名）也带上，否则下拉框只显示 key
    data = ROOT / "tdgame" / "data"
    for kind in ("plants", "enemies"):
        src = data / kind
        if src.is_dir():
            dst = OUT / "tdgame" / "data" / kind
            dst.mkdir(parents=True, exist_ok=True)
            for f in src.glob("*.json"):
                shutil.copy2(f, dst / f.name)

    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(OUT.rglob("*")):
            if f.is_dir():
                continue
            arc = f.relative_to(OUT.parent).as_posix()
            if f.name.endswith(".command"):
                info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
                info.external_attr = 0o755 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, f.read_bytes())
            else:
                z.write(f, arc)

    n = sum(1 for f in OUT.rglob("*") if f.is_file())
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"文件夹: {OUT.relative_to(ROOT)}  ({n} 文件, {size/1024/1024:.1f} MB)")
    print(f"压缩包: {ZIP.relative_to(ROOT)}  ({ZIP.stat().st_size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    build()

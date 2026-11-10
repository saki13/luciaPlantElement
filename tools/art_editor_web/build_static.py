# -*- coding: utf-8 -*-
"""把现有角色资源打成自包含的静态 HTML，并可选打成一个可分发的 zip。

用法:
    python tools/art_editor_web/build_static.py            # 只生成 index.html
    python tools/art_editor_web/build_static.py --pack     # 额外产出可直接发人的 zip

为什么内嵌 base64 而不是引用相对路径：
    浏览器在 file:// 下把本地图片画进 canvas 会"污染"画布，
    导致 getImageData / toBlob 抛 SecurityError——而本工具恰恰要合成精灵表并导出。
    base64 data URI 不受此限制，所以必须内嵌。

画质：用**无损 PNG** 内嵌（不做有损压缩）。文件大一点没关系，
交付方式是整个压缩包，设计师解压后用即可。
"""
from __future__ import annotations

import base64
import json
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "tdgame" / "data"
SPR = ROOT / "anim_demo" / "assets" / "sprites"
TPL = HERE / "index.template.html"
OUT = HERE / "index.html"
PACK = HERE / "PlantArtForge.zip"


def to_png_b64(path: Path) -> str:
    """原样内嵌 PNG（无损）。"""
    raw = path.read_bytes()
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii")


def collect() -> list[dict]:
    units = []
    for sub, kind in (("plants", "plant"), ("enemies", "enemy")):
        for f in sorted((DATA / sub).glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            key = d.get("key") or f.stem
            sheet = (SPR / "enemies" / f"{key}.png") if kind == "enemy" else (SPR / f"{key}.png")
            if not sheet.exists():
                print(f"  [skip] {key} 没有精灵表")
                continue
            units.append({
                "key": key,
                "cn": d.get("cn", key),
                "role": d.get("role", "ranged"),
                "kind": kind,
                "desc": d.get("art_prompt", "") or "",
                "sheet": to_png_b64(sheet),
            })
    return units


def build() -> int:
    tpl = TPL.read_text(encoding="utf-8")
    units = collect()
    payload = json.dumps(units, ensure_ascii=False, separators=(",", ":"))
    if "/*__UNITS__*/" not in tpl:
        raise SystemExit("模板缺少 /*__UNITS__*/ 占位")
    seed = json.dumps({"style": "", "promptsByUnit": {}}, ensure_ascii=False)
    if "__SEED__" not in tpl:
        raise SystemExit("模板缺少 __SEED__ 占位")
    html = tpl.replace("/*__UNITS__*/", "const UNITS = " + payload + ";")
    html = html.replace("__SEED__", seed)
    OUT.write_text(html, encoding="utf-8", newline="\n")
    size = OUT.stat().st_size / 1024
    print(f"收集 {len(units)} 个角色 -> {OUT.relative_to(ROOT)}")
    print(f"index.html 大小 {size:.0f} KB（无损 PNG 内嵌）")
    return len(units)


def pack() -> None:
    readme = HERE / "README.md"
    with zipfile.ZipFile(PACK, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(OUT, "植物立绘工坊/index.html")
        if readme.exists():
            z.write(readme, "植物立绘工坊/说明.md")
        z.writestr("植物立绘工坊/打开我.txt",
                   "双击 index.html 即可开始。不用装任何东西。\n"
                   "\n"
                   "【怎么保存】\n"
                   "  改完一批，点左侧「导出工作副本（下次双击它继续改）」，\n"
                   "  会下载一个新的 HTML 文件（名字带时间）。\n"
                   "  下次直接双击那个新文件，你改的东西全在里面，接着改就行。\n"
                   "\n"
                   "  这样不依赖浏览器存储：用 Safari、清缓存、换电脑都不怕。\n"
                   "\n"
                   "【交给开发】\n"
                   "  点「导出全部已改（zip）」或「导出资源包 .zip」，把 zip 发回去。\n"
                   "\n"
                   "不需要联网（除非你要用页面里的 AI 生成）。\n")
    print(f"打包 -> {PACK.relative_to(ROOT)}  {PACK.stat().st_size/1024:.0f} KB")


def main() -> int:
    build()
    if "--pack" in sys.argv:
        pack()
    return 0


if __name__ == "__main__":
    sys.exit(main())

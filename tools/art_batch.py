# -*- coding: utf-8 -*-
"""把设计工坊导出的任务包批量跑成图片。

为什么需要它：ModelScope（以及多数图片 API）不允许浏览器直连（CORS），
所以网页里点「重抽」在本地浏览器里一定失败。正确流程是：

   设计师：页面点「导出生成任务 .zip」→ 发给我们
   我们：  python tools/art_batch.py 任务包.zip
           python tools/art_batch.py 任务包.zip --out 结果包.zip
   设计师：页面点「导入生成结果 .zip」→ 自动回填到对应帧

用法：
    $env:MODELSCOPE_TOKEN = "ms-xxxx"
    python tools/art_batch.py 某角色_jobs.zip
    python tools/art_batch.py 某角色_jobs.zip --only idle_0,attack_1
    python tools/art_batch.py 某角色_jobs.zip --dry-run

输出：<key>_results.zip，里面是 <key>__<slot>.png，可直接被页面导入。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "anim_demo"))

try:
    from gen_image_qwen import generate          # noqa: E402 复用已跑通的管线
except Exception as exc:                          # noqa: BLE001
    print(f"无法导入 anim_demo/gen_image_qwen.py: {exc}")
    print("请确认在仓库根目录执行，且已安装 requests / Pillow")
    raise SystemExit(1)


def load_jobs(zip_path: Path, workdir: Path) -> dict:
    with zipfile.ZipFile(zip_path) as z:
        if "jobs.json" not in z.namelist():
            raise SystemExit("任务包里没有 jobs.json")
        meta = json.loads(z.read("jobs.json").decode("utf-8"))
        for name in z.namelist():
            if name.startswith("frames/") and name.endswith(".png"):
                target = workdir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(z.read(name))
    return meta


def main() -> int:
    ap = argparse.ArgumentParser(description="批量跑设计工坊的生成任务")
    ap.add_argument("jobs_zip", type=Path, help="页面导出的 *_jobs.zip")
    ap.add_argument("--out", type=Path, default=None, help="结果 zip 路径")
    ap.add_argument("--only", default="", help="只跑这些槽位，逗号分隔，如 idle_0,attack_1")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不真的生成")
    args = ap.parse_args()

    token = os.environ.get("MODELSCOPE_TOKEN") or os.environ.get("MS_TOKEN")
    if not token and not args.dry_run:
        print("未读到 token。PowerShell:  $env:MODELSCOPE_TOKEN = \"ms-xxxx\"")
        return 2

    key_guess = args.jobs_zip.stem.replace("_jobs", "")
    out_zip = args.out or (args.jobs_zip.parent / f"{key_guess}_results.zip")
    only = [s.strip() for s in args.only.split(",") if s.strip()]

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        meta = load_jobs(args.jobs_zip, work)
        jobs = meta.get("jobs") or []
        model = meta.get("model") or "Qwen/Qwen-Image-2.1"
        sel = [j for j in jobs if not only or j["slot"] in only]
        print(f"任务 {len(jobs)} 个，本次处理 {len(sel)} 个，模型 {model}")
        if args.dry_run:
            for j in sel:
                print(f"  {j['slot']:<10} {'图生图' if j.get('ref') else '文生图'}  {j['prompt'][:60]}…")
            return 0

        results = []
        t0 = time.time()
        for n, j in enumerate(sel, 1):
            slot = j["slot"]
            out_png = work / f"{j['key']}__{slot}.png"
            ref = work / j["ref"] if j.get("ref") else None
            print(f"[{n}/{len(sel)}] {slot} …", flush=True)
            try:
                generate(j["prompt"], str(out_png), model=model,
                         ref_path=str(ref) if ref and ref.exists() else None)
                results.append((f"{j['key']}__{slot}.png", out_png.read_bytes()))
            except SystemExit as exc:                 # generate 内部用 sys.exit 报错
                print(f"  !! {slot} 失败：{exc}")
            except Exception as exc:                  # noqa: BLE001
                print(f"  !! {slot} 失败：{exc.__class__.__name__}: {exc}")

    if not results:
        print("一个都没成功，未写结果包")
        return 1
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in results:
            z.writestr(name, data)
        z.writestr("README.txt",
                   f"由 tools/art_batch.py 生成，共 {len(results)} 帧。\n"
                   "在网页里点「导入生成结果 .zip」即可回填。\n")
    print(f"\n完成 {len(results)}/{len(sel)}，用时 {time.time()-t0:.0f}s")
    print("结果包:", out_zip)
    print("把这个 zip 发给设计师，在页面点「导入生成结果」即可回填。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

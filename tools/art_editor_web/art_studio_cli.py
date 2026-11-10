#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""植物立绘工坊 · 本机生成器（零第三方依赖，只用 Python 标准库）

用途：把网页「导出生成任务 .zip」得到的任务包，批量跑成图片，
      产出 `<key>_results.zip`，再回网页点「导入生成结果」回填。

用法（三种都行）：
    python art_studio_cli.py 任务包.zip
    python art_studio_cli.py                    # 不带参数会自动找同目录的 *_jobs.zip
    python art_studio_cli.py 任务包.zip --dry-run     # 只看计划，不花钱
    python art_studio_cli.py 任务包.zip --only idle_0,attack_1

Token 从环境变量读（不要写进脚本）：
    macOS / Linux:   export MODELSCOPE_TOKEN="ms-xxxx"
    Windows PowerShell:  $env:MODELSCOPE_TOKEN = "ms-xxxx"
    Windows CMD:     set MODELSCOPE_TOKEN=ms-xxxx

依赖：Python 3.8+。不需要 pip install 任何东西。
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://api-inference.modelscope.cn"
DEFAULT_MODEL = "Qwen/Qwen-Image-2.1"
POLL_INTERVAL = 5
POLL_ROUNDS = 72          # 5s * 72 = 6 分钟
UA = "plant-art-studio/1.0"


# ---------------------------------------------------------------- 基础请求
def _request(url: str, *, data: bytes | None = None, headers: dict | None = None,
             timeout: int = 90) -> bytes:
    req = urllib.request.Request(url, data=data, method="POST" if data else "GET")
    req.add_header("User-Agent", UA)
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _json(url: str, **kw) -> dict:
    return json.loads(_request(url, **kw).decode("utf-8"))


# ---------------------------------------------------------------- 生成一帧
def generate_one(prompt: str, ref_png: bytes | None, token: str, model: str) -> bytes:
    """调用 ModelScope 异步任务，返回 PNG 字节。"""
    payload: dict = {"model": model, "prompt": prompt}
    if ref_png:                                   # 图生图：参考图以 data-uri 传入
        payload["image_url"] = ["data:image/png;base64," + base64.b64encode(ref_png).decode()]
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-ModelScope-Async-Mode": "true",
    }
    # 注意：该接口不能传 size，传了会 500
    sub = _json(BASE + "/v1/images/generations", data=body, headers=headers)
    task_id = sub.get("task_id")
    if not task_id:
        raise RuntimeError("提交成功但没拿到 task_id：" + json.dumps(sub, ensure_ascii=False)[:300])

    poll_headers = {
        "Authorization": f"Bearer {token}",
        "X-ModelScope-Task-Type": "image_generation",
    }
    for i in range(POLL_ROUNDS):
        time.sleep(POLL_INTERVAL)
        print(f"    · 等待 {i + 1}/{POLL_ROUNDS}", end="\r", flush=True)
        js = _json(f"{BASE}/v1/tasks/{task_id}", headers=poll_headers)
        status = js.get("task_status")
        if status == "SUCCEED":
            imgs = js.get("output_images") or []
            if not imgs:
                raise RuntimeError("任务成功但没有图片")
            print(" " * 30, end="\r")
            return _request(imgs[0], timeout=180)
        if status == "FAILED":
            raise RuntimeError("生成失败：" + json.dumps(js, ensure_ascii=False)[:400])
    raise RuntimeError("轮询超时（6 分钟）")


# ---------------------------------------------------------------- 任务包读取
def read_jobs(zip_path: Path) -> tuple[dict, dict[str, bytes]]:
    with zipfile.ZipFile(zip_path) as z:
        if "jobs.json" not in z.namelist():
            raise SystemExit("这个 zip 里没有 jobs.json——请确认选的是网页导出的 *_jobs.zip")
        meta = json.loads(z.read("jobs.json").decode("utf-8"))
        refs = {n: z.read(n) for n in z.namelist()
                if n.startswith("frames/") and n.lower().endswith(".png")}
    return meta, refs


def find_jobs_zip() -> Path | None:
    here = Path.cwd()
    cands = sorted(here.glob("*_jobs.zip")) + sorted(Path(__file__).resolve().parent.glob("*_jobs.zip"))
    if cands:
        return cands[0]
    return None


# ---------------------------------------------------------------- 主流程
def main() -> int:
    ap = argparse.ArgumentParser(
        description="植物立绘工坊本机生成器（零第三方依赖）")
    ap.add_argument("jobs_zip", nargs="?", type=Path, help="网页导出的 *_jobs.zip")
    ap.add_argument("--out", type=Path, default=None, help="结果 zip 输出路径")
    ap.add_argument("--only", default="", help="只跑这些槽位，逗号分隔，如 idle_0,attack_1")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划，不真的生成（不花钱）")
    args = ap.parse_args()

    if sys.version_info < (3, 8):
        print(f"当前 Python {sys.version.split()[0]} 太旧，请装 3.8 或更新版本。")
        return 2

    jobs_zip = args.jobs_zip or find_jobs_zip()
    if not jobs_zip or not jobs_zip.exists():
        print("没找到任务包。请这样用：\n"
              "    python art_studio_cli.py 你的任务包.zip\n"
              "或者把任务包放在这个脚本同一个文件夹里再运行一次。")
        return 2
    print(f"任务包：{jobs_zip}")

    meta, refs = read_jobs(jobs_zip)
    jobs = meta.get("jobs") or []
    if not jobs:
        print("任务包里没有任务。")
        return 2
    model = meta.get("model") or DEFAULT_MODEL
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    sel = [j for j in jobs if not only or j.get("slot") in only]

    print(f"共 {len(jobs)} 个任务，本次处理 {len(sel)} 个，模型 {model}")
    if args.dry_run:
        for j in sel:
            how = "图生图" if j.get("ref") else "文生图"
            print(f"  {j['slot']:<10} {how}  {j['prompt'][:70]}…")
        print("\n这是 dry-run，没有花任何额度。去掉 --dry-run 就会真的生成。")
        return 0

    token = os.environ.get("MODELSCOPE_TOKEN") or os.environ.get("MS_TOKEN")
    if not token:
        print("没读到 token。请先设置环境变量，再重新运行：\n"
              "  macOS/Linux:        export MODELSCOPE_TOKEN=\"ms-xxxx\"\n"
              "  Windows PowerShell: $env:MODELSCOPE_TOKEN = \"ms-xxxx\"\n"
              "  Windows CMD:        set MODELSCOPE_TOKEN=ms-xxxx\n"
              "（token 在 https://modelscope.cn → 个人中心 → 访问令牌 里复制）")
        return 2

    key = jobs[0].get("key") or jobs_zip.stem.replace("_jobs", "")
    out_zip = args.out or (jobs_zip.parent / f"{key}_results.zip")

    results: list[tuple[str, bytes]] = []
    failed: list[str] = []
    t0 = time.time()
    for n, j in enumerate(sel, 1):
        slot = j.get("slot", f"frame{n}")
        ref = refs.get(j.get("ref") or "")
        print(f"[{n}/{len(sel)}] {slot}  {'图生图' if ref else '文生图'}")
        try:
            png = generate_one(j["prompt"], ref, token, model)
            results.append((f"{key}__{slot}.png", png))
            print(f"    完成 {len(png) // 1024} KB")
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            if exc.code in (401, 403):
                print(f"    !! token 无效或无权限（HTTP {exc.code}）")
                print("       请检查 MODELSCOPE_TOKEN 是否是「访问令牌」而不是登录密码")
                return 3
            print(f"    !! HTTP {exc.code}：{detail}")
            failed.append(slot)
        except urllib.error.URLError as exc:
            print(f"    !! 网络错误：{exc.reason}")
            failed.append(slot)
        except KeyboardInterrupt:
            print("\n你按了 Ctrl+C，已停止。已生成的部分仍会保存。")
            break
        except Exception as exc:                       # noqa: BLE001
            print(f"    !! 失败：{exc}")
            failed.append(slot)

    if not results:
        print("一帧都没成功，没有写结果包。")
        return 1

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in results:
            z.writestr(name, data)
        note = (f"由 art_studio_cli.py 生成，共 {len(results)} 帧。\n"
                "回到网页点「导入生成结果 .zip」即可自动回填到对应帧。\n")
        if failed:
            note += "本次失败：" + ", ".join(failed) + "\n"
        z.writestr("说明.txt", note.encode("utf-8"))

    print(f"\n完成 {len(results)}/{len(sel)}，用时 {time.time() - t0:.0f}s")
    if failed:
        print("失败槽位：", ", ".join(failed), "（可加 --only 重跑）")
    print("结果包：", out_zip)
    print("把这个 zip 拖回网页的「导入生成结果」即可。")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as exc:                           # noqa: BLE001
        print(f"\n出错了：{exc.__class__.__name__}: {exc}")
        sys.exit(1)

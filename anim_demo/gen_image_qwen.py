# -*- coding: utf-8 -*-
"""
魔搭 ModelScope 千问文生图客户端（Qwen-Image-2.1，异步任务封装为一次调用）。
Token 从环境变量读取，不写死在代码里：
  PowerShell:  $env:MODELSCOPE_TOKEN = "你的token"
用法：
  python gen_image_qwen.py --prompt "2D游戏精灵立绘，……，纯白色干净背景" --out raw.png
注意：
  - 不要传 size 字段（该模型此接口会因此 submit 500）；默认返回约 760x1280 竖图，后期再裁切。
  - 做精灵请在 prompt 里强制“纯白色干净背景、全身居中、无阴影、无文字”，便于 build_spritesheet 自动去背。
"""
import os
import sys
import time
import json
import base64
import argparse
import requests
from io import BytesIO
from PIL import Image

BASE = "https://api-inference.modelscope.cn/"


def generate(prompt, out, model="Qwen/Qwen-Image-2.1", ref_path=None,
             poll_interval=5, timeout_rounds=60):
    token = os.environ.get("MODELSCOPE_TOKEN") or os.environ.get("MS_TOKEN")
    if not token:
        sys.exit("未读到 token：请先设置环境变量 MODELSCOPE_TOKEN（PowerShell: $env:MODELSCOPE_TOKEN='...'）")
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"model": model, "prompt": prompt}
    if ref_path:  # 图像编辑：本地参考图转 base64 data-uri，锚定同一角色
        b64 = base64.b64encode(open(ref_path, "rb").read()).decode()
        payload["image_url"] = ["data:image/png;base64," + b64]

    r = requests.post(BASE + "v1/images/generations",
                      headers={**headers, "X-ModelScope-Async-Mode": "true"},
                      data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), timeout=60)
    if r.status_code != 200:
        sys.exit(f"提交失败 HTTP {r.status_code}: {r.text[:400]}")
    task_id = r.json()["task_id"]
    print("task_id:", task_id)

    for i in range(timeout_rounds):
        q = requests.get(BASE + f"v1/tasks/{task_id}",
                         headers={**headers, "X-ModelScope-Task-Type": "image_generation"}, timeout=60)
        q.raise_for_status()
        status = q.json().get("task_status")
        print(f"poll {i}: {status}")
        if status == "SUCCEED":
            url = q.json()["output_images"][0]
            raw = requests.get(url, timeout=120).content
            im = Image.open(BytesIO(raw))
            os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
            im.save(out)
            print("saved:", out, im.size, im.mode)
            return out
        if status == "FAILED":
            sys.exit("生成失败: " + json.dumps(q.json(), ensure_ascii=False)[:500])
        time.sleep(poll_interval)
    sys.exit("轮询超时")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="Qwen/Qwen-Image-2.1")
    ap.add_argument("--ref", default=None, help="可选：本地参考图路径，提供则走图像编辑以锚定同一角色")
    a = ap.parse_args()
    generate(a.prompt, a.out, a.model, ref_path=a.ref)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""植物工坊 · 本地服务（Python 标准库版，零第三方依赖）

和 server.js 功能完全一样，只是换成 Python：
  - 用 Python 去调 ModelScope（浏览器直连会被 CORS 拦，服务端没有这个限制）
  - 页面从本机加载，请求自己这个服务，同源，没有 CORS
  - 文件由本服务直接写进仓库

用法：
    python3 server.py            # 默认 8777
    python3 server.py 8888

令牌（三选一）：
    环境变量 MODELSCOPE_TOKEN / MS_TOKEN
    或 anim_demo/.ms_token 文件（一行）
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANIM = ROOT / "anim_demo"
SPRITES = ANIM / "assets" / "sprites"
ENEMIES = SPRITES / "enemies"
PLANTS_DIR = ANIM / "assets" / "plants"
DATA = ROOT / "tdgame" / "data"
PUBLIC = HERE / "public"
TOKEN_FILE = ANIM / ".ms_token"

MS_BASE = "https://api-inference.modelscope.cn"
MODEL = "Qwen/Qwen-Image-2.1"
FRAME, COLS = 64, 4
ROW_FRAMES = [2, 4, 3, 2]
ROW_NAMES = ["idle", "walk", "attack", "hurt"]
SLOTS = []
for _r, _n in enumerate(ROW_FRAMES):
    for _c in range(COLS):
        SLOTS.append({"name": f"{ROW_NAMES[_r]}_{_c}", "row": _r, "col": _c,
                      "enabled": _c < _n})

PROJ_KINDS = {"seed": "种子/光球弹", "blade": "剑气/刀光",
              "leaf": "飞叶", "organ": "延伸器官/触手"}
PROJ_HINT = {
    "seed": "一颗圆润饱满、带简洁高光的种子形能量弹，略卡通可爱，适合从花口/炮口直线射出",
    "blade": "一道月牙形的半透明剑气刀光，带锐利刃缘和清晰的速度拖尾，朝向画面正前方",
    "leaf": "一片边缘锋利、叶脉清晰的飞旋叶片，造型利落、带轻微旋转动势",
    "organ": "一段可弹射出去的植物延伸器官（如卷须尖、硬刺或孢子囊），造型饱满有弹性",
}
PROJ_TAIL = (
    "画面中只有这一个道具，不要出现整株植物、角色五官、花盆、地面、手或任何其它物体；"
    "纯白色干净背景(#FFFFFF)，2D 卡通 Q 版手游道具图标风格，粗深色描边、明快平涂加少量渐变，"
    "单个道具完整居中、四周充分留白、无地面投影、无文字水印。"
)


# ---------------------------------------------------------------- 令牌
def load_token() -> tuple[str, str]:
    env = (os.environ.get("MODELSCOPE_TOKEN") or os.environ.get("MS_TOKEN") or "").strip()
    if env:
        return env, "环境变量"
    try:
        t = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if t:
            return t, ".ms_token 文件"
    except OSError:
        pass
    return "", "未配置"


# ---------------------------------------------------------------- HTTP 工具
def http_json(url: str, *, method: str = "GET", headers: dict | None = None,
              body: bytes | None = None, tries: int = 4,
              timeout: int = 90) -> dict:
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, method=method)
            req.add_header("User-Agent", "plant-forge/1.0")
            for k, v in (headers or {}).items():
                req.add_header(k, v)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            err = RuntimeError(f"HTTP {exc.code}: {detail}")
            if exc.code < 500 and exc.code != 429:
                raise err from None
            last = err
        except Exception as exc:                       # noqa: BLE001
            last = exc
        if i < tries - 1:
            time.sleep(1.5 + 1.5 * i)
    raise last if last else RuntimeError("请求失败")


def http_bytes(url: str, *, tries: int = 3, timeout: int = 180) -> bytes:
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "plant-forge/1.0")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as exc:                       # noqa: BLE001
            last = exc
            if i < tries - 1:
                time.sleep(1.5)
    raise last if last else RuntimeError("下载失败")


# ---------------------------------------------------------------- 生成
def generate_one(prompt: str, ref: str | None = None) -> dict:
    token, _src = load_token()
    if not token:
        raise RuntimeError("没有配置令牌：请设置环境变量 MODELSCOPE_TOKEN，"
                           "或在 anim_demo 下放 .ms_token 文件")
    payload: dict = {"model": MODEL, "prompt": prompt}
    if ref:
        payload["image_url"] = [ref]

    sub = http_json(MS_BASE + "/v1/images/generations", method="POST",
                    headers={"Authorization": f"Bearer {token}",
                             "Content-Type": "application/json",
                             "X-ModelScope-Async-Mode": "true"},
                    body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    timeout=120)
    task_id = sub.get("task_id")
    if not task_id:
        raise RuntimeError("提交成功但没拿到 task_id：" + json.dumps(sub, ensure_ascii=False)[:200])

    poll = float(os.environ.get("POLL_SECONDS", "3"))
    for _ in range(100):
        time.sleep(poll)
        js = http_json(f"{MS_BASE}/v1/tasks/{task_id}",
                       headers={"Authorization": f"Bearer {token}",
                                "X-ModelScope-Task-Type": "image_generation"},
                       timeout=60)
        st = js.get("task_status")
        if st == "SUCCEED":
            imgs = js.get("output_images") or []
            if not imgs:
                raise RuntimeError("任务成功但没有图片")
            return {"taskId": task_id, "buffer": http_bytes(imgs[0])}
        if st == "FAILED":
            raise RuntimeError("生成失败：" + json.dumps(js, ensure_ascii=False)[:300])
    raise RuntimeError("轮询超时（约 5 分钟）")


# ---------------------------------------------------------------- 项目数据
def unit_cn(kind: str, key: str) -> str:
    try:
        return json.loads((DATA / kind / f"{key}.json").read_text(encoding="utf-8")).get("cn", key)
    except Exception:                                  # noqa: BLE001
        return key


def project_dir(key: str) -> Path:
    return PLANTS_DIR / key


def frames_dir(key: str) -> Path:
    return project_dir(key) / "frames"


def project_json(key: str) -> Path:
    return project_dir(key) / "plant.json"


def read_project(key: str) -> dict:
    try:
        return json.loads(project_json(key).read_text(encoding="utf-8"))
    except Exception:                                  # noqa: BLE001
        return {}


def write_project(key: str, data: dict) -> None:
    project_dir(key).mkdir(parents=True, exist_ok=True)
    data["key"] = key
    data.setdefault("cn", unit_cn("plants", key))
    data["updated"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    project_json(key).write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                 encoding="utf-8", newline="\n")


def safe_key(key: str) -> str:
    return re.sub(r"[^\w-]", "", key or "")


def sheet_path(key: str) -> Path | None:
    for p in (SPRITES / f"{key}.png", ENEMIES / f"{key}.png"):
        if p.exists():
            return p
    return None


def list_units() -> list[dict]:
    out = []
    for d, kind in ((SPRITES, "plants"), (ENEMIES, "enemies")):
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.png")):
            k = f.stem
            out.append({"key": k, "cn": unit_cn(kind, k), "kind": kind,
                        "frames": {s["name"]: (frames_dir(k) / f"{s['name']}.png").exists()
                                   for s in SLOTS if s["enabled"]}})
    return sorted(out, key=lambda u: u["key"])


# ---------------------------------------------------------------- 业务
def proj_prompt(kind: str, desc: str) -> str:
    part = (desc or "").strip() or PROJ_HINT.get(kind, PROJ_HINT["seed"])
    return part + "。" + PROJ_TAIL


def api_state() -> dict:
    token, src = load_token()
    return {"ok": True, "token": {"configured": bool(token), "from": src},
            "slots": SLOTS, "frame": FRAME, "cols": COLS,
            "rowFrames": ROW_FRAMES, "model": MODEL, "root": str(ROOT)}


def api_frames(key: str) -> dict:
    key = safe_key(key)
    frames = {}
    for s in SLOTS:
        if not s["enabled"]:
            continue
        f = frames_dir(key) / f"{s['name']}.png"
        frames[s["name"]] = base64.b64encode(f.read_bytes()).decode() if f.exists() else None
    pj = read_project(key)
    proj_file = project_dir(key) / "projectile.png"
    return {"ok": True, "frames": frames, "prompts": pj.get("frames") or {},
            "base": pj.get("base_desc") or "",
            "projectile": pj.get("projectile"),
            "projectileImage": (base64.b64encode(proj_file.read_bytes()).decode()
                                if proj_file.exists() else None),
            "projectileKinds": PROJ_KINDS,
            "exists": {s["name"]: frames[s["name"]] is not None
                       for s in SLOTS if s["enabled"]}}


class Handler(BaseHTTPRequestHandler):
    server_version = "PlantForge/1.0"

    def log_message(self, fmt, *args):                 # 安静一点
        pass

    # ---------- 输出 ----------
    def _send(self, code: int, body, ctype: str = "application/json; charset=utf-8"):
        if not isinstance(body, (bytes, bytearray)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except Exception:                              # noqa: BLE001
            return {}

    # ---------- 路由 ----------
    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        try:
            if p == "/api/state":
                return self._send(200, api_state())
            if p == "/api/units":
                return self._send(200, {"ok": True, "units": list_units()})
            if p == "/api/sheet":
                key = safe_key((q.get("key") or [""])[0])
                f = sheet_path(key)
                if not f:
                    return self._send(404, {"ok": False, "error": "没有这个角色的精灵表"})
                return self._send(200, f.read_bytes(), "image/png")
            if p == "/api/frames":
                return self._send(200, api_frames((q.get("key") or [""])[0]))
            return self._static(p)
        except Exception as exc:                       # noqa: BLE001
            self._send(500, {"ok": False, "error": str(exc)})

    def do_POST(self):
        p = urlparse(self.path).path
        try:
            if p == "/api/generate":
                b = self._body()
                prompt = (b.get("prompt") or "").strip()
                if not prompt:
                    return self._send(400, {"ok": False, "error": "prompt 为空"})
                t0 = time.time()
                try:
                    r = generate_one(prompt, b.get("ref"))
                except Exception as exc:               # noqa: BLE001
                    print("  生成失败:", exc)
                    return self._send(400, {"ok": False, "error": str(exc)})
                print(f"  生成完成 {time.time()-t0:.0f}s  {len(r['buffer'])//1024}KB")
                return self._send(200, {
                    "ok": True, "taskId": r["taskId"],
                    "seconds": round(time.time() - t0),
                    "image": "data:image/png;base64," + base64.b64encode(r["buffer"]).decode()})

            if p == "/api/generate3":
                import concurrent.futures as cf
                b = self._body()
                prompt = (b.get("prompt") or "").strip()
                if not prompt:
                    return self._send(400, {"ok": False, "error": "prompt 为空"})
                n = min(4, max(2, int(b.get("n") or 3)))
                t0 = time.time()
                images, errors = [], []
                with cf.ThreadPoolExecutor(max_workers=n) as ex:
                    futs = [ex.submit(generate_one, prompt, b.get("ref")) for _ in range(n)]
                    for i, fu in enumerate(futs):
                        try:
                            images.append("data:image/png;base64,"
                                          + base64.b64encode(fu.result()["buffer"]).decode())
                        except Exception as exc:       # noqa: BLE001
                            errors.append(f"第{i+1}张失败：{exc}")
                print(f"  三连抽 {len(images)}/{n}  {time.time()-t0:.0f}s")
                if not images:
                    return self._send(400, {"ok": False, "error": "；".join(errors) or "全部失败"})
                return self._send(200, {"ok": True, "images": images, "errors": errors,
                                        "seconds": round(time.time() - t0)})

            if p == "/api/frame":
                b = self._body()
                key = safe_key(b.get("key") or "")
                slot = b.get("slot") or ""
                if not key or slot not in [s["name"] for s in SLOTS]:
                    return self._send(400, {"ok": False, "error": "key 或 slot 不合法"})
                b64 = re.sub(r"^data:image/\w+;base64,", "", b.get("image") or "")
                if not b64:
                    return self._send(400, {"ok": False, "error": "没有图片数据"})
                frames_dir(key).mkdir(parents=True, exist_ok=True)
                (frames_dir(key) / f"{slot}.png").write_bytes(base64.b64decode(b64))
                data = read_project(key)
                data.setdefault("frames", {})
                if b.get("prompt"):
                    data["frames"][slot] = b["prompt"]
                write_project(key, data)
                return self._send(200, {"ok": True, "saved": slot})

            if p == "/api/project":
                b = self._body()
                key = safe_key(b.get("key") or "")
                if not key:
                    return self._send(400, {"ok": False, "error": "缺少 key"})
                data = read_project(key)
                if isinstance(b.get("base"), str):
                    data["base_desc"] = b["base"]
                if isinstance(b.get("frames"), dict):
                    data["frames"] = {**(data.get("frames") or {}), **b["frames"]}
                write_project(key, data)
                return self._send(200, {"ok": True, "saved": True})

            if p == "/api/projectile":
                b = self._body()
                key = safe_key(b.get("key") or "")
                if not key:
                    return self._send(400, {"ok": False, "error": "缺少 key"})
                b64 = re.sub(r"^data:image/\w+;base64,", "", b.get("image") or "")
                data = read_project(key)
                if b64:
                    project_dir(key).mkdir(parents=True, exist_ok=True)
                    (project_dir(key) / "projectile.png").write_bytes(base64.b64decode(b64))
                    data["projectile"] = {"enabled": True, "kind": b.get("kind") or "seed",
                                          "desc": b.get("desc") or "", "file": "projectile.png"}
                else:
                    f = project_dir(key) / "projectile.png"
                    if f.exists():
                        f.unlink()
                    data["projectile"] = {"enabled": False, "kind": b.get("kind") or "seed",
                                          "desc": b.get("desc") or "", "file": None}
                write_project(key, data)
                return self._send(200, {"ok": True, "saved": bool(b64)})

            if p == "/api/projectile-prompt":
                b = self._body()
                return self._send(200, {"ok": True,
                                        "prompt": proj_prompt(b.get("kind") or "seed",
                                                              b.get("desc") or "")})

            if p == "/api/sheet":
                b = self._body()
                key = safe_key(b.get("key") or "")
                b64 = re.sub(r"^data:image/\w+;base64,", "", b.get("image") or "")
                if not key or not b64:
                    return self._send(400, {"ok": False, "error": "缺少 key 或图片"})
                target = SPRITES / f"{key}.png"
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(base64.b64decode(b64))
                print(f"  拼表已写入 {target}")
                return self._send(200, {"ok": True, "path": str(target.relative_to(ROOT))})

            return self._send(404, {"ok": False, "error": "接口不存在: " + p})
        except Exception as exc:                       # noqa: BLE001
            self._send(500, {"ok": False, "error": f"{exc.__class__.__name__}: {exc}"})

    # ---------- 静态 ----------
    def _static(self, path: str):
        rel = unquote(path)
        if rel in ("", "/"):
            rel = "/index.html"
        f = (PUBLIC / rel.lstrip("/")).resolve()
        if not str(f).startswith(str(PUBLIC.resolve())):
            return self._send(403, b"forbidden", "text/plain")
        if not f.is_file():
            return self._send(404, ("not found: " + rel).encode(), "text/plain")
        ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        self._send(200, f.read_bytes(), ctype)


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", "8777"))
    token, src = load_token()
    print("=" * 54)
    print(f"  植物工坊已启动  http://127.0.0.1:{port}")
    print(f"  运行时: Python {sys.version.split()[0]}")
    print(f"  仓库: {ROOT}")
    print(f"  令牌: {'已配置（' + src + '）' if token else '未配置 —— 生成会失败，请设置 MODELSCOPE_TOKEN'}")
    print(f"  模型: {MODEL}")
    print("=" * 54)
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

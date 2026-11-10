# -*- coding: utf-8 -*-
"""在本地起一个 http 服务并打开工坊页面。

为什么需要它：
    浏览器把 file:// 当成"不透明来源"，Safari 会直接禁用 IndexedDB / localStorage，
    Chrome/Edge 有时也会限制。改用 http://127.0.0.1 打开，存储就完全正常了。

用法：
    双击同目录的 start_local_server.bat，或
    python serve.py [端口]
"""
from __future__ import annotations

import http.server
import os
import socketserver
import sys
import webbrowser
from functools import partial
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    os.chdir(HERE)
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(HERE))
    try:
        httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    except OSError as exc:
        print(f"端口 {port} 被占用：{exc}\n换个端口： python serve.py 8766")
        return 1
    url = f"http://127.0.0.1:{port}/index.html"
    print("=" * 56)
    print("  植物立绘工坊已启动")
    print(f"  地址：{url}")
    print("  在这个地址下，本机存档（IndexedDB）可以正常工作。")
    print("  关掉这个黑窗口即停止服务。")
    print("=" * 56)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

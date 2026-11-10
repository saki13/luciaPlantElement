#!/bin/bash
# ---------------------------------------------------------------
#  Plant Forge - 网页版植物编辑器（macOS）
#  双击启动。有 Python 就用 Python，没有就用 Node。
#  第一次若提示"来自身份不明的开发者"：右键 -> 打开 -> 再点「打开」
# ---------------------------------------------------------------
cd "$(dirname "$0")" || exit 1

echo "======================================"
echo "  植物工坊 · Plant Forge"
echo "======================================"
echo

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done

if [ -n "$PY" ]; then
  echo "运行时：$PY ($("$PY" --version 2>&1))"
  echo
  "$PY" server.py
elif command -v node >/dev/null 2>&1; then
  echo "运行时：node ($(node --version))"
  echo
  node server.js
else
  cat <<'EOF'
[!] 这台机器上既没有 Python 3 也没有 Node。

装任意一个都行：
  Python: https://www.python.org/downloads/macos/
  Node:   https://nodejs.org/

装完重新双击本文件。
EOF
  read -r -p "按回车关闭…" _
  exit 1
fi

CODE=$?
echo
if [ "$CODE" -ne 0 ]; then
  echo "[退出码 $CODE]"
  read -r -p "按回车关闭…" _
fi

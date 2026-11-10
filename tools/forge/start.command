#!/bin/bash
# ---------------------------------------------------------------
#  Plant Forge - HTML + Node editor (macOS)
#  Double-click. Then open the printed URL in your browser.
#  First time: if macOS says "unidentified developer",
#              right-click -> Open -> Open.
# ---------------------------------------------------------------
cd "$(dirname "$0")" || exit 1

echo "======================================"
echo "  植物工坊 · Plant Forge"
echo "======================================"
echo

if ! command -v node >/dev/null 2>&1; then
  cat <<'EOF'
[!] 没有找到 Node.js

安装方式（二选一）：
  1. 官网：https://nodejs.org/  下载 macOS 的 LTS 版 .pkg，双击安装
  2. Homebrew：brew install node

装完重新双击本文件。
EOF
  read -r -p "按回车关闭…" _
  exit 1
fi

echo "Node 版本：$(node --version)"
echo

if [ ! -f server.js ]; then
  echo "[!] 这个目录里没有 server.js，请确认解压完整。"
  read -r -p "按回车关闭…" _
  exit 1
fi

node server.js
CODE=$?
echo
if [ "$CODE" -ne 0 ]; then
  echo "[退出码 $CODE]"
  read -r -p "按回车关闭…" _
fi

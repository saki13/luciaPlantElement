#!/bin/bash
# ---------------------------------------------------------------
#  植物立绘工坊 - 在本机生成图片（macOS）
#  双击本文件即可运行。
#  第一次运行如果提示"无法打开"，见 说明.md 的常见问题。
# ---------------------------------------------------------------
cd "$(dirname "$0")" || exit 1

echo "======================================"
echo "  植物立绘工坊 · 本机生成"
echo "======================================"
echo

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done

if [ -z "$PY" ]; then
  echo "[!] 没有找到 Python 3。"
  echo "    请先安装：https://www.python.org/downloads/macos/"
  echo "    装完再双击本文件。"
  echo
  read -r -p "按回车关闭…" _
  exit 1
fi

echo "使用 Python：$PY"
"$PY" --version
echo

if [ -z "$MODELSCOPE_TOKEN" ] && [ ! -f .token ]; then
  if [ -f .token ]; then
    export MODELSCOPE_TOKEN="$(cat .token)"
  fi
fi

"$PY" art_studio_cli.py "$@"
CODE=$?

echo
if [ "$CODE" -ne 0 ]; then
  echo "[退出码 $CODE]"
  echo "如果失败，请看 说明.md 里的「常见问题」。"
else
  echo "完成。回到网页点「导入生成结果」即可。"
fi
read -r -p "按回车关闭…" _

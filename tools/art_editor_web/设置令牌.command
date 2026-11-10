#!/bin/bash
# ---------------------------------------------------------------
#  一次性设置 ModelScope 令牌（macOS）
#  双击运行，粘贴令牌即可。会写进同目录的 .token 文件。
# ---------------------------------------------------------------
cd "$(dirname "$0")" || exit 1

echo "======================================"
echo "  设置 ModelScope 令牌"
echo "======================================"
echo
echo "令牌在 https://modelscope.cn 获取："
echo "  右上角头像 → 个人中心 → 访问令牌（Access Token）"
echo "  形如 ms-xxxxxxxx-xxxx-xxxx"
echo

if [ -f .token ] && [ -s .token ]; then
  echo "当前已有令牌：$(cut -c1-8 < .token)…（长度 $(wc -c < .token | tr -d ' ')）"
  read -r -p "要覆盖它吗？[y/N] " yn
  case "$yn" in
    y|Y) ;;
    *) echo "已取消，保持原样。"; read -r -p "按回车关闭…" _; exit 0 ;;
  esac
fi

printf "请粘贴令牌后回车："
read -r TOKEN

# 去掉可能的引号和空白
TOKEN="$(printf '%s' "$TOKEN" | tr -d '[:space:]' | sed 's/^["'\'']//; s/["'\'']$//')"

if [ -z "$TOKEN" ]; then
  echo
  echo "[!] 没有输入内容，未写入。"
  read -r -p "按回车关闭…" _
  exit 1
fi

case "$TOKEN" in
  ms-*) ;;
  *) echo
     echo "[!] 令牌通常以 ms- 开头，你输入的是：${TOKEN:0:12}…"
     read -r -p "仍要保存吗？[y/N] " yn
     case "$yn" in y|Y) ;; *) echo "已取消。"; read -r -p "按回车关闭…" _; exit 0 ;; esac ;;
esac

printf '%s' "$TOKEN" > .token
chmod 600 .token
echo
echo "已保存到 $(pwd)/.token（$(( $(wc -c < .token) )) 字节）"
echo
echo "下一步：双击「开始生成.command」即可开始生成图片。"
read -r -p "按回车关闭…" _

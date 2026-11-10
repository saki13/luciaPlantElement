# -*- coding: utf-8 -*-
"""把植物编辑器打包成一份可以直接交给外部设计师的文件夹 + zip。

用法:
    python tools/build_editor_pack.py

产物:
    dist/PlantForge/            文件夹（本地自己也能直接跑）
    dist/PlantForge.zip         发给设计师

包含:
    plant_editor.py / gen_image_qwen.py / gen_plant.py / build_spritesheet.py
    assets/sprites/**.png       现有 54 个角色的成品精灵表（供参考与改造）
    assets/plants/              空目录，设计师的新项目落在里面
    requirements.txt            pillow / requests
    说明.md                     安装、令牌、使用、怎么把资产交回来
    开始编辑.command            macOS 双击
    开始编辑.bat                Windows 双击

不包含（体积原因，也不需要）:
    assets/plants 里我们已有的 16 个项目、候选图、历史帧（共约 238MB）
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "anim_demo"
OUT = ROOT / "dist" / "PlantForge"
ZIP = ROOT / "dist" / "PlantForge.zip"

PY_FILES = ["plant_editor.py", "gen_image_qwen.py", "gen_plant.py",
            "build_spritesheet.py"]

README = """# 植物工坊 Plant Forge

给美术同学用的植物立绘编辑器。**桌面向导**，一步步来：
描述 → 生成立绘 → 选一张 → 逐帧重抽 → 拼成精灵表。

---

## 一、装环境（只需一次）

需要 **Python 3.8+**。先确认：

```bash
python3 --version      # macOS
python --version       # Windows
```

没有就去 <https://www.python.org/downloads/> 下载安装（Windows 记得勾
`Add python.exe to PATH`）。

然后装两个库（在本文件夹里执行）：

```bash
python3 -m pip install -r requirements.txt     # macOS
py -m pip install -r requirements.txt          # Windows
```

> 国内网络慢可以加镜像：
> `-i https://pypi.tuna.tsinghua.edu.cn/simple`

---

## 二、设置 ModelScope 令牌

1. <https://modelscope.cn> 登录 → 右上角头像 → **个人中心** → **访问令牌**
2. 复制形如 `ms-xxx` 的那串

然后二选一：

**A. 直接在界面里填**（推荐）
打开编辑器，点顶部的令牌按钮，粘贴进去。它会存到本机 `.ms_token`
（这个文件不要发给别人）。

**B. 环境变量**

```bash
export MODELSCOPE_TOKEN="ms-xxx"       # macOS
$env:MODELSCOPE_TOKEN = "ms-xxx"       # Windows PowerShell
```

---

## 三、打开编辑器

| 系统 | 双击 |
|---|---|
| macOS | `开始编辑.command` |
| Windows | `开始编辑.bat` |

或者命令行：

```bash
python3 plant_editor.py       # macOS
py plant_editor.py            # Windows
```

macOS 第一次双击 `.command` 若提示"来自身份不明的开发者"：
**右键 → 打开 → 弹窗点「打开」**（只需一次）。

---

## 四、改哪个角色

左上角下拉框列出 **现有 54 个角色**（植物 + 僵尸）。
选中一个，编辑器会自动把它的精灵表拆成 11 帧，直接进入可编辑状态。

想从零做一个新的，点「新建植物」。

---

## 五、五步流程

1. **描述**：写清楚长什么样（颜色、形状、有没有眼睛、拿什么武器）
2. **立绘连抽**：一次生成 3 张，挑一张；不满意可以回去改描述
3. **动作帧单张重抽**：11 帧逐张调，每帧有自己的 prompt，可以改
4. **道具**（可选）：子弹/飞行物的透明贴图
5. **拼表**：自动裁切去背、拼成 256×256 精灵表，右侧可看动画预览

完成后精灵表落在 `assets/sprites/<key>.png`，
项目数据在 `assets/plants/<key>/`。

---

## 六、怎么把成果交回来

**把这两个目录整个打包发回即可：**

```
assets/sprites/     改过/新增的精灵表（<key>.png）
assets/plants/      你的项目（<key>/plant.json + frames/ + base.png）
```

只发你改过的也行，文件名保持一致就能对上。

> 不要发 `.ms_token`，那是你的令牌。

---

## 七、帧规格（编辑器会自动满足）

| 项 | 说明 |
|---|---|
| 精灵表 | 256×256，4 列，行帧数 2/4/3/2，共 11 个可用格 |
| 单帧 | 64×64，底部居中 |
| 每张图 | 只能有一个角色 |

---

## 八、常见问题

**`python3: command not found`** → 装 Python，装完重开终端。

**`ModuleNotFoundError: No module named 'PIL'`** → 没装依赖，执行第二节那条 pip。

**生成失败 HTTP 401** → 令牌不对或过期；确认是「访问令牌」不是密码。

**卡在"生成中"** → 模型排队，等；超时会报错。

**macOS 提示无法打开 .command** → 右键 → 打开 → 再点「打开」。
"""

LAUNCH_SH = """#!/bin/bash
# macOS: 双击运行植物工坊
cd "$(dirname "$0")" || exit 1

PY=""
for c in python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo "没有找到 Python 3。请到 https://www.python.org/downloads/ 安装后重试。"
  read -r -p "按回车关闭…" _
  exit 1
fi

"$PY" -c "import PIL" 2>/dev/null || {
  echo "缺少依赖，正在安装…"
  "$PY" -m pip install -r requirements.txt || {
    echo "安装失败，请手动执行： $PY -m pip install -r requirements.txt"
    read -r -p "按回车关闭…" _
    exit 1
  }
}

"$PY" plant_editor.py
CODE=$?
if [ "$CODE" -ne 0 ]; then
  echo "[退出码 $CODE]"
  read -r -p "按回车关闭…" _
fi
"""

LAUNCH_BAT = """@echo off
rem Windows: 双击运行植物工坊
setlocal
cd /d "%~dp0"

set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo 没有找到 Python。请到 https://www.python.org/downloads/ 安装，
  echo 安装时勾选 "Add python.exe to PATH"。
  pause
  exit /b 1
)

%PY% -c "import PIL" 2>nul || (
  echo 缺少依赖，正在安装...
  %PY% -m pip install -r requirements.txt
)

%PY% plant_editor.py
if not "%ERRORLEVEL%"=="0" pause
endlocal
"""

REQUIREMENTS = "# Plant Forge 依赖\npillow>=9.0\nrequests>=2.28\n"


def build() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets" / "plants").mkdir(parents=True)

    for name in PY_FILES:
        src = SRC / name
        if not src.exists():
            raise SystemExit(f"缺少 {src}")
        shutil.copy2(src, OUT / name)

    # 现有精灵表（供参考/改造），不含候选图与历史
    sprites_src = SRC / "assets" / "sprites"
    if sprites_src.is_dir():
        shutil.copytree(sprites_src, OUT / "assets" / "sprites")

    (OUT / "说明.md").write_text(README, encoding="utf-8", newline="\n")
    (OUT / "requirements.txt").write_text(REQUIREMENTS, encoding="utf-8", newline="\n")
    (OUT / "开始编辑.command").write_text(LAUNCH_SH, encoding="utf-8", newline="\n")
    (OUT / "开始编辑.bat").write_text(LAUNCH_BAT, encoding="utf-8", newline="\n")

    # zip：保留 .command 的可执行位
    if ZIP.exists():
        ZIP.unlink()
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for f in sorted(OUT.rglob("*")):
            if f.is_dir():
                continue
            arc = f.relative_to(OUT.parent).as_posix()
            if f.name.endswith(".command"):
                info = zipfile.ZipInfo(arc, date_time=(2026, 1, 1, 0, 0, 0))
                info.external_attr = 0o755 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, f.read_bytes())
            else:
                z.write(f, arc)

    n_files = sum(1 for f in OUT.rglob("*") if f.is_file())
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"文件夹: {OUT.relative_to(ROOT)}  ({n_files} 个文件, {size/1024/1024:.1f} MB)")
    print(f"压缩包: {ZIP.relative_to(ROOT)}  ({ZIP.stat().st_size/1024/1024:.1f} MB)")


if __name__ == "__main__":
    build()

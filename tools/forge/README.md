# 植物工坊 · Plant Forge（HTML + Node）

网页界面做图，Node 在本机起服务。

**关键**：图片生成由 **Node** 去调 ModelScope——浏览器直连会被 CORS 拦（实测
`TypeError: Failed to fetch`），Node 没有这个限制。页面从 `http://127.0.0.1:8777`
加载，请求自己这个服务是同源，所以也没有 CORS 问题。文件同样由 Node 直接写进仓库。

---

## 目录

1. [装 Node](#一装-node只需一次)
2. [配令牌](#二配令牌)
3. [启动](#三启动)
4. [界面怎么用](#四界面怎么用)
5. [工作流](#五推荐工作流)
6. [成果怎么回主仓库](#六成果怎么回主仓库)
7. [帧规格](#七帧规格)
8. [命令行接口](#八命令行接口给自己或脚本用)
9. [常见问题](#九常见问题)

---

## 一、装运行时（只需一次，Python 或 Node 任选其一）

服务端有两个等价实现，**有哪个用哪个，页面完全一样**：

| 文件 | 需要 | 说明 |
|---|---|---|
| `server.py` | **Python 3.8+** | 只用标准库，**不用 pip install** |
| `server.js` | **Node 18+** | 只用内置模块，**不用 npm install** |

`start.command` / `start.bat` 会**自动挑**：先找 Python，没有再用 Node，
两个都没有才提示你去装。

自己确认一下：

```bash
python3 --version      # macOS，有 3.8+ 就行
node --version         # 需要 18+
```

都没有的话（装任意一个即可，装完重开终端）：

- Python：<https://www.python.org/downloads/>（Windows 记得勾 `Add python.exe to PATH`）
- Node：<https://nodejs.org/>（下 LTS 版）

## 二、配令牌

三选一，服务启动时会打印用的是哪一种：

**A. 放在 `anim_demo/.ms_token`（推荐）**

新建这个文件，内容只有一行：

```
ms-你的令牌
```

**B. 环境变量**

```bash
export MODELSCOPE_TOKEN="ms-你的令牌"      # macOS
$env:MODELSCOPE_TOKEN = "ms-你的令牌"      # Windows PowerShell
```

**C. 直接改 server.js** —— 不推荐，容易被误提交。

令牌在 <https://modelscope.cn> → 右上角头像 → 个人中心 → **访问令牌**。

> `.ms_token` 已在 `.gitignore` 里，不会进版本库。

---

## 三、启动

| 系统 | 双击 |
|---|---|
| macOS | `start.command` |
| Windows | `start.bat` |

或命令行（用哪个运行时都行）：

```bash
python3 server.py        # Python 版，默认 8777
python3 server.py 8888   # 换端口

node server.js           # Node 版，等价
node server.js 8888
```

看到这样就绪了：

```
======================================================
  植物工坊已启动  http://127.0.0.1:8777
  令牌: 已配置（.ms_token 文件）
  模型: Qwen/Qwen-Image-2.1
======================================================
```

浏览器打开那个地址。

> macOS 第一次双击 `.command` 提示「来自身份不明的开发者」：
> **右键 → 打开 → 弹窗再点「打开」**，只需一次。

---

## 四、界面怎么用

### 左栏

| 区块 | 作用 |
|---|---|
| **① 选择角色** | 下拉框列出仓库里全部 54 个（植物 + 僵尸）。选中后自动把它的精灵表切成 11 帧 |
| **② 整株描述** | 用大白话写这株植物长什么样。**会拼进每一帧的 prompt**，也是三选一用的描述 |
| **③ 立绘三选一** | 点一下并行抽 3 张，点哪张就设为 `idle_0` |
| **④ 风格约束** | 统一画风的尾巴，自动拼在 prompt 后面 |

### 中间

**③ 动作帧**：16 格里 11 格可用（idle×2 / walk×4 / attack×3 / hurt×2）。

**点任意一格选中它**，上方出现这一帧的编辑区：

| 按钮 | 作用 |
|---|---|
| **生成这一帧** | 出图并显示。已有图时会以它为参考（图生图），保持还是同一株 |
| **生成并保存** | 出图 + 直接写盘，最常用 |
| **只保存图片** | 单独存 |
| **撤销** | 每帧保留上一张（生成/清空/替换前都会记） |
| **← 上一帧 / 下一帧 →** | 不用回格子点 |
| **上传替换 / 清空** | 用自己画的图 / 移除这一帧 |

**快捷键**

```
← / →         切帧
Ctrl + Enter  生成
Ctrl + S      保存
```

**自动落盘**：改动整株描述或每帧 prompt 后 700ms 自动写进
`anim_demo/assets/plants/<key>/plant.json`，不用手动保存。

### 右栏

**④ 合成预览**：实时显示拼好的 256×256 表和动画。

**拼表并写入**：把这 11 帧拼成精灵表，覆盖
`anim_demo/assets/sprites/<key>.png`。

**⑤ 子弹 / 道具**：选类型 → 可写描述 → 生成 → 自动去白底 → 保存到
`assets/plants/<key>/projectile.png`。

类型有：种子/光球弹、剑气/刀光、飞叶、延伸器官。
去白底是从**四边泛洪**，所以角色内部的白高光不会被误删。

---

## 五、推荐工作流

```
选角色
  → 写整株描述
  → ③ 立绘三选一，挑一张设为 idle_0
  → 逐帧点开，按需改该帧 prompt →「生成并保存」
  → ⑤ 生成道具
  → 拼表并写入
  → git add anim_demo/assets && git commit
```

改现有角色时，整株描述会自动带出它原来的 `art_prompt`（没有就空着）。

---

## 六、成果怎么回主仓库

**文件是直接写进仓库的**，不需要导出再导入。

同机器 / 同仓库：

```bash
git add anim_demo/assets/plants anim_demo/assets/sprites
git commit -m "美术更新：<角色>"
```

在别的机器上跑：把这两个目录打回传，收到后覆盖进来再校验：

```
anim_demo/assets/plants/<key>/plant.json
anim_demo/assets/plants/<key>/frames/*.png
anim_demo/assets/plants/<key>/projectile.png
anim_demo/assets/sprites/<key>.png
```

```bash
python scripts/check_sprites.py
python scripts/check_render.py --shot-dir _work
```

新增角色还要补 `tdgame/data/plants/<key>.json`（阳光/血量/能力），
然后重新打包 exe：`tools\build_exe.ps1`。

---

## 七、帧规格

| 项 | 说明 |
|---|---|
| 精灵表 | 256×256，4 列，行帧数 2/4/3/2，共 11 个可用格 |
| 单帧 | 64×64，底部居中 |
| 每张图 | 只能有一个角色 |

---

## 八、命令行接口（给自己或脚本用）

```bash
GET  /api/state                     服务状态、令牌来源、槽位定义
GET  /api/units                     54 个角色
GET  /api/sheet?key=<key>           精灵表 PNG
GET  /api/frames?key=<key>          项目帧（base64）+ prompts + base + projectile
POST /api/generate   {prompt, ref?}  生成一张，返回 dataURL（同步等待）
POST /api/generate3  {prompt, n}     并行抽 n 张
POST /api/frame      {key, slot, image, prompt}   写帧 + 同步 prompt
POST /api/project    {key, base, frames}          写整株描述与各帧 prompt
POST /api/projectile {key, kind, desc, image}     写道具
POST /api/projectile-prompt {kind, desc}          取拼好的道具 prompt
POST /api/sheet      {key, image}                 覆盖精灵表
```

生成是同步接口：POST 之后服务端负责提交 + 轮询，最长约 5 分钟。
所有外部请求带重试（实测遇到过 SSL EOF 断连）。

---

## 九、常见问题

**`python3` 和 `node` 都没有**
→ 装任意一个。Python 更省事：只要 3.8+，不用装包。

**页面打不开 / 空白**
→ 服务没起来。看终端有没有报错；端口被占就换：`node server.js 8888`。

**`令牌: 未配置`**
→ `.ms_token` 不在 `anim_demo/` 下，或内容有空格。检查：`cat anim_demo/.ms_token`。

**生成失败 HTTP 401**
→ 令牌无效或过期。确认是「访问令牌」而不是登录密码。

**生成很慢 / 一直排队**
→ 正常 20 秒~1 分钟；三连抽并行约 24 秒。超时会报错，可重试。

**改了图但游戏里没变**
→ 要先点「拼表并写入」，才会覆盖 `assets/sprites/<key>.png`；
   之后还要重新打包 exe。

**道具边缘有白边**
→ 生成时偶尔会有淡阴影。可以再生成一次，或用「上传替换」放自己抠好的图。

**想回滚**
→ 一切都在 git 里：`git checkout -- anim_demo/assets`。

**Mac 提示无法打开 .command**
→ 右键 → 打开 → 再点「打开」。

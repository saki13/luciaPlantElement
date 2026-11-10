# 植物工坊（HTML + Node 版）

网页界面，Node 在本机起服务。**图片生成由 Node 去调 ModelScope**
（浏览器不能直连，Node 没有 CORS 限制），文件也由 Node 直接写进仓库。

---

## 一、装 Node（只需一次）

```bash
node --version        # 需要 v18 或更新
```

没有就去 <https://nodejs.org/> 下 LTS 版安装包，双击装完重开终端再验证。

> **不需要 `npm install`**：服务端只用 Node 内置模块，零依赖。

---

## 二、配置令牌

三选一，服务启动时会打印用的是哪一种：

**A. 放在 `anim_demo/.ms_token`（推荐）**

新建这个文件，内容只有一行：

```
ms-你的令牌
```

**B. 环境变量**

```bash
export MODELSCOPE_TOKEN="ms-你的令牌"        # macOS
$env:MODELSCOPE_TOKEN = "ms-你的令牌"        # Windows PowerShell
```

令牌在 <https://modelscope.cn> → 右上角头像 → 个人中心 → **访问令牌**。

> `.ms_token` 已在 `.gitignore` 里，不会被提交。

---

## 三、启动

| 系统 | 双击 |
|---|---|
| macOS | `start.command` |
| Windows | `start.bat` |

或者命令行：

```bash
node server.js          # 默认 8777
node server.js 8888     # 换端口
```

看到这段就说明好了：

```
======================================================
  植物工坊已启动  http://127.0.0.1:8777
  令牌: 已配置（.ms_token 文件）
======================================================
```

浏览器打开那个地址。

> macOS 第一次双击 `.command` 提示"来自身份不明的开发者"：
> **右键 → 打开 → 弹窗点「打开」**（只需一次）。

---

## 四、怎么用

1. **左边选角色** —— 下拉框列出仓库里全部 54 个（植物 + 僵尸），
   选中后自动把它的精灵表切成 11 帧
2. **点中间任意一格** —— 上方出现这一帧的 prompt，可以随便改
3. **「生成这一帧」** —— 用当前帧当参考图（图生图），保持还是同一株。
   一次 20 秒到 1 分钟
4. **「保存到磁盘」** —— 写进 `anim_demo/assets/plants/<key>/frames/<帧名>.png`
5. **「拼表并写入」** —— 把 11 帧拼成 256×256，覆盖
   `anim_demo/assets/sprites/<key>.png`

右侧实时显示拼好的表和动画效果。

**换任意角色、改任意帧都行。** 想从零做新的：先用原有流程建一个
`anim_demo/assets/plants/<新key>/` 目录，它就会出现在下拉框里。

---

## 五、成果怎么回到主仓库

**文件是直接写进仓库的**，所以：

- 如果用同一台机器 / 同一个仓库 → 直接提交：
  ```bash
  git add anim_demo/assets/plants anim_demo/assets/sprites
  git commit -m "美术更新：<角色>"
  ```
- 如果在别的机器上 → 把这两个目录打回传：
  ```
  anim_demo/assets/plants/      项目：plant.json + frames/
  anim_demo/assets/sprites/     成品精灵表：<key>.png
  ```
  收到后覆盖进来，跑一次校验：
  ```bash
  python scripts/check_sprites.py
  python scripts/check_render.py --shot-dir _work
  ```

新增角色还要补游戏数据 `tdgame/data/plants/<key>.json`（阳光/血量/能力），
然后重新打包 exe。

---

## 六、帧规格（界面已按此约束）

| 项 | 说明 |
|---|---|
| 精灵表 | 256×256，4 列，行帧数 2/4/3/2，共 11 个可用格 |
| 单帧 | 64×64，底部居中 |
| 每张图 | 只能有一个角色 |

---

## 七、常见问题

**页面打不开 / 空白**
→ 服务没起来。看终端窗口有没有报错；端口被占用就换一个：`node server.js 8888`。

**`令牌: 未配置`**
→ `.ms_token` 不在 `anim_demo/` 下，或内容有空格。检查：`cat anim_demo/.ms_token`。

**生成失败 HTTP 401**
→ 令牌不对或过期。

**生成很慢**
→ 模型排队，正常 20 秒~1 分钟。失败会自动重试（遇到过 SSL 断连）。

**改了图但游戏里没变**
→ 点过「拼表并写入」才会覆盖 `assets/sprites/<key>.png`。
   之后还要重新打包 exe（`tools\build_exe.ps1`）。

**想回滚**
→ 一切都写在 git 里：`git checkout -- anim_demo/assets`。

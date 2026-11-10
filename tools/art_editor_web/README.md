# 植物立绘工坊（静态网页版）

给 UI / 立绘设计师用的**单文件工具**：双击 `index.html` 就能用，不装任何东西，不连服务器，图片只在本地处理。

**内置了游戏现有的 51 个角色**（36 株植物 + 15 种僵尸），设计师可以逐个查看、决定哪些需要改，也可以从零新建植物。

---

## 一、给设计师：怎么用

### 1. 选角色 or 新建

- 左上角 **下拉框** 里是现有全部角色，选一个就会载入它当前的 10 帧
- 点 **＋ 新建植物**，填必填项（英文 key / 中文名 / 类型）即可从零开始

> 新建的角色**只需要外形**，游戏数值（阳光、血量、能力）由开发补齐。

### 2. 出图的三种方式

| 方式 | 怎么做 |
|---|---|
| **A. 页面内 AI** | 右上填 API 地址 / 模型 / Key，点「文生图 → 填入 idle_0」 |
| **B. 自己画** | 画好 PNG 直接**拖进**中间的格子 |
| **C. 用你自己的工具** | 复制 prompt 去别处出图，再拖回来 |

支持的接口（OpenAI 兼容）：

- 文生图：`POST /v1/images/generations`
- **图生图：`POST /v1/images/edits`**（用当前帧做参考，保持同一个角色只改姿态）

### 3. 单帧重抽（关键功能）

鼠标悬停到任意格子上，会出现两个按钮：

| 按钮 | 作用 |
|---|---|
| **↻** | **用这一帧自己当参考图，重抽这一帧**（图生图）。这是保证 10 帧看起来是同一株植物的关键 |
| **×** | 清空这一格 |

也可以点 **「↻ 逐帧重抽全部」** 一次跑完 10 帧（慢，按顺序）。

每帧喂给模型的 prompt 会自动带上该行的姿态要求：

| 行 | 姿态提示 |
|---|---|
| idle ×2 | 平静待机，身体端正放松 |
| walk ×4 | 茎叶被微风轻摇（植物不移动） |
| attack ×3 | 出手：前倾、炮口/嘴张开、有张力 |
| hurt ×2 | 受击：后仰、眼睛眯起或闭成弧线 |

### 4. 导出

点 **「导出资源包 .zip」**，得到 `<key>_art_pack.zip`：

```
sheets/<key>.png   精灵表（256×256 / 4列4行 / 每格64）
meta.json          key、中文名、类型、是否新角色、完整 prompt、哪些帧是空的
prompt.txt         提示词
README.txt         说明
```

把 zip 发回给开发即可。

---

## 二、帧规格（页面已按此校验）

| 项 | 要求 |
|---|---|
| 一帧一张图 | 尺寸不限，页面自动缩放并底部居中 |
| **宽高比 0.35 ~ 1.3** | 太瘦长（比如一根竖线）游戏会拒收 |
| **每张图只能有一个角色** | 多角色会拒收 |
| 10 格 | idle×2 / walk×4 / attack×3 / hurt×2 |
| 留空没关系 | 必需帧留空会自动用 `idle_0` 补齐，导出仍合法 |

**植物不移动**，所以 walk 那 4 格可以留空，游戏用静立的轻微呼吸代替。

---

## 三、给我们自己：拿到资源包后

```powershell
# 1) 解压，导入（会顺带跑规格校验）
python tools\art_manager.py import snow_pea 解压目录\sheets\snow_pea.png

# 2) 复核
python scripts\check_sprites.py
python scripts\check_render.py --shot-dir _work

# 3) 若是新角色，补数据 JSON：
#    tdgame/data/plants/<key>.json  或  tdgame/data/enemies/<key>.json
#    （阳光/血量/axes/tags/combat 这些游戏数值）

# 4) 重新打包 exe
powershell -File tools\build_exe.ps1
```

### 重新生成页面（当内置资源更新后）

```powershell
python tools\art_editor_web\build_static.py
```

会把 `tdgame/data/*` 与 `anim_demo/assets/sprites/**` 里的全部角色
转成 WebP 内嵌进 `index.html`，输出到 `tools/art_editor_web/index.html`。

- 模板在 `index.template.html`（改 UI 改这个）
- 构建产物 `index.html` 是给设计师的，约 1.1 MB

---

## 四、技术说明

- **单文件、零依赖、零构建**（对使用者而言）
- 内置资源用 **WebP q=88** 压缩：54 张 PNG 约 2MB → 内嵌后约 1.1MB，便于邮件/IM 传输
- ZIP 打包为手写最小实现（store 无压缩 + 标准 CRC32），不引第三方库
- API Key 存在浏览器 `localStorage`，**不会**写进导出的资源包

### 已验证

- Node `vm.Script` 语法检查通过
- 内嵌 51 个角色全部为合法 WebP（RIFF/WEBP 魔数校验）
- `CRC32("123456789") == 0xCBF43926`（标准向量）
- 页面代码生成的 zip 能被 Python `zipfile` 正确解开，中文与 PNG 字节完整

### 已知限制

- 不支持动画预览播放（只显示合成后的精灵表）
- 图生图依赖对方服务支持 `/images/edits`；不支持时请走"复制 prompt + 手工放图"
- 浏览器直连第三方 API 可能被 CORS 拦，页面会明确提示改用别的方式

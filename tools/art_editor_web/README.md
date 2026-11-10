# 植物立绘工坊（静态网页版）

给 UI / 立绘设计师用的**单文件工具**：双击 `index.html` 就能用，不装任何东西，不连服务器，图片只在本地处理。

**内置游戏现有 51 个角色**（36 株植物 + 15 种僵尸），可以逐个查看、决定改哪些，也可以从零新建。

---

## ⭐ 怎么保存（不依赖任何软件）

**点左侧「导出工作副本（下次双击它继续改）」**，会下载一个新的 HTML 文件（名字带时间戳）。

下次**双击那个新文件**，你改过的所有图都在里面，可以接着改、再导出一次。

- 不需要安装任何东西（不用 node、不用 python、不用开服务器）
- 不依赖浏览器存储，**Safari / 清缓存 / 换电脑都不怕**
- 相当于「另存为新版本」，文件名自带时间，天然有历史备份

> 在 Chrome / Edge 里，改动还会额外自动存到本机浏览器
> （左上角显示「已保存到本机 HH:MM」），但**别依赖它**——
> Safari 双击打开时浏览器会禁用存储。养成「改完就导出工作副本」的习惯最稳。

### 三个导出按钮分别干嘛

| 按钮 | 给谁 | 内容 |
|---|---|---|
| **导出工作副本（.html）** | **你自己留档** | 完整工作台，双击继续改 |
| 导出资源包 .zip | 发回给开发 | 当前这一个角色的精灵表 |
| 导出全部已改（zip） | 发回给开发 | 所有改过的角色的精灵表 + `workspace.json` |

---

## ⚠️ 关于「在页面里直接生成」

**已实测：ModelScope（Qwen-Image）不允许浏览器直连**，从网页发请求会得到
`TypeError: Failed to fetch`——这是服务端的 CORS 策略，不是页面写错，
换任何浏览器都一样。

所以日常生产请走**离线批量**（下面的流程），它不受 CORS 限制、还能一次跑一批。

### 离线批量流程（推荐）

```
设计师                          开发
────────                        ────────
写好每帧 prompt
点「导出生成任务 .zip」  ───────►  python tools/art_batch.py 任务包.zip
                                    （用我们自己的 MODELSCOPE_TOKEN）
点「导入生成结果 .zip」 ◄───────  回传 xxx_results.zip
自动回填到对应帧
```

命令行细节：

```powershell
$env:MODELSCOPE_TOKEN = "ms-xxxx"
python toolsrt_batch.py ballista_jobs.zip            # 全跑
python toolsrt_batch.py ballista_jobs.zip --dry-run  # 只看计划
python toolsrt_batch.py ballista_jobs.zip --only idle_0,attack_1
```

任务包里每个 job 都带这一帧的完整 prompt 和参考图，
所以生成出来还是同一株植物。

### 如果你有代理

「服务商」选 **本地代理**，地址填 `http://127.0.0.1:8787`（或你的中转站），
就能在页面里直接生成、单帧重抽。代理只需把 `/v1/images/generations`
和 `/v1/tasks/{id}` 原样转发到 `https://api-inference.modelscope.cn`，并放开 CORS：
`Access-Control-Allow-Origin: *`。

---

## 一、怎么用

### 1. 选角色 or 新建

- 下拉框按「植物 / 僵尸」分组，选中就载入该角色的 10 帧（**优先载入你改过的版本**，没有才是内置原图）
- 点 **＋ 新建植物**，填必填项（英文 key / 中文名 / 类型）即可从零开始

> 新建的角色**只需要外形**，游戏数值（阳光、血量、能力）由开发补齐。

### 2. 出图的三种方式

| 方式 | 怎么做 |
|---|---|
| **A. 页面内 AI** | 右侧填 API 地址 / 模型 / Key，点「文生图 → 填入 idle_0」 |
| **B. 自己画** | 画好 PNG 直接**拖进**格子 |
| **C. 用你自己的工具** | 复制 prompt 去别处出图，再拖回来 |

支持的接口（OpenAI 兼容）：

- 文生图：`POST /v1/images/generations`
- **图生图：`POST /v1/images/edits`**（用当前帧做参考，保持同一角色只改姿态）

### 3. 单帧编辑（核心）

**点任意一格 = 选中这一帧**，网格上方会出现这一帧的编辑区：

| 元素 | 说明 |
|---|---|
| **这一帧的 prompt** | 可自由编辑。默认 = 总描述 + 该行姿态要求 + 风格约束；你改了就会**随档保存** |
| **↻ 用这段 prompt 重抽这一帧** | 有图时走图生图（以该帧为参考，保证同一株），没图时走文生图 |
| **上传替换…** | 用你自己画的图替换这一帧 |
| **恢复默认 prompt** | 丢掉你为这一帧写的 prompt，回到默认 |
| **清空这一帧** | 移除这一帧的图 |

每帧的 prompt 会自动带上该行的姿态要求：

| 行 | 姿态 |
|---|---|
| idle ×2 | 平静待机，身体端正放松 |
| walk ×4 | 茎叶被微风轻摇（植物不移动） |
| attack ×3 | 出手：前倾、炮口/嘴张开、有张力 |
| hurt ×2 | 受击：后仰、眼睛眯起或闭成弧线 |

### 4. Prompt 都会被保存

这是为了"以后知道这些图是怎么来的"：

- **外观描述**（左栏 ②）：整株植物的自然语言描述，会拼进每一帧
- **风格约束**（左栏 ③）：统一的画风尾巴
- **每帧 prompt**：你在帧编辑区里写的那段

三者都会存进本机存档，并写进导出包的 `meta.json`：

```json
{
  "key": "snow_pea",
  "desc": "……整株描述……",
  "style": "……风格约束……",
  "frame_prompts": { "idle_0": "……", "attack_1": "……" },
  "frames": ["idle_0", "idle_1", "..."],
  "filled_by_idle0": ["hurt_1"]
}
```

「导出工作副本」也会把这些 prompt 一起带进新 HTML，下次打开照样能看到每帧当初是怎么来的。

### 5. 导出

| 按钮 | 产物 |
|---|---|
| **导出资源包 .zip** | 当前这一个角色：`sheets/<key>.png` + `meta.json` + `prompt.txt` + `README.txt` |
| **导出全部已改（zip）** | 所有改过的角色：每个的精灵表 + `workspace.json` + `manifest.json` + `README.txt` |

发给开发即可。

---

## 二、帧规格（页面已按此校验）

| 项 | 要求 |
|---|---|
| 一帧一张图 | 尺寸不限，页面自动缩放并底部居中 |
| **宽高比 0.35 ~ 1.3** | 太瘦长游戏会拒收 |
| **每张图只能有一个角色** | 多角色会拒收 |
| 10 格 | idle×2 / walk×4 / attack×3 / hurt×2 |
| 留空没关系 | 必需帧留空自动用 `idle_0` 补齐，导出仍合法 |

**植物不移动**，walk 那 4 格可以留空。

---

## 三、给我们自己：拿到资源包后

```powershell
# 单个角色
python tools\art_manager.py import snow_pea 解压目录\sheets\snow_pea.png

# 批量（遍历 sheets/ 下的所有 png，按文件名当 key）
Get-ChildItem 解压目录\sheets\*.png | ForEach-Object {
    python tools\art_manager.py import $_.BaseName $_.FullName
}

# 复核
python scripts\check_sprites.py
python scripts\check_render.py --shot-dir _work
```

新角色还要补数据 JSON（阳光/血量/axes/tags/combat），再 `build_exe.ps1` 重新打包。

### 重新生成页面（内置资源更新后）

```powershell
python tools\art_editor_web\build_static.py --pack
```

- 改界面 → 改 `index.template.html`
- 产物：`index.html`（约 2.4 MB）+ `PlantArtForge.zip`（约 1.8 MB，直接发人）

---

## 四、技术说明

- **单文件、零依赖、零构建**（对使用者而言）
- 内置资源用**无损 PNG base64** 内嵌
  - 必须 base64：`file://` 下把本地图绘入 canvas 会污染画布，`getImageData`/`toBlob` 会抛 `SecurityError`，而本工具要合成并导出精灵表
- 持久化用 **IndexedDB**（容量远大于 localStorage，能放多帧原图）
- ZIP 打包为手写最小实现（store 无压缩 + 标准 CRC32）

### 已验证

- Node `vm.Script` 语法检查通过
- 51 个内嵌资源全部为合法 PNG（魔数校验）
- 持久化接线静态检查 13 项全部命中，无 saveNow 递归
- `CRC32("123456789") == 0xCBF43926`（标准向量）
- 页面代码生成的 zip 能被 Python `zipfile` 正确解开，中文与 PNG 字节完整

### 已知限制

- 存档跟随**浏览器**：换浏览器/清缓存会丢，务必用「导出全部」备份
- 不支持动画预览播放（只显示合成后的精灵表）
- 图生图依赖服务支持 `/images/edits`；不支持时走"复制 prompt + 手工放图"
- 浏览器直连第三方 API 可能被 CORS 拦，页面会提示改用别的方式

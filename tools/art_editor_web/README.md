# 植物立绘工坊（静态网页版）

给 UI / 立绘设计师用的**单文件工具**：双击 `index.html` 就能用，不用装任何东西，不连服务器，图片只在自己电脑上处理。

---

## 给设计师的说明

### 怎么开始

1. 双击 `index.html`（推荐 Chrome / Edge）
2. 在左侧填 **英文 key**（如 `snow_pea`）和 **中文名**
3. 写清楚 **外观描述**——这决定画出来长什么样，越具体越好（有没有眼睛、什么颜色、什么形状、拿什么武器）
4. 「风格约束」那段不要删，它保证和游戏里已有的四十多个角色风格统一
5. 点 **复制完整 prompt** 或 **下载 prompt.txt**

### 出图的三种方式（任选）

| 方式 | 怎么做 |
|---|---|
| **A. 用页面里的 AI** | 右侧第 ⑥ 栏填 API 地址、模型名、Key（只存本机浏览器），点「生成立绘」 |
| **B. 你自己画** | 画好 PNG 直接**拖进**中间的 10 个格子 |
| **C. 用你惯用的工具** | 把 prompt.txt 丢给你自己的 AI/画图工具，再把结果拖进来 |

> 页面里的 API 只支持 **OpenAI 兼容**的 `/v1/images/generations`。
> 如果报 CORS 错误，说明该服务不允许浏览器直连——用 B 或 C。

### 帧的规格（页面已按此校验）

| 项 | 说明 |
|---|---|
| 一帧一张图 | 尺寸不限，页面会自动缩放 |
| **宽高比要在 0.35 ~ 1.3 之间** | 太瘦长（比如只有一条竖线）会被游戏拒收 |
| **每张图里只能有一个角色** | 多角色会被拒收 |
| 10 个格子 | 第1行 idle×2 ／ 第2行 walk×4 ／ 第3行 attack×3 ／ 第4行 hurt×2 |
| 留空没关系 | 留空的帧会自动用 `idle_0` 补，导出照样合法 |

**植物不会移动**，所以 walk 那 4 格可以直接留空（游戏用静立的轻微呼吸代替）。

### 导出

点 **「导出资源包 .zip」**，会得到一个 `<key>_art_pack.zip`，里面：

```
sheets/<key>.png    ← 程序要用的精灵表（256×256，4列4行，每格64）
meta.json           ← key / 中文名 / 完整 prompt / 哪些帧是空的
prompt.txt          ← 生成这段立绘用的提示词
README.txt          ← 这份说明
```

把这个 zip 发回给我们即可。

---

## 给我们自己的说明（开发侧）

拿到 zip 后：

```powershell
# 解压后，用素材管理器导入（会自动校验规格）
python tools\art_manager.py import snow_pea 解压目录\sheets\snow_pea.png

# 复核
python scripts\check_sprites.py
python scripts\check_render.py --shot-dir _work

# 如果这个 key 是新的植物/僵尸，还要有对应的数据 JSON：
#   tdgame/data/plants/<key>.json  或  tdgame/data/enemies/<key>.json
```

### 这个页面校验了什么（和 `check_sprites.py` 对齐）

- 尺寸/网格：导出时固定合成 256×256、4 列、行帧数 `[2,4,3,2]`
- 底部居中锚点：`drawCell()` 里按 `FRAME - 4 - h` 贴底，避免切帧跳变
- 单角色 / 宽高比：页面给出**警示**（红字），但不会阻止导出
  —— 最终以 `check_sprites.py` 为准

### 已知限制

- 不支持 image-to-image（用参考图改姿态）。要逐帧保持同一角色，建议：先出立绘 → 「用立绘填充全部空槽」→ 再逐格替换有变化的帧
- 不支持动画预览播放（只显示合成后的精灵表）
- API Key 存在浏览器 localStorage，导出的 zip 里**不含** Key

### 技术说明

- 单文件、零依赖、零构建
- ZIP 打包是手写的最小实现（store 无压缩），CRC32 用标准多项式
- 已用 Node 校验 JS 语法、CRC32 标准向量、以及「导出的 zip 能被 Python `zipfile` 正确解开」

# 精灵动画框架与贴图替换说明

演示「单张静态 PNG 贴图」如何通过**序列帧 + 程序化变换**做出灵动效果。所有素材由代码生成占位图，
不依赖任何外部资源；拿到真图后同名替换即可，无需改代码。

## 运行
```
D:\ProgramData\anaconda3\python.exe sprite_animation_demo.py
```
按键：←/→ 移动（走路切帧 + 朝向翻转）｜空格 攻击（squash & stretch）｜H 受击（白色闪白 + 后仰）
｜I 回待机｜**R 运行中热重载贴图**｜Esc 退出。

## 文件
- `animation.py`：可复用框架。`generate_placeholder_sheet`（缺图时程序化生成）、
  `SpriteSheet`（加载/裁帧/染白缓存）、`AnimatedSprite`（状态机 + 切帧 + 弹性 + 闪白 + 翻转）。
- `sprite_animation_demo.py`：交互演示。
- `capture_anim.py`：离屏（SDL dummy）自动断言 + 逐状态出图。
- `gen_image_qwen.py`：魔搭千问文生图/图像编辑客户端（token 走环境变量，异步轮询封装，支持 `--ref` 参考图）。
- `gen_frames_qwen.py`：以标准立绘为参考，批量生成 idle/walk/attack/hurt 共 10 个**不同姿态**帧（断点续跑、失败不中断）。
- `build_spritesheet.py`：输入单图则全格复制（单立绘驱动）；输入**帧目录**则按 `idle_0…/walk_0…` 逐格去背拼表（多帧序列）。
- `gen_plant.py`：配置化**原创植物角色**生成器；每个植物定义外观描述 + 特色攻击帧，`--base` 出立绘、`--frames` 出 10 动作帧。
- `verify_plant.py`：任意精灵表的离屏切帧/动效断言（`--sheet 表 --tag 名`），植物与通用角色共用。
- `plant_editor.py`：**植物工坊图形编辑器**（Tkinter，标准库零额外安装），五步向导完成描述→立绘三选一→动作帧→子弹贴图→拼表预览。
- `assets/frames_raw/`：史莱姆逐帧生成的原始姿态图（白底 760×1280）。
- `assets/plants/<角色>/`：`plant.json` 配置 + `base.png` 立绘 + `frames/` 动作帧 + `candidates/` 立绘候选 + `frame_history/` 重 roll 备份；`assets/sprites/bamboo.png` 为拼好的竹笋刀手表。
- `.ms_token`：本地保存的 ModelScope token（界面可写，已在 `.gitignore`，切勿提交）。
- `assets/sprites/blob.png`：当前 demo 实际加载的**多帧 AI 精灵表**；`blob_qwen.png` 同内容备份；删除后框架会自动回退生成代码占位表。

## 动效是怎么叠出来的（三层）
1. **序列帧**：一张精灵表含多格，按毫秒节拍切换 `subsurface` 裁剪出的帧。
2. **程序化变换**：对当前帧 `smoothscale` 做挤压拉伸（弹性系数向目标指数回弹）、`flip` 转向、
   以**底部中心为锚点**缩放避免悬空；呼吸/脚步用正弦，攻击按帧给蓄力→突刺→回弹目标。
3. **特效层**：受击用 `BLEND_RGB_ADD` 生成保留轮廓的白色剪影做闪白；脚下独立椭圆阴影随形变变化。

## 用真 PNG 替换的约定
精灵表固定网格（见 `animation.py` 顶部 `FRAME` / `ANIM_DEF`）：
- 整张 **256×256，4 列 × 4 行，每格 64×64**，PNG 带透明背景；
- 行序与帧数：第 0 行 idle（2 帧）、第 1 行 walk（4 帧）、第 2 行 attack（3 帧）、第 3 行 hurt（2 帧），用不到的格留空透明；
- 角色在每格内**底部居中**（锚点约 x=32, y=58），保证各帧切换不跳变；
- 节奏在 `ANIM_DEF` 里调（每帧毫秒、是否循环）。

替换步骤：用同网格的 PNG 覆盖 `assets/sprites/blob.png` → 游戏运行中按 **R**（或重启）即生效。
若要改格尺寸、行数或帧节奏，同步修改 `FRAME` 和 `ANIM_DEF` 即可；多个角色就建多张表、
多个 `AnimatedSprite` 实例，皮肤包则按文件夹分组后切换加载路径。

## AI 资源管线：千问生图/编辑 → 自动拼表 → 框架动效（已跑通）
有两种成品档位。

### A. 多帧序列（推荐，当前 blob.png 即此方案，每格姿态真的不同）
```powershell
$env:MODELSCOPE_TOKEN = "你的token"
# 1) 先生成一张标准立绘作为“角色基准”（白底、居中、无阴影文字）
D:\ProgramData\anaconda3\python.exe gen_image_qwen.py --out ..\logs\qwen_test.png `
  --prompt "2D游戏精灵立绘，一只原创绿色史莱姆怪物，卡通粗描边，正面，全身居中，纯白色干净背景，无阴影，无文字"
# 2) 以该立绘为参考，图像编辑批量产出 10 个不同姿态帧到 assets/frames_raw（已存在自动跳过）
D:\ProgramData\anaconda3\python.exe gen_frames_qwen.py
# 3) 逐帧去背/底部居中/拼表（输入是目录即多帧模式，缺帧用 idle_0 兜底）
D:\ProgramData\anaconda3\python.exe build_spritesheet.py assets\frames_raw assets\sprites\blob.png
```
demo 里按 **R**（或重启）即生效。单帧不满意时，删掉 `frames_raw` 里对应 `<名>.png` 重跑第 2 步即可只补那一帧。

### B. 单立绘驱动（最快，零多帧成本）
只生成一张立绘，所有格放同一姿态，呼吸/挤压/闪白/朝向全交给 `animation.py` 程序化变换：
```powershell
D:\ProgramData\anaconda3\python.exe build_spritesheet.py ..\logs\qwen_test.png assets\sprites\blob.png
```

实测要点与坑：
- 接口**不要传 `size` 字段**，否则提交返回 `submit failed 500`；默认输出约 760×1280 竖图，拼表自动裁透明边再等比缩放。
- 图像编辑的本地参考图用 **base64 data-uri**（`data:image/png;base64,...`）放入 `image_url`，已验证可用；每帧约 30–80 秒。
- **抑制逐帧漂移的关键**：所有帧都以同一张标准立绘为参考（星型，不用上一帧链式），并在 prompt 里强约束
  “保持相同颜色/描边/眼睛/高光、光滑无四肢、**绝不长出手脚翅膀角等新器官**、纯白底、固定平视、仅改身体形状与表情”。
- 去背用“到白色距离”双阈值羽化（`LO/HI`），白描边和浅高光都能保住；非纯白背景再调阈值。
- 多帧序列负责“姿态切换”，程序化弹性负责“帧内回弹/呼吸/闪白”，两者叠加最灵动。
- 合规：AI 生成内容确认平台条款，角色与命名保持原创，不使用原版游戏资产；token 勿写入代码，用完建议轮换。

## 原创植物角色管线（竹笋刀手 / 牵牛花射手 …）
植物塔固定在格子上、不移动，所以复用同一张 4×4 网格时，第 1 行 walk 槽改作“茎叶/花冠被微风轻摇”的循环，
attack 三帧按植物特色定制（竹笋=蓄力/劈砍/收刀，牵牛花=蓄能/后坐吐种/回位）。角色都在 `gen_plant.py` 的
`PLANTS` 字典里配置（外观 `base_desc` + `attack` 帧文案），新增植物只需加一项。

```powershell
$env:MODELSCOPE_TOKEN = "你的token"
# 1) 先出标准立绘定风格（建议先人工确认再铺帧，避免十几张白跑）
D:\ProgramData\anaconda3\python.exe gen_plant.py --plant bamboo --base
# 2) 以立绘为参考批量出 10 个动作帧（断点续跑；删掉某帧重跑即只补该帧）
D:\ProgramData\anaconda3\python.exe gen_plant.py --plant bamboo --frames
# 3) 目录模式拼表（多帧全局统一缩放）
D:\ProgramData\anaconda3\python.exe build_spritesheet.py assets/plants/bamboo/frames assets/sprites/bamboo.png
# 4) 离屏断言 + 真实窗口预览（--sheet 可在任意角色表间切换，默认仍是 blob.png）
D:\ProgramData\anaconda3\python.exe verify_plant.py --sheet assets/sprites/bamboo.png --tag bamboo
D:\ProgramData\anaconda3\python.exe sprite_animation_demo.py --sheet assets/sprites/bamboo.png
```

多帧拼表的两个关键工程点（`build_spritesheet.py` 目录模式）：
- **全局统一缩放**：先对所有帧去背裁剪，取“让最宽/最高帧也能进格”的同一个缩放系数，所有帧共用，并统一水平居中、
  底边锚点对齐。避免“每帧各自按 bbox 缩放”导致的身体忽大忽小、攻击帧整体缩小的跳变。
- **底部锚点一致 + 禁止茎柄根茬**：prompt 的 `TAIL` 约束各帧底部形态与立绘一致，防止某帧多出小柄破坏着地点对齐。
- 武器在**攻击瞬间完全展开**（如竹笋刀刃劈砍时更修长）、回收帧恢复立绘尺寸，既强化出手张力又无需重画立绘。

## 植物工坊图形编辑器（plant_editor.py）
不写命令行也能定制植物的 Tkinter 桌面向导，底层复用上面同一套千问客户端与拼表逻辑：
```
D:\ProgramData\anaconda3\python.exe plant_editor.py
```
五步流程：
1. **描述与 Prompt**：填中文名、外观描述，工坊自动拼接统一风格模板（`TAIL`），右侧只读实时预览完整 prompt。
2. **立绘三选一**：后台线程**并发连抽 3 张**（界面不卡死），三张独立成功/失败展示，点“选它”定稿为 `base.png` 并同步 `idle_0`，
   **定稿后自动跳转到动作帧步骤**；都不满意就返回上一步改词重抽。候选留存在 `candidates/`。
3. **动作帧（先批量、后精修）**：`idle_0` 锁定为立绘。进入后先用顶部“一键生成全部动作帧（n）”**串行批量生成全部缺失帧**，
   每张约 30–80 秒、网格实时显示“生成中 x/n”，已存在的帧跳过（断点续跑），单张失败会被隔离、不影响其它帧，结束后可再点
   “补齐缺失帧”单独补；批量完成后，点任一帧可在右侧改写该帧 prompt 后**单张重 roll**，重 roll 前旧版自动备份到
   `frame_history/`，可“回退上一版”。同一时间只允许一个生成任务，避免并发抽卡。
4. **子弹/飞行道具**：勾选启用、选类型（种子弹/剑气刀光/飞叶/延伸器官）、写描述（留空则按类型默认形态），
   只读框实时预览自动拼接的出图 prompt；点“生成 / 重 roll 子弹贴图”会以定稿立绘为参考出图，工坊随即**自动去背、裁剪并把
   最长边压到 48px**，产出独立透明底 `projectile.png`（**不占角色 4×4 精灵表**），原始白底存 `projectile_raw.png`，
   旧定稿备份到 `projectile_history/` 可“回退上一版”；定稿相对路径写入 `plant.json` 的 `projectile.file`，运行时据此加载。
5. **拼表预览**：一键去背 + 全局统一缩放拼表，缩略图查看，并可直接拉起 `sprite_animation_demo.py --sheet` 预览。

数据格式与游戏集成（编辑器与运行时解耦）：
- 每个植物一个目录 `assets/plants/<key>/`，配置集中在 `plant.json`；CLI（`gen_plant.py`）与工坊共用该格式，
  旧目录首次在工坊打开会自动补建 `plant.json`。
- **游戏运行时只读 `plant.json` 和定稿 PNG，不调用千问、不依赖编辑器、可离线**；正式塔防只需扫描该目录注册自定义植物，
  再用 `AnimatedSprite` 加载即可，这就是工坊资产进入玩法的接入点。
- Token 优先读环境变量 `MODELSCOPE_TOKEN/MS_TOKEN`，也可在界面右上角填写并保存到本地 `.ms_token`（已 gitignore）。

## 移植到正式塔防
把 `animation.py` 拷入项目，让敌人/塔持有 `AnimatedSprite`：移动时播 walk、攻击瞬间调 `attack()`、
中弹调 `hurt()`；现有粒子/光晕代码可继续作为第三层特效叠加。`SpriteSheet` 已是“外部图优先、
缺图回退占位图”的安全结构，素材没做全也不会让游戏崩溃。

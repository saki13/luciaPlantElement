# PVZ 逆向 → 自研塔防：练习交付说明

在合法拥有的《植物大战僵尸》GOTY 中文版上做个人学习/二次开发练习。REA 因 Windows 原生安全自检
（fail-closed 门控）在本机不可用，改用 **Ghidra 12 headless + 自研脚本**完成同等逆向，再用 Python
标准库重写了一个**不依赖任何原版素材、可直接运行**的原创塔防原型。

## 一、怎么运行游戏
统一用 Anaconda 的 Python（系统便携 Python 的 tkinter 缺 init.tcl，无法建窗）。

**推荐：pygame 精美版**（渐变/阴影/高光/发光/粒子，依赖已随项目放在 `./libs`，无需再安装）：
```
D:\ProgramData\anaconda3\python.exe tower_defense_pygame.py
```
备用：tkinter 极简版（仅标准库、无第三方依赖，画面较朴素）：
```
D:\ProgramData\anaconda3\python.exe tower_defense_prototype.py
```
- 操作：鼠标点顶部按钮选防御塔 → 点格子放置；点金色能量块收集；**空格暂停、R 重开**。
- 目标：守住 8 波进攻即胜利；敌人越过左侧红线扣基地生命，生命归零失败。
- 两版玩法与数值完全一致，仅表现层不同；所有图形均为代码原创绘制、无任何原版素材。
- 说明：Anaconda 系统目录只读，pygame 用 `pip install --target=./libs pygame` 装在项目内，
  程序启动自动把 `./libs` 加入 `sys.path`，拷贝整个项目到同平台机器即可运行。

## 二、三件活与对应产物
### 1. 解包 main.pak（数据格式与资源结构）
- 全文件单字节 XOR 0xF7 混淆；解密后头部魔数 `0xBAC04AC0`，索引含 3250 个条目。
- 7 个顶层目录：compiled/data/images/particles/properties/reanim/sounds；
  PNG 2452、compiled 251、OGG 167、reanim 146 等。
- 结论：表现层（美术/动画/粒子/音频/本地化）数据驱动；**植物/僵尸核心数值硬编码在 exe**。
- 产物：`scripts/unpack_pak.py`、`logs/pak-format-notes.md`、`logs/pak-filelist.txt`、`unpacked/`（3250 文件）。

### 2. 定位并反编译三大核心函数
- 用字符串交叉引用（`ADVICE_CLICKED_ON_SUN`、`NOT_ENOUGH_SUN`、`MAX_ZOMBIES_IN_WAVE` 等）定位，
  再用 DecompInterface 反编译 9 个代表函数。
- 波次：预计算类型数组 + 运行时按毫秒队列放出，用"点数预算随波次递增 × 关卡系数"控制。
- 攻击：塔产生弹道 → 移动/矩形碰撞 → 查伤害表结算（含减速）。
- 经济：单一全局资源计数器 + 可点击掉落物，消费走"余额 ≥ 成本"门控。
- 产物：`scripts/LocateXref.java`、`scripts/DecompileFunctions.java`、
  `logs/xref-map.txt`、`logs/decompiled.txt`、`logs/core-functions-analysis.md`。

### 3. Python 原创塔防原型（tkinter 版 + pygame 精美版）
- 严格复刻上述三大机制：波次点数预算、弹道数据表、单一资源计数器 + 天降能量块。
- 数据驱动：塔/弹道/敌人数值都在文件顶部配置表，调平衡直接改表。
- pygame 版表现层：渐变草坪、塔底座/炮管/高光/阴影、敌人眼睛与护甲、发光弹道、
  呼吸光晕能量块、命中/击杀粒子、半透明 UI 与圆角按钮、冷却环、后坐力。
- 验证：`scripts/smoke_test_pygame.py`（pygame，SDL dummy 离屏）与 `scripts/smoke_test.py`（tkinter）
  均 headless 跑通 8 波并以胜利结算；`scripts/capture_screens.py` 直接从 surface 出图核对美术；
  真实窗口经 PrintWindow 截图确认。过程中修复了结束遮罩被同帧 render 覆盖、pygame SysFont 枚举崩溃两处问题。

## 三、合规边界
- 逆向自己合法拥有的游戏用于个人学习可以；**不要分发原版 exe 或提取出的美术/音频**。
- 自研塔防需重写逻辑、使用原创或开源素材，不照搬 PVZ 的角色形象与名称（本原型图形与命名均为原创）。

## 四、目录结构
```
tower_defense_pygame.py     推荐：pygame 精美版主程序（可运行）
tower_defense_prototype.py  备用：tkinter 极简版主程序（可运行）
libs/                       项目自带依赖（pygame，--target 安装，可随项目拷贝）
scripts/  unpack_pak.py、LocateXref.java、DecompileFunctions.java、
          smoke_test.py、smoke_test_pygame.py、capture_screens.py、run-*.ps1
logs/     格式/函数分析文档、伪代码、交叉引用、文件清单、截图（pygame-*.png 为精美版画面）
unpacked/  main.pak 解包出的 3250 个文件
```

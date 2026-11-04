# -*- coding: utf-8 -*-
"""tdgame：数据驱动的原创塔防战斗框架。

- 纯标准库实现 headless 数值引擎（engine/），不依赖 pygame，可批量回归。
- data/ 为植物/敌人/counter_map/关卡 JSON，单一事实来源。
- balance.py 为确定性伤害管线与品阶/代币/成本公式，headless 与真机共用。
- app_pygame.py 为薄渲染壳（后续里程碑接入精灵表）。
"""
__version__ = "0.2.0"

# -*- coding: utf-8 -*-
"""植物工坊（最小可用版）：玩家在这里设计自己的植物。

设计要点：
- 逻辑（WorkshopState）与渲染分离，逻辑可脱离 pygame 单测。
- 产出直接交给 `customizer.build_plant_definition`，与手工 JSON 同结构，
  所以造出来的植物能立刻进卡池、进战斗。
- 定价口径沿用 `tdgame/scenarios/customizer.py`（旧五轴+标签代币），
  档位点体系（design_slots）待后续替换时再统一。
"""
from __future__ import annotations

from pathlib import Path

from dataclasses import dataclass, field
from typing import Optional
from typing import Dict, List, Tuple

from .scenarios import customizer
from .scenarios.customizer import PHASE_RULES, BuildError

ROOT = Path(__file__).resolve().parent.parent
ANIM = ROOT / "anim_demo"
SPRITES = ANIM / "assets" / "sprites"

# 立绘风格尾巴：和美术管线保持一致
STYLE_TAIL = ("，Q版圆润卡通，粗深色描边，明快平涂，**一定要有一双又大又亮的卡通眼睛**"
              "（黑色大眼珠+白色高光），表情生动，正面平视，全身居中，"
              "站在画面底部中央，纯白色干净背景，无阴影，无文字，无边框")

AXES = ("fire", "area", "pierce", "durability", "control")
AXIS_CN = {"fire": "火力", "area": "打击面", "pierce": "破甲",
           "durability": "坦度", "control": "控制"}
ROLES = ("ranged", "melee")
ROLE_CN = {"ranged": "远程", "melee": "近战"}
TAGS = ("shield_break", "armor_pierce")
TAG_CN = {"shield_break": "破盾", "armor_pierce": "穿甲"}

MAX_LEVEL = 5


@dataclass
class WorkshopState:
    """工坊的纯逻辑状态：可无限次调整，直到确认建造。"""
    phase: str = "P2"
    role: str = "ranged"
    levels: Dict[str, int] = field(default_factory=lambda: {a: 0 for a in AXES})
    tags: List[str] = field(default_factory=list)
    tokens: int = 400
    name: str = "自定义植物"

    # ---------------------------------------------------------------- 调整
    def bump(self, axis: str, delta: int) -> None:
        if axis not in self.levels:
            return
        cap = PHASE_RULES[self.phase]["max_axis"]
        self.levels[axis] = max(0, min(cap, self.levels[axis] + delta))

    def toggle_tag(self, tag: str) -> None:
        if tag not in TAGS:
            return
        if tag in self.tags:
            self.tags.remove(tag)
        elif tag in PHASE_RULES[self.phase]["tags"]:
            self.tags.append(tag)

    def cycle_role(self) -> None:
        i = ROLES.index(self.role)
        self.role = ROLES[(i + 1) % len(ROLES)]

    # ---------------------------------------------------------------- 查询
    @property
    def cost(self) -> int:
        return int(customizer.quote_tokens(self.role, self.levels, self.tags)["total"])

    @property
    def affordable(self) -> bool:
        return self.cost <= self.tokens

    def tag_available(self, tag: str) -> bool:
        return tag in PHASE_RULES[self.phase]["tags"]

    def summary(self) -> Tuple[int, str]:
        """返回 (代币, 提示)。提示为空表示可以建造。"""
        ok, errs, quote = customizer.validate_build(
            self.role, self.levels, self.tags, self.phase, self.tokens)
        cost = int(quote.get("total", self.cost)) if quote else self.cost
        return cost, "" if ok else "；".join(errs)

    @property
    def can_build(self) -> bool:
        return self.summary()[1] == ""

    # ---------------------------------------------------------------- 产出
    # ---------------------------------------------------------------- 外观
    def plant_key(self) -> str:
        """与 build() 用同一套 key 规则，保证图和植物对得上。"""
        return "custom_" + (self.name.strip().replace(" ", "_")[:16] or "plant")

    def appearance_prompt(self) -> str:
        """按当前能力实时推导外观描述（改一项能力，描述跟着变）。"""
        return customizer.describe_appearance(
            self.name or "自定义植物", self.role, self.levels, self.tags)

    def full_prompt(self) -> str:
        """喂给文生图模型的完整 prompt。"""
        return self.appearance_prompt() + STYLE_TAIL

    def sprite_path(self) -> Path:
        return SPRITES / f"{self.plant_key()}.png"

    def has_sprite(self) -> bool:
        return self.sprite_path().exists()

    def build(self, save: bool = False) -> dict:
        """产出一张可被 loader 注册的植物定义；save=True 时直接写进 data/plants。"""
        ok, why = self.summary()
        if not ok:
            raise BuildError(why)
        key = "custom_" + (self.name.strip().replace(" ", "_")[:16] or "plant")
        clean = customizer._clean_axes(self.role, self.levels)
        d = customizer.build_plant_definition(
            key, self.name, self.role, clean, tuple(self.tags),
            self.phase, self.tokens)
        # 补齐免费底盘下限，否则 loader 会拒收（durability<1 / area<2）
        from . import balance as _bal
        _free = _bal.free_chassis_axes(self.role)
        d["axes"] = {a: max(int(d["axes"].get(a, 0)), int(_free.get(a, 0)))
                     for a in d["axes"]}
        d["_user_built"] = True
        if save:
            import json
            from pathlib import Path as _P
            out = _P(__file__).resolve().parent / "data" / "plants" / f"{key}.json"
            out.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
        return d


def render_state(state: WorkshopState) -> str:
    """把工坊状态渲染成文本（供 --smoke 自检与截图用）。"""
    lines = [f"【工坊】阶段 {state.phase}  角色 {ROLE_CN[state.role]}  代币 {state.tokens}"]
    lines.append("─" * 46)
    for a in AXES:
        bar = "■" * state.levels[a] + "□" * (MAX_LEVEL - state.levels[a])
        lines.append(f"  {AXIS_CN[a]:<4} {bar}  {state.levels[a]}/{MAX_LEVEL}")
    lines.append("─" * 46)
    for t in TAGS:
        mark = "√" if t in state.tags else ("×" if state.tag_available(t) else "-")
        lines.append(f"  [{mark}] {TAG_CN[t]}（{t}）")
    cost, why = state.summary()
    lines.append("─" * 46)
    lines.append(f"  消耗代币 {cost} / {state.tokens}")
    lines.append(f"  状态：{why if why else '可以建造'}")
    return "\n".join(lines)


class ArtGenerator:
    """后台生图：跑 gen_image_qwen.py -> build_spritesheet.py，UI 轮询状态。

    线程里只做 subprocess 调用，不碰 pygame，避免跨线程渲染问题。
    """

    IDLE, RUNNING, OK, FAIL = "idle", "running", "ok", "fail"

    def __init__(self, state: WorkshopState):
        self.state = state
        self.status = self.IDLE
        self.message = ""
        self._thread = None

    # ---------------------------------------------------------------- 内部
    @staticmethod
    def _token() -> str:
        import os
        t = os.environ.get("MODELSCOPE_TOKEN") or os.environ.get("MS_TOKEN")
        if t:
            return t.strip()
        f = ANIM / ".ms_token"
        if f.exists():
            return f.read_text(encoding="utf-8").strip()
        return ""

    def _run(self) -> None:
        import subprocess
        import sys
        import os
        try:
            token = self._token()
            if not token:
                self.status, self.message = self.FAIL, "没有 token（设置 MODELSCOPE_TOKEN 或 anim_demo/.ms_token）"
                return
            key = self.state.plant_key()
            raw = ROOT / "_work" / "art_gen" / f"{key}.png"
            raw.parent.mkdir(parents=True, exist_ok=True)
            env = dict(os.environ, MODELSCOPE_TOKEN=token, PYTHONIOENCODING="utf-8")
            self.message = "正在出立绘…"
            r = subprocess.run(
                [sys.executable, str(ANIM / "gen_image_qwen.py"),
                 "--out", str(raw), "--prompt", self.state.full_prompt()],
                cwd=str(ANIM), env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace")
            if r.returncode != 0 or not raw.exists():
                self.status, self.message = self.FAIL, f"出图失败：{(r.stderr or r.stdout)[-120:]}"
                return
            self.message = "正在拼表…"
            out = self.state.sprite_path()
            r = subprocess.run(
                [sys.executable, str(ANIM / "build_spritesheet.py"), str(raw), str(out)],
                cwd=str(ANIM), env=env, capture_output=True, text=True,
                encoding="utf-8", errors="replace")
            if r.returncode != 0:
                self.status, self.message = self.FAIL, f"拼表失败：{(r.stderr or r.stdout)[-120:]}"
                return
            self.status, self.message = self.OK, "外观已生成"
        except Exception as exc:                      # noqa: BLE001
            self.status, self.message = self.FAIL, f"{exc.__class__.__name__}: {exc}"

    # ---------------------------------------------------------------- 对外
    def start(self) -> bool:
        if self.status == self.RUNNING:
            return False
        import threading
        self.status, self.message = self.RUNNING, "排队中…"
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return True

    @property
    def busy(self) -> bool:
        return self.status == self.RUNNING

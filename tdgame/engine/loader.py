# -*- coding: utf-8 -*-
"""数据加载与校验：植物/敌人/counter_map JSON -> 运行时注册表。

- 重算 power/tier 并与声明值核对；自制植物缺省 recharge 时按品阶系统派生（5s 硬下限）。
- 校验设计代币、阳光、字段范围，越界配装写入 errors，拒绝进入注册表。
- 可扫描植物工坊资产目录（含战斗字段才注册为可参战单位）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .. import balance
from .. import config as C

REQUIRED_PLANT_FIELDS = ("key", "cn", "role", "axes", "sun", "hp")
REQUIRED_ENEMY_FIELDS = ("key", "cn", "hp_body", "speed", "bite_dps", "budget")


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def derive_plant(defn: Dict[str, Any]) -> Dict[str, Any]:
    """补齐/校验派生字段：power、tier、sun、recharge。"""
    out = dict(defn)
    tags = list(out.get("tags", []))
    generic_tag_count = len([t for t in tags if t in C.COMBAT_TAGS])
    power = balance.power_score(out["axes"], generic_tag_count, tags)
    tier = balance.tier_of(power)
    out["_power"] = power
    out["_tier"] = tier
    # 内置卡可显式声明 tier（锚定原版价位）；自制株（无 tier）以公式计算为准
    if "tier" not in out:
        out["tier"] = tier
    elif out["tier"] != tier:
        out["_tier_mismatch"] = {"declared": out["tier"], "computed": tier}
    if "recharge" not in out:
        out["recharge"] = balance.derive_recharge(out["tier"], tags)
    out["recharge"] = max(C.RECHARGE_FLOOR, float(out["recharge"]))
    return out


def validate_plant(defn: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    for f in REQUIRED_PLANT_FIELDS:
        if f not in defn:
            errs.append(f"{defn.get('key','?')}: missing field {f}")
    if errs:
        return errs
    key = defn["key"]
    for ax, lv in defn["axes"].items():
        if ax not in balance.AXES:
            errs.append(f"{key}: unknown axis {ax}")
        elif not (0 <= int(lv) <= C.AXIS_LEVELS):
            errs.append(f"{key}: axis {ax} out of 0..5 -> {lv}")
    # 所有植物至少有 100HP=坦度1；打击面起步档仅近战/远程战斗职业强制
    if int(defn["axes"].get("durability", 0)) < 1:
        errs.append(f"{key}: durability below free chassis floor 1")
    if defn.get("role") in ("ranged", "melee"):
        area_floor = balance.free_chassis_axes(defn["role"])["area"]
        if int(defn["axes"].get("area", 0)) < area_floor:
            errs.append(f"{key}: area below free chassis floor {area_floor}")
    derived = derive_plant(defn)
    if derived["recharge"] < C.RECHARGE_FLOOR:
        errs.append(f"{key}: recharge below floor")
    if not (0 < int(defn["sun"]) <= 1000):
        errs.append(f"{key}: sun out of sane range")
    return errs


def validate_enemy(defn: Dict[str, Any]) -> List[str]:
    errs: List[str] = []
    for f in REQUIRED_ENEMY_FIELDS:
        if f not in defn:
            errs.append(f"{defn.get('key','?')}: missing field {f}")
    if errs:
        return errs
    red = defn.get("armor", {}).get("reduction", 0)
    if not (0 <= float(red) < 1):
        errs.append(f"{defn['key']}: armor reduction must in [0,1)")
    for f in ("slow_resist",):
        if f in defn and not (0 <= float(defn[f]) <= 1):
            errs.append(f"{defn['key']}: {f} out of 0..1")
    return errs


class Registry:
    def __init__(self) -> None:
        self.plants: Dict[str, Dict[str, Any]] = {}
        self.enemies: Dict[str, Dict[str, Any]] = {}
        self.counter_map: Dict[str, Any] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_plant(self, defn: Dict[str, Any], source: str = "") -> None:
        errs = validate_plant(defn)
        if errs:
            self.errors.extend(errs)
            return
        d = derive_plant(defn)
        if d["tier"] != d.get("tier") and d.get("tier") is not None:
            self.warnings.append(f"{d['key']}: declared tier {d.get('tier')} != computed {d['tier']}")
        d["_source"] = source
        self.plants[d["key"]] = d

    def add_enemy(self, defn: Dict[str, Any], source: str = "") -> None:
        errs = validate_enemy(defn)
        if errs:
            self.errors.extend(errs)
            return
        defn["_nominal_hp"] = balance.nominal_hp(defn)
        defn["_source"] = source
        self.enemies[defn["key"]] = defn


def load_registry(data_dir: str | Path, custom_plant_dirs: Optional[List[str | Path]] = None) -> Registry:
    data_dir = Path(data_dir)
    reg = Registry()
    for pj in sorted((data_dir / "plants").glob("*.json")):
        reg.add_plant(_read_json(pj), source=str(pj))
    for ej in sorted((data_dir / "enemies").glob("*.json")):
        reg.add_enemy(_read_json(ej), source=str(ej))
    cm = data_dir / "counter_map.json"
    if cm.exists():
        reg.counter_map = _read_json(cm)
    for cdir in (custom_plant_dirs or []):
        cdir = Path(cdir)
        if not cdir.exists():
            reg.warnings.append(f"custom plant dir not found: {cdir}")
            continue
        for pj in sorted(cdir.glob("*/plant.json")):
            raw = _read_json(pj)
            if "axes" in raw and "combat" in raw:
                reg.add_plant(raw, source=str(pj))
            else:
                reg.warnings.append(f"skip art-only plant (no combat stats): {pj}")
    return reg

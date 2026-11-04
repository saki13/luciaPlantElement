# -*- coding: utf-8 -*-
"""生成 `balance.resolve_hit` 的黄金用例，供 Godot 侧 GDScript 实现做一致性门禁。

思路：Python 实现是唯一事实源（oracle）。这里把「敌人初始状态 + 逐次伤害序列」
全喂给 Python 算一遍，把每一步的明细和结算后的血量一起写进 JSON；GDScript 侧
只需复现同样的输入，逐字段比对输出，任何偏差都判失败。

用法：
    python scripts/gen_golden_hits.py --out _work/golden_resolve_hit.json
    python scripts/gen_golden_hits.py            # 默认写 godot/tests/ 下
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tdgame import balance  # noqa: E402
from tdgame import config as C  # noqa: E402
from tdgame.engine.loader import load_registry  # noqa: E402

DATA = ROOT / "tdgame" / "data"
FORMAT = "pvz-golden/resolve_hit/1"


def runtime_enemy(defn: Dict[str, Any]) -> Dict[str, Any]:
    """JSON 定义 -> resolve_hit 认识的运行时字段名。"""
    armor = defn.get("armor") or {}
    return {
        "hp_body": float(defn.get("hp_body", 0) or 0),
        "armor_hp": float(armor.get("hp", 0) or 0),
        "armor_reduction": float(armor.get("reduction", 0) or 0),
        "block_flat": float(defn.get("block_flat", 0) or 0),
    }


def run_case(case_id: str, enemy: Dict[str, Any], hits: List[List[Any]]) -> Dict[str, Any]:
    state = dict(enemy)
    expected = []
    for dmg, tags, ap in hits:
        detail = balance.resolve_hit(state, float(dmg), list(tags), ap)
        expected.append({
            "raw": round(float(detail["raw"]), 6),
            "after_block": float(detail["after_block"]),
            "shield_broke": bool(detail["shield_broke"]),
            "blocked_fully": bool(detail["blocked_fully"]),
            "armor_absorbed": float(detail["armor_absorbed"]),
            "body_damage": float(detail["body_damage"]),
            "killed": bool(detail["killed"]),
            "hp_body": float(state["hp_body"]),
            "armor_hp": float(state["armor_hp"]),
        })
    return {"id": case_id, "enemy": dict(enemy), "hits": hits, "expected": expected}


DAMAGES = [0.0, -5.0, 1.0, 5.0, 12.5, 20.0, 20.0001, 33.3333,
           50.0, 80.0, 100.0, 150.0, 250.0, 400.0, 800.0, 2600.0, 5000.0]
TAG_SETS = [[], ["shield_break"], ["armor_pierce"], ["shield_break", "armor_pierce"]]
AP_SWEEP = [None, 1.0, 1.5, 2.0, 3.0]


def build_cases(reg) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    enemies = {k: runtime_enemy(d) for k, d in reg.enemies.items()}

    # ---- A. 真实敌人 × 单次伤害 × 主要标签组合
    for ekey in sorted(enemies):
        base = enemies[ekey]
        for dmg in DAMAGES:
            for tags in TAG_SETS:
                cid = f"A/{ekey}/dmg={dmg}/tags={','.join(tags) or '-'}"
                cases.append(run_case(cid, base, [[dmg, tags, None]]))

    # ---- B. 显式 ap_mult 覆盖（穿甲倍率只作用甲段，重点考察）
    for ekey in ("cone", "bucket", "boss_50"):
        if ekey not in enemies:
            continue
        base = enemies[ekey]
        for dmg in (5.0, 50.0, 180.0, 400.0, 900.0):
            for ap in AP_SWEEP:
                cid = f"B/{ekey}/dmg={dmg}/ap={ap}"
                cases.append(run_case(cid, base, [[dmg, [], ap]]))

    # ---- C. 边界：伤害恰好等于格挡 / 恰好等于甲段可吸收上限
    for ekey in ("shield_cadet", "cone", "bucket", "boss_50"):
        if ekey not in enemies:
            continue
        base = enemies[ekey]
        block = base["block_flat"]
        if block > 0:
            cases.append(run_case(f"C/{ekey}/dmg==block={block}", base, [[block, [], None]]))
            cases.append(run_case(f"C/{ekey}/dmg==block-1", base, [[block - 1.0, [], None]]))
            cases.append(run_case(f"C/{ekey}/dmg==block+1", base, [[block + 1.0, [], None]]))
        armor = base["armor_hp"]
        if armor > 0:
            for ap in (1.0, 2.0):
                cap = armor / ap
                # 不叠加格挡，单独考察甲段边界
                cases.append(run_case(f"C/{ekey}/dmg==cap(ap={ap})", base, [[cap, [], ap]]))
                cases.append(run_case(f"C/{ekey}/dmg==cap-0.5(ap={ap})", base, [[cap - 0.5, [], ap]]))
                cases.append(run_case(f"C/{ekey}/dmg==cap+0.5(ap={ap})", base, [[cap + 0.5, [], ap]]))

    # ---- D. 合成极端配置
    synth = [
        ("D/no_armor_no_block", {"hp_body": 100.0, "armor_hp": 0.0,
                                 "armor_reduction": 0.0, "block_flat": 0.0}),
        ("D/block1000", {"hp_body": 100.0, "armor_hp": 0.0,
                         "armor_reduction": 0.0, "block_flat": 1000.0}),
        ("D/armor1", {"hp_body": 100.0, "armor_hp": 1.0,
                      "armor_reduction": 0.5, "block_flat": 0.0}),
        ("D/reduction0.999", {"hp_body": 1000.0, "armor_hp": 100.0,
                              "armor_reduction": 0.999, "block_flat": 0.0}),
        ("D/reduction0", {"hp_body": 1000.0, "armor_hp": 100.0,
                          "armor_reduction": 0.0, "block_flat": 0.0}),
        ("D/tiny_hp", {"hp_body": 0.1, "armor_hp": 0.0,
                       "armor_reduction": 0.0, "block_flat": 0.0}),
        ("D/block_armor_both", {"hp_body": 200.0, "armor_hp": 300.0,
                                "armor_reduction": 0.25, "block_flat": 20.0}),
    ]
    for cid, enemy in synth:
        for dmg in (0.0, 0.5, 20.0, 21.0, 60.0, 5000.0):
            for tags in ([], ["shield_break"]):
                cases.append(run_case(f"{cid}/dmg={dmg}/tags={','.join(tags) or '-'}",
                                      enemy, [[dmg, tags, None]]))

    # ---- E. 连续多段伤害：考察状态累积与每步 round(...,6) 的确定性
    seq_enemies = {
        "normal": enemies.get("normal"),
        "shield_cadet": enemies.get("shield_cadet"),
        "cone": enemies.get("cone"),
        "bucket": enemies.get("bucket"),
        "boss_50": enemies.get("boss_50"),
    }
    sequences = {
        "many_small": [[20.0, [], None]] * 6,
        "mixed": [[20.0, [], None], [35.5, ["armor_pierce"], None],
                  [80.0, ["shield_break"], None], [12.25, [], 2.0], [100.0, [], None]],
        "kill": [[500.0, [], None]] * 4,
        "float_stress": [[33.3333, [], None], [0.1, [], None], [0.2, [], None],
                         [7.77, ["armor_pierce"], None], [1e-3, [], None]],
    }
    for ekey, base in seq_enemies.items():
        if base is None:
            continue
        for sname, hits in sequences.items():
            cases.append(run_case(f"E/{ekey}/{sname}", base, hits))

    return cases


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "godot" / "tests" / "golden_resolve_hit.json"))
    args = ap.parse_args(argv)

    reg = load_registry(DATA)
    if reg.errors:
        print(f"loader errors: {reg.errors}", file=sys.stderr)
        return 3

    cases = build_cases(reg)
    payload = {
        "format": FORMAT,
        "ap_mult_default": float(C.AP_MULT_DEFAULT),
        "case_count": len(cases),
        "cases": cases,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    hits = sum(len(c["hits"]) for c in cases)
    print(f"cases={len(cases)}  hits={hits}  size={out.stat().st_size/1024:.1f}KB")
    print("saved:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

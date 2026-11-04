extends RefCounted
## Python 引擎（`tdgame/engine/board.py`）的 GDScript 移植，按**可验证增量**推进。
##
## 已移植：
##   块 1 —— 移动 + 啃食 + 割草机/破线 + 清理 + 存活判定（trace 场景 move_bite）
##   块 2 —— 远程射击 + 弹道飞行 + 命中扣血（trace 场景 shoot_only）
## 未移植（后续增量，每个都要过对应 trace 场景）：
##   护甲/格挡结算、AoE/溅射/碎片、控制（减速/击退）、召唤、Boss 阶段、经济
##
## 与 Python 侧的对齐点（**顺序也必须一致**）：
##   now += dt（round 6 位）-> cooldowns -> economy -> spawn_due
##   -> update_plants -> update_projectiles -> update_enemies -> cleanup -> check_end

const DT := 0.1
const ROWS := 5
const COLS := 9
const CELL := 76.0
const TRIGGER_X := -0.2
const START_LIVES := 5
const SPAWN_X := COLS + 0.5
const AP_MULT_DEFAULT := 2.0   # 与 tdgame/config.py 的 AP_MULT_DEFAULT 对齐

var now := 0.0
var sun := 0
var lives := START_LIVES
var over := false
var won := false
var mowers_used := 0
var breaches := 0
var kills := 0

var plants: Array = []       # {row, col, key, hp, cx, combat, atk_timer, dead}
var enemies: Array = []      # {row, key, x, hp, bite, speed, dead, eating}
var projectiles: Array = []  # {row, x, speed, damage, hit_left, hit, dead}
var schedule: Array = []
var enemy_defs: Dictionary = {}
var plant_defs: Dictionary = {}
var _spawn_idx := 0
var _mowers: Dictionary = {0: true, 1: true, 2: true, 3: true, 4: true}


func setup(scenario: Dictionary, defs: Dictionary, pdefs: Dictionary = {}) -> void:
	enemy_defs = defs
	plant_defs = pdefs
	for entry in scenario.get("plants", []):
		var row: int = int(entry[0])
		var col: int = int(entry[1])
		var key: String = String(entry[2])
		var d: Dictionary = plant_defs.get(key, {})
		plants.append({
			"row": row, "col": col, "key": key,
			"hp": float(d.get("hp", 100)),
			"cx": float(col) + 0.5,
			"combat": d.get("combat", {}),
			"atk_timer": 0.0,          # Python 侧 Plant.attack_timer 初值就是 0
			"tags": d.get("tags", []),
			"dead": false,
		})
	schedule.clear()
	for entry2 in scenario.get("schedule", []):
		schedule.append([float(entry2[0]), String(entry2[1]), int(entry2[2])])
	schedule.sort_custom(func(a, b): return a[0] < b[0])


# ---------------------------------------------------------------------- 主步进
func step() -> void:
	if over:
		return
	# 注意：GDScript 的 round() 是**取整**，Python 的 round(x, 6) 是保留 6 位小数，
	# 两者不能互换（写 round() 会把 now 直接归零）。用 snappedf 对齐语义。
	now = snappedf(now + DT, 0.000001)
	_spawn_due()
	_update_plants()
	_update_projectiles()
	_update_enemies()
	_cleanup()
	_check_end()


func _spawn_due() -> void:
	while _spawn_idx < schedule.size() and float(schedule[_spawn_idx][0]) <= now:
		var entry = schedule[_spawn_idx]
		var key: String = String(entry[1])
		var d: Dictionary = enemy_defs.get(key, {})
		enemies.append({
			"row": int(entry[2]), "key": key, "x": SPAWN_X,
			"hp": float(d.get("hp_body", 100)),
			"bite": float(d.get("bite_dps", 0)),
			"speed": float(d.get("speed", 0)),
			"armor": float(d.get("armor", {}).get("hp", 0)),
			"armor_red": float(d.get("armor", {}).get("reduction", 0)),
			"block": float(d.get("block_flat", 0)),
			"dead": false, "eating": -1,
		})
		_spawn_idx += 1


# ---------------------------------------------------------------------- 植物行为
func _update_plants() -> void:
	for p in plants:
		if bool(p.get("dead", false)):
			continue
		var combat: Dictionary = p["combat"]
		if combat.is_empty():
			continue
		p["atk_timer"] = float(p["atk_timer"]) - DT
		if float(p["atk_timer"]) <= 0.0:
			if _plant_attack(p, combat):
				p["atk_timer"] = float(p["atk_timer"]) + float(combat["atk_interval"])


func _plant_attack(p: Dictionary, combat: Dictionary) -> bool:
	var rng: Dictionary = combat.get("range", {"type": "row", "cells": COLS})
	if String(rng.get("type", "row")) != "row":
		# 近战/其它形态尚未移植，明确不假装支持
		return false
	var target := _ranged_target(p, float(rng.get("cells", COLS)))
	if target < 0:
		return false
	var proj: Dictionary = combat["projectile"]
	projectiles.append({
		"row": int(p["row"]),
		"x": float(p["cx"]) + 0.2,
		"speed": float(proj["speed"]) / CELL,   # Python: Projectile 把像素速度除以 CELL
		"damage": float(combat["damage"]),
		"hit_left": 1,                           # pierce 计数，本块恒为 1
		"tags": p["tags"],
		"dead": false,
		"hit": String(proj.get("hit", "single")),
	})
	return true


func _ranged_target(p: Dictionary, range_cells: float) -> int:
	var best := -1
	var best_x := 1e18
	for i in enemies.size():
		var e = enemies[i]
		if bool(e["dead"]) or int(e["row"]) != int(p["row"]):
			continue
		var ex: float = float(e["x"])
		if ex <= float(p["cx"]) + range_cells and ex > float(p["cx"]) - 1.0:
			if ex < best_x:
				best_x = ex
				best = i
	return best


# ---------------------------------------------------------------------- 弹道
func _update_projectiles() -> void:
	for pr in projectiles:
		if bool(pr["dead"]):
			continue
		pr["x"] = float(pr["x"]) + float(pr["speed"]) * DT
		if float(pr["x"]) > COLS + 1.0:
			pr["dead"] = true
			continue
		var hit_idx := _projectile_find_target(pr)
		if hit_idx >= 0:
			_resolve_projectile_hit(pr, enemies[hit_idx])


func _projectile_find_target(pr: Dictionary) -> int:
	var best := -1
	var best_x := 1e18
	for i in enemies.size():
		var e = enemies[i]
		if bool(e["dead"]) or int(e["row"]) != int(pr["row"]):
			continue
		var ex: float = float(e["x"])
		if float(pr["x"]) >= ex - 0.3 and float(pr["x"]) <= ex + 0.6:
			if ex < best_x:
				best_x = ex
				best = i
	return best


func _resolve_projectile_hit(pr: Dictionary, enemy: Dictionary) -> void:
	# 直击伤害走统一入口；AoE/溅射/控制留给后续增量
	_apply_damage(enemy, float(pr["damage"]), pr["tags"])
	pr["hit_left"] = int(pr["hit_left"]) - 1
	if int(pr["hit_left"]) <= 0 or not String(pr["hit"]).begins_with("pierce:"):
		pr["dead"] = true


# ---------------------------------------------------------------------- 伤害结算
func _apply_damage(enemy: Dictionary, raw: float, tags) -> void:
	## 镜像 tdgame/balance.py::resolve_hit，顺序：格挡 -> 归零短路 -> 护甲段 -> 本体。
	var tag_set := {}
	for t in tags:
		tag_set[String(t)] = true

	var dmg: float = raw
	var block: float = float(enemy["block"])
	if block > 0.0 and not tag_set.has("shield_break"):
		dmg = maxf(0.0, dmg - block)

	# 归零短路：不破甲、不打本体
	if dmg <= 0.0:
		return

	var armor: float = float(enemy["armor"])
	if armor > 0.0:
		var ap: float = AP_MULT_DEFAULT if tag_set.has("armor_pierce") else 1.0
		var reduction: float = float(enemy["armor_red"])
		var capacity_raw: float = armor / ap          # 甲段还能吸收的原始伤害当量
		if dmg <= capacity_raw:
			enemy["armor"] = snappedf(armor - dmg * ap, 0.000001)
		else:
			enemy["armor"] = 0.0
			var overflow_raw: float = dmg - capacity_raw
			var body: float = overflow_raw * (1.0 - reduction)   # 溢出折减后打本体
			enemy["hp"] = snappedf(float(enemy["hp"]) - body, 0.000001)
	else:
		# 穿甲倍率不作用于裸本体
		enemy["hp"] = snappedf(float(enemy["hp"]) - dmg, 0.000001)


# ---------------------------------------------------------------------- 敌人
func _update_enemies() -> void:
	for e in enemies:
		if bool(e["dead"]):
			continue
		var blocker := _blocker_for(e)
		if blocker >= 0:
			e["eating"] = blocker
			var dmg: float = float(e["bite"]) * DT
			plants[blocker]["hp"] = float(plants[blocker]["hp"]) - dmg
			if float(plants[blocker]["hp"]) <= 0.0:
				plants[blocker]["hp"] = 0.0
				plants[blocker]["dead"] = true
				e["eating"] = -1
		else:
			e["eating"] = -1
			e["x"] = float(e["x"]) - float(e["speed"]) * DT / CELL
			if float(e["x"]) <= TRIGGER_X:
				_handle_breach(e)


func _blocker_for(e: Dictionary) -> int:
	var best := -1
	var best_col := -1
	for i in plants.size():
		var p = plants[i]
		if bool(p.get("dead", false)):
			continue
		if int(p["row"]) != int(e["row"]):
			continue
		if float(int(p["col"]) + 1) >= float(e["x"]) - 1e-9:
			if int(p["col"]) > best_col:
				best_col = int(p["col"])
				best = i
	if best < 0:
		return -1
	if float(e["x"]) <= float(best_col) + 1.0 + 1e-9:
		return best
	return -1


func _handle_breach(e: Dictionary) -> void:
	var row: int = int(e["row"])
	if bool(_mowers.get(row, false)):
		_mowers[row] = false
		mowers_used += 1
		for other in enemies:
			if int(other["row"]) == row and not bool(other["dead"]):
				other["dead"] = true
				kills += 1
	else:
		e["dead"] = true
		breaches += 1
		lives -= 1


func _cleanup() -> void:
	var live_e := []
	for e in enemies:
		if bool(e["dead"]):
			continue
		if float(e["hp"]) <= 0.0:
			kills += 1
			continue
		live_e.append(e)
	enemies = live_e
	var live_p := []
	for p in plants:
		if not bool(p.get("dead", false)) and float(p["hp"]) > 0.0:
			live_p.append(p)
	plants = live_p
	var live_pr := []
	for pr in projectiles:
		if not bool(pr["dead"]):
			live_pr.append(pr)
	projectiles = live_pr


func _check_end() -> void:
	if lives <= 0:
		over = true
		won = false
		return
	if _spawn_idx >= schedule.size() and enemies.is_empty():
		over = true
		won = true


# ---------------------------------------------------------------------- digest
func digest() -> Dictionary:
	var p_arr := []
	for p in plants:
		p_arr.append([int(p["row"]), int(p["col"]), snappedf(float(p["hp"]), 0.0001)])
	p_arr.sort_custom(func(a, b): return _lt(a, b))
	var e_arr := []
	for e in enemies:
		e_arr.append([int(e["row"]), snappedf(float(e["x"]), 0.0001),
			snappedf(float(e["hp"]), 0.0001), snappedf(float(e["armor"]), 0.0001)])
	e_arr.sort_custom(func(a, b): return _lt(a, b))
	var pr_arr := []
	for pr in projectiles:
		pr_arr.append([int(pr["row"]), snappedf(float(pr["x"]), 0.0001)])
	pr_arr.sort_custom(func(a, b): return _lt(a, b))
	return {
		"t": snappedf(now, 0.0001),
		"sun": sun,
		"lives": lives,
		"plants": p_arr,
		"enemies": e_arr,
		"proj": pr_arr,
		"kills": kills,
		"mowers": mowers_used,
		"breaches": breaches,
		"over": over,
	}


static func _lt(a: Array, b: Array) -> bool:
	for i in mini(a.size(), b.size()):
		if a[i] < b[i]:
			return true
		if a[i] > b[i]:
			return false
	return a.size() < b.size()

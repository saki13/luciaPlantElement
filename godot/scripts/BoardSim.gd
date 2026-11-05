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
const AP_MULT_DEFAULT := 2.0
const SKY_SUN_VALUE := 25
const SKY_SUN_INTERVAL := 10.0
const SUN_VALUE := 25
const SUNFLOWER_INTERVAL := 8.0

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
var sky_sun_enabled := false
var sky_timer := SKY_SUN_INTERVAL
var _mowers: Dictionary = {0: true, 1: true, 2: true, 3: true, 4: true}


func setup(scenario: Dictionary, defs: Dictionary, pdefs: Dictionary = {}) -> void:
	enemy_defs = defs
	plant_defs = pdefs
	sky_sun_enabled = bool(scenario.get("sky_sun", false))
	sky_timer = SKY_SUN_INTERVAL
	sun = int(scenario.get("start_resource", 0))
	for entry in scenario.get("plants", []):
		var row: int = int(entry[0])
		var col: int = int(entry[1])
		var key: String = String(entry[2])
		var d: Dictionary = plant_defs.get(key, {})
		# 注意：GDScript 的 `or` 返回 bool（Python 返回操作数），
		# 所以不能写 `(d.get("economy") or {})` —— 那会得到 true 然后 .get 报错。
		var eco: Dictionary = d.get("economy", {})
		plants.append({
			"row": row, "col": col, "key": key,
			"hp": float(d.get("hp", 100)),
			"cx": float(col) + 0.5,
			"combat": d.get("combat", {}),
			"atk_timer": 0.0,          # Python 侧 Plant.attack_timer 初值就是 0
			"tags": d.get("tags", []),
			"produce_timer": float(eco.get("first", 0.0)),
			"economy": eco,
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
	_update_economy()
	_spawn_due()
	_update_plants()
	_update_projectiles()
	_update_enemies()
	_cleanup()
	_check_end()


func _add_sun(amount: int) -> void:
	sun += amount


func _update_economy() -> void:
	# 天空阳光：每 SKY_SUN_INTERVAL 秒给一次（落点随机不影响 sun 数值）
	if sky_sun_enabled:
		sky_timer = sky_timer - DT
		if sky_timer <= 0.0:
			_add_sun(SKY_SUN_VALUE)
			sky_timer += SKY_SUN_INTERVAL
	# 植物产阳光
	for p in plants:
		if bool(p.get("dead", false)):
			continue
		var eco: Dictionary = p["economy"]
		if eco.is_empty():
			continue
		p["produce_timer"] = float(p["produce_timer"]) - DT
		if float(p["produce_timer"]) <= 0.0:
			_add_sun(int(eco.get("produce", SUN_VALUE)))
			p["produce_timer"] = float(p["produce_timer"]) + float(
				eco.get("interval", SUNFLOWER_INTERVAL))


func _spawn_due() -> void:
	while _spawn_idx < schedule.size() and float(schedule[_spawn_idx][0]) <= now:
		var entry = schedule[_spawn_idx]
		var key: String = String(entry[1])
		var d: Dictionary = enemy_defs.get(key, {})
		# GDScript 的 `or` 返回 bool，不能写 `(d.get("summon") or {})`
		var summ: Dictionary = d.get("summon", {})
		var ph: Dictionary = d.get("phase", {})
		var armor_def: Dictionary = d.get("armor", {})
		enemies.append({
			"row": int(entry[2]), "key": key, "x": SPAWN_X,
			"hp": float(d.get("hp_body", 100)),
			"bite": float(d.get("bite_dps", 0)),
			"speed": float(d.get("speed", 0)),
			"armor": float(armor_def.get("hp", 0)),
			"armor_red": float(armor_def.get("reduction", 0)),
			"block": float(d.get("block_flat", 0)),
			"slow_resist": float(d.get("slow_resist", 0)),
			"weight": float(d.get("weight", 1)),
			"kb_immune": bool(d.get("kb_immune", false)),
			"mower_immune": bool(d.get("mower_immune", false)),
			"slow_mult": 1.0,
			"slow_until": -1.0,
			"summon_mob": String(summ.get("mob", "")),
			"summon_interval": float(summ.get("interval", 0.0)),
			"summon_max": int(summ.get("max_alive", 0)),
			"summon_timer": float(summ.get("interval", 0.0)),
			"summoned_by": -1,
			"phase": 1,
			"phase_ratio": float(ph.get("hp_ratio", 0.0)),
			"phase_speed_mult": float(ph.get("speed_mult", 1.0)),
			"phase_summon_mult": float(ph.get("summon_interval_mult", 1.0)),
			"hp_max": float(d.get("hp_body", 100)),
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
		"slow": proj.get("slow", {}),
		"knockback_cells": proj.get("knockback_cells", 0.0),
		"edge_mult": float(proj.get("edge_damage_mult", 1.0)),
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
	# 普通溅射弹（西瓜类）：直击之后对周围再打一次，中心单位不吃边缘衰减
	var hit: String = String(pr.get("hit", "single"))
	if hit.begins_with("splash:"):
		var radius := float(hit.split(":", true, 1)[1])
		_area_damage(int(enemy["row"]), float(enemy["x"]) + 0.4, radius,
			float(pr["damage"]), pr["tags"], float(pr["edge_mult"]), enemy)
	_apply_control(enemy, pr)
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


func _area_damage(row: int, cx: float, radius: float, damage: float, tags,
		edge_mult: float, center_enemy: Dictionary) -> void:
	## 镜像 board.py::_area_damage：行差与列差都在半径内才吃伤害；
	## 中心单位乘 1.0，其余乘 edge_mult。
	for e in enemies:
		if bool(e["dead"]):
			continue
		if absf(float(e["row"]) - float(row)) > radius:
			continue
		if absf((float(e["x"]) + 0.4) - cx) > radius + 0.4:
			continue
		var mult: float = 1.0 if e == center_enemy else edge_mult
		_apply_damage(e, damage * mult, tags)


func _apply_control(enemy: Dictionary, pr: Dictionary) -> void:
	## 镜像 board.py::_apply_control + balance.effective_speed_mult / knockback_distance
	var slow: Dictionary = pr.get("slow", {})
	if not slow.is_empty():
		# 减速量按抵抗比例折减：1 - (1-factor)*(1-resist)，保留 4 位（与 Python 一致）
		var factor := float(slow.get("factor", 1.0))
		var resist := float(enemy["slow_resist"])
		var amount: float = maxf(0.0, 1.0 - factor)
		enemy["slow_mult"] = snappedf(1.0 - amount * (1.0 - resist), 0.0001)
		enemy["slow_until"] = now + float(slow.get("duration", 2.5))
	var kb := float(pr.get("knockback_cells", 0.0))
	if kb > 0.0 and not bool(enemy["kb_immune"]):
		var dist: float = snappedf(kb / maxf(1.0, float(enemy["weight"])), 0.0001)
		enemy["x"] = minf(COLS + 0.5, float(enemy["x"]) + dist)


func _current_speed_mult(e: Dictionary) -> float:
	return float(e["slow_mult"]) if now < float(e["slow_until"]) else 1.0


# ---------------------------------------------------------------------- 敌人
func _update_boss_phases() -> void:
	## 本体血量跌破阈值 -> 进二阶段：提速、召唤更频繁。
	for e in enemies:
		if bool(e["dead"]) or int(e["phase"]) != 1 or float(e["phase_ratio"]) <= 0.0:
			continue
		if float(e["hp_max"]) <= 0.0:
			continue
		if float(e["hp"]) / float(e["hp_max"]) <= float(e["phase_ratio"]):
			e["phase"] = 2
			e["speed"] = float(e["speed"]) * float(e["phase_speed_mult"])
			if float(e["summon_interval"]) > 0.0:
				e["summon_interval"] = float(e["summon_interval"]) * float(e["phase_summon_mult"])


func _update_summons() -> void:
	## 每 interval 秒生一只 mob，同父存活数不超过 max_alive。
	## Python 侧遍历的是 list(self.enemies) 的快照，所以这里也先拷一份下标。
	for idx in range(enemies.size()):
		var e = enemies[idx]
		if bool(e["dead"]) or String(e["summon_mob"]) == "":
			continue
		if float(e["summon_interval"]) <= 0.0:
			continue
		e["summon_timer"] = float(e["summon_timer"]) - DT
		if float(e["summon_timer"]) > 0.0:
			continue
		e["summon_timer"] = float(e["summon_timer"]) + float(e["summon_interval"])
		var alive := 0
		for c in enemies:
			if not bool(c["dead"]) and int(c["summoned_by"]) == idx:
				alive += 1
		if alive >= int(e["summon_max"]):
			continue
		var mob: String = String(e["summon_mob"])
		var d: Dictionary = enemy_defs.get(mob, {})
		var summ2: Dictionary = d.get("summon", {})
		var ph2: Dictionary = d.get("phase", {})
		var armor2: Dictionary = d.get("armor", {})
		var child := {
			"row": int(e["row"]), "key": mob,
			"x": minf(COLS + 0.5, float(e["x"]) + 0.8),
			"hp": float(d.get("hp_body", 100)),
			"bite": float(d.get("bite_dps", 0)),
			"speed": float(d.get("speed", 0)),
			"armor": float(armor2.get("hp", 0)),
			"armor_red": float(armor2.get("reduction", 0)),
			"block": float(d.get("block_flat", 0)),
			"slow_resist": float(d.get("slow_resist", 0)),
			"weight": float(d.get("weight", 1)),
			"kb_immune": bool(d.get("kb_immune", false)),
			"mower_immune": bool(d.get("mower_immune", false)),
			"slow_mult": 1.0,
			"slow_until": -1.0,
			"summon_mob": String(summ2.get("mob", "")),
			"summon_interval": float(summ2.get("interval", 0.0)),
			"summon_max": int(summ2.get("max_alive", 0)),
			"summon_timer": float(summ2.get("interval", 0.0)),
			"summoned_by": idx,
			"phase": 1,
			"phase_ratio": float(ph2.get("hp_ratio", 0.0)),
			"phase_speed_mult": float(ph2.get("speed_mult", 1.0)),
			"phase_summon_mult": float(ph2.get("summon_interval_mult", 1.0)),
			"hp_max": float(d.get("hp_body", 100)),
			"dead": false, "eating": -1,
		}
		enemies.append(child)


func _update_enemies() -> void:
	_update_boss_phases()
	_update_summons()
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
			# 减速乘子：slow_until 之前按 slow_mult，之后恢复 1.0
			e["x"] = float(e["x"]) - float(e["speed"]) * _current_speed_mult(e) * DT / CELL
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
	# mower_immune 的 Boss 级单位不吃割草机，直接算破线扣命
	if bool(_mowers.get(row, false)) and not bool(e["mower_immune"]):
		_mowers[row] = false
		mowers_used += 1
		# 割草机清场，但碾不动 mower_immune 的单位
		for other in enemies:
			if int(other["row"]) == row and not bool(other["dead"]) \
					and not bool(other["mower_immune"]):
				other["dead"] = true
				kills += 1
	else:
		e["dead"] = true
		breaches += 1
		lives -= 1
		# Boss 冲到家里 = 这一局彻底失败，不能被"出怪跑完且无敌人"误判成通关
		if bool(e["mower_immune"]):
			over = true
			won = false


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
	if over:                      # 已有结论（例如 Boss 破线判负）就别覆盖
		return
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

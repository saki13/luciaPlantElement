extends RefCounted
## Python 引擎（`tdgame/engine/board.py`）的最小 GDScript 移植 —— 第一块：移动 + 啃食。
##
## 只覆盖 `move_bite` 场景需要的路径，刻意**不**包含弹道/护甲/格挡/召唤/阶段。
## 每加一块就用对应的 trace 场景做逐步比对，避免"半成品移植看起来能用"。
##
## 与 Python 侧的对齐点（顺序也必须一致）：
##   now += dt（round 到 6 位）-> cooldowns -> economy -> spawn_due
##   -> update_plants -> update_projectiles -> update_enemies -> cleanup -> check_end
## 本块里 cooldowns/economy/projectiles/plants 都是空实现（坚果不产阳光、不攻击）。

const DT := 0.1
const ROWS := 5
const COLS := 9
const CELL := 76.0
const TRIGGER_X := -0.2
const START_LIVES := 5
const SPAWN_X := COLS + 0.5

var now := 0.0
var sun := 0
var lives := START_LIVES
var over := false
var won := false
var mowers_used := 0
var breaches := 0
var kills := 0

var plants: Array = []       # [{row, col, key, hp}]
var enemies: Array = []      # [{row, key, x, hp, dead, eating}]
var schedule: Array = []     # [[t, key, row], ...]
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
		var hp := float(plant_defs.get(key, {}).get("hp", 800.0))
		plants.append({"row": row, "col": col, "key": key, "hp": hp})
	schedule.clear()
	for entry in scenario.get("schedule", []):
		schedule.append([float(entry[0]), String(entry[1]), int(entry[2])])
	schedule.sort_custom(func(a, b): return a[0] < b[0])


func _plant_hp(key: String) -> float:
	# 本块只有坚果，血量从 defs 里取；缺省给 1 防止除零
	return float(enemy_defs.get("__plant_" + key, {}).get("hp", 800.0))


# ---------------------------------------------------------------------- 主步进
func step() -> void:
	if over:
		return
	# 注意：GDScript 的 round() 是**取整**，Python 的 round(x, 6) 是保留 6 位小数，
	# 两者不能互换（写成 round() 会把 now 直接归零）。这里用 snappedf 对齐语义。
	now = snappedf(now + DT, 0.000001)
	_spawn_due()
	_update_enemies()
	_cleanup()
	_check_end()


func _spawn_due() -> void:
	while _spawn_idx < schedule.size() and float(schedule[_spawn_idx][0]) <= now:
		var entry = schedule[_spawn_idx]
		var key: String = String(entry[1])
		var row: int = int(entry[2])
		var d: Dictionary = enemy_defs.get(key, {})
		enemies.append({
			"row": row,
			"key": key,
			"x": SPAWN_X,
			"hp": float(d.get("hp_body", 100)),
			"bite": float(d.get("bite_dps", 0)),
			"speed": float(d.get("speed", 0)),
			"dead": false,
			"eating": -1,
		})
		_spawn_idx += 1


func _update_enemies() -> void:
	for e in enemies:
		if e["dead"]:
			continue
		var blocker := _blocker_for(e)
		if blocker >= 0:
			e["eating"] = blocker
			var dmg: float = float(e["bite"]) * DT
			plants[blocker]["hp"] -= dmg
			if float(plants[blocker]["hp"]) <= 0.0:
				plants[blocker]["hp"] = 0.0
				e["eating"] = -1
				# 标记死亡由 cleanup 统一处理（与 Python 的 _cleanup 一致）
				plants[blocker]["dead"] = true
		else:
			e["eating"] = -1
			# current_speed_mult 在本块里恒为 1.0（没有减速源）
			e["x"] = float(e["x"]) - float(e["speed"]) * DT / CELL
			if float(e["x"]) <= TRIGGER_X:
				_handle_breach(e)


func _blocker_for(e: Dictionary) -> int:
	## 返回最靠右、且与敌人接触的植物下标；没有则 -1。
	## 与 Python 的 `_blocker_for` 同义：先取本行最右的活植物，再判断是否接触。
	var best := -1
	var best_col := -1
	for i in plants.size():
		var p = plants[i]
		if p.get("dead", false):
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
		if not bool(e["dead"]):
			live_e.append(e)
	enemies = live_e
	var live_p := []
	for p in plants:
		if not bool(p.get("dead", false)) and float(p["hp"]) > 0.0:
			live_p.append(p)
	plants = live_p


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
			snappedf(float(e["hp"]), 0.0001)])
	e_arr.sort_custom(func(a, b): return _lt(a, b))
	return {
		"t": snappedf(now, 0.0001),
		"sun": sun,
		"lives": lives,
		"plants": p_arr,
		"enemies": e_arr,
		"proj": [],
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

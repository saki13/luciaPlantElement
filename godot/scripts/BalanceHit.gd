extends RefCounted

## `tdgame/balance.py::resolve_hit` 的 GDScript 复刻（阶段 2 一致性门禁的第一步）。
##
## 语义必须与 Python 版逐字段一致，包括：
##   - 格挡是每实例固定减、可归零；带 shield_break 则跳过格挡并标记 shield_broke
##   - 归零短路后不破甲、不打本体
##   - 穿甲倍率 ap 只作用于甲段；溢出原始伤害 ×(1-reduction) 进本体
##   - 血量写回时 round(...,6)，明细 round(...,4)
##
## 注意：这里刻意不声明 class_name，避免与 preload 的常量名冲突。

const AP_MULT_DEFAULT := 2.0


static func _val(o: Dictionary, key: String) -> float:
	# 对应 Python 的 float(o.get(key, default) or 0)：缺字段/None/0 都归 0.0
	if not o.has(key):
		return 0.0
	var v: Variant = o[key]
	if v == null:
		return 0.0
	return float(v)


static func _round_dec(x: float, n: int) -> float:
	# 复刻 Python round(x, n)：对二进制 double 做十进制正确舍入
	return String.num(x, n).to_float()


static func resolve_hit(enemy: Dictionary, raw_damage: float, tags: Array,
		ap_mult: Variant = null) -> Dictionary:
	var tag_set := {}
	for t in tags:
		tag_set[str(t)] = true

	var dmg := float(raw_damage)
	var detail := {
		"raw": dmg,
		"shield_broke": false,
		"blocked_fully": false,
		"armor_absorbed": 0.0,
		"body_damage": 0.0,
	}

	# 步骤 1：格挡
	var block := _val(enemy, "block_flat")
	if block > 0.0 and not tag_set.has("shield_break"):
		dmg = maxf(0.0, dmg - block)
	elif block > 0.0 and tag_set.has("shield_break"):
		detail["shield_broke"] = true
	detail["after_block"] = _round_dec(dmg, 4)

	# 步骤 2：归零短路
	if dmg <= 0.0:
		detail["blocked_fully"] = true
		detail["killed"] = _val(enemy, "hp_body") <= 0.0
		return detail

	# 步骤 3：护甲段
	var armor_hp := _val(enemy, "armor_hp")
	if armor_hp > 0.0:
		var ap: float
		if ap_mult != null:
			ap = float(ap_mult)
		elif tag_set.has("armor_pierce"):
			ap = AP_MULT_DEFAULT
		else:
			ap = 1.0
		var reduction := _val(enemy, "armor_reduction")
		var capacity_raw := armor_hp / ap
		if dmg <= capacity_raw:
			var absorbed := dmg * ap
			enemy["armor_hp"] = _round_dec(armor_hp - absorbed, 6)
			detail["armor_absorbed"] = _round_dec(absorbed, 4)
		else:
			enemy["armor_hp"] = 0.0
			detail["armor_absorbed"] = _round_dec(armor_hp, 4)
			var overflow_raw := dmg - capacity_raw
			var body := overflow_raw * (1.0 - reduction)
			enemy["hp_body"] = _round_dec(_val(enemy, "hp_body") - body, 6)
			detail["body_damage"] = _round_dec(body, 4)
	else:
		# 步骤 4：无甲直接扣本体
		enemy["hp_body"] = _round_dec(_val(enemy, "hp_body") - dmg, 6)
		detail["body_damage"] = _round_dec(dmg, 4)

	detail["killed"] = _val(enemy, "hp_body") <= 0.0
	return detail

extends SceneTree

## 一致性门禁：用 Python 生成的黄金用例，逐字段校验 BalanceHit.gd 与 balance.resolve_hit 是否等价。
##
## 跑法：
##   godot --headless --path godot --script res://tests/run_conformance.gd
##   godot --headless --path godot --script res://tests/run_conformance.gd -- --golden=D:/x/golden.json
##
## 退出码：0 全通过 / 1 有偏差 / 2 无法载入黄金文件

const BH := preload("res://scripts/BalanceHit.gd")

const MAX_REPORT := 20

var _golden := "res://tests/golden_resolve_hit.json"


func _initialize() -> void:
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--golden="):
			_golden = a.substr("--golden=".length())

	if not FileAccess.file_exists(_golden):
		printerr("golden file not found: " + _golden)
		quit(2)
		return

	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(_golden))
	if typeof(data) != TYPE_DICTIONARY:
		printerr("golden file is not a JSON object")
		quit(2)
		return

	var fmt := str(data.get("format", ""))
	if fmt != "pvz-golden/resolve_hit/1":
		printerr("unexpected golden format: " + fmt)
		quit(2)
		return

	var cases: Array = data["cases"]
	var total_hits := 0
	var fails: Array = []
	var max_diff := 0.0
	var field_fail := {}

	for c in cases:
		var cid := str(c["id"])
		var enemy: Dictionary = (c["enemy"] as Dictionary).duplicate(true)
		var hits: Array = c["hits"]
		var expected: Array = c["expected"]

		if hits.size() != expected.size():
			fails.append("%s: hits/expected 长度不一致" % cid)
			continue

		for i in range(hits.size()):
			var h: Array = hits[i]
			var got: Dictionary = BH.resolve_hit(enemy, float(h[0]), h[1], h[2])
			var exp: Dictionary = expected[i]
			total_hits += 1

			for key in exp.keys():
				var e: Variant = exp[key]
				var g: Variant
				if key == "hp_body" or key == "armor_hp":
					g = enemy[key]
				else:
					g = got.get(key, null)

				if typeof(e) == TYPE_BOOL:
					if bool(g) != bool(e):
						fails.append("%s hit#%d %s: got %s exp %s" % [cid, i + 1, key, str(g), str(e)])
						field_fail[key] = int(field_fail.get(key, 0)) + 1
				else:
					var gf := float(g)
					var ef := float(e)
					var d: float = absf(gf - ef)
					if d > max_diff:
						max_diff = d
					if gf != ef:
						fails.append("%s hit#%d %s: got %.12f exp %.12f (diff %s)" % [
							cid, i + 1, key, gf, ef, String.num(d, 12)])
						field_fail[key] = int(field_fail.get(key, 0)) + 1

	print("=== resolve_hit conformance ===")
	print("golden : %s" % _golden)
	print("cases  : %d" % cases.size())
	print("hits   : %d" % total_hits)
	print("fails  : %d" % fails.size())
	print("max_abs_diff: %s" % String.num(max_diff, 12))

	if not fails.is_empty():
		print("--- 按字段统计 ---")
		print(str(field_fail))
		print("--- 前 %d 条 ---" % mini(MAX_REPORT, fails.size()))
		for k in range(mini(MAX_REPORT, fails.size())):
			print("  " + str(fails[k]))
		print("RESULT: FAIL")
		quit(1)
		return

	print("RESULT: PASS")
	quit(0)

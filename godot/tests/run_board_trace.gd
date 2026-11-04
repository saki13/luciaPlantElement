extends SceneTree
## E-01 移植校验：用 GDScript 版 BoardSim 重放 Python 导出的 board trace，
## 逐步逐字段比对。第一块只覆盖 `move_bite` 场景（移动 + 啃食）。
##
## 用法：
##   godot --headless --path godot --script res://tests/run_board_trace.gd
## 退出码 0 = 逐步一致；1 = 有分歧（会打印第一个分歧的步号与字段）。

const TOL := 1e-4          # 与 Python 侧 round(...,4) 的粒度一致
const TRACE_PATH := "res://tests/golden_board_trace.json"
const ONLY := ["move_bite", "shoot_only"]  # 已移植的场景；其余待后续增量


func _initialize() -> void:
	var raw := FileAccess.get_file_as_string(TRACE_PATH)
	if raw.is_empty():
		print("RESULT: FAIL 读不到 %s" % TRACE_PATH)
		quit(1)
		return
	var data = JSON.parse_string(raw)
	if typeof(data) != TYPE_DICTIONARY:
		print("RESULT: FAIL trace JSON 解析失败")
		quit(1)
		return

	var failures: Array[String] = []
	for name in ONLY:
		var sc: Dictionary = data["scenarios"].get(name, {})
		if sc.is_empty():
			failures.append("%s: trace 里没有这个场景" % name)
			continue
		failures.append_array(_check_scenario(name, sc))

	print("")
	if failures.is_empty():
		print("RESULT: PASS（%d 场景逐步一致）" % ONLY.size())
		quit(0)
	else:
		print("RESULT: FAIL（%d 处）" % failures.size())
		for f in failures:
			print("  - " + f)
		quit(1)


func _check_scenario(name: String, sc: Dictionary) -> Array[String]:
	var out: Array[String] = []
	var sim = load("res://scripts/BoardSim.gd").new()
	# trace 自带她用到的角色定义，所以这里不需要访问仓库外的文件
	var defs: Dictionary = sc.get("defs", {})
	sim.setup(sc, defs.get("enemies", {}), defs.get("plants", {}))

	var frames: Array = sc["frames"]
	for i in frames.size():
		sim.step()
		var want: Dictionary = frames[i]
		var got: Dictionary = sim.digest()
		var bad := _diff_fields(want, got)
		if not bad.is_empty():
			out.append("%s: 第 %d 步起不一致" % [name, i])
			for b in bad:
				out.append("    %s" % b)
			return out
	return out


func _diff_fields(want: Dictionary, got: Dictionary) -> Array[String]:
	var bad: Array[String] = []
	for k in ["t", "sun", "lives", "kills", "mowers", "breaches"]:
		if not _num_eq(want.get(k, 0), got.get(k, 0)):
			bad.append("%s: want %s got %s" % [k, str(want.get(k)), str(got.get(k))])
	if bool(want.get("over", false)) != bool(got.get("over", false)):
		bad.append("over: want %s got %s" % [str(want.get("over")), str(got.get("over"))])
	for k in ["plants", "enemies"]:
		bad.append_array(_diff_list(k, want.get(k, []), got.get(k, [])))
	return bad


func _diff_list(key: String, want: Array, got: Array) -> Array[String]:
	var bad: Array[String] = []
	if want.size() != got.size():
		return ["%s: 数量 want %d got %d" % [key, want.size(), got.size()]]
	for i in want.size():
		var a: Array = want[i]
		var b: Array = got[i]
		if a.size() != b.size():
			bad.append("%s[%d]: 维度不同" % [key, i])
			continue
		for j in a.size():
			if not _num_eq(a[j], b[j]):
				bad.append("%s[%d][%d]: want %s got %s" % [key, i, j, str(a[j]), str(b[j])])
				break
	return bad


func _num_eq(a, b) -> bool:
	if typeof(a) == TYPE_INT and typeof(b) == TYPE_INT:
		return int(a) == int(b)
	return absf(float(a) - float(b)) <= TOL

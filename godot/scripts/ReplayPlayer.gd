extends Node2D

## 阶段 1 回放播放器：**纯渲染**，零战斗逻辑。
## 所有位置/血量/胜负都来自 tdgame/replay.py 导出的确定性快照，本脚本只做插值与切帧。
##
## 运行：
##   godot --path godot
##   godot --path godot -- --replay=../replays/boss50_late_s1002.json
## 环境变量覆盖：
##   PVZ_REPLAY  回放 JSON 绝对/相对路径
##   PVZ_SPRITES 精灵表目录（默认 ../anim_demo/assets/sprites）
##   PVZ_SPEED   播放倍速（默认 1.0）
##   PVZ_AUTOQUIT=1  跑完自动退出（CI 冒烟用）

const COL_A := Color(0.486, 0.769, 0.361)
const COL_B := Color(0.424, 0.706, 0.314)
const COL_LINE := Color(1.0, 1.0, 1.0, 0.45)
const COL_PROJ := Color(0.18, 0.32, 0.12)
const COL_MOWER := Color(0.85, 0.25, 0.22)

var rep: Dictionary = {}
var frames: Array = []
var anim: Dictionary = {}
var units: Dictionary = {}
var cell: float = 76.0
var top_h: float = 96.0
var gutter: float = 34.0
var rows: int = 5
var cols: int = 9

var t: float = 0.0
var idx: int = 0
var speed: float = 1.0
var done: bool = false
var autoquit: bool = false

var sprite_root: String = ""
var tex_cache: Dictionary = {}
var sf_cache: Dictionary = {}
var views: Dictionary = {}          # uid -> AnimatedSprite2D
var proj_draw: Array = []           # [row, x_cells]
var mowers: Array = []
var sun: int = 0
var lives: int = 0
var end_tb: float = 0.0

var hud: Label
var missing_sprites: Dictionary = {}


func _ready() -> void:
	speed = _env_float("PVZ_SPEED", 1.0)
	autoquit = OS.get_environment("PVZ_AUTOQUIT") == "1"

	var replay_path := _resolve_replay_path()
	_load_replay(replay_path)
	_resolve_sprite_root()
	_make_hud()

	print("replay loaded: %s" % replay_path)
	print("  scene=%s seed=%d frames=%d win=%s" % [
		str(rep["meta"]["scene"]), int(rep["meta"]["seed"]),
		frames.size(), str(rep["meta"]["won"])])
	print("  sprite_root=%s" % sprite_root)


# ------------------------------------------------------------------ 路径 / 载入
func _env_float(name: String, dflt: float) -> float:
	var v := OS.get_environment(name)
	return float(v) if v != "" else dflt


func _project_dir() -> String:
	return ProjectSettings.globalize_path("res://")


func _resolve_replay_path() -> String:
	var env := OS.get_environment("PVZ_REPLAY")
	if env != "":
		return env
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--replay="):
			return a.substr("--replay=".length())
	return _project_dir().path_join("../replays/m1_day_10w_s1000.json").simplify_path()


func _resolve_sprite_root() -> void:
	var env := OS.get_environment("PVZ_SPRITES")
	if env != "":
		sprite_root = env
	else:
		sprite_root = _project_dir().path_join("../anim_demo/assets/sprites").simplify_path()


func _load_replay(path: String) -> void:
	if not FileAccess.file_exists(path):
		push_error("replay not found: " + path)
		set_process(false)
		return
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("cannot open replay: " + path)
		set_process(false)
		return
	var parsed: Variant = JSON.parse_string(f.get_as_text())
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("replay is not valid JSON object")
		set_process(false)
		return
	rep = parsed
	frames = rep["frames"]
	anim = rep["anim"]
	units = rep["units"]

	var meta: Dictionary = rep["meta"]
	rows = int(meta.get("rows", 5))
	cols = int(meta.get("cols", 9))
	var layout: Dictionary = meta.get("layout", {})
	cell = float(layout.get("cell_px", 76))
	top_h = float(layout.get("top_h", 96))
	gutter = float(layout.get("gutter_px", 34))


# ------------------------------------------------------------------ 素材
func _texture_for(key: String) -> Texture2D:
	var u: Dictionary = units.get(key, {})
	var kind := str(u.get("kind", "plant"))
	var rel := ("enemies/" if kind == "enemy" else "") + key + ".png"
	var path := sprite_root.path_join(rel)

	if tex_cache.has(path):
		return tex_cache[path]
	if not FileAccess.file_exists(path):
		missing_sprites[path] = true
		tex_cache[path] = null
		return null
	var img := Image.load_from_file(path)
	if img == null:
		missing_sprites[path] = true
		tex_cache[path] = null
		return null
	var tex := ImageTexture.create_from_image(img)
	tex_cache[path] = tex
	return tex


func _frames_for(key: String) -> SpriteFrames:
	if sf_cache.has(key):
		return sf_cache[key]
	var tex := _texture_for(key)
	if tex == null:
		sf_cache[key] = null
		return null
	var sf := SpriteLibrary.build_frames(tex, anim)
	sf_cache[key] = sf
	return sf


func _ensure_view(uid: int, key: String) -> AnimatedSprite2D:
	if views.has(uid):
		return views[uid]
	var sf := _frames_for(key)
	if sf == null:
		return null
	var v := AnimatedSprite2D.new()
	v.sprite_frames = sf
	v.centered = false
	# 每一格 64px，角色在格内底部对齐且离格底留 4px，故整体下移 4px 让脚落地
	v.offset = Vector2(-32.0, -60.0)
	var u: Dictionary = units.get(key, {})
	var kind := str(u.get("kind", "plant"))
	var s: float = cell / 64.0 * (1.06 if kind == "enemy" else 0.94)
	v.scale = Vector2(s, s)
	v.set_meta("base_state", "walk" if kind == "enemy" else "idle")
	v.play("idle")
	v.animation_finished.connect(_on_anim_finished.bind(v))
	add_child(v)
	views[uid] = v
	return v


func _on_anim_finished(v: AnimatedSprite2D) -> void:
	var base := str(v.get_meta("base_state", "idle"))
	if v.animation != base:
		v.play(base)


# ------------------------------------------------------------------ HUD
func _make_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	hud = Label.new()
	hud.position = Vector2(8.0, 6.0)
	hud.add_theme_font_size_override("font_size", 16)
	hud.add_theme_color_override("font_color", Color(0.09, 0.16, 0.09))
	layer.add_child(hud)


func _update_hud() -> void:
	if hud == null:
		return
	var sc := str(rep["meta"]["scene"])
	hud.text = "%s  seed=%d   t=%5.1fs   sun=%d   lives=%d   %s" % [
		sc, int(rep["meta"]["seed"]), t, sun, lives,
		"(finished)" if done else ""]


# ------------------------------------------------------------------ 主循环
func _process(delta: float) -> void:
	if done or frames.is_empty():
		return
	t += delta * speed

	var n := frames.size()
	while idx + 1 < n and float(frames[idx + 1]["t"]) <= t:
		idx += 1

	if idx >= n - 1:
		_apply(n - 1, n - 1, 0.0)
		done = true
		_finish()
		return

	var ta := float(frames[idx]["t"])
	var tb := float(frames[idx + 1]["t"])
	end_tb = tb
	var alpha: float = 0.0 if tb <= ta else clampf((t - ta) / (tb - ta), 0.0, 1.0)

	_apply(idx, idx + 1, alpha)
	_update_hud()
	queue_redraw()


func _finish() -> void:
	_update_hud()
	print("playback finished at t=%.1fs  sun=%d lives=%d" % [t, sun, lives])
	if not missing_sprites.is_empty():
		print("WARNING: %d sprite(s) missing, first: %s" % [
			missing_sprites.size(), str(missing_sprites.keys()[0])])
	if autoquit:
		get_tree().quit()


func _apply(ia: int, ib: int, alpha: float) -> void:
	var fa: Dictionary = frames[ia]
	var fb: Dictionary = frames[ib]

	var prev_enemy := {}
	for d in fa["e"]:
		prev_enemy[int(d[0])] = d

	var seen := {}
	# --- 敌人
	for d in fb["e"]:
		var uid := int(d[0])
		seen[uid] = true
		var v := _ensure_view(uid, str(d[3]))
		if v == null:
			continue
		var x_current := float(d[2])
		var x_prev := x_current
		if prev_enemy.has(uid):
			x_prev = float(prev_enemy[uid][2])
		var x := lerpf(x_prev, x_current, alpha)
		v.position = Vector2(gutter + (x + 0.4) * cell, top_h + float(d[1]) * cell + cell - 6.0)
		if int(d[6]) == 1:
			if v.animation != "attack":
				v.play("attack")
		elif v.animation != "walk":
			v.play("walk")

	# --- 植物
	var prev_plant := {}
	for d in fa["p"]:
		prev_plant[int(d[0])] = d

	for d in fb["p"]:
		var uid := int(d[0])
		seen[uid] = true
		var v := _ensure_view(uid, str(d[3]))
		if v == null:
			continue
		v.position = Vector2(gutter + (float(d[2]) + 0.5) * cell,
			top_h + float(d[1]) * cell + cell - 6.0)
		var shots := int(d[5]) if d.size() > 5 else 0
		var shots_prev := shots
		if prev_plant.has(uid) and prev_plant[uid].size() > 5:
			shots_prev = int(prev_plant[uid][5])
		if shots > shots_prev and v.animation != "attack":
			v.play("attack")

	# --- 回收已消失的单位
	for uid in views.keys():
		if not seen.has(uid):
			views[uid].queue_free()
			views.erase(uid)

	# --- 弹道：等速直飞，用"当前帧位置 - 速度 × 剩余时间"反推，比逐帧跳格平滑
	proj_draw.clear()
	var dt_remaining: float = maxf(0.0, end_tb - t)
	for pr in fb["b"]:
		var x_cells := float(pr[1]) - float(pr[3]) * dt_remaining
		proj_draw.append([int(pr[0]), x_cells])

	mowers = fb["m"]
	sun = int(fb["sun"])
	lives = int(fb["lives"])


# ------------------------------------------------------------------ 绘制
func _draw() -> void:
	for r in range(rows):
		for c in range(cols):
			var col := COL_A if (r + c) % 2 == 0 else COL_B
			var rect := Rect2(gutter + c * cell, top_h + r * cell, cell, cell)
			draw_rect(rect, col, true)
			draw_rect(rect, COL_LINE, false, 1.0)

	# 小车（该行还有小车时画在左端）
	for r in range(mini(rows, mowers.size())):
		if int(mowers[r]) == 1:
			var y := top_h + r * cell + cell * 0.5
			draw_circle(Vector2(gutter * 0.5, y), 9.0, COL_MOWER)

	for pd in proj_draw:
		var y2 := top_h + float(pd[0]) * cell + cell * 0.45
		draw_circle(Vector2(gutter + float(pd[1]) * cell, y2), 4.0, COL_PROJ)

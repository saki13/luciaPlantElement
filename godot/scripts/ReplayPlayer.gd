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

const COL_A := Color(0.494, 0.769, 0.373)          # 草地浅格
const COL_B := Color(0.451, 0.725, 0.337)          # 草地深格
const COL_SEAM := Color(0.25, 0.44, 0.19, 0.28)    # 行/列接缝（替代刺眼白线）
const COL_BORDER := Color(0.22, 0.38, 0.17, 0.90)  # 场地外框
const COL_DIRT := Color(0.451, 0.361, 0.263)       # 左侧小车通道
const COL_DIRT_D := Color(0.349, 0.275, 0.196)
const COL_PANEL_BG := Color(0.949, 0.941, 0.871)   # 顶部卡栏底板
const COL_PANEL_EDGE := Color(0.647, 0.627, 0.514, 0.9)
const COL_PROJ := Color(0.18, 0.32, 0.12)
const COL_MOWER := Color(0.85, 0.25, 0.22)

var rep: Dictionary = {}
var frames: Array = []
var anim: Dictionary = {}
var units: Dictionary = {}
var cell: float = 76.0
var top_h: float = 96.0
var gutter: float = 34.0

# 视觉资源（全部由 Godot 内置资源程序化生成，零外部素材、零授权风险）
var grass_tex: Texture2D          # FastNoiseLite 生成的草地明暗斑
var shadow_tex: Texture2D         # GradientTexture2D 径向渐变做的柔和投影
var panel_tex: Texture2D          # 顶部卡栏的竖向渐变
var panel_shadow_tex: Texture2D   # 面板压在草坪上的窄投影
var shadow_draw: Array = []       # 每帧 [x_px, ground_y_px, width]
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
var font: Font
var missing_sprites: Dictionary = {}

# 截图通道（PVZ_SHOT=<png 路径>，PVZ_SHOT_AT=<播放到第几秒截>）
var _shot_path := ""
var _shot_at := 2.0
var _shot_done := false


func _ready() -> void:
	speed = _env_float("PVZ_SPEED", 1.0)
	autoquit = OS.get_environment("PVZ_AUTOQUIT") == "1"
	_shot_path = OS.get_environment("PVZ_SHOT")
	_shot_at = _env_float("PVZ_SHOT_AT", 2.0)

	var replay_path := _resolve_replay_path()
	_load_replay(replay_path)
	_resolve_sprite_root()
	_build_visual_resources()
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


# ------------------------------------------------------------------ 视觉资源
## 草地明暗斑：FastNoiseLite 直接烧进一张小图，铺满整块草地（不平铺，避免接缝）
func _make_grass_tex() -> Texture2D:
	var n := FastNoiseLite.new()
	n.noise_type = FastNoiseLite.TYPE_SIMPLEX_SMOOTH
	n.seed = 20261104
	n.frequency = 0.045
	n.fractal_octaves = 3
	var size := 96
	var img := Image.create(size, size, false, Image.FORMAT_RGBA8)
	for y in range(size):
		for x in range(size):
			var v := n.get_noise_2d(float(x), float(y))
			var a := clampf(v * 0.5 + 0.5, 0.0, 1.0)
			img.set_pixel(x, y, Color(0.0, 0.0, 0.0, a * a * 0.30))
	return ImageTexture.create_from_image(img)


## 柔和投影：径向渐变（中心不透明 → 边缘透明），拉伸成椭圆当影子用
func _make_shadow_tex() -> Texture2D:
	var g := Gradient.new()
	g.set_color(0, Color(0.0, 0.0, 0.0, 0.42))
	g.set_color(1, Color(0.0, 0.0, 0.0, 0.0))
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_RADIAL
	gt.fill_from = Vector2(0.5, 0.5)
	gt.fill_to = Vector2(1.0, 0.5)
	gt.width = 64
	gt.height = 64
	return gt


func _build_visual_resources() -> void:
	texture_repeat = CanvasItem.TEXTURE_REPEAT_ENABLED
	font = ThemeDB.fallback_font
	grass_tex = _make_grass_tex()
	shadow_tex = _make_shadow_tex()
	panel_tex = _make_vertical_gradient(
		Color(0.973, 0.965, 0.902), Color(0.886, 0.878, 0.788))
	panel_shadow_tex = _make_vertical_gradient(
		Color(0.0, 0.0, 0.0, 0.22), Color(0.0, 0.0, 0.0, 0.0))


func _make_vertical_gradient(top: Color, bottom: Color) -> Texture2D:
	var g := Gradient.new()
	g.set_color(0, top)
	g.set_color(1, bottom)
	var gt := GradientTexture2D.new()
	gt.gradient = g
	gt.fill = GradientTexture2D.FILL_LINEAR
	gt.fill_from = Vector2(0.0, 0.0)
	gt.fill_to = Vector2(0.0, 1.0)
	gt.width = 4
	gt.height = 64
	return gt


# ------------------------------------------------------------------ HUD
func _make_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	hud = Label.new()
	hud.position = Vector2(92.0, top_h + rows * cell + 6.0)
	hud.add_theme_font_size_override("font_size", 14)
	hud.add_theme_color_override("font_color", Color(0.30, 0.34, 0.26))
	layer.add_child(hud)


func _update_hud() -> void:
	if hud == null:
		return
	var sc := str(rep["meta"]["scene"])
	hud.text = "%s   seed=%d   t=%5.1fs%s" % [
		sc, int(rep["meta"]["seed"]), t, "   (finished)" if done else ""]


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

	if _shot_path != "" and not _shot_done and t >= _shot_at:
		_shot_done = true
		_capture_and_quit()


func _capture_and_quit() -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var err := img.save_png(_shot_path)
	print("shot saved: %s (err=%d)" % [_shot_path, err])
	get_tree().quit()


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
	shadow_draw.clear()
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
		shadow_draw.append([v.position.x, v.position.y, cell * 0.92])
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
		shadow_draw.append([v.position.x, v.position.y, cell * 0.74])
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
	var bx := gutter
	var by := top_h
	var bw := cols * cell
	var bh := rows * cell

	# 顶部卡栏底板（竖向渐变）+ 分隔线
	draw_rect(Rect2(0, 0, gutter + bw, top_h), COL_PANEL_BG, true)
	if panel_tex != null:
		draw_texture_rect(panel_tex, Rect2(0, 0, gutter + bw, top_h), false)
	draw_line(Vector2(0, top_h), Vector2(gutter + bw, top_h), COL_PANEL_EDGE, 2.0)

	# 草地两色格
	for r in range(rows):
		for c in range(cols):
			var col := COL_A if (r + c) % 2 == 0 else COL_B
			draw_rect(Rect2(bx + c * cell, by + r * cell, cell, cell), col, true)

	# 草地明暗斑（铺满整块，不平铺，无接缝）
	if grass_tex != null:
		draw_texture_rect(grass_tex, Rect2(bx, by, bw, bh), false)

	# 接缝：细、暗、低对比（替代原来的白线）
	for r in range(1, rows):
		var sy := by + r * cell
		draw_line(Vector2(bx, sy), Vector2(bx + bw, sy), COL_SEAM, 1.0)
	for c in range(1, cols):
		var sx := bx + c * cell
		draw_line(Vector2(sx, by), Vector2(sx, by + bh), COL_SEAM, 1.0)

	# 左侧小车通道：泥土带
	draw_rect(Rect2(0, by, gutter, bh), COL_DIRT, true)
	if grass_tex != null:
		draw_texture_rect(grass_tex, Rect2(0, by, gutter, bh), false)
	draw_line(Vector2(gutter, by), Vector2(gutter, by + bh), COL_DIRT_D, 2.0)

	# 场地外框
	draw_rect(Rect2(bx, by, bw, bh), COL_BORDER, false, 2.0)

	# 面板压在草坪上的窄投影，避免"贴上去"的割裂感
	if panel_shadow_tex != null:
		draw_texture_rect(panel_shadow_tex, Rect2(bx, by, bw, 10.0), false)

	# 卡栏：按回放的 card_pool 画出可用卡片（图标 + 阳光价，阳光不足则变灰）
	var pool: Array = rep.get("meta", {}).get("card_pool", [])
	if not pool.is_empty() and font != null:
		var n := pool.size()
		var gap := 6.0
		var card_w := minf(64.0, (bw - 24.0 - (n - 1) * gap) / float(n))
		var card_h := top_h - 20.0
		var total := n * card_w + (n - 1) * gap
		var x0 := bx + (bw - total) * 0.5
		for i in range(n):
			var key := str(pool[i])
			var cx := x0 + i * (card_w + gap)
			var cy := 10.0
			var cost := float(units.get(key, {}).get("sun", 0))
			var afford := float(sun) >= cost
			draw_rect(Rect2(cx, cy, card_w, card_h),
				Color(0.996, 0.988, 0.941) if afford else Color(0.847, 0.847, 0.816), true)
			draw_rect(Rect2(cx, cy, card_w, card_h),
				Color(0.514, 0.478, 0.353, 0.95) if afford else Color(0.6, 0.6, 0.58, 0.9),
				false, 1.5)

			var sf := _frames_for(key)
			if sf != null and sf.has_animation("idle"):
				var icon := sf.get_frame_texture("idle", 0)
				if icon != null:
					var s := card_w - 10.0
					draw_texture_rect(icon, Rect2(cx + 5.0, cy + 3.0, s, s), false,
						Color(1, 1, 1, 1) if afford else Color(1, 1, 1, 0.55))

			draw_string(font, Vector2(cx + 4.0, cy + card_h - 4.0), "%d" % int(cost),
				HORIZONTAL_ALIGNMENT_LEFT, -1, 13,
				Color(0.13, 0.24, 0.09) if afford else Color(0.45, 0.45, 0.44))

	# 单位落地投影（父节点 _draw 先于子节点渲染，所以自然压在精灵下面）
	if shadow_tex != null:
		for sd in shadow_draw:
			var w := float(sd[2])
			var h := w * 0.42
			draw_texture_rect(shadow_tex,
				Rect2(float(sd[0]) - w * 0.5, float(sd[1]) - h * 0.5, w, h), false)

	# 小车：红轮 + 黄毂
	for r in range(mini(rows, mowers.size())):
		if int(mowers[r]) == 1:
			var cy := top_h + r * cell + cell * 0.5
			var cx := gutter * 0.5
			draw_circle(Vector2(cx, cy), 10.0, COL_MOWER)
			draw_circle(Vector2(cx, cy), 6.0, Color(0.97, 0.80, 0.28))
			draw_circle(Vector2(cx, cy), 2.5, Color(0.28, 0.19, 0.14))

	# 弹道：白色描边一圈，保证在草地上可读
	for pd in proj_draw:
		var py := top_h + float(pd[0]) * cell + cell * 0.45
		var px := gutter + float(pd[1]) * cell
		draw_circle(Vector2(px, py), 5.0, Color(1.0, 1.0, 1.0, 0.55))
		draw_circle(Vector2(px, py), 4.0, COL_PROJ)

	# 底部状态栏（画在最后，盖住越界的落地投影）
	var bar_y := by + bh
	var bar_h := 26.0
	draw_rect(Rect2(0, bar_y, gutter + bw, bar_h), COL_PANEL_BG, true)
	if panel_tex != null:
		draw_texture_rect(panel_tex, Rect2(0, bar_y, gutter + bw, bar_h), false)
	draw_line(Vector2(0, bar_y), Vector2(gutter + bw, bar_y), COL_PANEL_EDGE, 2.0)

	var cy2 := bar_y + bar_h * 0.5
	# 左下：阳光
	draw_circle(Vector2(18.0, cy2), 9.0, Color(0.984, 0.827, 0.286))
	draw_circle(Vector2(18.0, cy2), 9.0, Color(0.816, 0.627, 0.145), false, 1.5)
	if font != null:
		draw_string(font, Vector2(31.0, cy2 + 5.0), "%d" % sun, HORIZONTAL_ALIGNMENT_LEFT,
			-1, 15, Color(0.13, 0.24, 0.09))

	# 右下：剩余小车（= 剩余生命）
	for i in range(maxi(0, lives)):
		var lx := gutter + bw - 16.0 - i * 18.0
		draw_circle(Vector2(lx, cy2), 7.0, COL_MOWER)
		draw_circle(Vector2(lx, cy2), 4.0, Color(0.97, 0.80, 0.28))
		draw_circle(Vector2(lx, cy2), 1.8, Color(0.28, 0.19, 0.14))

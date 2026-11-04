class_name SpriteLibrary
extends RefCounted

## 把"4x4 / 64px / 行序 idle-walk-attack-hurt / 有效帧 2-4-3-2"这套既有精灵表约定
## 转成 Godot 的 SpriteFrames。约定参数由回放文件里的 anim 段提供，这里不写死。

static func build_frames(tex: Texture2D, anim: Dictionary) -> SpriteFrames:
	var sf := SpriteFrames.new()
	if sf.has_animation("default"):
		sf.remove_animation("default")

	var fp: int = int(anim.get("frame_px", 64))

	for state_v in anim["order"]:
		var state := str(state_v)
		var row: int = int(anim["rows"][state])
		var count: int = int(anim["frames"][state])
		var ms: float = float(anim["frame_ms"][state])
		var loops: bool = bool(anim["loop"][state])

		sf.add_animation(state)
		sf.set_animation_loop(state, loops)
		# Godot 的 speed 是"每秒帧数"，我们的约定是"每帧毫秒"
		sf.set_animation_speed(state, 1000.0 / ms)

		for i in range(count):
			var at := AtlasTexture.new()
			at.atlas = tex
			at.region = Rect2(i * fp, row * fp, fp, fp)
			sf.add_frame(state, at)

	return sf

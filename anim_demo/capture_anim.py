# Headless 验证 + 逐状态出图（SDL dummy），不弹窗。
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import sys
HERE = r"D:\lucia\rea\project\pvz\anim_demo"
sys.path.insert(0, HERE)
sys.path.insert(0, r"D:\lucia\rea\project\pvz\libs")
import pygame
from sprite_animation_demo import Demo, SHEET_PATH
from animation import ANIM_DEF

OUT = r"D:\lucia\rea\project\pvz\logs"
demo = Demo()
assert os.path.exists(SHEET_PATH), "占位精灵表应已生成"
print("sheet generated:", SHEET_PATH)
for name, (_, cols, _, loop) in ANIM_DEF.items():
    assert len(demo.sheet.frames[name]) == cols
    assert len(demo.sheet.flash[name]) == cols
print("frame counts OK:", {k: len(v) for k, v in demo.sheet.frames.items()})


def shot(fname):
    demo.draw()
    pygame.image.save(demo.screen, os.path.join(OUT, fname))


# idle 呼吸
for _ in range(10):
    demo.update(16)
shot("anim-idle.png")

# walk 向右（切帧 + 翻转朝向）
demo.hero.play("walk", force=True)
demo.hero.facing = 1
for _ in range(14):
    demo.update(16, right=True)
shot("anim-walk.png")
assert demo.hero.facing == 1

# attack：进入突刺帧（frame 1）后再推进几帧，等弹性形变到达峰值再采样
demo.hero.play("idle", force=True)
demo.hero.attack()
ticks_in_frame1 = 0
for _ in range(40):
    demo.update(16)
    if demo.hero.state == "attack" and demo.hero.frame_idx == 1:
        ticks_in_frame1 += 1
        if ticks_in_frame1 == 5:
            break
assert ticks_in_frame1 > 0 and demo.hero.sy > 1.05, "攻击突刺帧应纵向拉伸"
shot("anim-attack.png")
for _ in range(20):
    demo.update(16)
assert demo.hero.state == "idle", "单次攻击结束应自动回 idle"

# hurt：闪白 + 后仰
demo.hero.hurt()
demo.update(16)
assert demo.hero.flash_timer > 0 and demo.hero.state == "hurt"
shot("anim-hurt.png")
for _ in range(30):
    demo.update(16)
assert demo.hero.state == "idle"

# 热重载：重新加载同一精灵表不报错且帧仍可用
demo.reload_sheet()
demo.update(16)
shot("anim-reload.png")
pygame.quit()
print("ANIMATION CAPTURE + ASSERTIONS PASSED")

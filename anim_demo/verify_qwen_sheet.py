# Headless 验证：AI 立绘拼成的精灵表在动画框架里的动效。
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import sys
HERE = r"D:\lucia\rea\project\pvz\anim_demo"
sys.path.insert(0, HERE)
sys.path.insert(0, r"D:\lucia\rea\project\pvz\libs")
import pygame
from sprite_animation_demo import Demo
from animation import SpriteSheet

QWEN = os.path.join(HERE, "assets", "sprites", "blob_qwen.png")
OUT = r"D:\lucia\rea\project\pvz\logs"
demo = Demo()
demo.reload_sheet.__self__  # noqa
demo.hero.reload(SpriteSheet(QWEN))          # 换成 AI 精灵表
assert os.path.getsize(QWEN) > 0


def shot(name):
    demo.draw()
    pygame.image.save(demo.screen, os.path.join(OUT, name))


for _ in range(8):
    demo.update(16)
shot("qwen-idle.png")

# walk 多帧：强制走路并向右推进，截到非 0 帧，确认真的在切姿态
demo.hero.play("walk", force=True)
demo.hero.facing = 1
for _ in range(12):
    demo.update(16, right=True)
assert demo.hero.state == "walk" and demo.hero.frame_idx in (1, 2, 3)
shot("qwen-walk.png")
demo.hero.play("idle", force=True)

demo.hero.attack()
n = 0
for _ in range(40):
    demo.update(16)
    if demo.hero.state == "attack" and demo.hero.frame_idx == 1:
        n += 1
        if n == 5:
            break
assert demo.hero.sy > 1.05
shot("qwen-attack.png")

demo.hero.hurt()
demo.update(16)
assert demo.hero.flash_timer > 0
shot("qwen-hurt.png")
pygame.quit()
print("QWEN SHEET IN-FRAME ANIMATION PASSED")

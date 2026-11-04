# Headless 验证：任意植物精灵表在动画框架里的切帧与程序化动效。
# 用法：python verify_plant.py --sheet assets/sprites/bamboo.png --tag bamboo
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import sys
import argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "libs"))
import pygame
from sprite_animation_demo import Demo
from animation import SpriteSheet

OUT = os.path.join(os.path.dirname(HERE), "logs")
ap = argparse.ArgumentParser()
ap.add_argument("--sheet", required=True)
ap.add_argument("--tag", required=True)
a = ap.parse_args()
sheet_path = a.sheet if os.path.isabs(a.sheet) else os.path.join(HERE, a.sheet)
assert os.path.getsize(sheet_path) > 0, sheet_path

demo = Demo()
demo.hero.reload(SpriteSheet(sheet_path))


def shot(name):
    demo.draw()
    pygame.image.save(demo.screen, os.path.join(OUT, f"{a.tag}-{name}.png"))


for _ in range(8):
    demo.update(16)
shot("idle")

# walk 槽在植物上是“茎叶轻摇”，强制进入并推进到非 0 帧验证切帧
demo.hero.play("walk", force=True)
demo.hero.facing = 1
for _ in range(12):
    demo.update(16, right=True)
assert demo.hero.state == "walk" and demo.hero.frame_idx in (1, 2, 3)
shot("walk")
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
shot("attack")

demo.hero.hurt()
demo.update(16)
assert demo.hero.flash_timer > 0
shot("hurt")
pygame.quit()
print(f"PLANT SHEET OK: {a.tag} <- {sheet_path}")

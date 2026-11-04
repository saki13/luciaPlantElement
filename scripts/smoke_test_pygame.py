# Headless smoke test for the pygame build (SDL dummy video/audio), no real window.
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import sys
sys.path.insert(0, r"D:\lucia\rea\project\pvz")
sys.path.insert(0, r"D:\lucia\rea\project\pvz\libs")

import tower_defense_pygame as G

game = G.Game(headless=True)
game.res = 100000
for r in range(G.ROWS):
    for col, kind in ((0, "shooter"), (2, "cannon"), (4, "frost")):
        game.selected = kind
        game.handle_click((col * G.CELL + G.CELL // 2, r * G.CELL + G.TOP_H + G.CELL // 2))
expected = G.ROWS * 3
print("towers placed:", len(game.towers), "(expect %d)" % expected)
assert len(game.towers) == expected
assert len(game.waves) == G.TOTAL_WAVES and all(len(w) > 0 for w in game.waves)
print("wave sizes:", [len(w) for w in game.waves])

max_e = max_p = max_pt = 0
DT = 16
for i in range(16000):
    game.update(DT)
    game.draw()  # also exercise the whole render pipeline off-screen
    max_e = max(max_e, len(game.enemies))
    max_p = max(max_p, len(game.projectiles))
    max_pt = max(max_pt, len(game.particles))
    for s in list(game.suns):
        s.dead = True
        game.res += G.SUN_VALUE
    if game.over:
        break

print("wave reached:", game.wave_index + 1, "/", G.TOTAL_WAVES)
print("peak enemies:", max_e, " projectiles:", max_p, " particles:", max_pt)
print("lives:", game.lives, " over:", game.over, " win:", game.win)
assert game.over and game.win is True, "should finish with victory"
assert game.lives > 0
import pygame
pygame.quit()
print("PYGAME SMOKE TEST PASSED")

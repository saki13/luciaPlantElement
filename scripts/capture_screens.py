# Render deterministic screenshots straight from the pygame surface (dummy driver,
# identical pixels to a real window). Saves battle / victory / defeat frames.
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
import sys
sys.path.insert(0, r"D:\lucia\rea\project\pvz")
sys.path.insert(0, r"D:\lucia\rea\project\pvz\libs")
import pygame
import tower_defense_pygame as G

OUT = r"D:\lucia\rea\project\pvz\logs"
game = G.Game(headless=True)
game.res = 100000
for r in range(G.ROWS):
    for col, kind in ((0, "shooter"), (2, "cannon"), (4, "frost")):
        game.selected = kind
        game.handle_click((col * G.CELL + G.CELL // 2, r * G.CELL + G.TOP_H + G.CELL // 2))

battle_saved = False
for _ in range(20000):
    game.update(16)
    game.draw()
    if not battle_saved and len(game.enemies) >= 2 and len(game.projectiles) >= 2 and game.suns:
        pygame.image.save(game.screen, os.path.join(OUT, "pygame-battle.png"))
        battle_saved = True
        print("battle frame saved: enemies=%d projectiles=%d suns=%d"
              % (len(game.enemies), len(game.projectiles), len(game.suns)))
    if game.over:
        break

# victory panel (natural end with full defense)
game.draw()
pygame.image.save(game.screen, os.path.join(OUT, "pygame-victory.png"))
print("victory saved, win=", game.win)

# defeat panel: fresh game then force a loss
g2 = G.Game(headless=True)
g2.lives = 1
g2.end_game(False)
g2.draw()
pygame.image.save(g2.screen, os.path.join(OUT, "pygame-defeat.png"))
print("defeat saved")
pygame.quit()
print("CAPTURE DONE")

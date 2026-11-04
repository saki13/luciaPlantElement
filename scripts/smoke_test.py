# Headless smoke test: drive the game logic without entering mainloop.
import tkinter as tk
import tower_defense_prototype as G

root = tk.Tk()
game = G.Game(root)

# capture after() so the loop does not self-schedule; we drive frames manually
root.after = lambda ms, fn: None

class Evt:
    def __init__(self, x, y):
        self.x, self.y = x, y

# give ample resource, then build a full defensive layout covering every row
game.res = 100000
for r in range(G.ROWS):
    game.selected = "shooter"
    game.on_click(Evt(0 * G.CELL + 40, r * G.CELL + 40))     # col 0
    game.selected = "cannon"
    game.on_click(Evt(2 * G.CELL + 40, r * G.CELL + 40))     # col 2
    game.selected = "frost"
    game.on_click(Evt(4 * G.CELL + 40, r * G.CELL + 40))     # col 4
expected_towers = G.ROWS * 3
print("towers placed:", len(game.towers), "(expect %d)" % expected_towers)
assert len(game.towers) == expected_towers

# verify wave plan
assert len(game.waves) == G.TOTAL_WAVES
assert all(len(w) > 0 for w in game.waves)
print("wave plan OK, sizes:", [len(w) for w in game.waves])

# drive frames (~180s game time); exercise spawn/move/attack/economy
max_enemies = max_proj = 0
for _ in range(6000):
    game.tick()
    max_enemies = max(max_enemies, len(game.enemies))
    max_proj = max(max_proj, len(game.projectiles))
    for s in list(game.suns):
        s.dead = True
        game.res += G.SUN_VALUE

print("wave reached:", game.wave_index + 1, "/", G.TOTAL_WAVES)
print("peak enemies:", max_enemies, " peak projectiles:", max_proj)
print("lives:", game.lives, " game over:", game.over)
assert max_enemies > 0 and max_proj > 0, "combat should have occurred"
assert game.lives > 0, "full-row defense should hold the line"
assert game.over and game.win is True, "should end in victory"
root.destroy()
print("SMOKE TEST PASSED")

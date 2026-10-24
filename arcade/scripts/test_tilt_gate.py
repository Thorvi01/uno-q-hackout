"""Check that a tilt level can't be played until the tilt check passes.
Run from arcade/: python3 scripts/test_tilt_gate.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import levdevil as L  # noqa: E402


class Bridge:
    def call(self, *args, **kwargs):
        return True


LEVEL = {"video": 0, "connected": 7, "buttons": 0, "x": 0, "y": 0, "ax": -15, "ay": -994, "az": 13, "reset": 0}
TILT = next(i for i, level in enumerate(L.LEVELS) if "slider" in level)


def tick(game, n=1, **inputs):
    for i in range(n):
        held = dict(LEVEL, **inputs)
        if i % 2:  # Let go between frames so every A counts as a new press.
            held["buttons"] = 0
        game.tick(held, 1 / 60)
        game.cmds = []


game = L.Game(Bridge())
game.state, game.level = L.PLAYING, TILT
game.load_level()
tick(game)
assert game.state == L.CALIBRATE, game.state
start = (game.x, game.y)

tick(game, 60, buttons=1, x=100)  # Mashing A and running does nothing.
assert game.state == L.CALIBRATE and (game.x, game.y) == start and game.tilt_axis is None

tick(game, 30, connected=3, ax=400)  # Movement unplugged: a tilt can't count.
assert game.state == L.CALIBRATE and game.tilt_axis is None

tick(game, 5)  # Plugged back in, held level...
tick(game, 5, ax=400)  # ...then tilted right: the check passes.
assert game.state == L.PLAYING and game.tilt_axis is not None, (game.state, game.tilt_axis)

tick(game, 30, x=100)
assert game.x > start[0], "running works once the check passed"

x = game.x
tick(game, 30, connected=3, x=100)  # Movement unplugged mid-level: the game waits.
assert game.x == x and not game.playable()

game.new_game()
assert game.tilt_axis is None, "a new game asks for the tilt check again"
print(f"ok  level {TILT + 1}: no play before the tilt check, no A skip, no play without Movement")

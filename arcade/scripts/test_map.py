"""Check the title menu and the map: pick a region and a level, and back out.
Run from arcade/: python3 scripts/test_map.py"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))
import levdevil as L  # noqa: E402
from preview import INVERT_X, INVERT_Y  # noqa: E402


class Bridge:
    def call(self, *args, **kwargs):
        return True


DOWN = -100 if INVERT_Y else 100  # Raw stick value that reads as down after calibration.
IDLE = {"video": 0, "connected": 7, "buttons": 0, "x": 0, "y": 0, "ax": -15, "ay": -994, "az": 13, "reset": 0}


def press(game, **inputs):
    """Hold the input for a frame, then let go."""
    for held in (dict(IDLE, **inputs), IDLE):
        game.tick(held, 1 / 60)
        game.cmds = []


game = L.Game(Bridge())
press(game)
assert game.state == L.READY and game.menu == 0
press(game, y=DOWN)  # Stick down: Map.
assert game.menu == 1
press(game, buttons=1)
assert game.state == L.MAP and game.map_region == 0
press(game, y=DOWN)
press(game, y=DOWN)
assert game.map_pos == 2
press(game, buttons=2)  # B: back to the title.
assert game.state == L.READY
press(game, buttons=1)
press(game, x=-100 if INVERT_X else 100)  # Stick right: the next region.
assert L.REGIONS[game.map_region][0] == "Islands" and game.map_pos == 0
press(game, buttons=1)
assert game.state == L.PLAYING and game.level == L.REGIONS[1][1] and game.in_boat
assert L.region_of(game.level) == ("Islands", 0, 1)

game = L.Game(Bridge())
press(game)
press(game, buttons=1)  # Play starts from level 1.
assert game.state == L.PLAYING and game.level == 0
print(f"ok  map: {len(L.REGIONS)} regions, {len(L.LEVELS)} levels, title menu and back work")

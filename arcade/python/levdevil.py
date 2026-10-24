"""RAGEBAIT: a Level Devil-style troll platformer for the UNO Q console.

Game rules run here in Python; the sketch only draws (game_* Bridge calls).
"""
import math
import random
import struct

import levels
from preview import calibrated

W, H = 480, 320


def rgb(r, g, b):
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


BG = rgb(245, 175, 60)
INK = rgb(25, 15, 10)
SOLID = rgb(70, 40, 20)
SPIKE = rgb(200, 20, 20)
DOOR = rgb(255, 255, 255)
SLIDER = rgb(40, 90, 220)

PW, PH = 14, 18      # player size
GRAVITY = 1400.0     # px/s^2
RUN = 170.0          # px/s
JUMP = 480.0         # px/s upward
MAX_FALL = 700.0     # px/s
JUMP_BUFFER = 0.12   # s; a jump pressed just before landing still counts
STICK_RUN = 40       # calibrated stick units before the player runs
TILT_LEARN = 250     # mg of tilt that answers the "tilt right" check
TILT_SPEED = 0.6     # slider px/s per mg of tilt
TILT_MAX = 220.0     # slider px/s
TILT_DEAD = 40       # mg around the level-start angle that counts as level
TILE = 32            # tile-map levels (levels.py) use 15 x 10 tiles of this size
TRAP_NEAR = 2        # tiles; a hidden spike wakes when the player is this close
FLICKER = 0.4        # s a hidden spike or collapsing floor flickers before it acts
# Levels 6-8 pick a new trap layout every life, and their traps give no warning.
BLINK = 0.1          # s per flicker phase
DEBUG_TRAPS = False  # print every trap state change
DOUBLE_C = 0.4      # s; a second C press within this starts the whole game over
DOORS_CLOSE, DOORS_HOLD, DOORS_OPEN = 0.55, 0.4, 0.55  # s; the level transition, 1.5 s in all
BW, BH = 10, 4         # bullet size
BULLET_SPEED = 150.0   # px/s
CANNON_PERIOD = 1.8    # s between shots of one cannon
DISC_R = 13            # spiked disc radius
DISC_SPEED = {"x": 110.0, "y": 150.0}  # px/s
MOVE_STEP = 2          # px a bullet or disc moves before it is repainted
# Player frames in the sketch's SPRITES table; FLIP mirrors one to face left.
STAND, RUN_CYCLE, JUMP_FRAME, FLIP = 0, (1, 2, 3, 2), 4, 0x80
STRIDE = 8             # px run per animation frame
ENTER_SPEED, ENTER_PAUSE, ENTER_SHUT = 90.0, 0.12, 0.3  # walking into the door, then it shuts
TEETH_H, TEETH_W, CHOMP = 18, 24, 22  # devil jaws: teeth strip, tooth width, chomp gap (px)
EYES_BOTTOM = 112      # the devil's eyes show once its upper jaw covers this row
# Land mines go off the moment you land on one; walking onto one lights a fuse.
MINE_FUSE, BLAST_TIME, DIE_TIME, BLAST_R = 0.4, 0.3, 0.45, 22

# Rects are (x, y, w, h). A trap fires once per life when the player's centre x
# enters "when"; "remove" takes an index into solids. A slider is
# (x, y, w, h, x_min, x_max) and follows the console's tilt.
RECT_LEVELS = [
    {"name": "Easy start", "start": (20, 262), "door": (440, 240, 24, 40),
     "solids": [(0, 280, 230, 40), (230, 280, 70, 40), (300, 280, 180, 40)],
     "spikes": [],
     "traps": [{"when": (190, 480), "do": [("remove", 1)]}]},
    {"name": "Spiky", "start": (20, 262), "door": (440, 240, 24, 40),
     "solids": [(0, 280, 480, 40)],
     "spikes": [(180, 268, 30, 12)],
     "traps": [{"when": (290, 480), "do": [("spike", (330, 268, 40, 12))]},
               {"when": (400, 480), "do": [("door", (20, 240, 24, 40))]}]},
    {"name": "Mind the gap", "start": (20, 262), "door": (445, 240, 24, 40),
     "solids": [(0, 280, 140, 40), (220, 280, 120, 40), (370, 280, 110, 40)],
     "spikes": [],
     "traps": [{"when": (240, 480), "do": [("spike", (300, 268, 20, 12))]}]},
    {"name": "Tilt it", "start": (20, 262), "door": (445, 240, 24, 40),
     "solids": [(0, 280, 110, 40), (400, 280, 80, 40)],
     "spikes": [],
     "slider": (110, 280, 70, 12, 110, 330),
     "traps": [{"when": (410, 480), "do": [("door", (20, 240, 24, 40))]}]},
    {"name": "The devil", "start": (20, 262), "door": (450, 240, 24, 40),
     "solids": [(0, 280, 100, 40), (310, 280, 70, 40), (380, 280, 40, 40), (420, 280, 60, 40)],
     "spikes": [],
     "slider": (100, 280, 60, 12, 100, 250),
     "traps": [{"when": (330, 480), "do": [("remove", 2)]}]},
]



def spike_tile(x, y):
    return (x + 2, y + TILE - 12, TILE - 4, 12)


def door_tile(x, y):
    return (x + 4, y, TILE - 8, TILE)


def from_map(entry):
    """Turn a levels.py tile map into this module's level format."""
    grid, (col, row) = levels.parse(entry["map"])
    level = {"name": entry["name"], "solids": [], "spikes": [], "traps": [], "fakes": [],
             "hidden": [], "crumble": [], "decoys": [], "doors": [], "cannons": [], "ghosts": [], "discs": [], "mines": [],
             "start": (col * TILE + (TILE - PW) // 2, (row + 1) * TILE - PH), "map": True}
    for r, line in enumerate(grid):
        c = 0
        while c < len(line):
            x, y = c * TILE, r * TILE
            if line[c] == "#":  # Merge runs of solid tiles into one rect.
                end = c
                while end < len(line) and line[end] == "#":
                    end += 1
                level["solids"].append((x, y, (end - c) * TILE, TILE))
                c = end
                continue
            if line[c] in "<>":  # A wall tile that fires along its row.
                level["solids"].append((x, y, TILE, TILE))
                level["cannons"].append((x, y, -1 if line[c] == "<" else 1))
            elif line[c] == "m":  # Sits on whatever is below this tile.
                level["mines"].append((x, y + TILE))
            elif line[c] == "i":
                level["ghosts"].append((x, y, TILE, TILE))
            elif line[c] in "oO":  # Runs back and forth over the free tiles on its line.
                dc, dr = (1, 0) if line[c] == "o" else (0, 1)
                lo = hi = 0
                while grid[r - dr * (lo + 1)][c - dc * (lo + 1)] not in "#<>":
                    lo += 1
                while grid[r + dr * (hi + 1)][c + dc * (hi + 1)] not in "#<>":
                    hi += 1
                cx, cy = x + TILE // 2, y + TILE // 2
                axis = "x" if dc else "y"
                centre = cx if dc else cy
                level["discs"].append({"cx": cx, "cy": cy, "axis": axis,
                                       "lo": centre - lo * TILE, "hi": centre + hi * TILE})
            kind = {"^": "spikes", "F": "fakes", "s": "hidden", "v": "crumble", "d": "decoys", "D": "doors"}
            if line[c] in kind:
                maker = {"crumble": lambda x, y: (x, y, TILE, TILE), "decoys": door_tile, "doors": door_tile}
                key = kind[line[c]]
                level[key].append(maker.get(key, spike_tile)(x, y))
            c += 1
    level["door"] = level["doors"].pop(0)
    return level


levels.validate()
# Levels 1-3 rects, 4-6 tile maps, 7-8 tilt, 9-11 tile maps (bullets, invisible steps, discs).
MAPS = [from_map(m) for m in levels.LEVELS]
LEVELS = RECT_LEVELS[:3] + MAPS[:3] + RECT_LEVELS[3:] + MAPS[3:]
MAPS[4]["step_mine"] = True  # Leap of faith: one invisible step carries a mine that blows it away.
for level, kind in zip(LEVELS[5:], ("gate", "tilt", "devil")):
    level["surprise"] = kind

MAX_BATCH = 200  # Drawing bytes per Bridge call; the MCU accepts 256-byte messages.
INPUT_KEYS = ("video", "connected", "buttons", "x", "y", "ax", "ay", "az", "reset")

READY, PLAYING, CALIBRATE, PAUSED, DYING, ENTER, TRANSITION, RESULT = (
    "ready", "playing", "calibrate", "paused", "dying", "enter", "transition", "result")


def overlaps(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def clip(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0) if x1 > x0 and y1 > y0 else None


def disc_hits(box, cx, cy, r):
    nx = min(max(cx, box[0]), box[0] + box[2])
    ny = min(max(cy, box[1]), box[1] + box[3])
    return (nx - cx) ** 2 + (ny - cy) ** 2 < r * r


def ease(t):
    return t * t * (3 - 2 * t)


class Game:
    def __init__(self, bridge):
        self.bridge = bridge
        self.cmds = []  # Drawing queued during a tick, sent with the next frame call.
        self.prev_buttons = 0
        self.clock = 0.0
        self.last_c = -1.0  # clock time of the last C press
        self.connected = None
        self.tilt_axis = None  # Learned on the first tilt level: (index into (ax, ay), sign).
        self.ghost_level = None  # Invisible steps found stay found until the level changes.
        self.new_game()

    def new_game(self):
        self.tilt_axis = None  # Every run starts with the tilt check on the first tilt level.
        self.level = 0
        self.deaths = 0
        self.elapsed = 0.0
        self.state = READY
        self.load_level()

    def load_level(self):
        level = LEVELS[self.level]
        self.solids = list(level["solids"])
        self.spikes = list(level["spikes"])
        self.door = level["door"]
        self.traps = list(level["traps"])
        self.fired = [False] * len(self.traps)
        self.slider = list(level["slider"][:4]) if "slider" in level else None
        self.slider_rect = None
        self.tilt_zero = None  # Set from the first reading of each life.
        self.x, self.y = map(float, level["start"])
        self.vx = self.vy = 0.0
        self.on_ground = self.riding = False
        self.jump_buffer = 0.0
        self.drawn = None  # Player position on screen; None forces a full redraw.
        self.drawn_frame = None
        self.facing, self.run_dist = 1, 0.0
        self.entering, self.shut, self.gone = None, 0, False  # door being walked into
        self.slider_drawn = None
        # Tile-map traps. Collapsing floors are solids until they go.
        self.level_time = 0.0
        self.fakes = level.get("fakes", [])
        self.decoys = level.get("decoys", [])
        self.more_doors = level.get("doors", [])
        self.hidden = [{"kind": "hidden spike", "rect": r, "state": "hidden", "t": 0.0, "shown": False}
                       for r in level.get("hidden", [])]
        self.crumble = []
        for r in level.get("crumble", []):
            self.crumble.append({"kind": "floor", "rect": r, "state": "solid", "t": 0.0, "shown": True,
                                 "index": len(self.solids)})
            self.solids.append(r)
        self.trap_near, self.spike_delay, self.floor_delay = TRAP_NEAR, FLICKER, FLICKER
        self.tilt_flip = False
        # Bullets and discs start at a new point in their cycle every life.
        self.cannons = [{"x": x, "y": y, "dir": d, "phase": random.uniform(0, CANNON_PERIOD), "shots": 0}
                        for x, y, d in level.get("cannons", [])]
        self.bullets = []
        self.discs = [dict(d, phase=random.uniform(0, 2 * (d["hi"] - d["lo"])), drawn=None)
                      for d in level.get("discs", [])]
        for d in self.discs:
            self.place_disc(d)
        self.ghosts = list(level.get("ghosts", []))  # A blown-up step is gone for this life only.
        self.mines = [{"x": x, "s": y, "host": None, "lethal": True, "state": "armed", "t": 0.0}
                      for x, y in level.get("mines", [])]
        if level.get("step_mine"):
            g = random.choice(self.ghosts)
            self.mines.append({"x": g[0], "s": g[1], "host": g, "lethal": False, "state": "armed", "t": 0.0})
        self.blasts = []
        self.die_t = 0.0
        if self.ghost_level != self.level:
            self.ghost_level, self.revealed = self.level, set()
        if "surprise" in level:
            self.surprise(level["surprise"])

    def exchange(self):
        """Send the queued drawing and return fresh inputs: one Bridge call per frame."""
        chunks, chunk = [], b""
        for cmd in self.cmds:
            if len(chunk) + len(cmd) > MAX_BATCH:
                chunks.append(chunk)
                chunk = b""
            chunk += cmd
        chunks.append(chunk)
        self.cmds = []
        # Fail fast so main.py can recover; a full-screen clear gets longer.
        timeout = lambda c: 5 if c[:1] == b"C" else 1
        for c in chunks[:-1]:
            self.bridge.call("game_draw", c, timeout=timeout(c))
        reply = self.bridge.call("game_frame", chunks[-1], timeout=timeout(chunks[-1]))
        return dict(zip(INPUT_KEYS, map(int, reply.split(","))))

    def sprite(self):
        self.cmds.append(struct.pack("<chhBH", b"S", *self.drawn, self.drawn_frame, INK))

    def spike(self, rect):
        """A spike strip drawn as a row of red teeth."""
        x, y, w, h = rect
        self.cmds.append(struct.pack("<chhhhBHH", b"K", x, y, w, h, max(1, round(w / 10)), SPIKE, BG))

    def disc(self, x, y, r, color):
        self.cmds.append(struct.pack("<chhhH", b"O", x, y, r, color))

    def teeth(self, y, up):
        self.cmds.append(struct.pack("<chBBBBHH", b"J", y, TEETH_H, TEETH_W, up,
                                     TEETH_W // 2 if up else 0, DOOR, INK))

    def clear(self, color):
        self.cmds = [struct.pack("<cH", b"C", color)]  # Anything queued before is covered.

    def rect(self, x, y, w, h, color):
        self.cmds.append(struct.pack("<chhhhH", b"R", x, y, w, h, color))

    def text(self, x, y, size, fg, bg, line):
        data = line.encode("ascii", "replace")[:60]
        self.cmds.append(struct.pack("<chhBHHB", b"T", x, y, size, fg, bg, len(data)) + data)

    def tick(self, inputs, dt):
        if inputs.get("reset"):
            self.drawn = None  # The sketch showed its waiting screen.
        stick_x, _, buttons, ax, ay, az, connected = calibrated(inputs)
        pressed = buttons & ~self.prev_buttons  # New presses only.
        self.prev_buttons = buttons
        if connected != self.connected:
            self.connected = connected
            self.drawn = None
        playable = self.playable()
        self.clock += dt
        if pressed & 4:
            if self.clock - self.last_c <= DOUBLE_C or self.state == RESULT:
                self.new_game()  # C twice: start over from level 1.
                self.last_c = -1.0
            else:
                self.last_c = self.clock
                if self.state in (PLAYING, PAUSED, CALIBRATE, DYING):  # C once: retry this level.
                    self.state = PLAYING
                    self.load_level()
        if self.state == ENTER:
            if self.drawn is not None:
                self.run_enter(dt)
                return
            # The screen was reset while walking in: go straight on.
            if self.level + 1 < len(LEVELS):
                self.state, self.doors_loaded = TRANSITION, False
            else:
                self.state = RESULT
        if self.state == TRANSITION:
            if self.drawn is not None:
                self.run_transition(dt)
                return
            # The screen was reset mid-transition: skip to the new level.
            if not self.doors_loaded:
                self.level += 1
                self.load_level()
            self.state = PLAYING
        jump = pressed & 9              # A or the stick press.

        if pressed & 4:
            pass  # Handled above.
        elif self.state == DYING:  # Show the blast, then respawn.
            self.die_t += dt
            if self.die_t >= DIE_TIME:
                self.state = PLAYING
                self.load_level()
        elif self.state == RESULT and pressed & 8:
            self.new_game()
        elif self.state == PAUSED:
            if pressed & 2:  # B resumes.
                self.state = PLAYING
                self.drawn = None
        elif self.state == PLAYING and pressed & 2:  # B pauses.
            self.state = PAUSED
            self.draw_overlay()
        elif self.state == READY and jump and playable:
            self.state = PLAYING
            self.drawn = None
        elif self.state == CALIBRATE:
            self.learn_tilt(ax, ay, connected)
        elif self.state == PLAYING and self.slider and self.tilt_axis is None:
            # First tilt level: no playing until a tilt to the right shows which way is right.
            self.state = CALIBRATE
            self.tilt_base = (ax, ay) if connected & 4 else None
            self.drawn = None
        elif self.state == PLAYING and playable:
            run = 0 if abs(stick_x) < STICK_RUN else (1 if stick_x > 0 else -1)
            tilt = None
            if self.slider:  # Only reached after the tilt check, with Movement connected.
                index, sign = self.tilt_axis
                raw = (ax, ay, az)[index] * sign
                if self.tilt_zero is None:
                    self.tilt_zero = raw  # However the player holds it at the start counts as level.
                tilt = raw - self.tilt_zero
                if abs(tilt) < TILT_DEAD:
                    tilt = 0
            if jump:
                self.jump_buffer = JUMP_BUFFER
            self.step(run, tilt, dt)

        if self.drawn is None:
            self.redraw()
        elif self.state == PLAYING:
            self.draw_slider()
            self.draw_movers()
            self.draw_player()

    def learn_tilt(self, ax, ay, connected):
        """The check can't be skipped: it waits for Movement and a clear tilt to the right."""
        if not connected & 4:
            self.tilt_base = None
            return
        if self.tilt_base is None:
            self.tilt_base = (ax, ay)
            return
        deltas = (ax - self.tilt_base[0], ay - self.tilt_base[1])
        index = 0 if abs(deltas[0]) >= abs(deltas[1]) else 1
        if abs(deltas[index]) < TILT_LEARN:
            return
        self.tilt_axis = (index, 1 if deltas[index] > 0 else -1)
        # The reading from before the tilt is level, not the tilted one.
        self.tilt_zero = self.tilt_base[index] * self.tilt_axis[1]
        self.state = PLAYING
        self.drawn = None

    def playable(self):
        """Running needs the joystick, and a tilt level also needs Movement."""
        c = self.connected or 0
        return bool(c & 2) and (not self.slider or bool(c & 4))

    def box(self):
        return (self.x, self.y, PW, PH)

    def live_solids(self):
        solids = [s for s in self.solids if s] + self.ghosts
        if self.slider:
            self.slider_rect = (round(self.slider[0]), *self.slider[1:])
            solids.append(self.slider_rect)
        return solids

    def move_slider(self, tilt, dt):
        if not self.slider:
            return
        lo, hi = LEVELS[self.level]["slider"][4:]
        speed = 0.0 if tilt is None else max(-TILT_MAX, min(TILT_MAX, tilt * TILT_SPEED))
        x = max(lo, min(hi, self.slider[0] + speed * dt))
        if self.riding:
            self.x += x - self.slider[0]
        self.slider[0] = x

    def step(self, run, tilt, dt):
        self.elapsed += dt
        self.level_time += dt
        self.move_slider(-tilt if self.tilt_flip and tilt else tilt, dt)
        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if self.jump_buffer and self.on_ground:
            self.vy = -JUMP
            self.jump_buffer = 0.0
        self.vx = run * RUN
        if run:
            self.facing = run
        self.vy = min(MAX_FALL, self.vy + GRAVITY * dt)
        solids = self.live_solids()
        was_ground = self.on_ground
        self.on_ground = self.riding = False
        # Small sub-steps so a fast fall cannot pass through a thin platform.
        steps = max(1, math.ceil(max(abs(self.vx), abs(self.vy)) * dt / 4))
        for _ in range(steps):
            self.x = max(0.0, min(W - PW, self.x + self.vx * dt / steps))
            for s in solids:
                if overlaps(self.box(), s):
                    self.x = s[0] - PW if self.vx > 0 else s[0] + s[2]
            self.y += self.vy * dt / steps
            for s in solids:
                if overlaps(self.box(), s):
                    if self.vy > 0:
                        self.y = s[1] - PH
                        self.on_ground = True
                        self.riding = s is self.slider_rect
                    else:
                        self.y = s[1] + s[3]
                    self.vy = 0.0

        if self.on_ground:
            self.run_dist += abs(self.vx) * dt
        self.fire_traps()
        self.update_traps()
        self.update_movers(dt)
        box = self.box()
        touch = (self.x - 1, self.y - 1, PW + 2, PH + 2)
        for g in self.ghosts:
            if g not in self.revealed and overlaps(touch, g):
                self.revealed.add(g)
                self.rect(*g, SOLID)
        self.update_mines(self.on_ground and not was_ground)
        if self.state == DYING:
            return
        hit = any(overlaps(box, self.bullet_rect(b)) for b in self.bullets) or any(
            disc_hits(box, d["x"], d["y"], DISC_R - 1) for d in self.discs)
        if self.y > H or hit or any(overlaps(box, s) for s in self.spikes + self.decoys):
            self.deaths += 1
            self.load_level()
        elif any(overlaps(box, d) for d in [self.door] + self.more_doors):
            # Walk into the door before the next level.
            self.entering = next(d for d in [self.door] + self.more_doors if overlaps(box, d))
            self.state, self.enter_t, self.shut = ENTER, 0.0, 0
            self.vx = self.vy = 0.0
            self.draw_door(self.entering)

    def update_mines(self, landed):
        for m in self.mines:
            if m["state"] == "gone":
                continue
            on = (self.on_ground and abs(self.y + PH - m["s"]) < 0.5
                  and self.x < m["x"] + TILE and m["x"] < self.x + PW)
            if m["state"] == "armed" and on:
                if landed or not m["lethal"]:  # Land on it, and it goes off right then.
                    self.burst(m)
                    continue
                m["state"], m["t"] = "fuse", self.level_time  # Walked on: keep moving.
                self.draw_mine(m)
            elif m["state"] == "fuse" and self.level_time - m["t"] >= MINE_FUSE:
                self.burst(m)
        for b in list(self.blasts):
            if self.level_time - b[2] >= BLAST_TIME:
                self.blasts.remove(b)
                self.repair(b[3])

    def burst(self, m):
        m["state"] = "gone"
        cx, cy = m["x"] + TILE // 2, m["s"] - 6
        self.disc(cx, cy, BLAST_R, SPIKE)
        self.disc(cx, cy, BLAST_R // 2, DOOR)
        area = (cx - BLAST_R, cy - BLAST_R, 2 * BLAST_R + 1, 2 * BLAST_R + 1)
        if m["host"] in self.ghosts:  # The step under the mine is blown away.
            self.ghosts.remove(m["host"])
            hx, hy, hw, hh = m["host"]
            x0, y0 = min(area[0], hx), min(area[1], hy)
            area = (x0, y0, max(area[0] + area[2], hx + hw) - x0, max(area[1] + area[3], hy + hh) - y0)
        self.blasts.append((cx, cy, self.level_time, area))
        if m["lethal"] and overlaps(self.box(), (m["x"] - 8, m["s"] - 48, TILE + 16, 48)):
            self.deaths += 1
            self.state, self.die_t = DYING, 0.0

    def mine_box(self, m):
        return (m["x"] + 8, m["s"] - 9, 16, 9)

    def draw_mine(self, m):
        x, y = m["x"] + 8, m["s"]
        self.rect(x, y - 6, 16, 6, INK)
        self.rect(x + 6, y - 9, 4, 3, DOOR if m["state"] == "fuse" else SPIKE)  # Lit fuse goes white.

    def repair(self, area):
        """Repaint an area from the level as it is now."""
        self.draw_strip(area)
        for s in self.spikes:
            if overlaps(area, s):
                self.spike(s)
        self.draw_decor(area)
        if not self.gone and self.drawn and overlaps(area, (*self.drawn, PW, PH)):
            self.sprite()

    def player_frame(self):
        if not self.on_ground and self.vy:  # A level that just loaded has not landed yet.
            frame = JUMP_FRAME
        elif self.vx:
            frame = RUN_CYCLE[int(self.run_dist / STRIDE) % len(RUN_CYCLE)]
        else:
            frame = STAND
        return frame | (FLIP if self.facing < 0 else 0)

    def run_enter(self, dt):
        """Walk to the middle of the open door, stand, and let it shut on the player."""
        x, y, w, h = self.entering
        tx, ty = x + (w - PW) / 2, y + h - PH
        if abs(self.x - tx) > 0.5 or abs(self.y - ty) > 0.5:
            step = ENTER_SPEED * dt
            dx = max(-step, min(step, tx - self.x))
            self.x += dx
            self.y += max(-step, min(step, ty - self.y))
            self.vx, self.on_ground = dx, True
            if dx:
                self.facing = 1 if dx > 0 else -1
                self.run_dist += abs(dx)
            self.draw_player()
            return
        self.x, self.y, self.vx = tx, ty, 0.0
        self.draw_player()
        self.enter_t += dt
        shut = min(w - 6, round((w - 6) * max(0.0, self.enter_t - ENTER_PAUSE) / ENTER_SHUT))
        if shut > self.shut:
            self.rect(x + 3 + self.shut, y + 3, shut - self.shut, h - 3, DOOR)
            self.shut = shut
        if shut == w - 6:
            self.gone = True
            if self.level + 1 < len(LEVELS):
                self.state = TRANSITION
                self.doors_t, self.doors_k, self.doors_loaded, self.eyes = 0.0, 0, False, False
            else:
                self.state = RESULT
                self.drawn = None

    def fire_traps(self):
        cx = self.x + PW / 2
        for i, trap in enumerate(self.traps):
            lo, hi = trap["when"]
            if self.fired[i] or not lo <= cx <= hi:
                continue
            self.fired[i] = True
            for kind, arg in trap["do"]:
                if kind == "remove":
                    self.rect(*self.solids[arg], BG)
                    self.solids[arg] = None
                elif kind == "solid":
                    self.solids.append(arg)
                    self.rect(*arg, SOLID)
                elif kind == "spike":
                    self.spikes.append(arg)
                    self.spike(arg)
                elif kind == "door":
                    self.rect(*self.door, BG)
                    self.door = arg
                    self.draw_door()
                elif kind == "spike_ahead":  # A spike pops up a short way in front.
                    self.spike_ahead(cx + arg)
                elif kind == "drop_ahead":  # The next floor ahead falls away.
                    ahead = [i for i, s in enumerate(self.solids)
                             if s and s[0] > cx and not overlaps(s, (self.door[0], self.door[1] + self.door[3], self.door[2], 1))]
                    if ahead:
                        i = min(ahead, key=lambda i: self.solids[i][0])
                        self.rect(*self.solids[i], BG)
                        self.solids[i] = None

    def bullet_rect(self, b):
        return (round(b["x"]), b["y"], BW, BH)

    def place_disc(self, d):
        span = d["hi"] - d["lo"]
        s = (self.level_time * DISC_SPEED[d["axis"]] + d["phase"]) % (2 * span)
        pos = d["lo"] + (s if s < span else 2 * span - s)
        d["x"], d["y"] = (round(pos), d["cy"]) if d["axis"] == "x" else (d["cx"], round(pos))

    def update_movers(self, dt):
        for c in self.cannons:
            shots = int((self.level_time + c["phase"]) / CANNON_PERIOD)
            if shots > c["shots"]:
                c["shots"] = shots
                x = c["x"] - BW if c["dir"] < 0 else c["x"] + TILE
                self.bullets.append({"x": float(x), "y": c["y"] + (TILE - BH) // 2, "dir": c["dir"], "drawn": None})
        solids = self.live_solids()
        for b in list(self.bullets):
            b["x"] += b["dir"] * BULLET_SPEED * dt
            r = self.bullet_rect(b)
            if r[0] < 0 or r[0] + BW > W or any(overlaps(r, s) for s in solids):
                self.bullets.remove(b)
                if b["drawn"] is not None:
                    old = (b["drawn"], b["y"], BW, BH)
                    self.rect(*old, BG)
                    self.draw_decor(old)
        for d in self.discs:
            self.place_disc(d)

    def draw_movers(self):
        """Bullets repaint only the strips they move by; discs use the sketch's move command."""
        # Bytes cost ~0.09 ms each on the Bridge link, so all bullets go in one command
        # and a mover is only repainted once it has moved MOVE_STEP px.
        slides, gone = [], []
        for b in self.bullets:
            x, y, old = round(b["x"]), b["y"], b["drawn"]
            if old is not None and abs(x - old) < MOVE_STEP:
                continue
            slides.append(struct.pack("<hhh", -32768 if old is None else old, x, y))
            if old is not None:
                gone.append((b, (old, y, BW, BH) if abs(x - old) >= BW else
                             (old, y, x - old, BH) if x > old else (x + BW, y, old - x, BH)))
            b["drawn"] = x
        if slides:
            self.cmds.append(struct.pack("<cBBBHH", b"B", len(slides), BW, BH, SPIKE, BG) + b"".join(slides))
        for b, area in gone:
            if self.draw_decor(area):  # Crossed a door: put the bullet back on top.
                self.rect(b["drawn"], b["y"], BW, BH, SPIKE)
        box = lambda p: (p[0] - DISC_R, p[1] - DISC_R, 2 * DISC_R + 1, 2 * DISC_R + 1)
        moved = []
        for d in self.discs:
            pos, old = (d["x"], d["y"]), d["drawn"]
            if old is not None and max(abs(pos[0] - old[0]), abs(pos[1] - old[1])) < MOVE_STEP:
                continue
            moved += [(d, box(pos)), (d, box(old or pos))]
            if old is None:
                self.cmds.append(struct.pack("<chhhH", b"O", *pos, DISC_R, SPIKE))
            else:
                self.cmds.append(struct.pack("<chhhhhHH", b"M", *old, *pos, DISC_R, SPIKE, BG))
            d["drawn"] = pos
        for d in self.discs:  # Discs crossing each other: repaint the one that got cut.
            if any(m is not d and overlaps(area, box(d["drawn"])) for m, area in moved):
                self.cmds.append(struct.pack("<chhhH", b"O", *d["drawn"], DISC_R, SPIKE))
        for m in self.mines:
            if m["state"] != "gone" and any(overlaps(area, self.mine_box(m)) for _, area in moved):
                self.draw_mine(m)
        if self.drawn and any(overlaps(area, (*self.drawn, PW, PH)) for _, area in moved):
            if not self.gone:
                self.sprite()  # Keep the player on top of a near miss.

    def spike_ahead(self, x):
        x = round(x)
        for s in self.solids:
            if s and s[0] <= x and x + 20 <= s[0] + s[2] and s[1] >= self.y + PH - 1:
                spike = (x, s[1] - 12, 20, 12)
                if not overlaps(spike, self.door):
                    self.spikes.append(spike)
                    self.spike(spike)
                return

    def surprise(self, kind):
        """A fresh trap layout for this life, so a death can't be memorised."""
        self.spike_delay = self.floor_delay = 0.0  # No warning flicker on these levels.
        if kind == "gate":  # Level 6: which exit is real, where the spikes are, how fast the floor goes.
            self.trap_near = 1.5
            self.floor_delay = random.choice((0.1, 0.15, 0.25))
            if random.random() < 0.5:  # The ground door is real; the top one kills.
                self.door, self.decoys = self.decoys[0], [self.door] + self.decoys[1:]
                # Most of the ground runs under a 1-tile ceiling, so only column 6 can be jumped.
                rects = [spike_tile(6 * TILE, 7 * TILE)]
            else:  # The top door is real; spikes on the ground punish a fall, maybe one by the door.
                rects = [spike_tile(c * TILE, 7 * TILE) for c in random.sample(range(6, 13), random.choice((2, 3)))]
                if random.random() < 0.5:
                    rects.append(spike_tile(11 * TILE, 5 * TILE))
            self.hidden = [{"kind": "hidden spike", "rect": r, "state": "hidden", "t": 0.0, "shown": False}
                           for r in rects]
        elif kind == "tilt":  # Level 7: a short platform, a spike as you land, and the door may run back.
            self.slider[2] = 48
            self.traps = [{"when": (random.uniform(402, 430), 480), "do": [("spike_ahead", random.uniform(30, 46))]}]
            if random.random() < 0.7:
                self.traps.append({"when": (random.uniform(405, 440), 480), "do": [("door", (20, 240, 24, 40))]})
        elif kind == "devil":  # Level 8: shorter platform, the floor drops, a spike pops, tilt may flip.
            self.slider[2] = 44
            self.tilt_flip = random.random() < 0.35
            self.traps = [{"when": (random.uniform(312, 395), 480), "do": [("drop_ahead", None)]}]
            self.traps.append({"when": (random.uniform(320, 400), 480), "do": [("spike_ahead", random.uniform(30, 46))]})
        self.fired = [False] * len(self.traps)

    def set_trap(self, trap, state):
        if DEBUG_TRAPS:
            print(f"trap {trap['kind']} {trap['rect']}: {trap['state']} -> {state} at {self.level_time:.2f}s")
        trap["state"], trap["t"] = state, self.level_time

    def trap_visible(self, trap):
        if trap["state"] == "flicker":
            return int((self.level_time - trap["t"]) / BLINK) % 2 == 0
        return trap["state"] in ("armed", "solid")

    def show_trap(self, trap, color):
        visible = self.trap_visible(trap)
        if visible != trap["shown"]:  # Only tiles whose look changed get redrawn.
            if visible and color == SPIKE:
                self.spike(trap["rect"])
            else:
                self.rect(*trap["rect"], color if visible else BG)
            trap["shown"] = visible

    def update_traps(self):
        t = self.level_time
        cx, cy = self.x + PW / 2, self.y + PH / 2
        for trap in self.hidden:
            x, y, w, h = trap["rect"]
            near = abs(cx - (x + w / 2)) <= self.trap_near * TILE and abs(cy - (y + h / 2)) <= TRAP_NEAR * TILE
            if trap["state"] == "hidden" and near:
                self.set_trap(trap, "flicker")
            elif trap["state"] == "flicker" and t - trap["t"] >= self.spike_delay:
                self.set_trap(trap, "armed")
                self.spikes.append(trap["rect"])
            self.show_trap(trap, SPIKE)
        feet = (self.x, self.y + PH, PW, 1)
        for trap in self.crumble:
            if trap["state"] == "solid" and self.on_ground and overlaps(feet, trap["rect"]):
                self.set_trap(trap, "flicker")
            elif trap["state"] == "flicker" and t - trap["t"] >= self.floor_delay:
                self.set_trap(trap, "gone")
                self.solids[trap["index"]] = None
            self.show_trap(trap, SOLID)

    def draw_door(self, rect=None):
        x, y, w, h = rect = rect or self.door
        self.rect(x, y, w, h, INK)  # An open door is all dark inside.
        if rect != self.entering:
            self.rect(x + 3, y + 3, w - 6, h - 3, DOOR)
        elif self.shut:
            self.rect(x + 3, y + 3, self.shut, h - 3, DOOR)

    def barrels(self):
        return [((x if d < 0 else x + TILE - 10), y + 11, 10, 10) for x, y, d in
                ((c["x"], c["y"], c["dir"]) for c in self.cannons)]

    def draw_decor(self, area=None):
        """Doors, spike look-alikes and cannon barrels; with an area, only those it touches.
        With an area, also bullets and discs on it. Returns whether anything was drawn."""
        drew = False
        for d in [self.door] + self.more_doors + self.decoys:
            if area is None or overlaps(area, d):
                self.draw_door(d)
                drew = True
        shown = [t["rect"] for t in self.hidden if t["shown"]]
        for s in self.fakes + shown:
            if area is None or overlaps(area, s):
                self.spike(s)
                drew = True
        for b in self.barrels():
            if area is None or overlaps(area, b):
                self.rect(*b, INK)
                drew = True
        if area is not None:
            for b in self.bullets:
                if b["drawn"] is not None and overlaps(area, (b["drawn"], b["y"], BW, BH)):
                    self.rect(b["drawn"], b["y"], BW, BH, SPIKE)
            for d in self.discs:
                if d["drawn"] and overlaps(area, (d["drawn"][0] - DISC_R, d["drawn"][1] - DISC_R,
                                                  2 * DISC_R + 1, 2 * DISC_R + 1)):
                    self.cmds.append(struct.pack("<chhhH", b"O", *d["drawn"], DISC_R, SPIKE))
            for m in self.mines:
                if m["state"] != "gone" and overlaps(area, self.mine_box(m)):
                    self.draw_mine(m)
        return drew

    def scene(self):
        """The level as (rect, color) in draw order, for drawing it inside a strip."""
        items = [((0, 0, W, H), BG)] + [(s, SOLID) for s in self.solids if s]
        items += [(g, SOLID) for g in self.revealed if g in self.ghosts]
        items += [(b, INK) for b in self.barrels()]  # Spikes are teeth; repair() adds them.
        for x, y, w, h in [self.door] + self.more_doors + self.decoys:
            items += [((x, y, w, h), INK), ((x + 3, y + 3, w - 6, h - 3), DOOR)]
        if self.slider:
            items.append(((round(self.slider[0]), *self.slider[1:]), SLIDER))
        return items

    def draw_strip(self, area):
        for rect, color in self.scene():
            part = clip(rect, area)
            if part:
                self.rect(*part, color)

    def run_transition(self, dt):
        """A devil eats the screen: jaws close from the top and bottom, chomp twice on the
        next level's name, then open on it."""
        self.doors_t += dt
        t, half = self.doors_t, H // 2
        if t < DOORS_CLOSE:
            self.jaws(round(half * ease(t / DOORS_CLOSE)), None)
        elif not self.doors_loaded:
            self.jaws(half, None)
            self.level += 1
            self.load_level()
            self.doors_loaded = True
            self.drawn = (round(self.x), round(self.y))  # Drawn as the jaws open.
            self.drawn_frame = self.player_frame()
            self.slider_drawn = round(self.slider[0]) if self.slider else None
            for line, y in ((f"Level {self.level + 1}/{len(LEVELS)}", 206), (LEVELS[self.level]["name"], 246)):
                self.text((W - 12 * len(line)) // 2, y, 2, DOOR, SPIKE, line)
        elif t < DOORS_CLOSE + DOORS_HOLD:
            u = (t - DOORS_CLOSE) / DOORS_HOLD
            self.jaws(half - round(CHOMP * abs(math.sin(2 * math.pi * u))), lambda a: self.rect(*a, INK))
        elif t < DOORS_CLOSE + DOORS_HOLD + DOORS_OPEN:
            if self.eyes:
                self.draw_eyes(shut=True)  # Fed: the devil shuts its eyes as it opens up.
            self.jaws(round(half * (1 - ease((t - DOORS_CLOSE - DOORS_HOLD) / DOORS_OPEN))), self.repair)
        else:
            self.jaws(0, self.repair)
            self.draw_hud()
            self.state = PLAYING

    def jaws(self, k, inside):
        """Upper jaw's teeth end at row k, lower jaw's start at H - k. Opening calls
        inside(area) for each strip the jaws uncover."""
        p, T = self.doors_k, TEETH_H
        if k > p:
            a = max(0, p - T)
            if k - T > a:  # Skin over the old teeth and the new rows.
                self.rect(0, a, W, k - T - a, SPIKE)
                self.rect(0, H - k + T, W, k - T - a, SPIKE)
            self.teeth(k - T, 0)
            self.teeth(H - k, 1)
            if not self.eyes and k - T >= EYES_BOTTOM:
                self.draw_eyes()
        elif k < p:
            inside((0, k, W, p - k))
            inside((0, H - p, W, p - k))
            if k > 0:
                self.teeth(k - T, 0)
                self.teeth(H - k, 1)
        self.doors_k = k

    def draw_eyes(self, shut=False):
        self.eyes = not shut
        for cx, look in ((W // 2 - 90, 12), (W // 2 + 90, -12)):
            if shut:
                self.disc(cx, 80, 30, SPIKE)
                self.rect(cx - 26, 84, 52, 6, INK)
            else:
                self.disc(cx, 80, 30, DOOR)
                self.disc(cx + look, 88, 11, INK)
            for i in range(6):  # Angry brow, sloping down toward the nose.
                self.rect(cx - 45 + 14 * i if look > 0 else cx + 31 - 14 * i, 30 + 3 * i, 14, 7, INK)

    def redraw(self):
        self.clear(BG)
        for s in self.solids:
            if s:
                self.rect(*s, SOLID)
        for g in self.ghosts:
            if g in self.revealed:
                self.rect(*g, SOLID)
        for s in self.spikes:
            self.spike(s)
        for trap in self.hidden + self.crumble:
            trap["shown"] = self.trap_visible(trap)
            if not trap["shown"] and trap["state"] == "flicker":
                self.rect(*trap["rect"], BG)  # A flickering floor tile, mid-blink.
        self.draw_decor()
        self.slider_drawn = None
        self.draw_slider()
        for m in self.bullets + self.discs:
            m["drawn"] = None
        self.draw_movers()
        for m in self.mines:  # After the discs, as when a disc rolls past one.
            if m["state"] != "gone":
                self.draw_mine(m)
        for cx, cy, _, _ in self.blasts:
            self.disc(cx, cy, BLAST_R, SPIKE)
            self.disc(cx, cy, BLAST_R // 2, DOOR)
        self.draw_hud()
        self.drawn = (round(self.x), round(self.y))
        self.drawn_frame = self.player_frame()
        if not self.gone:
            self.sprite()
        if self.state not in (PLAYING, DYING) or not self.playable():
            self.draw_overlay()

    def draw_hud(self):
        level = LEVELS[self.level]
        # Tile maps have a solid ceiling, so the HUD goes light on dark there.
        ink, paper = (DOOR, SOLID) if level.get("map") else (INK, BG)
        self.text(4, 4, 2, ink, paper, f"{self.level + 1}/{len(LEVELS)} {level['name']}")
        deaths = f"Deaths {self.deaths}"
        self.text(W - 4 - 12 * len(deaths), 4, 2, ink, paper, deaths)
        if not self.connected & 1:
            self.text(4, 22, 1, ink, paper, "Buttons off: press the stick to jump")

    def draw_overlay(self):
        if not self.connected & 2:
            lines = ["Joystick disconnected", "Check the Qwiic cable.", "Game resumes when it's back"]
        elif self.slider and not self.connected & 4 and self.state in (PLAYING, CALIBRATE):
            lines = ["Movement disconnected", "This level needs tilt.", "Plug the Movement", "module back in."]
        elif self.state == CALIBRATE:
            lines = ["Tilt check", "Tilt the console to", "the RIGHT, then level", "it again to play."]
        elif self.state == PAUSED:
            lines = ["Paused", "B to resume", "C to retry the level", "C twice to start over"]
        elif self.state == READY:
            lines = ["RAGEBAIT", "Reach the door.", "Trust nothing.",
                     "Stick run   A jump", "B pause   C retry", "C twice: start over", "Tilt moves blue floors", "Press A to start"]
        else:
            lines = ["You escaped!", f"Deaths {self.deaths}  Time {self.elapsed:.0f}s",
                     "Press C to play again"]
        height = 40 + 24 * len(lines)
        self.rect(60, 60, 360, height, INK)
        self.rect(63, 63, 354, height - 6, BG)
        for i, line in enumerate(lines):
            self.text(80, 80 + 24 * i, 2, INK, BG, line)

    def draw_player(self):
        pos, frame = (round(self.x), round(self.y)), self.player_frame()
        if self.gone or (pos == self.drawn and frame == self.drawn_frame):
            return
        old = (*self.drawn, PW, PH)
        self.rect(*old, BG)
        self.draw_decor(old)  # Repair doors or fake spikes the player walked through.
        self.drawn, self.drawn_frame = pos, frame
        self.sprite()

    def draw_slider(self):
        if not self.slider:
            return
        x = round(self.slider[0])
        old = self.slider_drawn
        if x == old:
            return
        _, y, w, h = self.slider
        if old is None or abs(x - old) >= w:
            if old is not None:
                self.rect(old, y, w, h, BG)
            self.rect(x, y, w, h, SLIDER)
        elif x > old:  # Erase the trailing strip, paint the leading one.
            self.rect(old, y, x - old, h, BG)
            self.rect(old + w, y, x - old, h, SLIDER)
        else:
            self.rect(x + w, y, old - x, h, BG)
            self.rect(x, y, old - x, h, SLIDER)
        self.slider_drawn = x

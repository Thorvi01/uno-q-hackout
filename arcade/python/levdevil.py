"""Level Devil-style troll platformer for the UNO Q console.

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
TILT_X = (0, 1)      # Fallback (index into (ax, ay, az), sign) if the tilt check is skipped
TILT_LEARN = 250     # mg of tilt that answers the "tilt right" check
TILT_SPEED = 0.6     # slider px/s per mg of tilt
TILT_MAX = 220.0     # slider px/s
TILT_DEAD = 40       # mg around the level-start angle that counts as level
AUTO_SPEED = 70.0    # slider px/s when Movement is unavailable
TILE = 32            # tile-map levels (levels.py) use 15 x 10 tiles of this size
TRAP_NEAR = 2        # tiles; a hidden spike wakes when the player is this close
FLICKER = 0.4        # s a hidden spike or collapsing floor flickers before it acts
# Levels 6-8 pick a new trap layout every life, and their traps give no warning.
BLINK = 0.1          # s per flicker phase
DEBUG_TRAPS = False  # print every trap state change
DOORS_CLOSE, DOORS_HOLD, DOORS_OPEN = 0.55, 0.4, 0.55  # s; the level transition, 1.5 s in all

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
             "hidden": [], "crumble": [], "decoys": [], "doors": [],
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
            kind = {"^": "spikes", "F": "fakes", "s": "hidden", "v": "crumble", "d": "decoys", "D": "doors"}
            if line[c] in kind:
                maker = {"crumble": lambda x, y: (x, y, TILE, TILE), "decoys": door_tile, "doors": door_tile}
                key = kind[line[c]]
                level[key].append(maker.get(key, spike_tile)(x, y))
            c += 1
    level["door"] = level["doors"].pop(0)
    return level


levels.validate()
# The tile maps come after the first three levels; the tilt levels stay last.
LEVELS = RECT_LEVELS[:3] + [from_map(m) for m in levels.LEVELS] + RECT_LEVELS[3:]
for level, kind in zip(LEVELS[5:], ("gate", "tilt", "devil")):
    level["surprise"] = kind

MAX_BATCH = 200  # Drawing bytes per Bridge call; the MCU accepts 256-byte messages.
INPUT_KEYS = ("video", "connected", "buttons", "x", "y", "ax", "ay", "az", "reset")

READY, PLAYING, CALIBRATE, PAUSED, TRANSITION, RESULT = (
    "ready", "playing", "calibrate", "paused", "transition", "result")


def overlaps(a, b):
    return a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and a[1] < b[1] + b[3] and b[1] < a[1] + a[3]


def clip(a, b):
    x0, y0 = max(a[0], b[0]), max(a[1], b[1])
    x1, y1 = min(a[0] + a[2], b[0] + b[2]), min(a[1] + a[3], b[1] + b[3])
    return (x0, y0, x1 - x0, y1 - y0) if x1 > x0 and y1 > y0 else None


def ease(t):
    return t * t * (3 - 2 * t)


class Game:
    def __init__(self, bridge):
        self.bridge = bridge
        self.cmds = []  # Drawing queued during a tick, sent with the next frame call.
        self.prev_buttons = 0
        self.connected = None
        self.tilt_axis = None  # Learned on the first tilt level: (index into (ax, ay), sign).
        self.new_game()

    def new_game(self):
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
        self.slider_dir = 1
        self.tilt_zero = None  # Set from the first reading of each life.
        self.x, self.y = map(float, level["start"])
        self.vx = self.vy = 0.0
        self.on_ground = self.riding = False
        self.jump_buffer = 0.0
        self.drawn = None  # Player position on screen; None forces a full redraw.
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
        playable = bool(connected & 2)  # Running needs the joystick.
        if pressed & 4:  # C starts over from level 1, from anywhere.
            self.new_game()
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
            pass  # Already started over above.
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
            self.learn_tilt(ax, ay, pressed, connected)
        elif self.state == PLAYING and self.slider and connected & 4 and self.tilt_axis is None:
            # First tilt level: ask for a tilt to the right and learn which way is right.
            self.state = CALIBRATE
            self.tilt_base = (ax, ay)
            self.drawn = None
        elif self.state == PLAYING and playable:
            run = 0 if abs(stick_x) < STICK_RUN else (1 if stick_x > 0 else -1)
            tilt = None
            if connected & 4:
                index, sign = self.tilt_axis or TILT_X
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
            self.draw_player()

    def learn_tilt(self, ax, ay, pressed, connected):
        if not connected & 4 or pressed & 1:  # Movement gone, or A skips the check.
            self.tilt_axis = self.tilt_axis or TILT_X
        else:
            deltas = (ax - self.tilt_base[0], ay - self.tilt_base[1])
            index = 0 if abs(deltas[0]) >= abs(deltas[1]) else 1
            if abs(deltas[index]) < TILT_LEARN:
                return
            self.tilt_axis = (index, 1 if deltas[index] > 0 else -1)
            # The reading from before the tilt is level, not the tilted one.
            self.tilt_zero = self.tilt_base[index] * self.tilt_axis[1]
        self.state = PLAYING
        self.drawn = None

    def box(self):
        return (self.x, self.y, PW, PH)

    def live_solids(self):
        solids = [s for s in self.solids if s]
        if self.slider:
            self.slider_rect = (round(self.slider[0]), *self.slider[1:])
            solids.append(self.slider_rect)
        return solids

    def move_slider(self, tilt, dt):
        if not self.slider:
            return
        lo, hi = LEVELS[self.level]["slider"][4:]
        if tilt is None:  # No Movement module: the platform patrols on its own.
            speed = AUTO_SPEED * self.slider_dir
        else:
            speed = max(-TILT_MAX, min(TILT_MAX, tilt * TILT_SPEED))
        x = max(lo, min(hi, self.slider[0] + speed * dt))
        if x == hi:
            self.slider_dir = -1
        elif x == lo:
            self.slider_dir = 1
        if self.riding:
            self.x += x - self.slider[0]
        self.slider[0] = x

    def step(self, run, tilt, dt):
        self.elapsed += dt
        self.level_time += dt
        self.move_slider(tilt, dt)
        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if self.jump_buffer and self.on_ground:
            self.vy = -JUMP
            self.jump_buffer = 0.0
        self.vx = run * RUN
        self.vy = min(MAX_FALL, self.vy + GRAVITY * dt)
        solids = self.live_solids()
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

        self.fire_traps()
        self.update_traps()
        box = self.box()
        if self.y > H or any(overlaps(box, s) for s in self.spikes + self.decoys):
            self.deaths += 1
            self.load_level()
        elif any(overlaps(box, d) for d in [self.door] + self.more_doors):
            if self.level + 1 < len(LEVELS):
                self.state = TRANSITION
                self.doors_t, self.doors_k, self.doors_loaded = 0.0, 0, False
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
                    self.rect(*arg, SPIKE)
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

    def spike_ahead(self, x):
        x = round(x)
        for s in self.solids:
            if s and s[0] <= x and x + 20 <= s[0] + s[2] and s[1] >= self.y + PH - 1:
                spike = (x, s[1] - 12, 20, 12)
                if not overlaps(spike, self.door):
                    self.spikes.append(spike)
                    self.rect(*spike, SPIKE)
                return

    def surprise(self, kind):
        """A fresh trap layout for this life, so a death can't be memorised."""
        self.spike_delay = self.floor_delay = 0.0  # No warning flicker on these levels.
        if kind == "gate":  # Level 6: which exit is real, where the spikes are, how fast the floor goes.
            self.trap_near = 1.5
            self.floor_delay = random.choice((0.15, 0.25, 0.4))
            if random.random() < 0.5:  # The ground door is real; the top one kills.
                self.door, self.decoys = self.decoys[0], [self.door] + self.decoys[1:]
                # Most of the ground runs under a 1-tile ceiling, so only column 6 can be jumped.
                cols = random.choice(([], [6]))
            else:  # The top door is real; spikes on the ground punish a fall.
                cols = random.sample(range(6, 13), random.choice((1, 2)))
            self.hidden = [{"kind": "hidden spike", "rect": spike_tile(c * TILE, 7 * TILE), "state": "hidden",
                            "t": 0.0, "shown": False} for c in cols]
        elif kind == "tilt":  # Level 7: maybe a spike as you land, and the door may run back to the start.
            self.traps = [{"when": (random.uniform(402, 430), 480), "do": [("spike_ahead", random.uniform(30, 46))]}]
            if random.random() < 0.6:
                self.traps.append({"when": (random.uniform(405, 440), 480), "do": [("door", (20, 240, 24, 40))]})
        elif kind == "devil":  # Level 8: the floor ahead drops at a random spot; maybe a spike too.
            self.traps = [{"when": (random.uniform(312, 395), 480), "do": [("drop_ahead", None)]}]
            if random.random() < 0.5:
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
        x, y, w, h = rect or self.door
        self.rect(x, y, w, h, INK)
        self.rect(x + 3, y + 3, w - 6, h - 3, DOOR)

    def draw_decor(self, area=None):
        """Doors and spike look-alikes; with an area, only those it touches."""
        for d in [self.door] + self.more_doors + self.decoys:
            if area is None or overlaps(area, d):
                self.draw_door(d)
        shown = [t["rect"] for t in self.hidden if t["shown"]]
        for s in self.fakes + shown:
            if area is None or overlaps(area, s):
                self.rect(*s, SPIKE)

    def scene(self):
        """The level as (rect, color) in draw order, for drawing it inside a strip."""
        items = [((0, 0, W, H), BG)] + [(s, SOLID) for s in self.solids if s]
        items += [(s, SPIKE) for s in self.spikes + self.fakes]
        for x, y, w, h in [self.door] + self.more_doors + self.decoys:
            items += [((x, y, w, h), INK), ((x + 3, y + 3, w - 6, h - 3), DOOR)]
        if self.slider:
            items.append(((round(self.slider[0]), *self.slider[1:]), SLIDER))
        items.append(((round(self.x), round(self.y), PW, PH), INK))
        return items

    def draw_strip(self, area):
        for rect, color in self.scene():
            part = clip(rect, area)
            if part:
                self.rect(*part, color)

    def run_transition(self, dt):
        """Doors close from the top and bottom, show the next level's name, then open on it."""
        self.doors_t += dt
        t, half = self.doors_t, H // 2
        if t < DOORS_CLOSE:
            self.close_doors(round(half * ease(t / DOORS_CLOSE)))
        elif not self.doors_loaded:
            self.close_doors(half)
            self.level += 1
            self.load_level()
            self.doors_loaded = True
            self.drawn = (round(self.x), round(self.y))  # Drawn as the doors open.
            self.slider_drawn = round(self.slider[0]) if self.slider else None
            for line, y in ((f"Level {self.level + 1}/{len(LEVELS)}", 120), (LEVELS[self.level]["name"], 180)):
                self.text((W - 12 * len(line)) // 2, y, 2, BG, SOLID, line)
        elif t < DOORS_CLOSE + DOORS_HOLD:
            pass
        elif t < DOORS_CLOSE + DOORS_HOLD + DOORS_OPEN:
            self.open_doors(round(half * (1 - ease((t - DOORS_CLOSE - DOORS_HOLD) / DOORS_OPEN))))
        else:
            self.open_doors(0)
            self.draw_hud()
            self.state = PLAYING

    def close_doors(self, k):
        p = self.doors_k
        if k <= p:
            return
        start = max(0, p - 3)  # Repaint the old edge stripe as door.
        self.rect(0, start, W, k - start, SOLID)
        self.rect(0, k - 3, W, 3, INK)
        self.rect(0, H - k, W, k - start, SOLID)
        self.rect(0, H - k, W, 3, INK)
        self.doors_k = k

    def open_doors(self, k):
        p = self.doors_k
        if k >= p:
            return
        self.draw_strip((0, k, W, p - k))
        self.draw_strip((0, H - p, W, p - k))
        if k > 0:
            self.rect(0, k - 3, W, 3, INK)
            self.rect(0, H - k, W, 3, INK)
        self.doors_k = k

    def redraw(self):
        self.clear(BG)
        for s in self.solids:
            if s:
                self.rect(*s, SOLID)
        for s in self.spikes:
            self.rect(*s, SPIKE)
        for trap in self.hidden + self.crumble:
            trap["shown"] = self.trap_visible(trap)
            if not trap["shown"] and trap["state"] == "flicker":
                self.rect(*trap["rect"], BG)  # A flickering floor tile, mid-blink.
        self.draw_decor()
        self.slider_drawn = None
        self.draw_slider()
        self.draw_hud()
        self.drawn = (round(self.x), round(self.y))
        self.rect(*self.drawn, PW, PH, INK)
        if self.state != PLAYING or not self.connected & 2:
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
        elif self.slider and not self.connected & 4:
            self.text(4, 22, 1, ink, paper, "Tilt off: the blue platform moves itself")

    def draw_overlay(self):
        if not self.connected & 2:
            lines = ["Joystick disconnected", "Check the Qwiic cable.", "Game resumes when it's back"]
        elif self.state == CALIBRATE:
            lines = ["Tilt check", "Tilt the console to", "the RIGHT, then level", "it again.  A skips"]
        elif self.state == PAUSED:
            lines = ["Paused", "B to resume", "C to start over"]
        elif self.state == READY:
            lines = ["LEVEL DEVIL", "Reach the door.", "Trust nothing.",
                     "Stick run   A jump", "B pause  C start over", "Tilt moves blue floors", "Press A to start"]
        else:
            lines = ["You escaped!", f"Deaths {self.deaths}  Time {self.elapsed:.0f}s",
                     "Press C to play again"]
        height = 40 + 24 * len(lines)
        self.rect(60, 60, 360, height, INK)
        self.rect(63, 63, 354, height - 6, BG)
        for i, line in enumerate(lines):
            self.text(80, 80 + 24 * i, 2, INK, BG, line)

    def draw_player(self):
        pos = (round(self.x), round(self.y))
        if pos == self.drawn:
            return
        old = (*self.drawn, PW, PH)
        self.rect(*old, BG)
        self.draw_decor(old)  # Repair doors or fake spikes the player walked through.
        self.rect(*pos, PW, PH, INK)
        self.drawn = pos

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

# Level Devil on the UNO Q console

A troll platformer for the UNO Q arcade console, inspired by the browser game Level Devil. Every level asks you to walk to a door, and every level lies about how. A floor drops out, or a spike appears where there wasn't one. When you die you respawn straight away, so the second attempt is about remembering the trick. Levels 4 and 5 add something the original doesn't have: blue platforms you steer by tilting the console.

## How to play

Get the player to the white door on each of the five levels. Your death count and total time show at the end.

| Control | Action |
| --- | --- |
| Joystick left/right | Run |
| A (or joystick press) | Jump |
| Tilt the console left/right | Move the blue platforms (levels 4 and 5) |
| C | Restart the current level; from the end screen, play again |
| B | Not used |

The levels:

1. Easy start. Part of the floor drops out ahead of you.
2. Spiky. You can see the first spike. The second one pops up as you get close, and then the door moves back to where you started.
3. Mind the gap. A spike appears right before a gap, so you have to clear both in one jump.
4. Tilt it. The gap is too wide to jump. Stand on the blue platform and tilt the console to ride it across.
5. The devil. Tilt across, then watch your step.

## When a control is missing

Every frame, the game checks which Modulino modules answered.

- Without the joystick, the game pauses with a message on screen. It picks up again by itself once the joystick answers.
- Without Buttons, a note at the top tells you to press the joystick to jump.
- Without Movement, the blue platforms slide back and forth on their own, and a note says tilt is off.

## Run it

You need the console connected over USB-C, the board online, and adb on your computer (macOS: `brew install --cask android-platform-tools`).

From this `arcade/` folder, the quickest way is one script. It waits for the board, checks its internet and clock, flashes, and then follows the logs:

```sh
sh scripts/go.sh
```

The same steps by hand:

```sh
make flash   # package, copy to the board, compile the sketch, start Python
make logs    # follow Python output (Ctrl+C to leave; the game keeps running)
make stop    # stop the game
```

Or import `zip/uno-q-arcade.zip` into Arduino App Lab under My Apps, then Run. Rebuild it with `make package` after changing the code.

The first run downloads libraries and needs the board's clock to be right. If the build fails with "signature expired: is your system clock set correctly?", fix the board's date first.

## Settings

Display controller, in `sketch/sketch.ino`: `ARCADE_TFT_HX8357D` is `1` for HX8357D (our console) and `0` for RM68140.

Control calibration, in `python/preview.py`:

```python
DEAD_ZONE = 26
INVERT_X = False
INVERT_Y = True
MOVEMENT_ZERO_MG = (50, -75, 1034)
MOVEMENT_DEAD_ZONE_MG = 20
```

Hold the console in your normal playing position and follow "Calibrate Movement" in `README.md` to get your own `MOVEMENT_ZERO_MG`.

Tilt and feel, in `python/levdevil.py`:

| Setting | Meaning |
| --- | --- |
| `TILT_X` | Which acceleration axis tilts the platforms, and its sign. Flip the sign if they move the wrong way. |
| `TILT_SPEED`, `TILT_MAX` | How fast a tilt moves a platform |
| `AUTO_SPEED` | Platform speed when Movement is unplugged |
| `RUN`, `JUMP`, `GRAVITY` | Player feel |
| `STICK_RUN` | How far you push the stick before the player runs |

## How it works

Python on the Linux side owns the game: levels, physics, traps and screens (`python/levdevil.py`, driven by `python/main.py`). The sketch on the microcontroller reads the Modulinos and draws on the TFT. Python asks it to draw through five Bridge calls added to `sketch/sketch.ino`: `game_ping`, `game_clear`, `game_rect`, `game_circle` and `game_text`. Each frame redraws only what moved or changed, usually just the player and sometimes a platform or a trap. The whole screen is redrawn only when a level starts or you die. `game_ping` runs every frame so the sketch's 1.5-second "Waiting for App Lab" screen never cuts in, and it tells Python to redraw if that screen did appear.

Levels are plain data at the top of `levdevil.py`. A trap is a trigger range plus actions: remove a floor, add a spike, add a floor, or move the door. Adding a level means adding one more entry to `LEVELS`.

## Credits

- Game idea: Level Devil, the browser game. This is a fan remake with our own levels and the tilt mechanic.
- Starter code, Bridge setup and hardware guide: [aaishikasb/uno-q-hackout](https://github.com/aaishikasb/uno-q-hackout), Qualcomm Developer Relations.
- Hardware: Arduino UNO Q, Modulino Joystick, Buttons and Movement (the [Arduino UNO Q Arcade Bundle](https://projecthub.arduino.cc/Arduino_Genuino/uno-q-arcade-bundle-b272c5)), and the DIYables 3.5-inch TFT shield.
- Libraries: Arduino_RouterBridge, Arduino_Modulino, DIYables TFT Touch Shield, Adafruit GFX.
- Built by Vineeth Sakhamuru at Build Day with Qualcomm, Northeastern University Silicon Valley, Oct 24, 2026.

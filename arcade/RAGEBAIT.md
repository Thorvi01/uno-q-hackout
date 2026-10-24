# RAGEBAIT

A troll platformer for the UNO Q arcade console. It is inspired by the original Level Devil browser game. Every level asks you to walk to a door, and every level lies about how. A floor drops out, or a row of red teeth appears where there wasn't one. When you die you respawn straight away, so the second attempt is about remembering the trick. Levels 7 and 8 add something the original doesn't have: blue platforms you steer by tilting the console. The levels sit in two regions, Mountains and Mines (11 levels) and Islands (1 so far).

## How to play

Get the player to the white door on each level. Play starts at the first level and runs through both regions. Your death count and total time show at the end.

The title screen has two items, Play and Map. Push the stick up or down to pick one and press A. The map shows one region at a time with its levels listed. Push the stick left or right to change region, up or down to pick a level, and press A to play it. B goes back to the title. Every level is open from the map. A tilt level picked there still asks for the tilt check first.

| Control | Action |
| --- | --- |
| Joystick left/right | Run, or row the boat |
| Joystick up/down | Move through the title menu and the map |
| A (or joystick press) | Jump |
| Tilt the console left/right | Move the blue platforms (levels 7 and 8) |
| B | Pause; B again resumes |
| C | Retry the current level; press twice quickly to start over from level 1 (deaths and time reset) |

Mountains and Mines:

1. Easy start. Part of the floor drops out ahead of you.
2. Spiky. You can see the first spike. The second one pops up as you get close, and then the door moves back to where you started.
3. Mind the gap. A spike appears right before a gap, so you have to clear both in one jump.
4. Not everything bites. One spike is fake and one is hidden until you get close.
5. The floor is a liar. Part of the floor collapses under you, so keep moving.
6. Nothing is what it seems. One door is real and one kills you, and which is which changes every life.
7. Tilt it. The gap is too wide to jump. Stand on the blue platform and tilt the console to ride it across. The first time you reach this level, the game asks you to tilt the console to the right. It uses that to learn which way the Movement module is mounted, so tilting right always moves the platform right. You can't skip the check, and the level won't start until it passes. Every new game asks again.
8. The devil. Tilt across, then watch your step.
9. Dodge this. Wall cannons fire bullets along three rows. Dodge or jump them. A spike sits in the middle of the floor.
10. Leap of faith. Invisible steps over a spike pit lead up to the door. A step shows up once you touch it, and it stays visible after you die on this level. One step, a different one each life, carries a land mine that floats in the air until you find the step under it. Land on it and it blows the step away. Jump again the instant you land, or skip that step.
11. Saw you coming. The hardest level. Red spiked discs roll along the floor and drop from above, and land mines sit on both blocks and on the floor. A mine goes off the moment you land on it. Walk onto one and its light turns white; keep running, because it blows 0.4 s later. The safe landing spots are a few pixels wide. In automated tests, a timing slip of one or two frames anywhere in a winning run kills you about half the time.

Islands:

1. Up the creek. You start sitting in a boat on a blue river. Push the stick and he rows that way. Jump onto the island and the river turns to acid and the boat sinks. Leap for the door on the high ledge and a block pops up under you, but it drops away 0.7 s after you land. The ledge door is fake. Get close and it vanishes, and the real door shows up low down on a rock, with one more block in the middle to get there. Falling in the water or the acid kills you, and dying puts you back in the boat on a blue river.

Levels 6 to 8 pick a new trap layout every time you die, so remembering how you died doesn't help. Their traps give no warning flicker and fire the moment you reach them. Level 6 changes which door is real and where hidden spikes sit. Its floor collapses faster, in 0.1 to 0.25 s. The layouts with the door up top get 2 or 3 hidden floor spikes, and sometimes a hidden spike on the ledge before the door. Level 7's blue platform is narrower, 48 px, so it leaves a gap you have to jump. A spike always pops up as you land, and the door runs back to the start 70% of the time. Level 8's platform is 44 px. The floor ahead always drops and a spike always pops up. In about a third of lives the tilt is reversed. Levels 9 to 11 change bullet and disc timing every life, and level 10 moves its mine. Every layout leaves a way through. Automated runs through the game's own physics beat 40 random layouts of levels 6 and 8 to 11, and 100 of level 7.

When you reach the door, the stick figure walks into the dark doorway and the door shuts behind him. Then a devil eats the screen. Its jaws close from the top and bottom and chomp twice while the next level's name shows on its chin, then open on the new level (1.5 s).

Levels 4 to 6 and 9 to 11 are tile maps in `python/levels.py`, 15 x 10 tiles of 32 px:

| Tile | Meaning |
| --- | --- |
| `#` `.` | Solid, empty |
| `P` `D` | Player start, real exit |
| `^` | Spike, drawn as red teeth |
| `F` | Fake spike: looks like a spike, harmless |
| `s` | Hidden spike: appears when you get within 2 tiles, flickers for 0.4 s, then kills |
| `v` | Collapsing floor: looks solid, flickers for 0.4 s after you stand on it, then drops away |
| `d` | Decoy exit: looks like the door, kills you |
| `<` `>` | Wall cannon: fires bullets to the left, to the right |
| `i` | Invisible step: appears when you touch it |
| `o` `O` | Spiked disc: moves side to side, up and down |
| `m` | Land mine on whatever is below the tile: goes off when you land on it, or 0.4 s after you walk onto it |

Check the maps with `python3 scripts/test_levels.py`. `python3 scripts/test_tilt_gate.py` checks that a tilt level can't be played before the tilt check passes, that A doesn't skip it, and that play stops while Movement is unplugged. `python3 scripts/test_map.py` walks the title menu and the map, picks a level in each region and backs out. Set `DEBUG_TRAPS = True` in `python/levdevil.py` to print every trap state change to `make logs`.

## When a control is missing

Every frame, the game checks which Modulino modules answered.

- Without the joystick, the game pauses with a message on screen. It picks up again by itself once the joystick answers.
- Without Buttons, a note at the top tells you to press the joystick to jump.
- Without Movement, the tilt levels (7 and 8) won't play. The tilt check waits, and a level in progress pauses with a message until Movement is plugged back in.

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

Display controller, in `sketch/sketch.ino`: `ARCADE_TFT_HX8357D` is `1` for HX8357D (our console) and `0` for RM68140. `ARCADE_FAST_TFT` is `1` by default; set it to `0` to draw through the DIYables library instead (correct but about 2 s per full-screen redraw).

Control calibration, in `python/preview.py`:

```python
DEAD_ZONE = 26
INVERT_X = False
INVERT_Y = True
MOVEMENT_ZERO_MG = (-15, -994, 13)
MOVEMENT_DEAD_ZONE_MG = 20
```

Hold the console in your normal playing position and follow "Calibrate Movement" in `README.md` to get your own `MOVEMENT_ZERO_MG`.

Tilt and feel, in `python/levdevil.py`:

| Setting | Meaning |
| --- | --- |
| `TILT_DEAD` | How far from the starting angle you can drift before a platform moves |
| `TILT_SPEED`, `TILT_MAX` | How fast a tilt moves a platform |
| `RUN`, `JUMP`, `GRAVITY` | Player feel |
| `STICK_RUN` | How far you push the stick before the player runs |

## How it works

Python on the Linux side owns the game: levels, physics, traps and screens (`python/levdevil.py`, driven by `python/main.py`). The sketch on the microcontroller reads the Modulinos and draws on the TFT.

Each frame is one Bridge call, `game_frame`. Python sends the drawing it queued in the last tick as a small binary batch, and the sketch draws it, reads the controls and replies with a short comma-separated line. The batch can hold these commands:

- fill screen
- fill rectangle
- text
- `'O' x y r color`: a filled disc
- `'M' x0 y0 x1 y1 r color bg`: moves a disc. It repaints only the pixels the disc leaves or newly covers, so it doesn't flicker.
- `'S' x y frame color`: draws a 16 x 22 player frame from the sketch's `SPRITES` table (stand, three run frames, jump, three seated rowing frames). Bit 7 of `frame` mirrors it to face left.
- `'L' x0 y0 x1 y1 t color`: a line t pixels thick. The oar is drawn with it.
- `'J' y h tw up phase color gap`: a strip of triangle teeth for the devil's jaws.
- `'K' x y w h n color bg`: n teeth pointing up in a box. Every spike is drawn this way.
- `'B' n w h color bg`, then n times `x0 x1 y`: slides n bullets along x in one command. Each byte costs about 0.09 ms on the Bridge link, so this keeps level 9 near full speed.

A batch over 200 bytes goes out first through `game_draw`. Only what moved gets redrawn, usually just the player and sometimes a platform or a trap. The whole screen is redrawn when a level starts or you die. On the console this runs at about 85 frames per second, roughly 11 ms per frame.

The DIYables library drives the UNO Q's display pins one `digitalWrite` at a time, which takes about 2 s for a full screen. The sketch writes the same pins through the STM32 GPIO set/reset registers instead. It takes the pin numbers from the board's devicetree, so a full redraw takes a few tens of milliseconds.

If the board's MCU loader doesn't match the pinned Zephyr 0.55.2 core, sketches upload but never start. Python then reports "method ... not available". Flash the core's loader (`firmwares/zephyr-arduino_uno_q_stm32u585xx.elf`) with `/opt/openocd/bin/arduino-flash.sh` on the board, as described under "Board software" in `README.md`.

Levels are plain data at the top of `levdevil.py`. A trap is a trigger range plus actions: remove a floor, add a spike, add a floor, or move the door. Adding a level means adding one more entry to `LEVELS`. `REGIONS` groups the levels for the map and the level counter in the corner. The river level is different: it is an entry in `ISLAND_LEVELS`, and its boat, acid, pop-up block and door swap are code in `update_river`.

## Credits

- Game idea: Level Devil, the browser game. This is a fan remake with our own levels and the tilt mechanic.
- Starter code, Bridge setup and hardware guide: [aaishikasb/uno-q-hackout](https://github.com/aaishikasb/uno-q-hackout), Qualcomm Developer Relations.
- Hardware: Arduino UNO Q, Modulino Joystick, Buttons and Movement (the [Arduino UNO Q Arcade Bundle](https://projecthub.arduino.cc/Arduino_Genuino/uno-q-arcade-bundle-b272c5)), and the DIYables 3.5-inch TFT shield.
- Libraries: Arduino_RouterBridge, Arduino_Modulino, DIYables TFT Touch Shield, Adafruit GFX.
- Built by Vineeth Sakhamuru at Build Day with Qualcomm, Northeastern University Silicon Valley, Oct 24, 2026.

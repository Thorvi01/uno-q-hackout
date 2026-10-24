import json
import time

from arduino.app_utils import App, Bridge
from levdevil import Game

game = Game(Bridge)
last = time.monotonic()


def loop():
    global last
    try:
        inputs = json.loads(Bridge.call("arcade_read_inputs", timeout=1))
        if inputs.get("video", 0):
            time.sleep(0.5)
            return
        now = time.monotonic()
        game.tick(inputs, min(now - last, 0.05))
        last = now
    except Exception as error:
        # A failed call may leave a half-drawn screen, so redraw everything next time.
        print(f"Arcade connection/input error: {error}")
        game.drawn = None
        time.sleep(1)
        return
    time.sleep(0.01)


print("Level Devil: stick to run, A to jump, C to restart the level.")
App.run(user_loop=loop)

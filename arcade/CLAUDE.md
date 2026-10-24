# Level Devil on UNO Q
- TFT is 480x320 landscape. Tiles are 32px, grid 15x10.
- Bridge.call is a synchronous RPC at 115200 baud, max 256 bytes per call. Never redraw the full screen per frame; redraw only dirty tiles.
- Inputs: x/y are -127..128 (dead zone 26, in python/preview.py frame_values). buttons bitmask: A=1, B=2, C=4, stick press=8. Check inputs["connected"] before using a control.
- Controls: joystick X = move, A = jump (edge-triggered), C = restart.
- Clamp and validate all RPC arguments in the sketch.
- Use fixed physics substeps (1/60s) so fast falls can't tunnel through floors.
- Do not modify retroarch/. Deploy with make flash; logs with make logs.
- Keep the starter files working until the replacement is proven.

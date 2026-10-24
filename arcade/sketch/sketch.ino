#include <Arduino.h>
#include <Arduino_RouterBridge.h>
#include <Arduino_Modulino.h>
#include <DIYables_TFT_Touch_Shield.h>
#include <math.h>
#include "video_protocol.h"

#if !defined(ARDUINO_UNO_Q)
#error "Select Arduino UNO Q for this starter."
#endif

// Hosts select the controller fitted to their preassembled consoles.
#ifndef ARCADE_TFT_HX8357D
#define ARCADE_TFT_HX8357D 1
#endif
#if ARCADE_TFT_HX8357D
DIYables_TFT_HX8357D_Shield display;
#else
DIYables_TFT_RM68140_Shield display;
#endif

const uint8_t BUTTONS_ADDRESS = 0x3E;
const uint8_t JOYSTICK_ADDRESS = 0x2C;
ModulinoButtons buttons(BUTTONS_ADDRESS);
ModulinoMovement movement;
bool movementReady = false;

const uint16_t TFT_BLACK = 0x0000;
const uint16_t TFT_WHITE = 0xFFFF;
const uint16_t TFT_CYAN = 0x07FF;
unsigned long lastFrameAt = 0;
bool waiting = true;
int videoSession = 0;
int nextVideoSession = 0;
int lastX = -1;
int lastY = -1;
bool screenReset = true;  // The waiting screen replaced the game; Python must redraw.

bool readPacket(uint8_t address, uint8_t payload[3]) {
  // update() means "changed", not "read succeeded"; reject incomplete wire packets.
  int count = Wire1.requestFrom(address, (uint8_t)4);
  if (count != 4) {
    while (Wire1.available()) Wire1.read();
    return false;
  }
  Wire1.read();  // Modulino pinstrap address precedes the three input bytes.
  for (int i = 0; i < 3; ++i) payload[i] = Wire1.read();
  return true;
}

String readInputs() {
  uint8_t buttonData[3] = {};
  uint8_t stickData[3] = {};
  bool buttonsOk = readPacket(BUTTONS_ADDRESS, buttonData);
  bool joystickOk = readPacket(JOYSTICK_ADDRESS, stickData);
  bool movementOk = movementReady && movement.update();
  float ax = movementOk ? movement.getX() : 0;
  float ay = movementOk ? movement.getY() : 0;
  float az = movementOk ? movement.getZ() : 0;
  movementOk = movementOk && isfinite(ax) && isfinite(ay) && isfinite(az);
  int connected = (buttonsOk ? 1 : 0) | (joystickOk ? 2 : 0) | (movementOk ? 4 : 0);
  int pressed = 0;
  if (buttonsOk) {
    for (int i = 0; i < 3; ++i) if (buttonData[i]) pressed |= 1 << i;
    buttons.setLeds(buttonData[0], buttonData[1], buttonData[2]);
  }
  if (joystickOk && stickData[2]) pressed |= 8;
  char json[180];
  snprintf(json, sizeof(json),
           "{\"video\":%d,\"connected\":%d,\"buttons\":%d,\"x\":%d,\"y\":%d,"
           "\"ax\":%d,\"ay\":%d,\"az\":%d}",
           videoSession, connected, pressed,
           joystickOk ? 128 - (int)stickData[0] : 0,
           joystickOk ? 128 - (int)stickData[1] : 0,
           movementOk ? (int)(constrain(ax, -16.0f, 16.0f) * 1000) : 0,
           movementOk ? (int)(constrain(ay, -16.0f, 16.0f) * 1000) : 0,
           movementOk ? (int)(constrain(az, -16.0f, 16.0f) * 1000) : 0);
  return String(json);
}

void textLine(int y, const char* text) {
  display.setCursor(12, y);
  display.setTextColor(TFT_WHITE, TFT_BLACK);
  display.print(text);
}

void showWaiting() {
  if (videoSession) {
    videoSession = 0;
    display.fillScreen(TFT_BLACK);
    textLine(10, "UNO Q arcade starter");
    display.drawRect(12, 160, 456, 148, TFT_WHITE);
  }
  display.fillRect(12, 36, 456, 112, TFT_BLACK);
  textLine(36, "Waiting for App Lab...");
  if (lastX >= 0) display.fillCircle(lastX, lastY, 6, TFT_BLACK);
  lastX = -1;
  waiting = true;
  screenReset = true;
}

bool drawFrame(int x, int y, int pressed, int ax, int ay, int az, int connected) {
  if (videoSession) return false;  // RetroArch owns the display until release/timeout.
  // Bound every RPC input before using it for drawing or bit masks.
  x = constrain(x, 20, 460);
  y = constrain(y, 168, 300);
  pressed &= 15;
  connected &= 7;
  if (!(connected & 1)) pressed &= 8;
  if (!(connected & 2)) { pressed &= 7; x = 240; y = 234; }
  if (!(connected & 4)) { ax = 0; ay = 0; az = 0; }
  ax = constrain(ax, -16000, 16000);
  ay = constrain(ay, -16000, 16000);
  az = constrain(az, -16000, 16000);
  if (waiting) display.fillRect(12, 36, 456, 112, TFT_BLACK);
  char line[40];
  snprintf(line, sizeof(line), "Buttons:%s Stick:%s IMU:%s  ",
           connected & 1 ? "OK" : "--", connected & 2 ? "OK" : "--",
           connected & 4 ? "OK" : "--");
  textLine(36, line);
  snprintf(line, sizeof(line), "A:%d  B:%d  C:%d  Stick press:%d ",
           !!(pressed & 1), !!(pressed & 2), !!(pressed & 4), !!(pressed & 8));
  textLine(64, line);
  textLine(92, "Motion from neutral (mg)");
  snprintf(line, sizeof(line), "%6d / %6d / %6d   ", ax, ay, az);
  textLine(120, line);
  if (lastX >= 0) display.fillCircle(lastX, lastY, 6, TFT_BLACK);
  display.fillCircle(x, y, 6, pressed ? TFT_WHITE : TFT_CYAN);
  lastX = x;
  lastY = y;
  lastFrameAt = millis();
  waiting = false;
  return true;
}

int beginVideo() {
  if (videoSession) return 0;  // Only one stream may own the display.
  nextVideoSession = nextVideoSession == 2147483647 ? 1 : nextVideoSession + 1;
  videoSession = nextVideoSession;
  display.fillScreen(TFT_BLACK);
  textLine(10, "RetroArch / TFT bridge");
  textLine(294, "C + stick press: menu");
  lastX = -1;
  lastFrameAt = millis();
  waiting = false;
  return videoSession;
}

String pollVideo(int session) {
  if (!videoSession || session != videoSession) return String("");
  String inputs = readInputs();
  lastFrameAt = millis();
  return inputs;
}

String videoTile(int session, int tile, MsgPack::bin_t<uint8_t> data) {
  static uint16_t pixels[ArcadeVideo::TILE_PIXELS * 4];
  if (!videoSession || session != videoSession ||
      !ArcadeVideo::decode(tile, data.data(), data.size(), pixels)) return String("");
  display.drawRGBBitmap(80 + (tile % 10) * 32, 40 + (tile / 10) * 16, pixels, 32, 16);
  return pollVideo(session);  // Return fresh controls after each acknowledged tile.
}

bool endVideo(int session) {
  if (!videoSession || session != videoSession) return false;
  showWaiting();
  return true;
}

// Game primitives: Python owns the game state and asks the sketch to draw.
// game_ping keeps the 1.5-second timeout away and reports if the screen was reset.
bool gamePing() {
  if (videoSession) return false;
  bool reset = screenReset;
  screenReset = false;
  lastFrameAt = millis();
  waiting = false;
  return reset;
}

bool gameClear(int color) {
  if (videoSession) return false;
  display.fillScreen((uint16_t)color);
  return true;
}

bool gameRect(int x, int y, int w, int h, int color) {
  if (videoSession) return false;
  display.fillRect(x, y, constrain(w, 0, 480), constrain(h, 0, 320), (uint16_t)color);
  return true;
}

bool gameCircle(int x, int y, int r, int color) {
  if (videoSession) return false;
  display.fillCircle(x, y, constrain(r, 0, 160), (uint16_t)color);
  return true;
}

bool gameText(int x, int y, int size, int color, int bg, String text) {
  if (videoSession) return false;
  display.setTextSize(constrain(size, 1, 6));
  display.setCursor(x, y);
  display.setTextColor((uint16_t)color, (uint16_t)bg);
  display.print(text);
  display.setTextSize(2);  // The preview screens expect size 2.
  return true;
}

void setup() {
  Modulino.begin(Wire1);
  buttons.begin();
  movementReady = movement.begin();
  display.begin();
  display.setRotation(1);  // Landscape: 480 x 320.
  display.fillScreen(TFT_BLACK);
  display.setTextSize(2);
  display.setTextWrap(false);
  textLine(10, "UNO Q arcade starter");
  display.drawRect(12, 160, 456, 148, TFT_WHITE);
  showWaiting();
  if (Bridge.begin()) {
    Bridge.provide_safe("arcade_read_inputs", readInputs);
    Bridge.provide_safe("arcade_draw_frame", drawFrame);
    Bridge.provide_safe("arcade_video_begin", beginVideo);
    Bridge.provide_safe("arcade_video_tile", videoTile);
    Bridge.provide_safe("arcade_video_poll", pollVideo);
    Bridge.provide_safe("arcade_video_end", endVideo);
    Bridge.provide_safe("game_ping", gamePing);
    Bridge.provide_safe("game_clear", gameClear);
    Bridge.provide_safe("game_rect", gameRect);
    Bridge.provide_safe("game_circle", gameCircle);
    Bridge.provide_safe("game_text", gameText);
  } else {
    textLine(36, "Bridge failed: restart app");
  }
}

void loop() {
  if (!waiting && millis() - lastFrameAt > 1500) showWaiting();
  delay(5);
}

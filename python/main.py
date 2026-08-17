"""Entrypoint: wires the App Lab web_ui brick, the weight-triggered scan
loop, and the bridge/camera/code-detector clients together, then hands
control to App.run().

Run inside the App Lab container -- `arduino-app-cli app restart user:verdureai`
on the board, or `SIMULATE_HARDWARE=1` for the fake weight ramp + fixture
images. Note that even the simulated path now requires the App Lab
container: `arduino.app_bricks.web_ui`/`arduino.app_utils.App` aren't
importable on a bare laptop, so a full end-to-end run (unlike the pytest
suite) is no longer something you can do with plain `python3` outside the
container. See CLAUDE.md for that tradeoff.
"""
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App

from bridge_client import get_bridge_client
from camera import get_camera
from checkout import ScanResult, process_capture
from code_detector import get_code_detector

POLL_INTERVAL_S = 0.3


def _result_to_dict(result: ScanResult) -> dict:
    return {
        "flow": result.flow,
        "item_name": result.item_name,
        "for_sale": result.for_sale,
        "base_price": result.base_price,
        "discount_pct": result.discount_pct,
        "final_price": result.final_price,
        "discount_code": result.discount_code,
        "qr_data_uri": result.qr_data_uri,
        "detail": result.detail,
    }


ui = WebUI()
bridge = get_bridge_client()
camera = get_camera()
code_detector = get_code_detector(camera=camera.raw)

_state = {"phase": "idle", "weight_grams": 0.0, "result": None}
_was_stable = False


def _publish_state() -> None:
    ui.send_message("state_update", _state)


def poll_loop() -> None:
    """Called repeatedly by App.run(). Polls the MCU's load cell over the
    Bridge; on a stable-weight transition, captures a frame and runs it
    through the full routing/pricing pipeline."""
    global _was_stable

    reading = bridge.read_weight()

    if reading.stable and not _was_stable:
        _state.update(phase="scanning", weight_grams=reading.grams, result=None)
        _publish_state()

        image = camera.capture()
        result = process_capture(image, code_detector, weight_grams=reading.grams)
        _state.update(phase="result", result=_result_to_dict(result))
        _publish_state()
    elif not reading.stable:
        phase = "weighing" if reading.grams > 0 else "idle"
        if phase == "idle" and _state["phase"] != "idle":
            code_detector.on_item_reset()
        _state.update(phase=phase, weight_grams=reading.grams, result=None)
        _publish_state()

    _was_stable = reading.stable


def on_get_initial_state(sid, _data):
    """A freshly-connected browser has nothing to show until the next
    push -- hand it whatever we last knew instead of a blank kiosk screen."""
    ui.send_message("state_update", _state, room=sid)


ui.on_message("get_initial_state", on_get_initial_state)

App.run(user_loop=poll_loop)

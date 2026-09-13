"""Entrypoint: wires the web UI, the scale, the camera and the two vision
pipelines together, then hands control to App.run().

The MCU decides when a weight has settled; this loop watches for that
transition, grabs a frame at that moment, prices the item and pushes the
result to every connected browser over the web_ui brick's socket.
"""
from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App, Logger

from bridge_client import get_bridge_client
from camera import get_camera
from checkout import ScanResult, process_capture
from code_detector import get_code_detector
from produce_classifier import get_produce_classifier

logger = Logger("verdureai")


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
        "weight_grams": result.weight_grams,
        "produce_type": result.produce_type,
        "grade": result.grade,
        "price_per_kg": result.price_per_kg,
    }


ui = WebUI()
bridge = get_bridge_client()
camera = get_camera()
code_detector = get_code_detector(camera=camera.raw)
produce_classifier = get_produce_classifier()

_state = {"phase": "idle", "weight_grams": 0.0, "result": None}
_was_stable = False


def _publish_state() -> None:
    ui.send_message("state_update", _state)


def poll_loop() -> None:
    """Called repeatedly by App.run(): one weight poll, and the scan that
    follows when the reading settles."""
    global _was_stable

    reading = bridge.read_weight()

    if reading.stable and not _was_stable:
        _state.update(phase="scanning", weight_grams=reading.grams, result=None)
        _publish_state()

        image = camera.capture()
        result = process_capture(
            image, code_detector, produce_classifier, weight_grams=reading.grams
        )
        logger.info(
            f"Scanned {result.item_name} ({result.flow}) at {reading.grams:.0f}g -- {result.detail}"
        )
        _state.update(phase="result", result=_result_to_dict(result))
        _publish_state()
    elif not reading.stable:
        phase = "weighing" if reading.grams > 0 else "idle"
        if phase == "idle" and _state["phase"] != "idle":
            # Item lifted off: forget its barcode so the next one starts clean.
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

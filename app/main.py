"""Entrypoint: runs the weight-triggered scan loop in a background thread
and serves the kiosk-mode scale UI, which polls for the latest state.

Run with `SIMULATE_HARDWARE=1 python3 -m app.main` to exercise the whole
pipeline (fake weight ramp + fixture images) with no board attached.
"""
import threading
from pathlib import Path

from flask import Flask, jsonify, render_template

from app.bridge_client import get_bridge_client
from app.camera import get_camera
from app.checkout import ScanResult, process_capture

POLL_INTERVAL_S = 0.3
TEMPLATE_DIR = Path(__file__).parent / "web" / "templates"


class ScaleState:
    """Thread-safe holder for the latest poll-loop snapshot the UI reads."""

    def __init__(self):
        self._lock = threading.Lock()
        self._data = {"phase": "idle", "weight_grams": 0.0, "result": None}

    def update(self, **kwargs) -> None:
        with self._lock:
            self._data.update(kwargs)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._data)


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


def run_poll_loop(state: ScaleState, stop_event: threading.Event) -> None:
    bridge = get_bridge_client()
    camera = get_camera()
    was_stable = False

    while not stop_event.is_set():
        reading = bridge.read_weight()

        if reading.stable and not was_stable:
            state.update(phase="scanning", weight_grams=reading.grams)
            image = camera.capture()
            result = process_capture(image, weight_grams=reading.grams)
            state.update(phase="result", result=_result_to_dict(result))
        elif not reading.stable:
            phase = "weighing" if reading.grams > 0 else "idle"
            state.update(phase=phase, weight_grams=reading.grams, result=None)

        was_stable = reading.stable
        stop_event.wait(POLL_INTERVAL_S)


def create_app() -> Flask:
    app = Flask(__name__, template_folder=str(TEMPLATE_DIR))
    state = ScaleState()
    stop_event = threading.Event()

    thread = threading.Thread(target=run_poll_loop, args=(state, stop_event), daemon=True)
    thread.start()

    @app.route("/")
    def index():
        return render_template("scale_ui.html")

    @app.route("/state")
    def get_state():
        return jsonify(state.snapshot())

    return app


if __name__ == "__main__":
    create_app().run(port=5000, use_reloader=False)

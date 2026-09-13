"""Focused Flask demo: pick an image, decode a barcode, look up the product.

Not the full scale UI (no weight/pricing/QR -- those live in python/main.py,
which runs inside the App Lab container). Laptop-only bench tool, kept
outside python/ since it needs Flask/Jinja rather than the web_ui brick.
Wires barcode_decode.py + product_lookup.py together so the identification
half of the packaged-goods flow can be checked against a photo on a desk.
"""
import base64
import sys
from pathlib import Path

import cv2
import numpy as np
from flask import Flask, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

from product_lookup import lookup_product  # noqa: E402

from tools.barcode_decode import decode_first_barcode  # noqa: E402

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "barcodes"


def create_app(fixture_dir: Path = FIXTURE_DIR) -> Flask:
    app = Flask(__name__)

    @app.route("/", methods=["GET", "POST"])
    def index():
        result, error = None, None
        if request.method == "POST":
            image = _load_image(request, fixture_dir)
            if image is None:
                error = "Could not load an image from the upload or fixture selection."
            else:
                result = _run_pipeline(image)
        fixtures = sorted(p.name for p in fixture_dir.glob("*.png")) if fixture_dir.exists() else []
        return render_template("index.html", result=result, error=error, fixtures=fixtures)

    return app


def _load_image(req, fixture_dir: Path) -> np.ndarray | None:
    upload = req.files.get("image")
    if upload and upload.filename:
        data = np.frombuffer(upload.read(), np.uint8)
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    fixture_name = req.form.get("fixture")
    if fixture_name:
        path = fixture_dir / fixture_name
        if path.exists():
            return cv2.imread(str(path))
    return None


def _run_pipeline(image: np.ndarray) -> dict:
    barcode = decode_first_barcode(image)
    preview_b64 = _encode_preview(image)
    if barcode is None:
        return {"barcode": None, "product": None, "preview": preview_b64}
    product = lookup_product(barcode.value)
    return {"barcode": barcode, "product": product, "preview": preview_b64}


def _encode_preview(image: np.ndarray, max_width: int = 480) -> str:
    h, w = image.shape[:2]
    if w > max_width:
        image = cv2.resize(image, (max_width, int(h * max_width / w)))
    ok, buf = cv2.imencode(".jpg", image)
    return base64.b64encode(buf).decode("ascii") if ok else ""


if __name__ == "__main__":
    create_app().run(debug=True, port=5000)

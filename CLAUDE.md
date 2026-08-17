# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

VerdureAI — an edge-AI checkout scale for the Arduino "Invent the Future with UNO Q and App Lab"
hackathon. It assesses fresh-produce condition and packaged-goods expiry at the point of sale and
applies a proportional discount, to cut retail food waste. The original architecture/roadmap doc
lives at `/home/mferuscomelo/.claude/plans/piped-imagining-matsumoto.md`; the App-Lab migration
plan (bricks chosen, file-layout mapping, rationale) lives at
`/home/mferuscomelo/.claude/plans/i-ve-connected-the-arduino-resilient-twilight.md`. Both predate
things learned by actually inspecting the board — this file is the up-to-date source of truth.

## Repo layout — Arduino App Lab project structure

This repo **is** an Arduino App Lab app (`app.yaml` at the root) and is cloned directly onto the
UNO Q board at `~/ArduinoApps/verdureai`, tracked against this repo's GitHub remote — App Lab's
`arduino-app-cli` daemon watches that directory live and rebuilds the app's Docker container on
change. Laptop and board iteration stay in sync via normal `git push`/`git pull`; there's no
separate deploy step.

- `app.yaml` — app manifest: name/icon/description, declared bricks (`arduino:camera_code_detection`,
  `arduino:web_ui`), exposed ports (`[]` — the web_ui brick manages its own port internally).
- `python/` — the MPU-side app. **Flat directory, no subpackages** (matches every bundled App Lab
  example — `led-matrix-painter`, `edge-ai-assistant`, etc. — none use subpackages under `python/`).
  Runs inside App Lab's `ghcr.io/arduino/app-bricks/python-apps-base` Docker container via
  `arduino.app_utils.App.run(...)`, **not** as a bare `python3` process — `arduino.app_bricks`/
  `arduino.app_utils`/`arduino.app_peripherals` only exist inside that container.
- `python/requirements.txt` — on-device runtime deps, installed by App Lab's `uv`-managed venv
  inside the container at app start (not baked into the image). No `pytest`/`Flask` here — those
  are laptop-only, in the root `requirements.txt`.
- `sketch/` — the MCU-side Arduino sketch (`sketch.ino` + `sketch.yaml`), built/flashed by App Lab
  tooling, not a separate CLI command.
- `assets/` — static files for the `web_ui` brick (FastAPI + Socket.IO under the hood): plain
  HTML/CSS/JS, no Jinja/templating. `assets/libs/{socket.io.min.js,arduino.js}` are vendored
  copies (offline-only device, no CDN) — `arduino.js` is App Lab's small `WebUI` JS class wrapping
  the socket.io client (`on_message`/`send_message`/`on_connect`/`on_disconnect`).
- `tools/barcode_debug_server.py` — a **laptop-only** Flask+Jinja debug tool (unrelated to the
  App Lab runtime; adds `python/` to `sys.path` itself since it lives outside it). Run directly with
  plain `python3`, not deployed to the board.
- `tests/` — pytest suite, run directly on the laptop with plain `python3` (no App Lab container
  needed). `pyproject.toml`'s `[tool.pytest.ini_options] pythonpath = ["python"]` makes `python/`'s
  flat modules importable as `import ocr`, `from code_detector import ...`, etc.

**Important consequence of adopting the `web_ui` brick**: `python/main.py` now imports
`arduino.app_bricks.web_ui`/`arduino.app_utils.App` unconditionally, for both the simulated and
real-hardware paths (the brick replaced the old bespoke Flask app entirely, not just the
real-hardware branch of it). That means **a full end-to-end run — including `SIMULATE_HARDWARE=1`
— now requires the App Lab container** (i.e., the board, via `arduino-app-cli`); it can no longer
be run with plain `python3` on a bare laptop the way the old `app/main.py` could. Individual
modules stay fully testable on the laptop via `pytest` regardless (see below) — only the
full-stack UI demo needs the container.

## Current state

OCR, barcode/QR routing, product lookup/cache, pricing, discount codes, and the bridge/camera
layer are built and restructured into the App Lab layout above. Real MCU firmware now exists
(`sketch/sketch.ino`) but is **unverified on real hardware** — load-cell calibration constants are
placeholders (see below). The produce flow is still a stub: the Edge Impulse freshness classifier
hasn't been trained/built yet. When it is, prefer the `arduino:image_classification` brick
(`arduino.app_bricks.image_classification.ImageClassification`, wraps `.eim` model loading and
inference via a sidecar container) over hand-rolling the `edge_impulse_linux` SDK directly, per the
migration plan doc.

What exists:
- `python/ocr.py` — reads a captured product image (OpenCV BGR array, fed in **raw**, no manual
  crop/deskew/threshold) and extracts a printed best-by/expiry date. Runs `RapidOCR` (ONNX Runtime
  build of PP-OCR — a scene-text detector+recognizer) directly on the frame, then `_cluster_lines()`
  regroups the detected text boxes into reading-order rows (by y-center proximity relative to the
  box's own rotation-invariant short-side length) before `extract_date()` regexes the reassembled
  text for a date (`ISO`, `MM/DD/YYYY` falling back to `DD/MM/YYYY`, `DD MON YYYY`, and
  `MM/YYYY`-only resolving to end-of-month). Unchanged by the App Lab migration, still unverified
  that `onnxruntime`/RapidOCR actually installs and runs inside the App Lab container on the
  QRB2210 (aarch64) — check this on first real deploy, see Feasibility results below.
- `python/code_detector.py` — barcode/QR detection, following the same Simulated/Hardware split as
  `bridge_client.py`/`camera.py`. `decode_first_barcode()`/`decode_barcodes()` (pyzbar, UPC-A/
  UPC-E/EAN-8/EAN-13/Code128, zbar's own rotation tolerance, 12→13-digit UPC-A/EAN-13 leading-zero
  quirk normalized) are unchanged from the pre-migration `app/vision/barcode.py`.
  `SimulatedCodeDetector` calls that decode logic synchronously on the captured frame — today's
  exact behavior, kept as live code for `SIMULATE_HARDWARE=1` (and reused directly by
  `tools/barcode_debug_server.py`), not just test fixture material. `HardwareCodeDetector` wraps
  the `arduino:camera_code_detection` brick instead: it scans the live camera feed continuously in
  the background and fires an `on_detect(frame, detection)` callback asynchronously, so it tracks
  whatever's been seen since the last `on_item_reset()` (called by `main.py` when weight returns to
  ~0g between items) rather than decoding on demand. `get_code_detector(camera=...)` picks one
  based on `SIMULATE_HARDWARE`. **The real-hardware path has no pytest coverage** (no board/
  container in CI) — verify it manually on-device.
- `python/product_lookup.py` — Open Food Facts client (`/api/v2/product/<barcode>.json`) + a flat
  JSON cache at `python/data/product_cache.json` (gitignored), keyed by barcode, no TTL. Caches
  both "found" and definitive "not found" answers; does **not** cache transient network errors, so
  those retry on the next scan. **OFF rejects requests without a descriptive `User-Agent` header
  (403)** — `REQUEST_HEADERS` in this module sets one; don't strip it.
- `tools/barcode_debug_server.py` + `tools/templates/index.html` — single-route Flask demo
  (`create_app()` factory), laptop-only. Pick an uploaded image or a fixture from
  `tests/fixtures/barcodes/`, decodes the barcode, looks up the product, and shows the decoded
  value, cache/network source, and product name/brand/image. Run with
  `python3 -m tools.barcode_debug_server` (add the repo root to your PYTHONPATH, or run from repo
  root), open `http://localhost:5000`.
- `python/config.py` — static price/discount tables: `PRODUCE_PRICE_PER_KG`, `PRODUCE_DISCOUNT_BY_TIER`
  (grade → discount %, `reject` → `None`), `PACKAGED_DISCOUNT_TIERS` (days-until-expiry → discount %),
  `PACKAGED_DEFAULT_BASE_PRICE` (Open Food Facts has no reliable price data, so packaged goods use a flat
  placeholder price for the demo). All placeholder values, not researched retail pricing.
- `python/pricing.py` — flow-agnostic `apply_discount(base_price, discount_pct)` plus `price_produce()` and
  `price_packaged()`, both returning a `PriceResult` (`for_sale=False`/`final_price=None` for a `reject`
  grade or an expired best-by date). Pure functions, no I/O. Unchanged by the migration.
- `python/discount_codes.py` — `generate_discount_code()` mints a 6-char alphanumeric code, stores
  item/discount/price in an in-memory `_active_codes` registry, and renders a QR code of the code as a
  `data:image/png;base64,...` URI (via the `qrcode` lib) for direct `<img src>` embedding.
  `redeem_discount_code()` looks a code up. No external redemption service — in-memory only, so codes
  don't survive a process restart. Unchanged; the QR data URI is framework-agnostic so it dropped
  straight into the Socket.IO-pushed state payload with no change.
- `python/bridge_client.py` — `WeightReading(grams, stable)` from the MCU load cell over Bridge RPC.
  `HardwareBridgeClient` calls `Bridge.call("get_weight"/"is_stable")`, importing `Bridge` from
  `arduino.app_utils` **lazily inside `__init__`**. Confirmed against the real `arduino.app_utils.bridge`
  source on the board: `Bridge.call(method, *params, timeout=10)` synchronously returns whatever the
  MCU-side handler returns (this module's design was correct pre-migration). `SimulatedBridgeClient`
  fakes an item landing on the scale: ramps weight up in fixed steps, holds `stable=True` for a
  configured number of reads, then resets to 0g so the next poll cycle ramps up again ("next" item).
  `get_bridge_client()` picks one based on `SIMULATE_HARDWARE`.
- `python/camera.py` — `WebcamCamera` now wraps `arduino.app_peripherals.camera.V4LCamera` (lazily
  imported, same pattern as `HardwareBridgeClient`) instead of raw `cv2.VideoCapture` — App Lab
  handles device discovery/auto-reconnect, and it returns numpy BGR arrays so downstream code is
  unchanged. Exposes `.raw` (the underlying `V4LCamera`/`None`) so `main.py` can share one physical
  webcam between still-frame capture and `HardwareCodeDetector`'s continuous scanning instead of
  opening the device twice. `SimulatedCamera` (fixture-cycling) is unchanged.
- `python/router.py` — `route_item(image, code_detector)`: asks `code_detector.get_current_detection(image)`;
  found → `RoutingResult(flow="packaged", barcode=...)`, not found → `RoutingResult(flow="produce", barcode=None)`.
  Pure routing decision otherwise, no lookup/pricing side effects.
- `python/checkout.py` — `process_capture(image, code_detector, weight_grams=None)` is the one call
  per captured frame that wires everything above together: `route_item` → (produce: return a stub
  `ScanResult` saying the freshness classifier isn't built yet) or (packaged:
  `product_lookup.lookup_product` for the name, `ocr.read_best_by_date` for the expiry date →
  `pricing.price_packaged` → `discount_codes` if `for_sale`). Returns a `ScanResult` dataclass the
  UI layer renders directly. If OCR finds no date, prices at full value (0% discount) rather than
  guessing a tier.
- `python/main.py` — the real entrypoint, run by `arduino.app_utils.App.run(user_loop=poll_loop)`
  (App Lab's own runtime loop, not a bare Flask `app.run()`). `poll_loop()` polls `bridge_client`
  every ~300ms; on a stable-weight transition it captures a frame, calls `checkout.process_capture`,
  and pushes the result to connected browsers via `ui.send_message("state_update", ...)` (Socket.IO
  push through the `web_ui` brick) rather than writing to state a Flask route polls. A freshly
  connected browser sends `get_initial_state` to get caught up. `assets/index.html` +`app.js` render
  the kiosk display (live weight, phase, then item/price/discount/QR or a reject message) from
  pushed `state_update` events.
- `sketch/sketch.ino` — MCU firmware: reads the NAU7802 over I2C (`Adafruit_NAU7802`, confirmed API
  on-device: `begin/available/read/setGain/setLDO/setRate/calibrate`), keeps a rolling window of
  recent readings, and calls it stable once every reading in the window is within
  `STABILITY_TOLERANCE_GRAMS` of every other **and** the weight is above `MIN_ITEM_GRAMS` (filters
  scale noise near 0g). Exposes `get_weight()`/`is_stable()` via `Bridge.provide(...)` — confirmed
  on-device (`Arduino_RouterBridge`'s Python/C++ source, not just examples) that `Bridge.provide` is
  the right call, not `Bridge.provide_safe` as originally assumed; both exist, examples consistently
  use plain `provide`. **`COUNTS_PER_GRAM`/`ZERO_OFFSET_COUNTS` are placeholders** — must be
  calibrated against a known weight on the real load cell before trusting any reading.
- `tests/fixtures/generate_synthetic_dates.py` — throwaway generator for synthetic label images
  (clean print, dot-matrix stamp look, low contrast, noisy, rotated, blurry) with a `manifest.json` of
  ground-truth dates, used because no physical products were on hand to photograph. Real photos from
  an actual camera/product should replace or supplement these before the packaged-goods flow ships.
- `tests/fixtures/generate_barcode_rotations.py` — throwaway generator that rotates a real photo
  (`tests/fixtures/barcodes/source/candy_box_original.jpg`, a UPC-A `070970474088`) at 0/±5/±15/90/180/
  270° into `tests/fixtures/barcodes/` with a `manifest.json`.
- `tests/test_ocr_date_parsing.py`, `tests/test_ocr_real_photos.py`, `tests/test_code_detector.py`
  (renamed from `test_barcode.py`), `tests/test_product_lookup.py`, `tests/test_pricing.py`,
  `tests/test_discount_codes.py`, `tests/test_bridge_client.py`, `tests/test_camera.py`,
  `tests/test_router.py`, `tests/test_checkout.py` — pytest suite (73 tests: 70 passing + 3
  known-hard-frame `xfail`). `test_code_detector.py` covers both `decode_first_barcode()` directly
  (one test per rotation fixture) and `SimulatedCodeDetector`; there's no equivalent coverage for
  `HardwareCodeDetector` (needs the App Lab container/board). `test_router.py`/`test_checkout.py`
  pass a `SimulatedCodeDetector()` instance through the new `code_detector` parameter.
  Product-lookup tests mock `requests.get` (no real network calls) and cover cache hit/miss/write
  and the not-cached-on-error behavior. `test_checkout.py` mocks `router.route_item`/
  `product_lookup.lookup_product`/`ocr.read_best_by_date` for the packaged-flow cases (no fixture
  combines a barcode and a printed date in one image, and pricing-tier assertions use a
  `date.today() + timedelta(...)` offset rather than a fixture's baked-in date) — the produce-flow
  test uses a real fixture through real `router.route_item`. `test_ocr_real_photos.py` runs both
  barcode decoding and date OCR against `tests/fixtures/real_photos/` — 6 real webcam photos (2
  products x 3 shots); barcode decoding is 6/6, date OCR is 3/5 exact (the other 2 `xfail`, see
  `python/ocr.py` above).
- `tests/fixtures/run_ocr_report.py`, `tests/fixtures/run_barcode_report.py` — throwaway pass-rate/
  latency report scripts (not part of the test suite; run manually when tuning a pipeline).

Feasibility results: OCR 10/10 synthetic fixtures pass (RapidOCR), ~450ms/image on this dev laptop's CPU.
RapidOCR ships ONNX models + runs via `onnxruntime`, which has official aarch64 Linux wheels, so it
*should* run inside the App Lab container on the UNO Q's Qualcomm QRB2210 MPU, but this is still
**unverified on real hardware/inside the actual container** — verify on first real deploy (re-check
`python/requirements.txt` installs cleanly via the container's `uv`, and note actual latency).
Barcode 8/8 real-photo rotation fixtures pass, ~29ms/image, also laptop-only (this exercises
`SimulatedCodeDetector`'s pyzbar path; `HardwareCodeDetector`'s brick-based path is unverified).

## Commands

- `python3 -m pytest tests/` — run the test suite (laptop, no App Lab container needed).
- `python3 -m tools.barcode_debug_server` (from repo root) — the narrower manual barcode-scan-only
  debug UI at `http://localhost:5000`, laptop-only, no App Lab container needed.
- `python3 tests/fixtures/run_ocr_report.py` — pass/fail + latency report of `python/ocr.py` against
  every fixture in `tests/fixtures/best_by_dates/`.
- `python3 tests/fixtures/run_barcode_report.py` — pass/fail + latency report of
  `python/code_detector.py`'s `decode_first_barcode()` against every fixture in `tests/fixtures/barcodes/`.
- `python3 tests/fixtures/generate_synthetic_dates.py` — regenerate the synthetic OCR fixture set (only
  needed if you change the fixture generation logic itself).
- `python3 tests/fixtures/generate_barcode_rotations.py` — regenerate the barcode rotation fixture set
  from `tests/fixtures/barcodes/source/candy_box_original.jpg`.
- On the board (`ssh verdure-ai`): `arduino-app-cli app restart user:verdureai` to build/run the
  full app (sketch + `python/main.py` + web UI) inside its App Lab container;
  `arduino-app-cli app logs user:verdureai` to tail logs; `arduino-app-cli app list` to check status.
  There is no equivalent "run the whole app" command off the board anymore — see the `web_ui` brick
  tradeoff noted above.

## Architecture notes worth knowing before extending this

- **Target device is the Arduino UNO Q**: a dual-brain board — an STM32U585 MCU (real-time,
  `arduino:zephyr` platform, runs `sketch/sketch.ino`) paired with a Qualcomm QRB2210 MPU (Debian
  Linux aarch64, runs the `python/` app inside a Docker container), managed by the
  `arduino-app-cli` daemon and developed together in Arduino App Lab. The two talk over the Bridge
  RPC (`Bridge.begin()` + `Bridge.provide(name, handler)` on the sketch side, `Bridge.call(name,
  *params, timeout=10)` from Python) — confirmed from the actual `Arduino_RouterBridge`/
  `arduino.app_utils.bridge` source: `Bridge.call` is a synchronous request→response (Linux always
  initiates), and MCU-side registered functions must be non-blocking (no `delay()`). The load cell
  (NAU7802 ADC) is read on the MCU side for real-time weight sampling and stability detection; the
  camera is a USB webcam read directly by the Python/MPU side.
- **App Lab is not just a folder layout** — apps run inside
  `ghcr.io/arduino/app-bricks/python-apps-base` Docker containers (one container per app, plus a
  sidecar container per brick that needs one, e.g. `dbstorage_tsstore` → an InfluxDB container),
  managed by `arduino-app-cli`. Prebuilt **bricks** (`arduino.app_bricks.*`, e.g. `web_ui`,
  `camera_code_detection`, `image_classification`) cover common needs instead of hand-rolling
  everything — check `arduino-app-cli brick list`/`arduino-app-cli brick details <name>` and the
  ~40 example apps under `/var/lib/arduino-app-cli/examples` on the board before building something
  from scratch that a brick might already cover.
- **Everything must run fully offline on-device** — no cloud inference calls at scan time. The one
  exception the plan allows is barcode product lookups (Open Food Facts API), which are cached locally
  so repeat/offline scans still work.
- **Two item flows, routed by barcode presence**: an item with a decodable barcode is treated as
  packaged goods (fixed price, discount from best-by proximity via `python/ocr.py`); no barcode means
  fresh produce (priced per weight, discount from an Edge Impulse tiered-classification freshness
  grade).
- The produce freshness model is planned as **one combined Edge Impulse image classifier** with
  labels like `apple_gradeA`, `apple_gradeB`, `banana_gradeA`, etc. — not object detection, and not a
  separate model per produce type. Training happens in Edge Impulse Studio (external to this repo);
  prefer the `arduino:image_classification` brick over hand-rolling the `edge_impulse_linux` SDK
  when this gets built (see "Current state" above).
- `SIMULATE_HARDWARE=1` (checked once per module, at import time, in `bridge_client.py`,
  `camera.py`, and `code_detector.py`) swaps in fake weight/camera/detection fixtures throughout.
  Note this now only substitutes those three dependencies — it doesn't let the *whole app* run
  outside the App Lab container, since `main.py` unconditionally uses the `web_ui` brick (see the
  "Important consequence" note above). The real-hardware classes (`HardwareBridgeClient`,
  `WebcamCamera`, `HardwareCodeDetector`) exist but have no pytest coverage — no CI board to test
  against; verify them manually on-device.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

VerdureAI — an edge-AI checkout scale for the Arduino "Invent the Future with UNO Q and App Lab"
hackathon. It assesses fresh-produce condition and packaged-goods expiry at the point of sale and
applies a proportional discount, to cut retail food waste. Full architecture, all design decisions,
and the implementation roadmap live in the plan doc at
`/home/mferuscomelo/.claude/plans/piped-imagining-matsumoto.md` — **read that file before planning
further work here**, it is the source of truth for what's being built and why.

## Current state

The **OCR feasibility spike**, **barcode scanning**, **product lookup/cache**, the **pricing engine**,
**discount codes**, a **`SIMULATE_HARDWARE` bridge/camera layer**, and a **full simulated end-to-end scale
UI** have been built (the rest of the plan — real MCU firmware, a live Bridge connection, live camera
capture, and the Edge Impulse produce classifier — has not been started; the produce flow is a stub until
that classifier exists). The user does not have the UNO Q board on hand right now, so this repo currently
runs entirely on a regular Linux dev machine, no hardware attached, via `SIMULATE_HARDWARE=1`.

What exists:
- `app/ocr.py` — reads a captured product image (OpenCV BGR array, fed in **raw**, no manual crop/
  deskew/threshold) and extracts a printed best-by/expiry date. Runs `RapidOCR` (ONNX Runtime build of
  PP-OCR — a scene-text detector+recognizer) directly on the frame, then `_cluster_lines()` regroups the
  detected text boxes into reading-order rows (by y-center proximity relative to the box's own
  rotation-invariant short-side length — an axis-aligned bbox height balloons under rotation and is
  useless for this) before `extract_date()` regexes the reassembled text for a date (`ISO`, `MM/DD/YYYY`
  falling back to `DD/MM/YYYY` when the first interpretation isn't a real date, `DD MON YYYY`, and
  `MM/YYYY`-only resolving to end-of-month). **This replaced an earlier Tesseract + hand-rolled
  deskew/adaptive-threshold pipeline**, which read 10/10 synthetic label fixtures but 0/6 real photos
  (Tesseract is a document-OCR engine — built for scanned flat pages, not curved/skewed/glare-y scene
  text) — see `tests/fixtures/real_photos/` below. RapidOCR isn't perfect either: 3 of 6 real photos still
  fail (tracked as `xfail` in `tests/test_ocr_real_photos.py`, not deleted) with genuine recognizer
  misreads (dropped/extra digits, near-total detection miss on a bad angle) on frames where a *different*
  photo of the same physical item reads correctly — i.e. no fixable pipeline bug, just OCR's real error
  rate on hard frames.
- `app/vision/barcode.py` — decodes barcodes from an OpenCV BGR array via `pyzbar` (UPC-A/UPC-E/EAN-8/
  EAN-13/Code128). No deskew/rotation-retry step: zbar's own rotation tolerance handled all 8 real-photo
  rotation fixtures (0°, ±5°, ±15°, 90°, 180°, 270°) with a single plain `pyzbar.decode()` call, so no
  retry logic was added — keep it that way unless a future fixture set proves it's needed. Normalizes a
  known zbar quirk (12-digit UPC-A reported as a 13-digit EAN-13 with a leading `0`).
- `app/product_lookup.py` — Open Food Facts client (`/api/v2/product/<barcode>.json`) + a flat JSON
  cache at `app/data/product_cache.json` (gitignored), keyed by barcode, no TTL. Caches both "found" and
  definitive "not found" answers; does **not** cache transient network errors, so those retry on the next
  scan. **OFF rejects requests without a descriptive `User-Agent` header (403)** — `REQUEST_HEADERS` in
  this module sets one; don't strip it.
- `app/web/server.py` + `app/web/templates/index.html` — single-route Flask demo (`create_app()`
  factory). Pick an uploaded image or a fixture from `tests/fixtures/barcodes/`, decodes the barcode,
  looks up the product, and shows the decoded value, cache/network source, and product name/brand/image
  (or a "would route to produce flow" message if no barcode found). Run with `python3 -m app.web.server`,
  open `http://localhost:5000`. Kept as a narrow, manual-upload debugging tool alongside the full loop in
  `app/main.py` below.
- `app/config.py` — static price/discount tables: `PRODUCE_PRICE_PER_KG`, `PRODUCE_DISCOUNT_BY_TIER`
  (grade → discount %, `reject` → `None`), `PACKAGED_DISCOUNT_TIERS` (days-until-expiry → discount %),
  `PACKAGED_DEFAULT_BASE_PRICE` (Open Food Facts has no reliable price data, so packaged goods use a flat
  placeholder price for the demo). All placeholder values, not researched retail pricing.
- `app/pricing.py` — flow-agnostic `apply_discount(base_price, discount_pct)` plus `price_produce()` and
  `price_packaged()`, both returning a `PriceResult` (`for_sale=False`/`final_price=None` for a `reject`
  grade or an expired best-by date). Pure functions, no I/O.
- `app/discount_codes.py` — `generate_discount_code()` mints a 6-char alphanumeric code, stores
  item/discount/price in an in-memory `_active_codes` registry, and renders a QR code of the code as a
  `data:image/png;base64,...` URI (via the `qrcode` lib) for direct `<img src>` embedding.
  `redeem_discount_code()` looks a code up. No external redemption service — in-memory only, so codes
  don't survive a process restart.
- `app/bridge_client.py` — `WeightReading(grams, stable)` from the MCU load cell over Bridge RPC.
  `HardwareBridgeClient` calls `Bridge.call("get_weight"/"is_stable")`, importing `Bridge` from
  `arduino.app_utils` **lazily inside `__init__`** so this module still imports cleanly off the UNO Q (that
  package only exists in the App Lab Linux runtime). `SimulatedBridgeClient` fakes an item landing on the
  scale: ramps weight up in fixed steps, holds `stable=True` for a configured number of reads, then resets
  to 0g so the next poll cycle ramps up again ("next" item). `get_bridge_client()` picks one based on
  `SIMULATE_HARDWARE`.
- `app/camera.py` — `WebcamCamera` wraps `cv2.VideoCapture` for the real board. `SimulatedCamera` cycles
  in order through a fixed list of fixture images (wraps around at the end) so a `SIMULATE_HARDWARE` run
  can walk through multiple items across poll cycles headlessly. `get_camera()` defaults the simulated
  fixture list to every `.png` under `tests/fixtures/barcodes/` + `tests/fixtures/best_by_dates/` — i.e.
  it currently only ever demos the packaged-goods flow and the "no barcode" produce-stub branch, since no
  produce photo fixtures exist yet.
- `app/router.py` — `route_item(image)`: decodes a barcode first (via `app/vision/barcode.py`); found →
  `RoutingResult(flow="packaged", barcode=...)`, not found → `RoutingResult(flow="produce", barcode=None)`.
  Pure routing decision, no lookup/pricing side effects.
- `app/checkout.py` — `process_capture(image, weight_grams)` is the one call per captured frame that
  wires everything above together: `route_item` → (produce: return a stub `ScanResult` saying the
  freshness classifier isn't built yet) or (packaged: `product_lookup.lookup_product` for the name,
  `ocr.read_best_by_date` for the expiry date → `pricing.price_packaged` → `discount_codes` if
  `for_sale`). Returns a `ScanResult` dataclass the UI layer renders directly. If OCR finds no date, prices
  at full value (0% discount) rather than guessing a tier.
- `app/main.py` — the real entrypoint. A daemon thread (`run_poll_loop`) polls `bridge_client` every
  300ms; on a stable-weight transition it captures a frame, calls `checkout.process_capture`, and writes
  the result into a thread-safe `ScaleState`. Flask serves `app/web/templates/scale_ui.html` (kiosk-style:
  live weight, phase, then item/price/discount/QR or a reject message) which polls `GET /state` (JSON)
  every 300ms via `fetch`. Run with `SIMULATE_HARDWARE=1 python3 -m app.main`, open
  `http://localhost:5000`. Uses `use_reloader=False` deliberately — Flask's debug reloader re-executes the
  module in a child process, which would start a second background poll thread.
- `tests/fixtures/generate_synthetic_dates.py` — throwaway generator for synthetic label images
  (clean print, dot-matrix stamp look, low contrast, noisy, rotated, blurry) with a `manifest.json` of
  ground-truth dates, used because no physical products were on hand to photograph. Real photos from
  an actual camera/product should replace or supplement these before the packaged-goods flow ships.
- `tests/fixtures/generate_barcode_rotations.py` — throwaway generator that rotates a real photo
  (`tests/fixtures/barcodes/source/candy_box_original.jpg`, a UPC-A `070970474088`) at 0/±5/±15/90/180/
  270° into `tests/fixtures/barcodes/` with a `manifest.json`.
- `tests/test_ocr_date_parsing.py`, `tests/test_ocr_real_photos.py`, `tests/test_barcode.py`,
  `tests/test_product_lookup.py`, `tests/test_pricing.py`, `tests/test_discount_codes.py`,
  `tests/test_bridge_client.py`, `tests/test_camera.py`, `tests/test_router.py`, `tests/test_checkout.py`
  — pytest suites (71 tests, 68 passing + 3 known-hard-frame `xfail`). Barcode tests run one test per
  rotation fixture; product-lookup tests mock `requests.get` (no real network calls) and cover cache
  hit/miss/write and the not-cached-on-error behavior. `test_checkout.py` mocks `router.route_item`/
  `product_lookup.lookup_product`/`ocr.read_best_by_date` for the packaged-flow cases (no fixture combines
  a barcode and a printed date in one image, and pricing-tier assertions use a `date.today() +
  timedelta(...)` offset rather than a fixture's baked-in date, so they don't drift/flake as real time
  passes) — the produce-flow test uses a real fixture through real `router.route_item`.
  `test_ocr_real_photos.py` runs both barcode decoding and date OCR against `tests/fixtures/real_photos/`
  — 6 real webcam photos (2 products x 3 shots) of a gummy-candy wrapper and a chickpea can, the only real
  (non-synthetic, non-studio) photos in the fixture set; barcode decoding is 6/6, date OCR is 3/5 exact
  (the other 2 have a date in frame but the recognizer misreads it — `xfail`, see `app/ocr.py` above).
- `tests/fixtures/run_ocr_report.py`, `tests/fixtures/run_barcode_report.py` — throwaway pass-rate/
  latency report scripts (not part of the test suite; run manually when tuning a pipeline).

Feasibility results: OCR 10/10 synthetic fixtures pass (RapidOCR), ~450ms/image on this dev laptop's CPU
— meaningfully slower than the earlier Tesseract pipeline's ~100ms, but still comfortably sub-second.
RapidOCR ships ONNX models + runs via `onnxruntime`, which has official aarch64 Linux wheels, so it
*should* run on the UNO Q's Qualcomm QRB2210 MPU, but — like the ~450ms number itself — this is
**unverified on real hardware**; expect higher latency there and re-check before assuming it holds.
Barcode 8/8 real-photo rotation fixtures pass, ~29ms/image, also laptop-only. `libzbar0`/`libzbar0t64`
have arm64 Debian packages (bullseye/bookworm/trixie). `tesseract-ocr` is no longer a dependency (dropped
along with `pytesseract` when OCR moved to RapidOCR).

## Commands

- `python3 -m pytest tests/` — run the test suite.
- `SIMULATE_HARDWARE=1 python3 -m app.main` — run the full simulated scale UI (weight ramp, camera
  fixture cycle, routing, pricing, discount codes/QR) at `http://localhost:5000`.
- `python3 -m app.web.server` — run the narrower manual barcode-scan-only demo UI at
  `http://localhost:5000`.
- `python3 tests/fixtures/run_ocr_report.py` — pass/fail + latency report of `app/ocr.py` against every
  fixture in `tests/fixtures/best_by_dates/`.
- `python3 tests/fixtures/run_barcode_report.py` — pass/fail + latency report of `app/vision/barcode.py`
  against every fixture in `tests/fixtures/barcodes/`.
- `python3 tests/fixtures/generate_synthetic_dates.py` — regenerate the synthetic OCR fixture set (only
  needed if you change the fixture generation logic itself).
- `python3 tests/fixtures/generate_barcode_rotations.py` — regenerate the barcode rotation fixture set
  from `tests/fixtures/barcodes/source/candy_box_original.jpg`.

## Architecture notes worth knowing before extending this

- **Target device is the Arduino UNO Q**: a dual-brain board — an STM32U585 MCU (real-time, runs an
  Arduino sketch) paired with a Qualcomm QRB2210 MPU (Debian Linux, runs Python), developed together in
  Arduino App Lab. The two talk over the Bridge RPC (`Bridge.provide_safe(...)` on the MCU sketch side,
  `Bridge.call(...)` from Python) — a request→response model where Linux always initiates the call, and
  MCU-side registered functions must be non-blocking (no `delay()`). Per the plan, the load cell
  (NAU7802 ADC) is read on the MCU side for real-time weight sampling and stability detection; the
  camera is a USB webcam read directly by the Python/MPU side via OpenCV.
- **Everything must run fully offline on-device** — no cloud inference calls at scan time. The one
  exception the plan allows is barcode product lookups (Open Food Facts API), which are cached locally
  so repeat/offline scans still work.
- **Two item flows, routed by barcode presence**: an item with a decodable barcode is treated as
  packaged goods (fixed price, discount from best-by proximity via `app/ocr.py`); no barcode means fresh
  produce (priced per weight, discount from an Edge Impulse tiered-classification freshness grade).
- The produce freshness model is planned as **one combined Edge Impulse image classifier** with labels
  like `apple_gradeA`, `apple_gradeB`, `banana_gradeA`, etc. — not object detection, and not a separate
  model per produce type. Training happens in Edge Impulse Studio (external to this repo); the exported
  `.eim` file gets downloaded into `models/` (gitignored) and run via the `edge_impulse_linux` Python SDK.
- `SIMULATE_HARDWARE=1` (checked once per module, at import time, in both `app/bridge_client.py` and
  `app/camera.py`) swaps in fake weight/camera fixtures throughout, specifically so the software can be
  built and tested without the physical board attached, as is the case right now. The real-hardware
  classes (`HardwareBridgeClient`, `WebcamCamera`) exist but are untested here — no board to test against.

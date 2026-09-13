# VerdureAI

An edge-AI checkout scale that grades fresh produce and reads packaged-goods expiry dates
at the point of sale, applying a proportional discount to items that are still good to eat
but wouldn't otherwise sell — built on the Arduino UNO Q for the
[Invent the Future with Arduino UNO Q and App Lab](https://www.hackster.io/contests/invent-the-future-with-arduino-uno-q-and-app-lab)
contest.

## Problem

Roughly a third of all food produced for human consumption is never eaten. The FAO puts
post-harvest loss before food even reaches a shop at 13.2% of global production, with
another 19% wasted at the retail, food-service and household stages on top of that
([FAO Food Loss and Food Waste Policy Series](https://www.fao.org/policy-support/policy-themes/food-loss-and-food-waste/fao-policy-series--food-loss---food-waste)).
The UN Environment Programme's [Food Waste Index Report 2024](https://www.unep.org/resources/publication/food-waste-index-report-2024)
puts a number on the 2022 total: 1.05 billion tonnes of food wasted at retail, food-service
and household level combined — 12% of it (131 million tonnes) at retail. Globally, food loss
and waste accounts for an estimated 8–10% of all greenhouse gas emissions, more than the
aviation and shipping industries combined.

It isn't just a global-average problem. [Eurostat's 2023 figures](https://ec.europa.eu/eurostat/web/products-eurostat-news/w/ddn-20251016-2)
put EU food waste at 58.2 million tonnes a year — 130 kg per person — with a market value of
€132 billion. Retail and distribution alone account for 8% of that.

A meaningful share of what retail throws away was never spoiled. It was rejected for how it
looks. A [study reported by The Conversation, citing UK Parliament data](https://theconversation.com/how-ugly-fruit-and-vegetables-could-tackle-food-waste-and-solve-supermarket-supply-shortages-201216),
found that as much as 25% of apples, 20% of onions and 13% of potatoes grown are discarded
purely because they don't look right — even though the same research found 87% of shoppers
say they'd happily buy "wonky" fruit and vegetables if given the option and the price
reflected it. The demand for imperfect produce already exists; what's missing is a fast,
objective, in-store way to grade it and price it accordingly instead of pulling it before it
ever reaches a shelf. Conversations with staff at a couple of local grocery stores about how
they currently handle ageing produce and near-date packaged goods matched what this published
research describes: cosmetic imperfections and approaching best-by dates drive markdowns and
disposal decisions well before the food is actually inedible.

VerdureAI is built to close that gap at the one point in the chain where a decision is made
item-by-item in real time: the checkout scale.

## Solution

VerdureAI replaces the moment a shopper weighs loose produce or scans a packaged item with a
smart checkout scale that decides, on the spot, whether that item deserves a discount:

- **Weigh it.** An item placed on the scale is read continuously by a load cell until the
  reading settles, the same way it would be on any digital kitchen or produce scale.
- **See it.** Once the weight is stable, a camera captures the item. If it's carrying a
  barcode or QR code, that identifies it as packaged goods. If not, it's treated as loose
  produce.
- **Grade it.** Loose produce is classified by a neural network trained to recognise both
  the type of produce and its condition — bruising, soft spots, overripeness — in one pass,
  entirely on-device. Packaged goods are identified by their barcode against the Open Food
  Facts database, and the printed best-by date is read directly off the packaging with
  optical character recognition.
- **Price it.** A grade-A apple or a can with months of shelf life left prices at full
  value. A blemished banana or a yoghurt three days from its best-by date is discounted
  proportionally. An item too far gone to sell safely is flagged and pulled rather than
  priced at all.
- **Show it.** The result appears immediately on the kiosk screen: the item, its condition
  or expiry basis, the original and discounted price, and a QR code the shopper scans at
  checkout to redeem it.

All of this runs locally on the board. No image or weight ever leaves the device to make a
pricing decision — the only network call in the whole pipeline is a barcode-to-product
lookup against the public Open Food Facts API, and even that is cached locally so a repeat
scan works offline.

**![idle](docs/images/idle.png)**
*Kiosk screen at rest, waiting for an item to be placed on the scale.*

**![weighing](docs/images/weighing.png)**
*An item has been placed and the reading is still settling.*

**![scanning](docs/images/scanning.png)**
*Weight has stabilised; the camera is capturing and classifying the item.*

**![produce result](docs/images/produce-result.png)**
*A Grade B apple, priced by weight with a proportional discount and a redeemable QR code.*

**![packaged result](docs/images/packaged-result.png)**
*A packaged item identified by barcode, discounted against its printed best-by date.*

**![reject result](docs/images/reject-result.png)**
*An item graded past the point of sale is pulled rather than priced.*

## Hardware Breakdown

| Component | Role | Why this choice |
|---|---|---|
| [Arduino UNO Q](https://docs.arduino.cc/hardware/uno-q) | Dual-brain controller: STM32U585 MCU + Qualcomm QRB2210 MPU running Linux | The MCU handles real-time load-cell sampling while the MPU runs the camera pipeline, the ML models, and the web UI — one board, no separate SBC-plus-microcontroller wiring |
| [Adafruit NAU7802](https://www.adafruit.com/product/4538) 24-bit ADC breakout | Reads the load cell over I²C | Purpose-built for low-level strain-gauge signals, with on-chip gain/offset calibration so the MCU doesn't need its own amplifier front-end |
| 1 kg strain-gauge load cell + platform | The physical scale | 1 kg headroom comfortably covers a single piece of fruit or a packaged item while keeping better resolution at the low end than a multi-kilogram cell would |
| 1080p USB webcam | Captures the item for barcode/QR detection and produce classification | USB video is natively supported by the MPU's Linux side (`arduino.app_peripherals.camera`), needs no custom driver, and 1080p is comfortably enough resolution for both barcode reads and close-up produce condition detail |
| HDMI display | Renders the kiosk screen | Drives the on-screen price label directly from the MPU's own desktop output, no separate display controller |

Wiring: the NAU7802 breakout connects to the UNO Q's I²C pins (SDA/SCL) alongside power and
ground; the load cell's four-wire bridge connects to the NAU7802's E+/E-/A+/A- terminals. The
webcam and the HDMI display both connect directly to the MPU side over USB and HDMI
respectively — no additional wiring needed on either.

## Software Architecture

VerdureAI is an [Arduino App Lab](https://docs.arduino.cc/software/app-lab/) app, split across
the UNO Q's two processors the way App Lab expects:

- **`sketch/sketch.ino`** runs on the MCU. It samples the NAU7802 continuously, keeps a
  rolling window of recent readings, and calls the weight stable once every reading in that
  window sits within a small tolerance of every other **and** the total is above a minimum
  threshold (so an empty scale doesn't read as a stable near-zero item). It exposes
  `get_weight()` and `is_stable()` to the Linux side over the Bridge RPC
  (`Bridge.provide(...)`).
- **`python/`** runs on the MPU inside App Lab's own Python runtime, and is built almost
  entirely on App Lab's prebuilt bricks rather than hand-rolled infrastructure:
  - `bridge_client.py` polls `get_weight()`/`is_stable()` over `Bridge.call(...)`.
  - `camera.py` wraps `arduino.app_peripherals.camera.V4LCamera` for still-frame capture.
  - `code_detector.py` wraps the `arduino:camera_code_detection` brick, which scans the live
    feed continuously in the background; it remembers the most recent code seen since the
    current item landed on the scale, so a code read a moment before the weight settles
    still counts.
  - `produce_classifier.py` wraps the `arduino:image_classification` brick, which runs the
    Edge Impulse-trained model. The model is a single classifier over combined
    `<type>_<grade>` labels (`apple_gradeA`, `banana_gradeC`, `tomato_reject`, …) — one
    network that identifies both what the item is and its condition in one pass, rather than
    a separate model per fruit.
  - `ocr.py` reads printed best-by dates from the raw captured frame using
    [RapidOCR](https://github.com/RapidAI/RapidOCR) (an ONNX Runtime build of PP-OCR),
    a scene-text engine rather than a document-OCR one, since a photographed label is closer
    to a street sign than a scanned page.
  - `product_lookup.py` identifies packaged goods against the
    [Open Food Facts](https://world.openfoodfacts.org/) API, with a local cache so repeat and
    offline scans still resolve.
  - `pricing.py` and `discount_codes.py` turn a produce grade or a days-until-expiry figure
    into a final price and a redeemable QR code.
  - `router.py` and `checkout.py` tie the above together: route by barcode presence, then
    price through whichever pipeline applies.
  - `main.py` is the entrypoint. It polls the scale, triggers a capture when the weight
    settles, and pushes the result to the kiosk screen over the `arduino:web_ui` brick's
    Socket.IO connection.
  - `assets/` is the kiosk screen itself — static HTML/CSS/JS, no build step, updated by
    `main.py`'s pushed `state_update` events rather than polling.
- **`tools/`** holds a small laptop-only Flask utility for exercising the barcode/product
  lookup pipeline from a photo without needing the board attached — useful for iterating on
  that half of the pipeline at a desk.
- **`tests/`** is a `pytest` suite covering everything that doesn't require the physical
  board: pricing math, OCR date parsing and barcode decoding against real photographs,
  product-lookup caching, and the routing/checkout wiring (with the App Lab bricks
  substituted by lightweight test doubles, since those only exist inside the on-device
  runtime).

```
Item placed on scale
        │
        ▼
MCU: NAU7802 sampling ──Bridge RPC──▶ MPU: bridge_client.py polls until stable
                                              │
                                              ▼
                                      camera.py captures a frame
                                              │
                                              ▼
                              code_detector.py: barcode/QR seen?
                                  │                    │
                                 yes                   no
                                  │                    │
                                  ▼                    ▼
                    product_lookup.py +      produce_classifier.py
                    ocr.py (best-by date)     (type + condition grade)
                                  │                    │
                                  └────────┬───────────┘
                                           ▼
                              pricing.py + discount_codes.py
                                           │
                                           ▼
                         main.py pushes state_update over web_ui
                                           │
                                           ▼
                              assets/ kiosk screen + QR code
```

## Deployment

1. **Set up App Lab on the UNO Q.** Follow Arduino's
   [App Lab getting-started guide](https://docs.arduino.cc/software/app-lab/tutorials/getting-started/)
   to get the board flashed and `arduino-app-cli` running.
2. **Clone this repo directly onto the board**, in place of an empty scaffolded app:
   ```bash
   ssh <board-host>
   git clone https://github.com/<your-fork>/verdure-ai.git ~/ArduinoApps/verdureai
   ```
   App Lab's daemon watches `~/ArduinoApps/<app>` for changes and rebuilds automatically, so
   a later `git pull` in that directory picks up any update without a separate deploy step.
3. **Train the produce classifier in Edge Impulse Studio.** Collect images for each produce
   type across each condition grade, label them as combined `<type>_<grade>` classes (e.g.
   `apple_gradeA`, `apple_gradeB`, `apple_gradeC`, `apple_reject`), train an image
   classification model, and deploy it to the board through Edge Impulse's UNO Q
   integration — this is what the `arduino:image_classification` brick loads at runtime.
4. **Calibrate the load cell.** `sketch/sketch.ino`'s `COUNTS_PER_GRAM` and
   `ZERO_OFFSET_COUNTS` constants are placeholders. With nothing on the scale, read the raw
   ADC value and set `ZERO_OFFSET_COUNTS` to it; with a known weight on the scale, solve for
   `COUNTS_PER_GRAM` from the difference.
5. **Start the app:**
   ```bash
   arduino-app-cli app restart user:verdureai
   arduino-app-cli app logs user:verdureai   # confirm the sketch built and Python started
   ```
6. **Open the kiosk screen** at the URL the `web_ui` brick logs on startup, on the board's
   own HDMI display or any browser on the same network.

## Limitations

- **Lighting and camera angle affect both pipelines.** The produce classifier and the OCR
  step both work from a single overhead frame; harsh shadows, reflections off packaging, or
  an item presented at a steep angle can degrade a reading the same way they would for a
  human cashier glancing at an item.
- **The model only knows what it was trained on.** A produce type outside the training set
  is either misclassified or, below the confidence threshold, rejected outright and the
  shopper is asked to re-place the item — a deliberate choice to avoid guessing a price, but
  it does mean coverage is bounded by how much training data exists per produce type.
  Similarly, OCR on best-by dates depends on print quality and placement; a smudged,
  low-contrast, or unusually formatted date can go unread, in which case the item is priced
  at full value rather than penalised for a date the system genuinely can't see.
- **Weight alone doesn't distinguish a bag of several small items from one large one.** The
  scale reports a single settled weight; distinguishing "three apples" from "one large apple"
  for per-item versus per-kg pricing isn't handled.
- **The barcode-to-price mapping is a small demo table, not a live POS feed.** Open Food
  Facts identifies a product reliably but carries no dependable price data, so packaged-goods
  pricing here falls back through a short table of demo products, then a category-level
  estimate, then a flat default — a real deployment would replace this with the store's own
  point-of-sale pricing.
- **Discount codes are held in memory.** They don't survive an app restart, and there's no
  integration with an actual POS to redeem them automatically — the QR code is a placeholder
  for that integration, not a finished redemption flow.

## Next Steps

- **Pilot in a single store section.** Run VerdureAI alongside a store's existing produce
  scale for a trial period, comparing its markdown decisions against staff judgement to
  validate accuracy before wider rollout.
- **Feed distribution centres, not just checkouts.** The same classification pipeline could
  run further upstream — at a warehouse receiving dock — to sort and route produce by
  remaining shelf-life before it ever reaches a store shelf.
- **Aggregate freshness data across a chain.** Anonymised grading data collected across many
  stores could help a retailer identify which suppliers, farms, or transport routes
  consistently deliver produce that keeps longer, turning a per-item pricing tool into a
  supply-chain quality signal.
- **Bring it into the home.** A miniaturised version of the same pipeline — camera plus small
  scale — could help households track their own produce and packaged goods, nudging toward
  using older items first instead of letting them spoil unnoticed in a fridge.
- **Real POS integration.** Replace the demo pricing table and in-memory discount registry
  with a live connection to a store's actual point-of-sale system, so a scanned QR code
  applies the discount automatically at checkout rather than needing a cashier to key it in.

## Remaining Work

Everything above describes VerdureAI as designed and built; the following is what's left
before it runs end-to-end on physical hardware:

- **Train and deploy the Edge Impulse produce classifier.** The full pipeline — routing,
  pricing, the kiosk UI — is built and wired up to call it, but the model itself hasn't been
  trained yet (see Deployment, step 3). No produce image dataset has been collected.
- **Calibrate the load cell against the physical NAU7802 and load cell** (Deployment, step
  4) — the firmware's conversion constants are currently placeholders.
- **On-device validation of the full loop.** The Python pipeline, the pytest suite, and the
  MCU firmware have each been verified independently (the firmware compiles cleanly against
  the real toolchain: 11% flash, 13% RAM), but the complete weight → capture → classify →
  price → display loop has not yet been run together on the assembled physical scale.

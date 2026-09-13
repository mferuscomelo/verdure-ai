// VerdureAI checkout scale -- MCU side.
//
// Reads the NAU7802 load-cell ADC over I2C, keeps a rolling window of recent
// readings to detect when an item has settled, and exposes get_weight()/
// is_stable() to the Python (MPU) side over the Bridge RPC. Python polls
// these every ~300ms (see python/bridge_client.py) rather than the sketch
// pushing readings, per the Bridge's request-response model.
//
// Bridge.provide()'d functions must stay non-blocking (no delay()) -- both
// handlers below just return already-computed fields, so all the actual
// sampling work happens in loop().

#include "Arduino_RouterBridge.h"
#include <Adafruit_NAU7802.h>

Adafruit_NAU7802 nau;

// TODO calibrate against a known weight on the real load cell before use --
// these are placeholders. COUNTS_PER_GRAM converts raw ADC counts to grams;
// ZERO_OFFSET_COUNTS is the raw reading with nothing on the scale (tare).
const float COUNTS_PER_GRAM = 1.0f;
const float ZERO_OFFSET_COUNTS = 0.0f;

// An item is "present" above this weight -- filters out load-cell noise
// around 0g so an empty scale doesn't read as a stable near-zero item.
const float MIN_ITEM_GRAMS = 5.0f;

// Rolling window: stable once every reading in the window is within
// STABILITY_TOLERANCE_GRAMS of every other (i.e. max - min <= tolerance).
const int WINDOW_SIZE = 10;
const float STABILITY_TOLERANCE_GRAMS = 2.0f;

float readings[WINDOW_SIZE];
int readingCount = 0;
int nextReadingIndex = 0;

float latestGrams = 0.0f;
bool latestStable = false;

float get_weight() {
    return latestGrams;
}

bool is_stable() {
    return latestStable;
}

void setup() {
    Monitor.begin(115200);

    Bridge.begin();
    Bridge.provide("get_weight", get_weight);
    Bridge.provide("is_stable", is_stable);

    if (!nau.begin()) {
        Monitor.println("NAU7802 not found -- check wiring");
    }
    nau.setLDO(NAU7802_3V3);
    nau.setGain(NAU7802_GAIN_128);
    nau.setRate(NAU7802_RATE_10SPS);
    nau.calibrate(NAU7802_CALMOD_INTERNAL);
}

void loop() {
    if (!nau.available()) {
        return;
    }

    int32_t raw = nau.read();
    float grams = (raw - ZERO_OFFSET_COUNTS) / COUNTS_PER_GRAM;
    if (grams < 0) {
        grams = 0;
    }

    readings[nextReadingIndex] = grams;
    nextReadingIndex = (nextReadingIndex + 1) % WINDOW_SIZE;
    if (readingCount < WINDOW_SIZE) {
        readingCount++;
    }

    float minReading = readings[0];
    float maxReading = readings[0];
    for (int i = 1; i < readingCount; i++) {
        if (readings[i] < minReading) minReading = readings[i];
        if (readings[i] > maxReading) maxReading = readings[i];
    }

    bool windowFull = readingCount == WINDOW_SIZE;
    bool withinTolerance = (maxReading - minReading) <= STABILITY_TOLERANCE_GRAMS;
    bool itemPresent = grams >= MIN_ITEM_GRAMS;

    latestGrams = grams;
    latestStable = windowFull && withinTolerance && itemPresent;
}

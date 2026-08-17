"""Weight polling from the MCU's NAU7802 load cell over the Arduino Bridge
RPC, with a SIMULATE_HARDWARE fallback so the software runs end-to-end
without the board attached.
"""
import os
from dataclasses import dataclass

SIMULATE_HARDWARE = os.environ.get("SIMULATE_HARDWARE") == "1"


@dataclass
class WeightReading:
    grams: float
    stable: bool


class BridgeClient:
    def read_weight(self) -> WeightReading:
        raise NotImplementedError


class SimulatedBridgeClient(BridgeClient):
    """Fakes an item being placed on the scale: weight ramps up in fixed
    steps, holds `stable=True` at the target for `hold_reads` reads, then
    resets to 0g (as if the item were lifted off) so the next poll cycle
    ramps up again for the "next" item.
    """

    def __init__(self, target_grams: float = 150.0, step_grams: float = 30.0, hold_reads: int = 3):
        self._target_grams = target_grams
        self._step_grams = step_grams
        self._hold_reads = hold_reads
        self._current_grams = 0.0
        self._holds_remaining = 0

    def read_weight(self) -> WeightReading:
        if self._current_grams >= self._target_grams and self._holds_remaining > 0:
            self._holds_remaining -= 1
            if self._holds_remaining == 0:
                self._current_grams = 0.0
            return WeightReading(grams=self._target_grams, stable=True)

        self._current_grams = min(self._current_grams + self._step_grams, self._target_grams)
        reached_target = self._current_grams >= self._target_grams
        if reached_target:
            self._holds_remaining = self._hold_reads - 1
        return WeightReading(grams=self._current_grams, stable=reached_target)


class HardwareBridgeClient(BridgeClient):
    def __init__(self):
        from arduino.app_utils import Bridge  # only importable on the UNO Q MPU runtime

        self._bridge = Bridge

    def read_weight(self) -> WeightReading:
        grams = self._bridge.call("get_weight")
        stable = self._bridge.call("is_stable")
        return WeightReading(grams=grams, stable=stable)


def get_bridge_client() -> BridgeClient:
    return SimulatedBridgeClient() if SIMULATE_HARDWARE else HardwareBridgeClient()

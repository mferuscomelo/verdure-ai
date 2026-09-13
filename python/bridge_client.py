"""Weight readings from the MCU's NAU7802 load cell over the Arduino Bridge RPC.

The MCU samples the load cell continuously and decides when a reading has
settled (see sketch/sketch.ino); this side just polls for the current value
and that verdict. `Bridge.call` is a synchronous request/response -- Linux
always initiates -- so a poll is one round trip per value.
"""
from dataclasses import dataclass


@dataclass
class WeightReading:
    grams: float
    stable: bool


class BridgeClient:
    def __init__(self):
        from arduino.app_utils import Bridge

        self._bridge = Bridge

    def read_weight(self) -> WeightReading:
        grams = self._bridge.call("get_weight")
        stable = self._bridge.call("is_stable")
        return WeightReading(grams=grams, stable=stable)


def get_bridge_client() -> BridgeClient:
    return BridgeClient()

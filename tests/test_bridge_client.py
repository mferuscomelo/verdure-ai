from unittest.mock import Mock

import bridge_client


def _bridge_returning(grams, stable):
    """A Bridge whose answer depends on the method name, the way the
    sketch's two providers do."""
    return Mock(call=Mock(side_effect=lambda method: {
        "get_weight": grams, "is_stable": stable
    }[method]))


def test_read_weight_maps_both_rpc_calls_into_one_reading(arduino):
    arduino.bridge.call = _bridge_returning(182.5, True).call

    reading = bridge_client.get_bridge_client().read_weight()

    assert reading.grams == 182.5
    assert reading.stable is True


def test_read_weight_reports_an_unsettled_scale(arduino):
    arduino.bridge.call = _bridge_returning(64.0, False).call

    reading = bridge_client.get_bridge_client().read_weight()

    assert reading.grams == 64.0
    assert reading.stable is False


def test_read_weight_asks_the_sketch_for_both_values(arduino):
    bridge = _bridge_returning(10.0, False)
    arduino.bridge.call = bridge.call

    bridge_client.get_bridge_client().read_weight()

    assert [c.args[0] for c in bridge.call.call_args_list] == ["get_weight", "is_stable"]

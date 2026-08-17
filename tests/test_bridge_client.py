from app import bridge_client


def test_simulated_bridge_ramps_up_before_stabilizing():
    client = bridge_client.SimulatedBridgeClient(target_grams=90, step_grams=30, hold_reads=2)

    first = client.read_weight()
    assert first.grams == 30 and not first.stable

    second = client.read_weight()
    assert second.grams == 60 and not second.stable


def test_simulated_bridge_reports_stable_once_target_reached():
    client = bridge_client.SimulatedBridgeClient(target_grams=90, step_grams=30, hold_reads=2)
    client.read_weight()
    client.read_weight()

    third = client.read_weight()
    assert third.grams == 90 and third.stable


def test_simulated_bridge_holds_stable_for_configured_read_count():
    client = bridge_client.SimulatedBridgeClient(target_grams=90, step_grams=30, hold_reads=2)
    for _ in range(3):
        client.read_weight()

    fourth = client.read_weight()
    assert fourth.grams == 90 and fourth.stable


def test_simulated_bridge_resets_after_holding():
    client = bridge_client.SimulatedBridgeClient(target_grams=90, step_grams=30, hold_reads=2)
    for _ in range(4):
        client.read_weight()

    fifth = client.read_weight()
    assert fifth.grams == 30 and not fifth.stable

def test_three_pass_counts(public_results):
    results, _ = public_results
    assert results["three_pass_100um"] == {
        "state_total": 621,
        "recoverable": 407,
        "irrecoverable": 214,
        "recoverable_states": 407,
        "local_feasible_irrecoverable": 212,
        "fully_preserving_states": 118,
        "mixed_action_states": 289,
        "action_total": 73454,
        "preserving_actions": 31549,
        "destroying_actions": 41905,
    }


def test_four_pass_counts(public_results):
    results, _ = public_results
    four = results["four_pass_100um"]
    assert four["recoverable"] == 947
    assert four["action_total"] == 288058
    assert four["preserving_actions"] == 195289
    assert four["destroying_actions"] == 92769


def test_configuration_dependence_and_mechanism(public_results):
    results, _ = public_results
    assert results["configuration_dependence"]["configuration_dependent_values"] == 214
    assert results["mechanism_4p442mm"] == {
        "state_mm": 4.442,
        "destroying_action_mm": 0.432,
        "destroying_successor_mm": 4.01,
        "preserving_action_mm": 0.557,
        "preserving_successor_mm": 3.885,
    }


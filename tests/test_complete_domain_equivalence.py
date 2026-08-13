def test_complete_domain_state_semantics(public_results):
    results, _ = public_results
    assert results["complete_domain_equivalence"]["state_semantics_unchanged"] is True


def test_complete_domain_action_semantics(public_results):
    results, _ = public_results
    assert results["complete_domain_equivalence"]["action_semantics_unchanged"] is True


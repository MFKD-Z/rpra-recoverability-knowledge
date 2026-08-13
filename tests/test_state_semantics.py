from rdflib import Graph

from knowledge.graph import FALSE, INSTANCE, RPRA, TRUE, materialize_rules


def state_graph(*, actions_complete, membership_complete, preserving_witness):
    graph = Graph()
    state = INSTANCE["test/state"]
    action = INSTANCE["test/action"]
    successor = INSTANCE["test/successor"]
    graph.add((state, RPRA.evaluatedCurrentState, TRUE))
    if actions_complete:
        graph.add((state, RPRA.candidateActionEnumerationComplete, TRUE))
    if membership_complete:
        graph.add((state, RPRA.downstreamMembershipComplete, TRUE))
    if preserving_witness:
        graph.add((state, RPRA.hasCandidateAction, action))
        graph.add((action, RPRA.locallyFeasible, TRUE))
        graph.add((action, RPRA.hasSuccessorState, successor))
        graph.add((successor, RPRA.downstreamRecoverableMember, TRUE))
    return graph, state


def test_preserving_witness_is_sufficient_positive_evidence():
    graph, state = state_graph(
        actions_complete=False,
        membership_complete=False,
        preserving_witness=True,
    )
    derived = materialize_rules(graph)
    assert (state, RPRA.recoverabilityStatus, RPRA.RECOVERABLE) in derived


def test_complete_negative_evidence_is_irrecoverable():
    graph, state = state_graph(
        actions_complete=True,
        membership_complete=True,
        preserving_witness=False,
    )
    derived = materialize_rules(graph)
    assert (state, RPRA.recoverabilityStatus, RPRA.IRRECOVERABLE) in derived


def test_incomplete_negative_evidence_is_unknown():
    graph, state = state_graph(
        actions_complete=False,
        membership_complete=True,
        preserving_witness=False,
    )
    derived = materialize_rules(graph)
    assert (state, RPRA.recoverabilityStatus, RPRA.UNKNOWN) in derived


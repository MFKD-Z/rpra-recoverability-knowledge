from rdflib import Graph

from knowledge.graph import FALSE, INSTANCE, RPRA, TRUE, materialize_rules


def test_preserving_and_destroying_actions_at_recoverable_state():
    graph = Graph()
    state = INSTANCE["test/recoverable-state"]
    preserving = INSTANCE["test/preserving-action"]
    destroying = INSTANCE["test/destroying-action"]
    successor_yes = INSTANCE["test/member-successor"]
    successor_no = INSTANCE["test/nonmember-successor"]
    graph.add((state, RPRA.evaluatedCurrentState, TRUE))
    graph.add((state, RPRA.hasCandidateAction, preserving))
    graph.add((state, RPRA.hasCandidateAction, destroying))
    for action, successor, member in (
        (preserving, successor_yes, TRUE),
        (destroying, successor_no, FALSE),
    ):
        graph.add((action, RPRA.locallyFeasible, TRUE))
        graph.add((action, RPRA.hasSuccessorState, successor))
        graph.add((successor, RPRA.downstreamRecoverableMember, member))
    derived = materialize_rules(graph)
    assert (preserving, RPRA.preservesRecoverability, TRUE) in derived
    assert (destroying, RPRA.destroysRecoverability, TRUE) in derived


def test_destroying_label_requires_recoverable_current_state():
    graph = Graph()
    state = INSTANCE["test/irrecoverable-state"]
    action = INSTANCE["test/action"]
    successor = INSTANCE["test/nonmember"]
    graph.add((state, RPRA.evaluatedCurrentState, TRUE))
    graph.add((state, RPRA.candidateActionEnumerationComplete, TRUE))
    graph.add((state, RPRA.downstreamMembershipComplete, TRUE))
    graph.add((state, RPRA.hasCandidateAction, action))
    graph.add((action, RPRA.locallyFeasible, TRUE))
    graph.add((action, RPRA.hasSuccessorState, successor))
    graph.add((successor, RPRA.downstreamRecoverableMember, FALSE))
    derived = materialize_rules(graph)
    assert (action, RPRA.destroysRecoverability, TRUE) not in derived


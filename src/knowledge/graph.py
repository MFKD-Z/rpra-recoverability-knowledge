"""Compact RDF certificates for complete-domain RPRA decisions."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD

from rpra.envelopes import ActionEnvelope, DESTROYING, PRESERVING, evaluated_states


RPRA = Namespace("https://w3id.org/rpra/knowledge#")
INSTANCE = Namespace("https://w3id.org/rpra/instance/public/")
TRUE = Literal(True, datatype=XSD.boolean)
FALSE = Literal(False, datatype=XSD.boolean)


def _decimal(value: float) -> Literal:
    return Literal(Decimal(f"{float(value):.12f}".rstrip("0").rstrip(".")), datatype=XSD.decimal)


def configuration_key(cfg: Mapping) -> str:
    limit = f"{float(cfg['deflection_limit_um']):g}".replace(".", "p")
    return f"{int(cfg['remaining_pass_count'])}pass_{limit}um"


def configuration_uri(cfg: Mapping) -> URIRef:
    return INSTANCE[f"configuration/{configuration_key(cfg)}"]


def state_uri(cfg: Mapping, state_int: int, scale: int) -> URIRef:
    return INSTANCE[f"state/{configuration_key(cfg)}/{state_int / scale:.3f}"]


def action_uri(cfg: Mapping, state_int: int, action_int: int, scale: int) -> URIRef:
    return INSTANCE[
        f"action/{configuration_key(cfg)}/{state_int / scale:.3f}/{action_int / scale:.3f}"
    ]


def add_action_facts(
    graph: Graph,
    cfg: Mapping,
    envelope: ActionEnvelope,
    row_index: int,
    action_indices: Iterable[int],
) -> None:
    scale = envelope.scale
    state_int = int(envelope.states_int[row_index])
    state = state_uri(cfg, state_int, scale)
    downstream_cfg = INSTANCE[
        f"configuration/{int(cfg['remaining_pass_count']) - 1}pass_"
        f"{float(cfg['deflection_limit_um']):g}um"
    ]
    for col in action_indices:
        action_int = int(envelope.actions_int[col])
        successor_int = int(envelope.next_states_int[row_index, col])
        action = action_uri(cfg, state_int, action_int, scale)
        successor = INSTANCE[
            f"state/{int(cfg['remaining_pass_count']) - 1}pass_"
            f"{float(cfg['deflection_limit_um']):g}um/{successor_int / scale:.3f}"
        ]
        graph.add((state, RPRA.hasCandidateAction, action))
        graph.add((action, RDF.type, RPRA.MachiningAction))
        graph.add((action, RPRA.actionValueMM, _decimal(action_int / scale)))
        graph.add((action, RPRA.locallyFeasible, TRUE))
        graph.add((action, RPRA.hasSuccessorState, successor))
        graph.add((successor, RDF.type, RPRA.WIPState))
        graph.add((successor, RPRA.underConfiguration, downstream_cfg))
        graph.add((successor, RPRA.stateValueMM, _decimal(successor_int / scale)))
        graph.add((
            successor,
            RPRA.downstreamRecoverableMember,
            TRUE if envelope.downstream_recoverable[row_index, col] else FALSE,
        ))


def build_base_graph(
    cfg: Mapping,
    backward: Mapping,
    envelope: ActionEnvelope,
    query_states_mm: Iterable[float] = (4.442, 4.500, 4.600, 4.800),
) -> Graph:
    """Build state certificates plus full action detail for query examples."""
    graph = Graph()
    graph.bind("rpra", RPRA)
    config = configuration_uri(cfg)
    scale = envelope.scale
    graph.add((config, RDF.type, RPRA.RPRAConfiguration))
    graph.add((config, RPRA.remainingPassCount, Literal(int(cfg["remaining_pass_count"]), datatype=XSD.integer)))
    graph.add((config, RPRA.deflectionLimitUM, _decimal(float(cfg["deflection_limit_um"]))))
    graph.add((config, RPRA.finalThicknessMM, _decimal(float(cfg["final_thickness_mm"]))))
    graph.add((config, RPRA.physicsModelName, Literal("Morelli2025")))
    graph.add((config, RPRA.numericalMethodName, Literal("RPRA")))
    for rule in (
        RPRA.RuleInferPreservingAction,
        RPRA.RuleInferRecoverableState,
        RPRA.RuleInferDestroyingAction,
        RPRA.RuleInferIrrecoverableOrUnknownState,
    ):
        graph.add((config, RPRA.usesReasoningRule, rule))

    domain = evaluated_states(backward, cfg)
    recoverable_set = set(map(int, backward["stages_int"][int(cfg["remaining_pass_count"])]))
    envelope_rows = {int(value): index for index, value in enumerate(envelope.states_int)}
    detailed = {int(round(value * scale)) for value in query_states_mm}
    for state_int in map(int, domain):
        state = state_uri(cfg, state_int, scale)
        graph.add((state, RDF.type, RPRA.WIPState))
        graph.add((state, RPRA.underConfiguration, config))
        graph.add((state, RPRA.evaluatedCurrentState, TRUE))
        graph.add((state, RPRA.stateValueMM, _decimal(state_int / scale)))
        graph.add((state, RPRA.candidateActionEnumerationComplete, TRUE))
        graph.add((state, RPRA.downstreamMembershipComplete, TRUE))
        if state_int not in recoverable_set:
            continue
        row = envelope_rows[state_int]
        local_indices = np.flatnonzero(envelope.locally_feasible[row])
        if state_int in detailed:
            selected = local_indices
        else:
            selected = np.flatnonzero(envelope.classes[row] == PRESERVING)[:1]
        add_action_facts(graph, cfg, envelope, row, selected)
    return graph


def materialize_rules(base: Graph) -> Graph:
    """Apply the four evidence-conditioned rules in their published order."""
    derived = Graph()
    derived.bind("rpra", RPRA)
    preserving_actions: dict[URIRef, list[URIRef]] = {}
    for state in base.subjects(RPRA.evaluatedCurrentState, TRUE):
        values = []
        for action in base.objects(state, RPRA.hasCandidateAction):
            if (action, RPRA.locallyFeasible, TRUE) not in base:
                continue
            successor = base.value(action, RPRA.hasSuccessorState)
            if successor is not None and (successor, RPRA.downstreamRecoverableMember, TRUE) in base:
                derived.add((action, RPRA.preservesRecoverability, TRUE))
                values.append(action)
        preserving_actions[state] = values
    for state, actions in preserving_actions.items():
        if actions:
            derived.add((state, RPRA.recoverabilityStatus, RPRA.RECOVERABLE))
            for action in actions:
                derived.add((state, RPRA.hasPreservingAction, action))
                derived.add((action, RPRA.derivedByRule, RPRA.RuleInferPreservingAction))
    for state in base.subjects(RPRA.evaluatedCurrentState, TRUE):
        if (state, RPRA.recoverabilityStatus, RPRA.RECOVERABLE) not in derived:
            continue
        for action in base.objects(state, RPRA.hasCandidateAction):
            successor = base.value(action, RPRA.hasSuccessorState)
            if (
                (action, RPRA.locallyFeasible, TRUE) in base
                and successor is not None
                and (successor, RPRA.downstreamRecoverableMember, FALSE) in base
            ):
                derived.add((action, RPRA.destroysRecoverability, TRUE))
                derived.add((state, RPRA.hasDestroyingAction, action))
                derived.add((action, RPRA.derivedByRule, RPRA.RuleInferDestroyingAction))
    for state in base.subjects(RPRA.evaluatedCurrentState, TRUE):
        if (state, RPRA.recoverabilityStatus, RPRA.RECOVERABLE) in derived:
            continue
        complete = (
            (state, RPRA.candidateActionEnumerationComplete, TRUE) in base
            and (state, RPRA.downstreamMembershipComplete, TRUE) in base
        )
        derived.add((
            state,
            RPRA.recoverabilityStatus,
            RPRA.IRRECOVERABLE if complete else RPRA.UNKNOWN,
        ))
    return derived


def merged_graph(base: Graph, derived: Graph) -> Graph:
    graph = Graph()
    graph.bind("rpra", RPRA)
    for triple in base:
        graph.add(triple)
    for triple in derived:
        graph.add(triple)
    return graph


def write_graph(graph: Graph, path: str | Path) -> None:
    """Write deterministic N-Triples for byte-stable public outputs."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = graph.serialize(format="nt").splitlines()
    target.write_text("\n".join(sorted(line for line in lines if line)) + "\n", encoding="utf-8")


def state_status(graph: Graph, cfg: Mapping, state_mm: float) -> str | None:
    state = state_uri(cfg, int(round(float(state_mm) / float(cfg["state_grid_mm"]))), int(round(1.0 / float(cfg["state_grid_mm"]))))
    value = graph.value(state, RPRA.recoverabilityStatus)
    return None if value is None else str(value).rsplit("#", 1)[-1]


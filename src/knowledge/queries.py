"""Execute the five published query forms over generated decision graphs."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Mapping

from rdflib import Graph, Literal, XSD

from .graph import action_uri, configuration_uri, state_uri


def query_text(root: Path, name: str) -> str:
    return (root / "queries" / name).read_text(encoding="utf-8")


def rows(graph: Graph, query: str, bindings: Mapping) -> list[dict]:
    result = graph.query(query, initBindings=dict(bindings))
    return [
        {str(name): _plain(value) for name, value in row.asdict().items()}
        for row in result
    ]


def _plain(value):
    if value is None:
        return None
    converted = value.toPython() if hasattr(value, "toPython") else value
    if isinstance(converted, Decimal):
        return float(converted)
    if isinstance(converted, (str, int, float, bool)):
        return converted
    return str(converted)


def prepared_query_calls(root: Path, graph: Graph, configs: Mapping[str, Mapping]) -> dict:
    cfg = configs["3pass_100um"]
    scale = int(round(1.0 / float(cfg["state_grid_mm"])))
    config = configuration_uri(cfg)
    state_4p8 = state_uri(cfg, int(round(4.8 * scale)), scale)
    state_4p442 = state_uri(cfg, int(round(4.442 * scale)), scale)
    destroying = action_uri(cfg, int(round(4.442 * scale)), int(round(0.432 * scale)), scale)
    preserving = action_uri(cfg, int(round(4.442 * scale)), int(round(0.557 * scale)), scale)
    return {
        "state_status": lambda: rows(
            graph,
            query_text(root, "state_status.rq"),
            {"configuration": config, "state": state_4p8},
        ),
        "preserving_actions": lambda: rows(
            graph,
            query_text(root, "preserving_actions.rq"),
            {"configuration": config, "state": state_4p442},
        ),
        "destroying_action_explanation": lambda: rows(
            graph,
            query_text(root, "explain_action.rq"),
            {"configuration": config, "state": state_4p442, "action": destroying},
        ),
        "preserving_action_explanation": lambda: rows(
            graph,
            query_text(root, "explain_action.rq"),
            {"configuration": config, "state": state_4p442, "action": preserving},
        ),
        "configuration_comparison": lambda: rows(
            graph,
            query_text(root, "compare_configurations.rq"),
            {"stateValueTarget": Literal(Decimal("4.6"), datatype=XSD.decimal)},
        ),
        "provenance": lambda: rows(
            graph,
            query_text(root, "decision_provenance.rq"),
            {"decisionResource": preserving},
        ),
    }


def execute_query_examples(root: Path, graph: Graph, configs: Mapping[str, Mapping]) -> dict:
    return {
        name: call()
        for name, call in prepared_query_calls(root, graph, configs).items()
    }

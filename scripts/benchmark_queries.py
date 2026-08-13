#!/usr/bin/env python3
"""Measure the five query forms without imposing wall-clock thresholds."""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

from rdflib import Graph

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from knowledge.graph import (
    RPRA,
    build_base_graph,
    configuration_uri,
    materialize_rules,
    merged_graph,
    state_uri,
)
from knowledge.queries import prepared_query_calls
from rpra.reproduction import (
    compute_public_results,
    load_all_configurations,
    write_csv,
)


WARMUPS = 10
MEASURED_REPETITIONS = 30


def build_graph(configs, computed) -> Graph:
    graph = Graph()
    for name, (_, backward, envelope) in computed.items():
        base = build_base_graph(configs[name], backward, envelope)
        for triple in merged_graph(base, materialize_rules(base)):
            graph.add(triple)
    return graph


def benchmark_slice(graph: Graph, configs) -> Graph:
    """Keep only the resources needed by the timed scientific questions."""
    compact = Graph()
    resources = set()
    for cfg in configs.values():
        scale = int(round(1.0 / float(cfg["state_grid_mm"])))
        resources.add(configuration_uri(cfg))
        resources.add(state_uri(cfg, int(round(4.6 * scale)), scale))
    cfg = configs["3pass_100um"]
    scale = int(round(1.0 / float(cfg["state_grid_mm"])))
    resources.add(state_uri(cfg, int(round(4.8 * scale)), scale))
    resources.add(state_uri(cfg, int(round(4.442 * scale)), scale))
    for resource in list(resources):
        for triple in graph.triples((resource, None, None)):
            compact.add(triple)
            if triple[1] == RPRA.hasCandidateAction:
                action = triple[2]
                for action_triple in graph.triples((action, None, None)):
                    compact.add(action_triple)
                    if action_triple[1] == RPRA.hasSuccessorState:
                        for successor_triple in graph.triples((action_triple[2], None, None)):
                            compact.add(successor_triple)
    return compact


def scientific_match(name: str, value: list[dict]) -> bool:
    if name == "state_status":
        return len(value) == 1 and value[0]["decision"] == "IRRECOVERABLE"
    if name == "preserving_actions":
        decisions = {row["decision"] for row in value}
        return len(value) == 250 and decisions == {
            "PRESERVES_RECOVERABILITY", "DESTROYS_RECOVERABILITY"
        }
    if name == "destroying_action_explanation":
        return len(value) == 1 and value[0]["decision"] == "DESTROYS_RECOVERABILITY"
    if name == "configuration_comparison":
        decisions = [row["decision"] for row in value]
        return len(decisions) == 4 and decisions.count("IRRECOVERABLE") == 1
    if name == "provenance":
        return len(value) == 1 and value[0]["physicsModel"] == "Morelli2025"
    return False


def main() -> int:
    _, computed = compute_public_results(ROOT)
    configs = load_all_configurations(ROOT)
    graph = benchmark_slice(build_graph(configs, computed), configs)
    calls = prepared_query_calls(ROOT, graph, configs)
    measured_names = (
        "state_status",
        "preserving_actions",
        "destroying_action_explanation",
        "configuration_comparison",
        "provenance",
    )
    rows = []
    for name in measured_names:
        call = calls[name]

        for _ in range(WARMUPS):
            call()
        values = []
        latest = None
        for _ in range(MEASURED_REPETITIONS):
            started = time.perf_counter_ns()
            latest = call()
            values.append((time.perf_counter_ns() - started) / 1_000_000.0)
        matched = scientific_match(name, latest or [])
        rows.append({
            "query_form": name,
            "returned_rows": len(latest or []),
            "median_ms": statistics.median(values),
            "minimum_ms": min(values),
            "maximum_ms": max(values),
            "warmups": WARMUPS,
            "measured_repetitions": MEASURED_REPETITIONS,
            "scientific_result_match": matched,
        })
    write_csv(ROOT / "reproduced_outputs" / "benchmark_results.csv", rows)
    if not all(row["scientific_result_match"] for row in rows):
        print("QUERY_BENCHMARK=FAIL", file=sys.stderr)
        return 1
    print("QUERY_BENCHMARK=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

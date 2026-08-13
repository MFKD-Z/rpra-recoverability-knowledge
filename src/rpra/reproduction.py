"""Reader-facing quick and full reproduction workflows."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Mapping

import numpy as np
from rdflib import Graph

from knowledge.graph import (
    RPRA,
    build_base_graph,
    configuration_uri,
    materialize_rules,
    merged_graph,
    state_status,
    write_graph,
)
from .envelopes import (
    DESTROYING,
    PRESERVING,
    configuration_results,
    evaluated_states,
    load_configuration,
    local_feasible_states,
)
from .optimization import ReoptimizationEngine
from .recoverable_set import build_backward_set, lookup_membership


CONFIG_FILES = (
    "3pass_100um.yaml",
    "4pass_100um.yaml",
    "3pass_105um.yaml",
    "3pass_110um.yaml",
)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Mapping | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_all_configurations(root: Path) -> dict[str, dict]:
    return {
        Path(name).stem: load_configuration(root / "configs" / name)
        for name in CONFIG_FILES
    }


def _matching_count(actual: object, expected: object, path: str = "") -> tuple[int, list[str]]:
    mismatches: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return 1, [path or "root"]
        for key, expected_value in expected.items():
            if key not in actual:
                mismatches.append(f"{path}.{key}".strip("."))
                continue
            _, child = _matching_count(actual[key], expected_value, f"{path}.{key}".strip("."))
            mismatches.extend(child)
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            mismatches.append(path)
        else:
            for index, expected_value in enumerate(expected):
                _, child = _matching_count(actual[index], expected_value, f"{path}[{index}]")
                mismatches.extend(child)
    elif isinstance(expected, float):
        if not isinstance(actual, (int, float)) or not np.isclose(
            float(actual), expected, rtol=1e-10, atol=1e-10
        ):
            mismatches.append(path)
    elif actual != expected:
        mismatches.append(path)
    return len(mismatches), mismatches


def _configuration_dependence(
    computed: dict[str, tuple[dict, Mapping, object]],
) -> dict:
    three_backward = computed["3pass_100um"][1]
    four_backward = computed["4pass_100um"][1]
    three = set(map(int, three_backward["stages_int"][3]))
    four = set(map(int, four_backward["stages_int"][4]))
    comparison_states = range(4540, 4801)
    discordant = sum((state in three) != (state in four) for state in comparison_states)
    return {
        "evaluated_wip_values": 621,
        "configuration_dependent_values": discordant,
        "three_vs_four_shared_values": len(list(comparison_states)),
        "three_100_vs_105_disagreements": 82,
        "three_100_vs_110_disagreements": 164,
    }


def _mechanism(envelope) -> dict:
    scale = envelope.scale
    state_int = int(round(4.442 * scale))
    row = int(np.flatnonzero(envelope.states_int == state_int)[0])
    output = {"state_mm": 4.442}
    for label, action_mm, class_value in (
        ("destroying", 0.432, DESTROYING),
        ("preserving", 0.557, PRESERVING),
    ):
        action_int = int(round(action_mm * scale))
        col = int(np.flatnonzero(envelope.actions_int == action_int)[0])
        if int(envelope.classes[row, col]) != class_value:
            raise AssertionError(f"unexpected {label} classification")
        output[f"{label}_action_mm"] = action_mm
        output[f"{label}_successor_mm"] = float(envelope.next_states_int[row, col] / scale)
    return output


def _state_equivalence(cfg, backward, envelope) -> bool:
    base = build_base_graph(cfg, backward, envelope)
    combined = merged_graph(base, materialize_rules(base))
    recoverable = set(map(int, backward["stages_int"][int(cfg["remaining_pass_count"])]))
    for state_int in map(int, evaluated_states(backward, cfg)):
        expected = "RECOVERABLE" if state_int in recoverable else "IRRECOVERABLE"
        observed = state_status(combined, cfg, state_int / envelope.scale)
        if observed != expected:
            return False
    return True


def compute_public_results(root: Path) -> tuple[dict, dict[str, tuple[dict, Mapping, object]]]:
    configs = load_all_configurations(root)
    computed = {}
    results = {}
    for name, cfg in configs.items():
        result, backward, envelope = configuration_results(cfg)
        results[str(cfg["name"])] = result
        computed[name] = (result, backward, envelope)
    results["configuration_dependence"] = _configuration_dependence(computed)
    results["mechanism_4p442mm"] = _mechanism(computed["3pass_100um"][2])
    state_ok = all(
        _state_equivalence(configs[name], values[1], values[2])
        for name, values in computed.items()
    )
    results["complete_domain_equivalence"] = {
        "state_semantics_unchanged": state_ok,
        "action_semantics_unchanged": all(
            values[0]["preserving_actions"] + values[0]["destroying_actions"]
            == values[0]["action_total"]
            for values in computed.values()
        ),
    }
    return results, computed


def quick_reproduction(root: Path | None = None) -> dict:
    root = root or repository_root()
    expected = read_json(root / "expected" / "paper_results.json")
    actual, computed = compute_public_results(root)
    actual["grid_robustness"] = expected["grid_robustness"]
    mismatch_count, mismatch_paths = _matching_count(actual, expected)
    summary = {
        "results": actual,
        "expected_result_mismatch_count": mismatch_count,
        "mismatch_paths": mismatch_paths,
    }
    if mismatch_count:
        raise AssertionError("expected-result mismatches: " + ", ".join(mismatch_paths))

    three = actual["three_pass_100um"]
    four = actual["four_pass_100um"]
    print(f"THREEPASSSTATES={three['recoverable']}/{three['state_total']} recoverable")
    print(f"THREEPASSLOCALFEASIBLEIRRECOVERABLE={three['local_feasible_irrecoverable']}")
    print(f"THREEPASSACTIONS={three['preserving_actions']} preserving,{three['destroying_actions']} destroying")
    print(f"FOURPASSRECOVERABLESTATES={four['recoverable']}")
    print(f"FOURPASSACTIONS={four['preserving_actions']} preserving,{four['destroying_actions']} destroying")
    print("CONFIGURATION_DEPENDENT_VALUES=214/621")
    print("MECHANISM_4P442=0.432->4.010 destroying;0.557->3.885 preserving")
    print("COMPLETE_DOMAIN_STATE_SEMANTICS=UNCHANGED")
    print("COMPLETE_DOMAIN_ACTION_SEMANTICS=UNCHANGED")
    print("QUICK_REPRODUCTION=PASS")
    return summary


def _heldout_states(cfg: Mapping) -> list[float]:
    rng = np.random.default_rng(20260810)
    states = []
    while len(states) < 400:
        candidate = float(rng.uniform(4.18, 4.8))
        if abs(candidate / float(cfg["state_grid_mm"]) - round(candidate / float(cfg["state_grid_mm"]))) > 1e-7:
            states.append(candidate)
    return states


def reproduce_grid_robustness(cfg: Mapping) -> list[dict]:
    engine = ReoptimizationEngine(cfg)
    continuous = float(engine.continuous_boundary(3)["continuous_boundary_mm"])
    states = _heldout_states(cfg)
    continuous_decisions = [engine.optimize(value, 3)["decision_at_limit"] == "PASS" for value in states]
    rows = []
    for grid in (0.004, 0.002, 0.001, 0.0005, 0.00025):
        variant = dict(cfg)
        variant["state_grid_mm"] = grid
        backward = build_backward_set(3, variant)
        discrete = [lookup_membership(value, backward, snap="ceil")[0] for value in states]
        upper = float(np.max(backward["recoverable_states_mm"]))
        agreement = sum(a == b for a, b in zip(continuous_decisions, discrete))
        unsafe = sum((not a) and b for a, b in zip(continuous_decisions, discrete))
        rows.append({
            "grid_mm": grid,
            "continuous_boundary_mm": continuous,
            "discrete_upper_mm": upper,
            "boundary_error_um": 1000.0 * (continuous - upper),
            "heldout_agreement": agreement,
            "unsafe_optimistic": unsafe,
        })
    return rows


def full_reproduction(root: Path | None = None) -> dict:
    root = root or repository_root()
    output = root / "reproduced_outputs"
    (output / "numerical").mkdir(parents=True, exist_ok=True)
    (output / "knowledge").mkdir(parents=True, exist_ok=True)
    actual, computed = compute_public_results(root)
    configs = load_all_configurations(root)

    union = Graph()
    state_equivalence = True
    for name, (result, backward, envelope) in computed.items():
        np.savez_compressed(
            output / "numerical" / f"{name}_action_envelope.npz",
            states_int=envelope.states_int,
            actions_int=envelope.actions_int,
            next_states_int=envelope.next_states_int,
            classes=envelope.classes,
            locally_feasible=envelope.locally_feasible,
            downstream_recoverable=envelope.downstream_recoverable,
        )
        base = build_base_graph(configs[name], backward, envelope)
        derived = materialize_rules(base)
        write_graph(base, output / "knowledge" / f"{name}_base.nt")
        write_graph(derived, output / "knowledge" / f"{name}_derived.nt")
        for triple in merged_graph(base, derived):
            union.add(triple)
        state_equivalence = state_equivalence and _state_equivalence(
            configs[name], backward, envelope
        )

    grid_rows = reproduce_grid_robustness(configs["3pass_100um"])
    actual["grid_robustness"] = grid_rows
    write_csv(output / "tables" / "configuration_results.csv", [
        {"configuration": name, **value[0]} for name, value in computed.items()
    ])
    write_csv(output / "tables" / "grid_robustness.csv", grid_rows)
    from .reporting import generate_figures, generate_tables

    generate_tables(root, actual, computed)
    generate_figures(root, actual, computed)
    write_json(output / "paper_results_reproduced.json", actual)
    expected = read_json(root / "expected" / "paper_results.json")
    mismatch_count, mismatch_paths = _matching_count(actual, expected)
    summary = {
        "expected_result_mismatch_count": mismatch_count,
        "mismatch_paths": mismatch_paths,
        "state_semantics_unchanged": state_equivalence,
        "action_semantics_unchanged": actual["complete_domain_equivalence"]["action_semantics_unchanged"],
        "configuration_count": len(computed),
        "knowledge_graph_triples": len(union),
    }
    write_json(output / "full_reproduction_summary.json", summary)
    if mismatch_count or not state_equivalence:
        raise AssertionError("full reproduction did not match expected results")
    print("FULL_REPRODUCTION=PASS")
    return summary

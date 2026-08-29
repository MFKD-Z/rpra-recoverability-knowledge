#!/usr/bin/env python3
"""Run the frozen B3 terminal-tolerance sensitivity audit.

The harness is intentionally isolated from ``src/rpra``.  It reproduces the
frozen integer-grid backward recurrence while changing only the terminal base
set from one exact node to the four preregistered inclusive tolerance bands.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Mapping

import numpy as np
import scipy


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rpra.envelopes import load_configuration  # noqa: E402
from rpra.morelli_model import pass_deflection_um_vectorized  # noqa: E402


OUTPUT_DIR = ROOT / "audits" / "20260829_b3_terminal_tolerance_sensitivity"
CONFIG_PATH = ROOT / "configs" / "3pass_100um.yaml"
SCIENTIFIC_BASELINE = "c25540909939f65fad732420fa484f52931c02f9"
TERMINAL_CASES_UM = {"T0": 0, "T5": 5, "T10": 10, "T20": 20}
PASS_COUNT = 3
ACTION_AUDIT_FIELDS = (
    "terminal_case",
    "epsilon_um",
    "state_mm",
    "remaining_passes",
    "current_state_recoverable",
    "locally_feasible_state",
    "action_mm",
    "successor_mm",
    "transition_legal",
    "model_applicable",
    "deflection_evaluated",
    "deflection_um",
    "within_deflection_limit",
    "locally_feasible_action",
    "downstream_recoverable_member",
    "action_class",
    "included_in_recoverable_action_metrics",
    "selected_by_myopic",
    "selected_by_rpra",
)


def write_json(path: Path, value: object) -> None:
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_output(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def grid_values(cfg: Mapping) -> tuple[int, np.ndarray]:
    scale = int(round(1.0 / float(cfg["state_grid_mm"])))
    if abs(scale * float(cfg["state_grid_mm"]) - 1.0) > 1e-10:
        raise ValueError("state_grid_mm must have an integer reciprocal")
    lower = int(round(float(cfg["legal_radial_removal_min_mm"]) * scale))
    upper = int(round(float(cfg["legal_radial_removal_max_mm"]) * scale))
    return scale, np.arange(lower, upper + 1, dtype=np.int64)


def terminal_nodes(cfg: Mapping, epsilon_um: int) -> np.ndarray:
    scale, _ = grid_values(cfg)
    center = int(round(float(cfg["final_thickness_mm"]) * scale))
    epsilon_i = int(round((epsilon_um / 1000.0) * scale))
    return np.arange(center - epsilon_i, center + epsilon_i + 1, dtype=np.int64)


def build_tolerance_backward_set(
    pass_count: int, cfg: Mapping, epsilon_um: int
) -> dict:
    """Frozen RPRA recurrence with only R0 replaced by a tolerance band."""
    scale, actions = grid_values(cfg)
    action_min, action_max = int(actions[0]), int(actions[-1])
    base = terminal_nodes(cfg, epsilon_um)
    terminal_low, terminal_high = int(base[0]), int(base[-1])
    stages: dict[int, np.ndarray] = {0: base.copy()}
    transition_counts: dict[int, int] = {}
    previous = base
    limit = float(cfg["deflection_limit_um"])
    tolerance = float(cfg.get("decision_tolerance_um", 1e-7))
    model_max = float(cfg["workpiece_height_mm"]) / 10.0

    for stage in range(1, int(pass_count) + 1):
        possible_min = terminal_low + stage * action_min
        possible_max = terminal_high + stage * action_max
        membership = np.zeros(possible_max - possible_min + 1, dtype=bool)
        transitions = 0
        for next_i_value in previous:
            next_i = int(next_i_value)
            thickness_after = next_i / scale
            if thickness_after > model_max + 1e-12:
                continue
            deflections = pass_deflection_um_vectorized(
                actions.astype(float) / scale, thickness_after, cfg
            )
            feasible = actions[deflections <= limit + tolerance]
            states = next_i + feasible
            valid = (states >= possible_min) & (states <= possible_max)
            membership[states[valid] - possible_min] = True
            transitions += int(np.sum(valid))
        current = np.flatnonzero(membership).astype(np.int64) + possible_min
        stages[stage] = current
        transition_counts[stage] = transitions
        previous = current

    return {
        "pass_count": int(pass_count),
        "scale": scale,
        "epsilon_um": int(epsilon_um),
        "terminal_nodes_int": base,
        "stages_int": stages,
        "transition_counts": transition_counts,
    }


def action_candidates(
    state_i: int, remaining_passes: int, backward: Mapping, cfg: Mapping
) -> dict[str, np.ndarray]:
    scale, actions = grid_values(cfg)
    terminal = np.asarray(backward["terminal_nodes_int"], dtype=np.int64)
    action_min, action_max = int(actions[0]), int(actions[-1])
    next_states = int(state_i) - actions
    next_min = int(terminal[0]) + (remaining_passes - 1) * action_min
    next_max = int(terminal[-1]) + (remaining_passes - 1) * action_max
    structural = (next_states >= next_min) & (next_states <= next_max)
    model_max = float(cfg["workpiece_height_mm"]) / 10.0
    model_applicable = next_states / scale <= model_max + 1e-12
    evaluable = structural & model_applicable
    deflections = np.full(actions.shape, np.inf, dtype=float)
    if np.any(evaluable):
        deflections[evaluable] = pass_deflection_um_vectorized(
            actions[evaluable].astype(float) / scale,
            next_states[evaluable].astype(float) / scale,
            cfg,
        )
    tolerance = float(cfg.get("decision_tolerance_um", 1e-7))
    within_limit = evaluable & (
        deflections <= float(cfg["deflection_limit_um"]) + tolerance
    )
    local = evaluable & within_limit
    downstream = np.asarray(
        backward["stages_int"][remaining_passes - 1], dtype=np.int64
    )
    downstream_member = np.isin(next_states, downstream, assume_unique=False)
    preserving = local & downstream_member
    return {
        "actions": actions,
        "next_states": next_states,
        "deflections": deflections,
        "transition_legal": structural,
        "model_applicable": model_applicable,
        "evaluable": evaluable,
        "within_limit": within_limit,
        "local": local,
        "downstream_member": downstream_member,
        "preserving": preserving,
    }


def select_action(candidates: Mapping[str, np.ndarray], cfg: Mapping, *, rpra: bool) -> dict | None:
    admissible = np.asarray(
        candidates["preserving"] if rpra else candidates["local"], dtype=bool
    )
    indices = np.flatnonzero(admissible)
    if not indices.size:
        return None
    values = np.asarray(candidates["deflections"], dtype=float)[indices]
    best = float(np.min(values))
    tolerance = float(cfg.get("decision_tolerance_um", 1e-7))
    tied = indices[values <= best + tolerance]
    actions = np.asarray(candidates["actions"], dtype=np.int64)
    index = int(tied[np.argmin(actions[tied])])
    preserving = bool(np.asarray(candidates["preserving"], dtype=bool)[index])
    return {
        "action_i": int(actions[index]),
        "next_state_i": int(np.asarray(candidates["next_states"])[index]),
        "deflection_um": float(np.asarray(candidates["deflections"])[index]),
        "class": "PRESERVING" if preserving else "DESTROYING",
    }


def audit_case(
    case: str,
    epsilon_um: int,
    cfg: Mapping,
    action_writer: csv.DictWriter,
) -> tuple[dict, list[dict], int]:
    backward = build_tolerance_backward_set(PASS_COUNT, cfg, epsilon_um)
    scale = int(backward["scale"])
    domain = np.arange(
        int(round(float(cfg["evaluation_state_min_mm"]) * scale)),
        int(round(float(cfg["evaluation_state_max_mm"]) * scale)) + 1,
        dtype=np.int64,
    )
    recoverable_stage = np.asarray(backward["stages_int"][PASS_COUNT], dtype=np.int64)
    recoverable_mask = np.isin(domain, recoverable_stage, assume_unique=False)
    local_state_count = 0
    local_but_irrecoverable_count = 0
    recoverable_count = int(np.sum(recoverable_mask))
    mixed_count = 0
    all_preserving_count = 0
    preserving_action_count = 0
    destroying_action_count = 0
    myopic_destroying_count = 0
    action_row_count = 0

    for state_i_value, is_recoverable_value in zip(domain, recoverable_mask):
        state_i = int(state_i_value)
        is_recoverable = bool(is_recoverable_value)
        candidates = action_candidates(state_i, PASS_COUNT, backward, cfg)
        local_count = int(np.sum(candidates["local"]))
        preserving_count = int(np.sum(candidates["preserving"]))
        destroying_count = local_count - preserving_count
        local_state_count += int(local_count > 0)
        local_but_irrecoverable_count += int(local_count > 0 and not is_recoverable)
        myopic = select_action(candidates, cfg, rpra=False)
        rpra = select_action(candidates, cfg, rpra=True) if is_recoverable else None
        if is_recoverable:
            if preserving_count <= 0:
                raise RuntimeError(f"{case} recoverable state {state_i / scale} lacks a preserving action")
            preserving_action_count += preserving_count
            destroying_action_count += destroying_count
            mixed_count += int(destroying_count > 0)
            all_preserving_count += int(destroying_count == 0)
            myopic_destroying_count += int(myopic is not None and myopic["class"] == "DESTROYING")
        myopic_action_i = None if myopic is None else int(myopic["action_i"])
        rpra_action_i = None if rpra is None else int(rpra["action_i"])
        for index, action_i_value in enumerate(candidates["actions"]):
            action_i = int(action_i_value)
            locally_feasible = bool(candidates["local"][index])
            preserving = bool(candidates["preserving"][index])
            action_class = (
                "PRESERVING" if preserving
                else "DESTROYING" if locally_feasible
                else "INFEASIBLE"
            )
            evaluated = bool(candidates["evaluable"][index])
            action_writer.writerow({
                "terminal_case": case,
                "epsilon_um": epsilon_um,
                "state_mm": state_i / scale,
                "remaining_passes": PASS_COUNT,
                "current_state_recoverable": is_recoverable,
                "locally_feasible_state": local_count > 0,
                "action_mm": action_i / scale,
                "successor_mm": int(candidates["next_states"][index]) / scale,
                "transition_legal": bool(candidates["transition_legal"][index]),
                "model_applicable": bool(candidates["model_applicable"][index]),
                "deflection_evaluated": evaluated,
                "deflection_um": float(candidates["deflections"][index]) if evaluated else "",
                "within_deflection_limit": bool(candidates["within_limit"][index]),
                "locally_feasible_action": locally_feasible,
                "downstream_recoverable_member": bool(candidates["downstream_member"][index]),
                "action_class": action_class,
                "included_in_recoverable_action_metrics": is_recoverable and locally_feasible,
                "selected_by_myopic": myopic_action_i == action_i,
                "selected_by_rpra": rpra_action_i == action_i,
            })
            action_row_count += 1

    starts = domain[recoverable_mask]
    trajectory_rows: list[dict] = []
    rollout_results: dict[str, dict] = {}
    terminal_set = set(map(int, backward["terminal_nodes_int"]))
    for policy in ("MYOPIC", "RPRA"):
        completed = 0
        complete_sequences = 0
        failures: Counter[str] = Counter()
        for start_i_value in starts:
            start_i = int(start_i_value)
            state_i = start_i
            selected_steps = 0
            failed = False
            for step, remaining in enumerate(range(PASS_COUNT, 0, -1), start=1):
                candidates = action_candidates(state_i, remaining, backward, cfg)
                selected = select_action(candidates, cfg, rpra=(policy == "RPRA"))
                if selected is None:
                    reason = "NO_PRESERVING_ACTION" if policy == "RPRA" else "NO_LOCALLY_FEASIBLE_ACTION"
                    failures[f"{reason}_M{remaining}"] += 1
                    trajectory_rows.append({
                        "terminal_case": case,
                        "epsilon_um": epsilon_um,
                        "start_state_mm": start_i / scale,
                        "policy": policy,
                        "step": step,
                        "remaining_passes_before": remaining,
                        "state_before_mm": state_i / scale,
                        "selected_action_mm": "",
                        "immediate_deflection_um": "",
                        "selected_action_class": "",
                        "successor_mm": "",
                        "remaining_passes_after": remaining,
                        "step_status": reason,
                        "failure_detail": "",
                    })
                    failed = True
                    break
                successor_i = int(selected["next_state_i"])
                selected_steps += 1
                status = "CONTINUE" if remaining > 1 else "TERMINAL_REACHED"
                if remaining == 1 and successor_i not in terminal_set:
                    status = "TERMINAL_OUTSIDE_TOLERANCE"
                    failures[status] += 1
                    failed = True
                trajectory_rows.append({
                    "terminal_case": case,
                    "epsilon_um": epsilon_um,
                    "start_state_mm": start_i / scale,
                    "policy": policy,
                    "step": step,
                    "remaining_passes_before": remaining,
                    "state_before_mm": state_i / scale,
                    "selected_action_mm": selected["action_i"] / scale,
                    "immediate_deflection_um": selected["deflection_um"],
                    "selected_action_class": selected["class"],
                    "successor_mm": successor_i / scale,
                    "remaining_passes_after": remaining - 1,
                    "step_status": status,
                    "failure_detail": "",
                })
                state_i = successor_i
                if failed:
                    break
            complete_sequences += int(selected_steps == PASS_COUNT)
            if not failed and state_i in terminal_set:
                completed += 1
            elif not failed:
                failures["TERMINAL_OUTSIDE_TOLERANCE"] += 1
        rollout_results[policy] = {
            "completion_count": completed,
            "completion_rate": completed / len(starts) if len(starts) else None,
            "complete_action_sequence_count": complete_sequences,
            "failure_by_stage_reason": dict(sorted(failures.items())),
        }

    mechanism = mechanism_regression(cfg, backward) if case == "T0" else None
    summary = {
        "terminal_case": case,
        "epsilon_um": epsilon_um,
        "terminal_lower_mm": int(backward["terminal_nodes_int"][0]) / scale,
        "terminal_upper_mm": int(backward["terminal_nodes_int"][-1]) / scale,
        "terminal_node_count": len(backward["terminal_nodes_int"]),
        "evaluation_state_count": len(domain),
        "locally_feasible_state_count": local_state_count,
        "recoverable_state_count": recoverable_count,
        "local_but_irrecoverable_count": local_but_irrecoverable_count,
        "mixed_action_recoverable_state_count": mixed_count,
        "all_preserving_recoverable_state_count": all_preserving_count,
        "preserving_action_count": preserving_action_count,
        "destroying_locally_feasible_action_count": destroying_action_count,
        "myopic_first_action_destroying_count": myopic_destroying_count,
        "myopic_completion_count": rollout_results["MYOPIC"]["completion_count"],
        "myopic_completion_rate": rollout_results["MYOPIC"]["completion_rate"],
        "myopic_failure_by_stage_reason": json.dumps(
            rollout_results["MYOPIC"]["failure_by_stage_reason"], sort_keys=True
        ),
        "myopic_complete_action_sequence_count": rollout_results["MYOPIC"]["complete_action_sequence_count"],
        "rpra_completion_count": rollout_results["RPRA"]["completion_count"],
        "rpra_completion_rate": rollout_results["RPRA"]["completion_rate"],
        "rpra_failure_by_stage_reason": json.dumps(
            rollout_results["RPRA"]["failure_by_stage_reason"], sort_keys=True
        ),
        "rpra_complete_action_sequence_count": rollout_results["RPRA"]["complete_action_sequence_count"],
        "backward_r0_count": len(backward["stages_int"][0]),
        "backward_r1_count": len(backward["stages_int"][1]),
        "backward_r2_count": len(backward["stages_int"][2]),
        "backward_r3_count_all_grid_states": len(backward["stages_int"][3]),
        "mechanism_4p442_unchanged": "" if mechanism is None else mechanism["unchanged"],
    }
    return summary, trajectory_rows, action_row_count


def mechanism_regression(cfg: Mapping, backward: Mapping) -> dict:
    scale = int(backward["scale"])
    state_i = int(round(4.442 * scale))
    candidates = action_candidates(state_i, PASS_COUNT, backward, cfg)
    observations: dict[str, object] = {}
    for label, action_mm, expected_class, expected_successor in (
        ("destroying", 0.432, "DESTROYING", 4.010),
        ("preserving", 0.557, "PRESERVING", 3.885),
    ):
        action_i = int(round(action_mm * scale))
        indices = np.flatnonzero(candidates["actions"] == action_i)
        if indices.size != 1:
            raise RuntimeError(f"mechanism action {action_mm} not found")
        index = int(indices[0])
        observed_class = (
            "PRESERVING" if candidates["preserving"][index]
            else "DESTROYING" if candidates["local"][index]
            else "INFEASIBLE"
        )
        successor = int(candidates["next_states"][index]) / scale
        observations[label] = {
            "action_mm": action_mm,
            "successor_mm": successor,
            "class": observed_class,
            "matches_frozen": observed_class == expected_class and successor == expected_successor,
        }
    observations["unchanged"] = all(
        bool(observations[name]["matches_frozen"])  # type: ignore[index]
        for name in ("destroying", "preserving")
    )
    return observations


def t0_gate(summary: Mapping) -> bool:
    expected = {
        "locally_feasible_state_count": 621,
        "recoverable_state_count": 407,
        "local_but_irrecoverable_count": 214,
        "mixed_action_recoverable_state_count": 289,
        "all_preserving_recoverable_state_count": 118,
        "preserving_action_count": 31549,
        "destroying_locally_feasible_action_count": 41905,
        "myopic_completion_count": 3,
        "rpra_completion_count": 407,
    }
    return all(summary[key] == value for key, value in expected.items()) and bool(
        summary["mechanism_4p442_unchanged"]
    )


def classify(summaries: list[dict]) -> str:
    by_case = {row["terminal_case"]: row for row in summaries}
    if not t0_gate(by_case["T0"]):
        return "B3_SCIENTIFIC_CONFLICT"
    support = {
        case: (
            by_case[case]["local_but_irrecoverable_count"] > 0
            and by_case[case]["mixed_action_recoverable_state_count"] > 0
            and by_case[case]["rpra_completion_count"] == by_case[case]["recoverable_state_count"]
            and by_case[case]["myopic_completion_count"] < by_case[case]["recoverable_state_count"]
        )
        for case in ("T5", "T10", "T20")
    }
    if all(support.values()):
        return "B3_STRONG_SUPPORT"
    if not support["T5"]:
        return "B3_NO_SUPPORT"
    return "B3_BOUNDED_SUPPORT"


def protected_public_diff() -> str:
    paths = [
        "src/rpra", "configs", "expected", "README.md", "REPRODUCIBILITY.md",
        "CITATION.cff", "LICENSE", "LICENSE-DATA",
    ]
    return git_output("diff", "--name-only", "v1.1.0", "--", *paths)


def environment_record() -> dict:
    return {
        "scientific_baseline": SCIENTIFIC_BASELINE,
        "head_commit": git_output("rev-parse", "HEAD"),
        "public_tag_commit": git_output("rev-list", "-n", "1", "v1.1.0"),
        "python": sys.version,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "cpu_count": os.cpu_count(),
        "config_path": str(CONFIG_PATH.relative_to(ROOT)),
        "config_sha256": sha256_file(CONFIG_PATH),
        "harness_path": str(Path(__file__).resolve().relative_to(ROOT)),
        "harness_sha256": sha256_file(Path(__file__).resolve()),
        "terminal_cases_um": TERMINAL_CASES_UM,
        "corrective_rerun": True,
        "corrective_change_class": "EVIDENCE_GRANULARITY_AND_RETURN_FORMAT_ONLY",
        "state_action_evidence_semantics": "one row per case, evaluation state, and candidate action",
        "expected_state_action_row_count": 4 * 621 * 541,
        "protected_public_diff_from_v1_1_0": protected_public_diff(),
    }


def read_summary() -> list[dict]:
    with (OUTPUT_DIR / "B3_terminal_tolerance_summary.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    integer_fields = {
        "epsilon_um", "terminal_node_count", "evaluation_state_count",
        "locally_feasible_state_count", "recoverable_state_count",
        "local_but_irrecoverable_count", "mixed_action_recoverable_state_count",
        "all_preserving_recoverable_state_count", "preserving_action_count",
        "destroying_locally_feasible_action_count", "myopic_first_action_destroying_count",
        "myopic_completion_count", "myopic_complete_action_sequence_count",
        "rpra_completion_count", "rpra_complete_action_sequence_count",
        "backward_r0_count", "backward_r1_count", "backward_r2_count",
        "backward_r3_count_all_grid_states",
    }
    converted = []
    for row in rows:
        value = dict(row)
        for key in integer_fields:
            value[key] = int(value[key])
        value["mechanism_4p442_unchanged"] = (
            value["mechanism_4p442_unchanged"] == "True"
            if value["mechanism_4p442_unchanged"] else ""
        )
        converted.append(value)
    return converted


def csv_data_row_count(path: Path) -> int:
    newline_count = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            newline_count += chunk.count(b"\n")
    return max(0, newline_count - 1)


def build_report(summaries: list[dict], args: argparse.Namespace) -> None:
    by_case = {row["terminal_case"]: row for row in summaries}
    classification = classify(summaries)
    baseline_gate = "PASS" if t0_gate(by_case["T0"]) else "FAIL"
    all_rpra = all(row["rpra_completion_count"] == row["recoverable_state_count"] for row in summaries)
    result_gate = "PASS" if baseline_gate == "PASS" and all_rpra else "FAIL"
    external_gates = all(
        value == "PASS" for value in (
            args.pytest_result, args.quick_result, args.full_result,
            args.diff_check_result, args.public_v1_result, args.output_audit_result,
        )
    )
    task_status = "PASS" if result_gate == "PASS" and external_gates else (
        "FAIL" if "FAIL" in (
            args.pytest_result, args.quick_result, args.full_result,
            args.diff_check_result, args.public_v1_result,
            args.output_audit_result, result_gate,
        ) else "PENDING"
    )
    table_lines = [
        "| Case | |L| | |R| | |L \\ R| | Mixed | All preserving | Preserving actions | Destroying actions | Myopic completion | RPRA completion |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summaries:
        table_lines.append(
            f"| {row['terminal_case']} | {row['locally_feasible_state_count']} | "
            f"{row['recoverable_state_count']} | {row['local_but_irrecoverable_count']} | "
            f"{row['mixed_action_recoverable_state_count']} | "
            f"{row['all_preserving_recoverable_state_count']} | "
            f"{row['preserving_action_count']} | "
            f"{row['destroying_locally_feasible_action_count']} | "
            f"{row['myopic_completion_count']}/{row['recoverable_state_count']} | "
            f"{row['rpra_completion_count']}/{row['recoverable_state_count']} |"
        )
    remaining = "NONE" if task_status == "PASS" else "external regression gates pending or failed"
    report = f"""# B3 Terminal-Tolerance Sensitivity Formal Audit

## Scope and protocol

This audit executes the frozen B3 design only. The production RPRA implementation,
configuration, expected results, manuscript, and public `v1.1.0` content were not
changed. The only analytical change is the preregistered inclusive terminal base
set for `T0`, `T5`, `T10`, and `T20`; the state/action grid remains 0.001 mm and
all metrics use the fixed 621-state evaluation domain `[4.180, 4.800]` mm.

The rollout population is the intersection of each tolerance-specific `R3` with
that frozen evaluation domain. Failure rows and incomplete trajectories are kept
in `B3_rollout_trajectories.csv`; no cases, states, or actions were excluded.

## Results

{chr(10).join(table_lines)}

`B3_CLASSIFICATION={classification}`

The declared local-versus-recoverable and preserving-versus-destroying structure
is interpreted only within this frozen scalar three-pass case. This is not
uncertainty robustness, measurement-error tolerance, physical validation,
cross-configuration generality, or a tolerance-design theory.

## Regression gates

- T0 frozen state/action counts: {baseline_gate}
- T0 MYOPIC completion `3/407`: {'PASS' if by_case['T0']['myopic_completion_count'] == 3 else 'FAIL'}
- T0 RPRA completion `407/407`: {'PASS' if by_case['T0']['rpra_completion_count'] == 407 else 'FAIL'}
- Frozen 4.442-mm mechanism: {'PASS' if by_case['T0']['mechanism_4p442_unchanged'] else 'FAIL'}
- pytest: {args.pytest_result}
- quick reproduction: {args.quick_result}
- full reproduction: {args.full_result}
- git diff --check: {args.diff_check_result}
- public v1.1.0 protected content unchanged: {args.public_v1_result}
- independent output audit: {args.output_audit_result}

## Governance status

The C*-Focused Action Registry, Canonicalizer, detector, held-out, FOR, and cluster
bootstrap fields are not part of this RPRA experiment and are `NOT_APPLICABLE`.
The applicable freeze, fixed-denominator, no-exclusion, provenance, and regression
controls are satisfied as recorded above. This corrective rerun changes only
evidence granularity and the required report block; it does not change a verdict
boundary or any frozen experiment semantics.

```text
TASK_STATUS={task_status}
BASELINE_COMMIT={SCIENTIFIC_BASELINE}
WORKING_COMMIT={git_output('rev-parse', 'HEAD')}
B3_CLASSIFICATION={classification}

T0_LOCAL_FEASIBLE={by_case['T0']['locally_feasible_state_count']}
T0_RECOVERABLE={by_case['T0']['recoverable_state_count']}
T0_LOCAL_BUT_IRRECOVERABLE={by_case['T0']['local_but_irrecoverable_count']}
T0_MIXED_ACTION={by_case['T0']['mixed_action_recoverable_state_count']}
T0_MYOPIC_COMPLETION={by_case['T0']['myopic_completion_count']}/{by_case['T0']['recoverable_state_count']}
T0_RPRA_COMPLETION={by_case['T0']['rpra_completion_count']}/{by_case['T0']['recoverable_state_count']}

T5_LOCAL_FEASIBLE={by_case['T5']['locally_feasible_state_count']}
T5_RECOVERABLE={by_case['T5']['recoverable_state_count']}
T5_LOCAL_BUT_IRRECOVERABLE={by_case['T5']['local_but_irrecoverable_count']}
T5_MIXED_ACTION={by_case['T5']['mixed_action_recoverable_state_count']}
T5_MYOPIC_COMPLETION={by_case['T5']['myopic_completion_count']}/{by_case['T5']['recoverable_state_count']}
T5_RPRA_COMPLETION={by_case['T5']['rpra_completion_count']}/{by_case['T5']['recoverable_state_count']}

T10_LOCAL_FEASIBLE={by_case['T10']['locally_feasible_state_count']}
T10_RECOVERABLE={by_case['T10']['recoverable_state_count']}
T10_LOCAL_BUT_IRRECOVERABLE={by_case['T10']['local_but_irrecoverable_count']}
T10_MIXED_ACTION={by_case['T10']['mixed_action_recoverable_state_count']}
T10_MYOPIC_COMPLETION={by_case['T10']['myopic_completion_count']}/{by_case['T10']['recoverable_state_count']}
T10_RPRA_COMPLETION={by_case['T10']['rpra_completion_count']}/{by_case['T10']['recoverable_state_count']}

T20_LOCAL_FEASIBLE={by_case['T20']['locally_feasible_state_count']}
T20_RECOVERABLE={by_case['T20']['recoverable_state_count']}
T20_LOCAL_BUT_IRRECOVERABLE={by_case['T20']['local_but_irrecoverable_count']}
T20_MIXED_ACTION={by_case['T20']['mixed_action_recoverable_state_count']}
T20_MYOPIC_COMPLETION={by_case['T20']['myopic_completion_count']}/{by_case['T20']['recoverable_state_count']}
T20_RPRA_COMPLETION={by_case['T20']['rpra_completion_count']}/{by_case['T20']['recoverable_state_count']}

T0_BASELINE_REGRESSION={baseline_gate}
MECHANISM_4P442_UNCHANGED={'PASS' if by_case['T0']['mechanism_4p442_unchanged'] else 'FAIL'}
PYTEST={args.pytest_result}
QUICK_REPRODUCTION={args.quick_result}
FULL_REPRODUCTION={args.full_result}
GIT_DIFF_CHECK={args.diff_check_result}
PUBLIC_V1_1_0_MODIFIED={'false' if args.public_v1_result == 'PASS' else 'true_or_unresolved'}
REMAINING_BLOCKERS={remaining}

TERMINAL_CASE_COUNT={len(summaries)}
EVALUATION_STATE_COUNT_PER_CASE=621
STATE_ACTION_AUDIT_ROW_COUNT={csv_data_row_count(OUTPUT_DIR / 'B3_state_action_audit.csv')}
ROLLOUT_TRAJECTORY_ROW_COUNT={csv_data_row_count(OUTPUT_DIR / 'B3_rollout_trajectories.csv')}
EXCLUDED_CASE_COUNT=0
EXCLUDED_STATE_COUNT=0
EXCLUDED_ACTION_COUNT=0
FAILURE_ROWS_RETAINED=true
INFEASIBLE_ACTION_ROWS_RETAINED=true
NO_CHANGE_ROWS_RETAINED=true
EXPERIMENT_OUTPUT_AUDITOR_STATUS={args.output_audit_result}
```
"""
    (OUTPUT_DIR / "B3_FORMAL_AUDIT.md").write_text(report, encoding="utf-8")


def validate_frozen_configuration(cfg: Mapping) -> None:
    expected = {
        "remaining_pass_count": 3,
        "state_grid_mm": 0.001,
        "evaluation_state_min_mm": 4.180,
        "evaluation_state_max_mm": 4.800,
        "final_thickness_mm": 3.100,
        "deflection_limit_um": 100.0,
    }
    mismatches = [key for key, value in expected.items() if cfg.get(key) != value]
    if mismatches:
        raise RuntimeError("frozen configuration mismatch: " + ", ".join(mismatches))
    if git_output("rev-parse", "HEAD") != SCIENTIFIC_BASELINE:
        raise RuntimeError("HEAD is not the frozen scientific baseline")
    if git_output("rev-list", "-n", "1", "v1.1.0") != SCIENTIFIC_BASELINE:
        raise RuntimeError("v1.1.0 does not point to the frozen scientific baseline")
    if protected_public_diff():
        raise RuntimeError("protected public content differs from v1.1.0")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize-only", action="store_true")
    parser.add_argument("--pytest-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    parser.add_argument("--quick-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    parser.add_argument("--full-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    parser.add_argument("--diff-check-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    parser.add_argument("--public-v1-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    parser.add_argument("--output-audit-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = load_configuration(CONFIG_PATH)
    validate_frozen_configuration(cfg)
    if args.finalize_only:
        summaries = read_summary()
        build_report(summaries, args)
        return

    summaries: list[dict] = []
    trajectory_rows: list[dict] = []
    action_row_count = 0
    scale, actions = grid_values(cfg)
    domain_count = (
        int(round(float(cfg["evaluation_state_max_mm"]) * scale))
        - int(round(float(cfg["evaluation_state_min_mm"]) * scale))
        + 1
    )
    expected_action_rows = len(TERMINAL_CASES_UM) * domain_count * len(actions)
    action_tmp = OUTPUT_DIR / "B3_state_action_audit.csv.tmp"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with action_tmp.open("w", encoding="utf-8", newline="") as handle:
        action_writer = csv.DictWriter(handle, fieldnames=ACTION_AUDIT_FIELDS)
        action_writer.writeheader()
        for case, epsilon_um in TERMINAL_CASES_UM.items():
            summary, case_trajectories, case_action_rows = audit_case(
                case, epsilon_um, cfg, action_writer
            )
            summaries.append(summary)
            trajectory_rows.extend(case_trajectories)
            action_row_count += case_action_rows

    if action_row_count != expected_action_rows:
        raise RuntimeError(
            f"unexpected state/action audit row count: {action_row_count}; "
            f"expected {expected_action_rows}"
        )
    action_tmp.replace(OUTPUT_DIR / "B3_state_action_audit.csv")
    if not t0_gate({row["terminal_case"]: row for row in summaries}["T0"]):
        write_csv(OUTPUT_DIR / "B3_terminal_tolerance_summary.csv", summaries)
        write_csv(OUTPUT_DIR / "B3_rollout_trajectories.csv", trajectory_rows)
        write_json(OUTPUT_DIR / "B3_environment.json", environment_record())
        build_report(summaries, args)
        raise SystemExit("B3_SCIENTIFIC_CONFLICT: T0 regression failed")

    write_csv(OUTPUT_DIR / "B3_terminal_tolerance_summary.csv", summaries)
    write_csv(OUTPUT_DIR / "B3_rollout_trajectories.csv", trajectory_rows)
    write_json(OUTPUT_DIR / "B3_environment.json", environment_record())
    build_report(summaries, args)
    print(f"B3_CLASSIFICATION={classify(summaries)}")
    print("B3_FORMAL_RUN=PASS")


if __name__ == "__main__":
    main()

"""Run the controlled R8.1 experiment-freeze candidate audit.

This harness is deliberately outside the RPRA numerical implementation.  It
uses the frozen public APIs and configuration, records row-level policy
evidence, and times calls externally without changing production semantics.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import scipy


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rpra.envelopes import (  # noqa: E402
    DESTROYING,
    PRESERVING,
    analyze_envelope,
    evaluated_states,
    load_configuration,
    local_feasible_states,
)
from rpra.morelli_model import pass_deflection_um  # noqa: E402
from rpra.morelli_model import pass_deflection_um_vectorized  # noqa: E402
from rpra.recoverable_set import build_backward_set  # noqa: E402


OUTPUT_DIR = ROOT / "audits" / "20260828_r81_experiment_freeze_candidate"
PRIMARY_CONFIG = ROOT / "configs" / "3pass_100um.yaml"
REPETITIONS = 5
GRID_CASES = (0.004, 0.002, 0.001, 0.0005, 0.00025)
HORIZON_CASES = (1, 2, 3, 4)
VARIANTS = {
    "E2_BASELINE": {},
    "E2_FZ_LOW": {"feed_per_tooth_mm": 0.054, "axial_depth_mm": 35.0},
    "E2_FZ_HIGH": {"feed_per_tooth_mm": 0.066, "axial_depth_mm": 35.0},
    "E2_AP_LOW": {"feed_per_tooth_mm": 0.060, "axial_depth_mm": 31.5},
    "E2_AP_HIGH": {"feed_per_tooth_mm": 0.060, "axial_depth_mm": 38.5},
}
PREDECLARED_VARIANTS = tuple(name for name in VARIANTS if name != "E2_BASELINE")


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


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _grid(cfg: Mapping) -> tuple[int, np.ndarray]:
    scale = int(round(1.0 / float(cfg["state_grid_mm"])))
    if abs(scale * float(cfg["state_grid_mm"]) - 1.0) > 1e-10:
        raise ValueError("state_grid_mm must have an integer reciprocal")
    lower = int(round(float(cfg["legal_radial_removal_min_mm"]) * scale))
    upper = int(round(float(cfg["legal_radial_removal_max_mm"]) * scale))
    return scale, np.arange(lower, upper + 1, dtype=np.int64)


def action_candidates(
    state_i: int, remaining_passes: int, backward: Mapping, cfg: Mapping
) -> dict[str, np.ndarray]:
    """Reproduce the frozen local and downstream-membership semantics."""
    scale, actions = _grid(cfg)
    terminal = int(round(float(cfg["final_thickness_mm"]) * scale))
    action_min, action_max = int(actions[0]), int(actions[-1])
    next_states = int(state_i) - actions
    next_min = terminal + (remaining_passes - 1) * action_min
    next_max = terminal + (remaining_passes - 1) * action_max
    transition_legal = (next_states >= next_min) & (next_states <= next_max)
    model_max = float(cfg["workpiece_height_mm"]) / 10.0
    model_applicable = next_states / scale <= model_max + 1e-12
    evaluable = transition_legal & model_applicable
    deflections = np.full(actions.shape, np.inf, dtype=float)
    if np.any(evaluable):
        deflections[evaluable] = pass_deflection_um_vectorized(
            actions[evaluable].astype(float) / scale,
            next_states[evaluable].astype(float) / scale,
            cfg,
        )
    tolerance = float(cfg.get("decision_tolerance_um", 1e-7))
    local = evaluable & (
        deflections <= float(cfg["deflection_limit_um"]) + tolerance
    )
    downstream = np.asarray(
        backward["stages_int"][remaining_passes - 1], dtype=np.int64
    )
    preserving = local & np.isin(next_states, downstream, assume_unique=False)
    return {
        "actions": actions,
        "next_states": next_states,
        "deflections": deflections,
        "local": local,
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


def distribution_stats(values: Iterable[float]) -> dict[str, float | None]:
    data = np.asarray(list(values), dtype=float)
    if not data.size:
        return {"mean_um": None, "median_um": None, "p95_um": None, "max_um": None}
    return {
        "mean_um": float(np.mean(data)),
        "median_um": float(np.median(data)),
        "p95_um": float(np.percentile(data, 95)),
        "max_um": float(np.max(data)),
    }


def first_action_audit(cfg: Mapping, backward: Mapping) -> tuple[list[dict], dict]:
    scale = int(backward["scale"])
    starts = np.asarray(backward["stages_int"][3], dtype=np.int64)
    rows: list[dict] = []
    for state_i in starts:
        candidates = action_candidates(int(state_i), 3, backward, cfg)
        myopic = select_action(candidates, cfg, rpra=False)
        rpra = select_action(candidates, cfg, rpra=True)
        if myopic is None or rpra is None:
            raise RuntimeError(f"recoverable state {state_i / scale:.6f} lacks a policy action")
        sacrifice = rpra["deflection_um"] - myopic["deflection_um"]
        rows.append({
            "state_mm": int(state_i) / scale,
            "remaining_passes": 3,
            "myopic_action_mm": myopic["action_i"] / scale,
            "myopic_immediate_deflection_um": myopic["deflection_um"],
            "myopic_successor_mm": myopic["next_state_i"] / scale,
            "myopic_action_class": myopic["class"],
            "rpra_action_mm": rpra["action_i"] / scale,
            "rpra_immediate_deflection_um": rpra["deflection_um"],
            "rpra_successor_mm": rpra["next_state_i"] / scale,
            "immediate_deflection_sacrifice_um": sacrifice,
            "selected_actions_differ": myopic["action_i"] != rpra["action_i"],
        })
    destroying = sum(row["myopic_action_class"] == "DESTROYING" for row in rows)
    all_stats = distribution_stats(row["immediate_deflection_sacrifice_um"] for row in rows)
    differing_rows = [row for row in rows if row["selected_actions_differ"]]
    differing_stats = distribution_stats(
        row["immediate_deflection_sacrifice_um"] for row in differing_rows
    )
    summary = {
        "RECOVERABLE_START_STATES": len(rows),
        "MYOPIC_FIRST_ACTION_PRESERVING_COUNT": len(rows) - destroying,
        "MYOPIC_FIRST_ACTION_DESTROYING_COUNT": destroying,
        "MYOPIC_FIRST_ACTION_DESTROYING_RATE": destroying / len(rows) if rows else None,
        "DELTA_DEFLECTION_MEAN_UM": all_stats["mean_um"],
        "DELTA_DEFLECTION_MEDIAN_UM": all_stats["median_um"],
        "DELTA_DEFLECTION_P95_UM": all_stats["p95_um"],
        "DELTA_DEFLECTION_MAX_UM": all_stats["max_um"],
        "SELECTED_ACTIONS_DIFFER_COUNT": len(differing_rows),
        "DIFFERING_ACTION_DELTA_DEFLECTION_MEAN_UM": differing_stats["mean_um"],
        "DIFFERING_ACTION_DELTA_DEFLECTION_MEDIAN_UM": differing_stats["median_um"],
        "DIFFERING_ACTION_DELTA_DEFLECTION_P95_UM": differing_stats["p95_um"],
        "DIFFERING_ACTION_DELTA_DEFLECTION_MAX_UM": differing_stats["max_um"],
    }
    return rows, summary


def rollout_policy(
    starts: np.ndarray, backward: Mapping, cfg: Mapping, policy: str
) -> tuple[list[dict], dict]:
    scale = int(backward["scale"])
    terminal = int(round(float(cfg["final_thickness_mm"]) * scale))
    trajectory_rows: list[dict] = []
    completed = 0
    failures: Counter[str] = Counter()
    failed_starts = 0
    for start_i_value in starts:
        start_i = int(start_i_value)
        state_i = start_i
        failed = False
        for step, remaining in enumerate(range(3, 0, -1), start=1):
            try:
                candidates = action_candidates(state_i, remaining, backward, cfg)
                selected = select_action(candidates, cfg, rpra=(policy == "RPRA"))
            except Exception as exc:  # retained as row-level implementation evidence
                failures[f"IMPLEMENTATION_INCONSISTENCY_M{remaining}"] += 1
                trajectory_rows.append({
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
                    "step_status": "IMPLEMENTATION_INCONSISTENCY",
                    "failure_detail": f"{type(exc).__name__}: {exc}",
                })
                failed = True
                break
            if selected is None:
                reason = "NO_PRESERVING_ACTION" if policy == "RPRA" else "NO_LOCALLY_FEASIBLE_ACTION"
                failures[f"{reason}_M{remaining}"] += 1
                trajectory_rows.append({
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
            status = "CONTINUE" if remaining > 1 else "TERMINAL_REACHED"
            if remaining == 1 and successor_i != terminal:
                status = "TERMINAL_MISMATCH"
                failures[status] += 1
                failed = True
            trajectory_rows.append({
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
        if failed:
            failed_starts += 1
        elif state_i == terminal:
            completed += 1
        else:
            failures["TERMINAL_MISMATCH"] += 1
            failed_starts += 1
    return trajectory_rows, {
        "completion_count": completed,
        "completion_rate": completed / len(starts),
        "failure_by_stage": dict(sorted(failures.items())),
        "failed_start_count": failed_starts,
    }


def mechanism_regression(cfg: Mapping, backward: Mapping) -> dict:
    scale = int(backward["scale"])
    state_i = int(round(4.442 * scale))
    candidates = action_candidates(state_i, 3, backward, cfg)
    observations = {}
    for label, action_mm, expected_class, expected_successor in (
        ("destroying", 0.432, "DESTROYING", 4.010),
        ("preserving", 0.557, "PRESERVING", 3.885),
    ):
        action_i = int(round(action_mm * scale))
        index = int(np.flatnonzero(candidates["actions"] == action_i)[0])
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
    observations["MECHANISM_4P442_UNCHANGED"] = all(
        observations[name]["matches_frozen"] for name in ("destroying", "preserving")
    )
    return observations


def run_e1(cfg: Mapping) -> dict:
    backward = build_backward_set(3, cfg)
    first_rows, first_summary = first_action_audit(cfg, backward)
    starts = np.asarray(backward["stages_int"][3], dtype=np.int64)
    myopic_rows, myopic = rollout_policy(starts, backward, cfg, "MYOPIC")
    rpra_rows, rpra = rollout_policy(starts, backward, cfg, "RPRA")
    mechanism = mechanism_regression(cfg, backward)
    all_trajectory_rows = myopic_rows + rpra_rows
    invariant_violations = rpra["failed_start_count"]
    summary = {
        **first_summary,
        "MYOPIC_COMPLETION_COUNT": myopic["completion_count"],
        "MYOPIC_COMPLETION_RATE": myopic["completion_rate"],
        "MYOPIC_FAILURE_BY_STAGE": myopic["failure_by_stage"],
        "RPRA_COMPLETION_COUNT": rpra["completion_count"],
        "RPRA_COMPLETION_RATE": rpra["completion_rate"],
        "RPRA_FAILURE_BY_STAGE": rpra["failure_by_stage"],
        "RPRA_INVARIANT_VIOLATION_COUNT": invariant_violations,
        "MECHANISM_REGRESSION": mechanism,
        "ROW_COUNTS": {
            "first_action": len(first_rows),
            "rollout_trajectory": len(all_trajectory_rows),
        },
    }
    summary["E1_GATE"] = "PASS" if (
        len(first_rows) == 407
        and invariant_violations == 0
        and mechanism["MECHANISM_4P442_UNCHANGED"]
        and len({row["state_mm"] for row in first_rows}) == 407
        and len({(row["start_state_mm"], row["policy"]) for row in all_trajectory_rows}) == 814
    ) else "FAIL"
    write_csv(OUTPUT_DIR / "E1_first_action_audit.csv", first_rows)
    write_csv(OUTPUT_DIR / "E1_rollout_trajectories.csv", all_trajectory_rows)
    write_json(OUTPUT_DIR / "E1_summary.json", summary)
    return summary


def validate_variant_domain(cfg: Mapping) -> tuple[bool, str]:
    """Exercise all explicit Morelli scalar checks at frozen-domain corners."""
    try:
        action_min = float(cfg["legal_radial_removal_min_mm"])
        action_max = float(cfg["legal_radial_removal_max_mm"])
        terminal = float(cfg["final_thickness_mm"])
        model_max = float(cfg["workpiece_height_mm"]) / 10.0
        for removal in (action_min, action_max):
            for thickness in (terminal, model_max):
                pass_deflection_um(removal, thickness, cfg)
    except (ValueError, ArithmeticError, OverflowError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    return True, "all explicit Morelli applicability checks passed"


def run_e2(primary: Mapping) -> dict:
    rows: list[dict] = []
    audit_details: dict[str, dict] = {}
    for name, changes in VARIANTS.items():
        cfg = dict(primary)
        cfg.update(changes)
        valid, detail = validate_variant_domain(cfg)
        base_row = {
            "configuration": name,
            "status": "VALID" if valid else "INVALID_DOMAIN",
            "feed_per_tooth_mm": cfg["feed_per_tooth_mm"],
            "axial_depth_mm": cfg["axial_depth_mm"],
            "domain_check": detail,
        }
        if not valid:
            rows.append({
                **base_row,
                "STATE_TOTAL": "",
                "LOCAL_ACCEPTABLE_COUNT": "",
                "RECOVERABLE_COUNT": "",
                "LOCAL_BUT_IRRECOVERABLE_COUNT": "",
                "LOCAL_BUT_IRRECOVERABLE_RATE": "",
                "MIXED_ACTION_STATE_COUNT": "",
                "MIXED_ACTION_STATE_RATE": "",
                "PRESERVING_ACTION_COUNT": "",
                "DESTROYING_ACTION_COUNT": "",
                "MYOPIC_FIRST_ACTION_DESTROYING_COUNT": "",
                "MYOPIC_FIRST_ACTION_DESTROYING_RATE": "",
            })
            audit_details[name] = {"status": "INVALID_DOMAIN", "domain_check": detail}
            continue
        try:
            backward = build_backward_set(3, cfg)
            envelope = analyze_envelope(backward, cfg)
            domain = evaluated_states(backward, cfg)
            recoverable = np.isin(domain, backward["stages_int"][3])
            local = local_feasible_states(domain, cfg)
            _, first = first_action_audit(cfg, backward)
            recoverable_count = int(np.sum(recoverable))
            local_count = int(np.sum(local))
            separation = int(np.sum(local & ~recoverable))
            mixed = int(envelope.summary["mixed_action_states"])
            row = {
                **base_row,
                "STATE_TOTAL": int(domain.size),
                "LOCAL_ACCEPTABLE_COUNT": local_count,
                "RECOVERABLE_COUNT": recoverable_count,
                "LOCAL_BUT_IRRECOVERABLE_COUNT": separation,
                "LOCAL_BUT_IRRECOVERABLE_RATE": separation / local_count if local_count else None,
                "MIXED_ACTION_STATE_COUNT": mixed,
                "MIXED_ACTION_STATE_RATE": mixed / recoverable_count if recoverable_count else None,
                "PRESERVING_ACTION_COUNT": int(envelope.summary["preserving_actions"]),
                "DESTROYING_ACTION_COUNT": int(envelope.summary["destroying_actions"]),
                "MYOPIC_FIRST_ACTION_DESTROYING_COUNT": first["MYOPIC_FIRST_ACTION_DESTROYING_COUNT"],
                "MYOPIC_FIRST_ACTION_DESTROYING_RATE": first["MYOPIC_FIRST_ACTION_DESTROYING_RATE"],
            }
            rows.append(row)
            audit_details[name] = {"status": "VALID", **row}
        except (ValueError, ArithmeticError) as exc:
            base_row["status"] = "INVALID_DOMAIN"
            base_row["domain_check"] = f"{type(exc).__name__}: {exc}"
            rows.append({
                **base_row,
                "STATE_TOTAL": "",
                "LOCAL_ACCEPTABLE_COUNT": "",
                "RECOVERABLE_COUNT": "",
                "LOCAL_BUT_IRRECOVERABLE_COUNT": "",
                "LOCAL_BUT_IRRECOVERABLE_RATE": "",
                "MIXED_ACTION_STATE_COUNT": "",
                "MIXED_ACTION_STATE_RATE": "",
                "PRESERVING_ACTION_COUNT": "",
                "DESTROYING_ACTION_COUNT": "",
                "MYOPIC_FIRST_ACTION_DESTROYING_COUNT": "",
                "MYOPIC_FIRST_ACTION_DESTROYING_RATE": "",
            })
            audit_details[name] = {
                "status": "INVALID_DOMAIN", "domain_check": base_row["domain_check"]
            }
    predeclared_rows = [row for row in rows if row["configuration"] in PREDECLARED_VARIANTS]
    accounted = len(predeclared_rows) == 4 and all(
        row["status"] in {"VALID", "INVALID_DOMAIN"} for row in predeclared_rows
    )
    retained = all(
        row["status"] == "INVALID_DOMAIN"
        or all(row[key] != "" for key in (
            "STATE_TOTAL", "LOCAL_ACCEPTABLE_COUNT", "RECOVERABLE_COUNT",
            "LOCAL_BUT_IRRECOVERABLE_COUNT", "MIXED_ACTION_STATE_COUNT",
            "PRESERVING_ACTION_COUNT", "DESTROYING_ACTION_COUNT",
            "MYOPIC_FIRST_ACTION_DESTROYING_COUNT",
        ))
        for row in predeclared_rows
    )
    valid_names = [row["configuration"] for row in predeclared_rows if row["status"] == "VALID"]
    invalid_names = [row["configuration"] for row in predeclared_rows if row["status"] == "INVALID_DOMAIN"]
    state_persists = [
        row["configuration"] for row in predeclared_rows
        if row["status"] == "VALID" and int(row["LOCAL_BUT_IRRECOVERABLE_COUNT"]) > 0
    ]
    mixed_persists = [
        row["configuration"] for row in predeclared_rows
        if row["status"] == "VALID" and int(row["MIXED_ACTION_STATE_COUNT"]) > 0
        and int(row["PRESERVING_ACTION_COUNT"]) > 0 and int(row["DESTROYING_ACTION_COUNT"]) > 0
    ]
    summary = {
        "E2_GATE": "PASS" if accounted and retained else "FAIL",
        "PREDECLARED_VARIANTS": list(PREDECLARED_VARIANTS),
        "VALID_VARIANTS": valid_names,
        "INVALID_DOMAIN_VARIANTS": invalid_names,
        "STATE_SEPARATION_PERSISTS_IN": state_persists,
        "MIXED_ACTION_STRUCTURE_PERSISTS_IN": mixed_persists,
        "CONFIGURATIONS": audit_details,
        "INTERPRETATION_BOUNDARY": (
            "Controlled analytical-condition robustness only; not physical validation, "
            "uncertainty quantification, Monte Carlo evidence, or a generality claim."
        ),
    }
    write_csv(OUTPUT_DIR / "E2_configuration_robustness.csv", rows)
    write_json(OUTPUT_DIR / "E2_summary.json", summary)
    return summary


def timing_stats(values_ns: list[int]) -> tuple[float, float, str]:
    values_ms = np.asarray(values_ns, dtype=float) / 1_000_000.0
    median = float(np.median(values_ms))
    iqr = float(np.percentile(values_ms, 75) - np.percentile(values_ms, 25))
    raw = json.dumps([round(float(value), 9) for value in values_ms], separators=(",", ":"))
    return median, iqr, raw


def timed_core(pass_count: int, cfg: Mapping) -> tuple[dict, object, dict[str, list[int]]]:
    # Exactly one untimed warm-up of each requested call.
    warm_backward = build_backward_set(pass_count, cfg)
    analyze_envelope(warm_backward, cfg)
    backward_ns: list[int] = []
    envelope_ns: list[int] = []
    total_ns: list[int] = []
    last_backward = warm_backward
    last_envelope = None
    for _ in range(REPETITIONS):
        start = time.perf_counter_ns()
        last_backward = build_backward_set(pass_count, cfg)
        backward_elapsed = time.perf_counter_ns() - start
        start = time.perf_counter_ns()
        last_envelope = analyze_envelope(last_backward, cfg)
        envelope_elapsed = time.perf_counter_ns() - start
        backward_ns.append(backward_elapsed)
        envelope_ns.append(envelope_elapsed)
        total_ns.append(backward_elapsed + envelope_elapsed)
    assert last_envelope is not None
    return last_backward, last_envelope, {
        "backward": backward_ns, "envelope": envelope_ns, "total": total_ns
    }


def timing_fields(timings: Mapping[str, list[int]]) -> dict:
    backward_median, backward_iqr, backward_raw = timing_stats(timings["backward"])
    envelope_median, envelope_iqr, envelope_raw = timing_stats(timings["envelope"])
    total_median, total_iqr, total_raw = timing_stats(timings["total"])
    return {
        "REPETITIONS": REPETITIONS,
        "BACKWARD_MEDIAN_MS": backward_median,
        "BACKWARD_IQR_MS": backward_iqr,
        "ENVELOPE_MEDIAN_MS": envelope_median,
        "ENVELOPE_IQR_MS": envelope_iqr,
        "TOTAL_CORE_MEDIAN_MS": total_median,
        "TOTAL_CORE_IQR_MS": total_iqr,
        "BACKWARD_RUNS_MS_JSON": backward_raw,
        "ENVELOPE_RUNS_MS_JSON": envelope_raw,
        "TOTAL_CORE_RUNS_MS_JSON": total_raw,
    }


def run_e3(primary: Mapping) -> tuple[list[dict], list[dict]]:
    grid_rows: list[dict] = []
    for grid in GRID_CASES:
        cfg = dict(primary)
        cfg["state_grid_mm"] = grid
        cfg["remaining_pass_count"] = 3
        backward, envelope, timings = timed_core(3, cfg)
        stage_counts = {k: len(backward["stages_int"][k]) for k in range(4)}
        transition_counts = {k: int(backward["transition_counts"][k]) for k in range(1, 4)}
        grid_rows.append({
            "STATUS": "VALID" if stage_counts[3] else "EMPTY_PHYSICAL_DOMAIN",
            "GRID_MM": grid,
            "ACTION_GRID_COUNT": len(envelope.actions_int),
            "R0_STATE_COUNT": stage_counts[0],
            "R1_STATE_COUNT": stage_counts[1],
            "R2_STATE_COUNT": stage_counts[2],
            "R3_STATE_COUNT": stage_counts[3],
            "TRANSITIONS_STAGE_1": transition_counts[1],
            "TRANSITIONS_STAGE_2": transition_counts[2],
            "TRANSITIONS_STAGE_3": transition_counts[3],
            "TOTAL_TRANSITION_COUNT": sum(transition_counts.values()),
            "FINAL_RECOVERABLE_STATE_COUNT": stage_counts[3],
            "ENVELOPE_STATE_COUNT": len(envelope.states_int),
            "ENVELOPE_ACTION_COUNT": len(envelope.actions_int),
            "ENVELOPE_CELL_COUNT": len(envelope.states_int) * len(envelope.actions_int),
            **timing_fields(timings),
        })
    horizon_rows: list[dict] = []
    for pass_count in HORIZON_CASES:
        cfg = dict(primary)
        cfg["state_grid_mm"] = 0.001
        cfg["remaining_pass_count"] = pass_count
        backward, envelope, timings = timed_core(pass_count, cfg)
        stage_counts = {k: len(backward["stages_int"][k]) for k in range(pass_count + 1)}
        transition_counts = {
            k: int(backward["transition_counts"][k]) for k in range(1, pass_count + 1)
        }
        horizon_rows.append({
            "STATUS": "VALID" if stage_counts[pass_count] else "EMPTY_PHYSICAL_DOMAIN",
            "PASS_COUNT": pass_count,
            "ACTION_GRID_COUNT": len(envelope.actions_int),
            "R_K_STATE_COUNTS": json.dumps(stage_counts, separators=(",", ":")),
            "TOTAL_TRANSITION_COUNT": sum(transition_counts.values()),
            "ENVELOPE_CELL_COUNT": len(envelope.states_int) * len(envelope.actions_int),
            **timing_fields(timings),
        })
    write_csv(OUTPUT_DIR / "E3_grid_scalability.csv", grid_rows)
    write_csv(OUTPUT_DIR / "E3_horizon_scalability.csv", horizon_rows)
    return grid_rows, horizon_rows


def environment_record() -> dict:
    try:
        import psutil
        physical = psutil.cpu_count(logical=False)
        logical = psutil.cpu_count(logical=True)
    except ImportError:
        physical = None
        logical = os.cpu_count()
    if physical is None and platform.system() == "Windows":
        try:
            completed = subprocess.run(
                [
                    "powershell", "-NoProfile", "-Command",
                    "(Get-CimInstance Win32_Processor | "
                    "Measure-Object -Property NumberOfCores -Sum).Sum",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            physical = int(completed.stdout.strip())
        except (OSError, ValueError, subprocess.SubprocessError):
            physical = None
    cpu = platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER") or "unavailable"
    return {
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "os": platform.platform(),
        "cpu": cpu,
        "logical_core_count": logical,
        "physical_core_count": physical,
        "timer": "time.perf_counter_ns external call boundary",
        "warmup_runs_per_case": 1,
        "measured_repetitions_per_case": REPETITIONS,
        "timing_claim_boundary": "No real-time or asymptotic scaling-law claim.",
    }


def fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.12g}"
    if isinstance(value, list):
        return ",".join(map(str, value)) if value else "NONE"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def report_table(rows: list[dict], columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(fmt(row.get(column, "")) for column in columns) + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def build_report(args: argparse.Namespace) -> None:
    e1 = json.loads((OUTPUT_DIR / "E1_summary.json").read_text(encoding="utf-8"))
    e2 = json.loads((OUTPUT_DIR / "E2_summary.json").read_text(encoding="utf-8"))
    grid_rows = read_csv(OUTPUT_DIR / "E3_grid_scalability.csv")
    horizon_rows = read_csv(OUTPUT_DIR / "E3_horizon_scalability.csv")
    required_regression_pass = args.pytest_result == "PASS" and args.quick_result == "PASS"
    diff_pass = args.diff_check_result == "PASS"
    e3_gate = "PASS" if (
        len(grid_rows) == len(GRID_CASES)
        and len(horizon_rows) == len(HORIZON_CASES)
        and all(int(row["REPETITIONS"]) == REPETITIONS for row in grid_rows + horizon_rows)
        and all(row["STATUS"] in {"VALID", "EMPTY_PHYSICAL_DOMAIN"} for row in grid_rows + horizon_rows)
    ) else "FAIL"
    if e1["RPRA_INVARIANT_VIOLATION_COUNT"] > 0:
        task_status = "FAIL_SCIENTIFIC_INVARIANT"
    elif args.pytest_result == "FAIL" or args.quick_result == "FAIL" or args.diff_check_result == "FAIL":
        task_status = "FAIL_REGRESSION"
    elif "PENDING" in {args.pytest_result, args.quick_result, args.diff_check_result}:
        task_status = "IN_PROGRESS"
    else:
        task_status = "COMPLETE"
    gates_pass = e1["E1_GATE"] == e2["E2_GATE"] == e3_gate == "PASS"
    recommendation = "FREEZE" if task_status == "COMPLETE" and gates_pass and required_regression_pass and diff_pass else "DO_NOT_FREEZE"
    blockers = []
    if e1["E1_GATE"] != "PASS":
        blockers.append("E1_GATE")
    if e2["E2_GATE"] != "PASS":
        blockers.append("E2_GATE")
    if e3_gate != "PASS":
        blockers.append("E3_GATE")
    if not required_regression_pass or not diff_pass:
        blockers.append("REGRESSION_PENDING_OR_FAILED")
    remaining_blockers = ",".join(blockers) if blockers else "NONE"
    primary_grid = next(row for row in grid_rows if float(row["GRID_MM"]) == 0.001)
    finest_grid = next(row for row in grid_rows if float(row["GRID_MM"]) == 0.00025)
    four_pass = next(row for row in horizon_rows if int(row["PASS_COUNT"]) == 4)
    first_action_rows = len(read_csv(OUTPUT_DIR / "E1_first_action_audit.csv"))
    trajectory_rows = len(read_csv(OUTPUT_DIR / "E1_rollout_trajectories.csv"))
    report = f"""# R8.1 Main-Line Experiment Freeze Candidate Audit

## Scope and provenance

- Frozen configuration: `configs/3pass_100um.yaml`
- `GIT_COMMIT_BEFORE={args.git_commit_before}`
- `GIT_STATUS_BEFORE={args.git_status_before}`
- Baseline before experiment changes: `pytest -q` PASS (10 tests); quick reproduction PASS.
- No RPRA definition, Morelli model, frozen expected result, manuscript, supplementary manuscript, README/CITATION/release metadata, or numerical tolerance was modified.
- The existing untracked files named in `GIT_STATUS_BEFORE` were left untouched.

## E1 — decision consequence

Both policies minimize the same immediate Morelli deflection. The myopic policy uses the frozen local-feasibility mask; the RPRA policy differs only by intersecting that mask with exact downstream membership. Objective ties within `decision_tolerance_um` select the smaller radial-removal action.

- Recoverable start states audited: {e1['RECOVERABLE_START_STATES']}
- First-action rows: {first_action_rows}; rollout trajectory rows: {trajectory_rows}
- Myopic first actions: {e1['MYOPIC_FIRST_ACTION_PRESERVING_COUNT']} preserving, {e1['MYOPIC_FIRST_ACTION_DESTROYING_COUNT']} destroying ({fmt(e1['MYOPIC_FIRST_ACTION_DESTROYING_RATE'])}).
- Myopic completions: {e1['MYOPIC_COMPLETION_COUNT']} ({fmt(e1['MYOPIC_COMPLETION_RATE'])}); failures: `{fmt(e1['MYOPIC_FAILURE_BY_STAGE'])}`.
- RPRA completions: {e1['RPRA_COMPLETION_COUNT']} ({fmt(e1['RPRA_COMPLETION_RATE'])}); invariant violations: {e1['RPRA_INVARIANT_VIOLATION_COUNT']}.
- Deflection sacrifice over all starts (mean/median/P95/max, µm): {fmt(e1['DELTA_DEFLECTION_MEAN_UM'])} / {fmt(e1['DELTA_DEFLECTION_MEDIAN_UM'])} / {fmt(e1['DELTA_DEFLECTION_P95_UM'])} / {fmt(e1['DELTA_DEFLECTION_MAX_UM'])}.
- Selected actions differ in {e1['SELECTED_ACTIONS_DIFFER_COUNT']} states. Conditional sacrifice (mean/median/P95/max, µm): {fmt(e1['DIFFERING_ACTION_DELTA_DEFLECTION_MEAN_UM'])} / {fmt(e1['DIFFERING_ACTION_DELTA_DEFLECTION_MEDIAN_UM'])} / {fmt(e1['DIFFERING_ACTION_DELTA_DEFLECTION_P95_UM'])} / {fmt(e1['DIFFERING_ACTION_DELTA_DEFLECTION_MAX_UM'])}.
- Frozen mechanism: 0.432 → 4.010 DESTROYING; 0.557 → 3.885 PRESERVING; unchanged = {e1['MECHANISM_REGRESSION']['MECHANISM_4P442_UNCHANGED']}.

`E1_GATE={e1['E1_GATE']}`

## E2 — controlled analytical-condition robustness

{report_table([e2['CONFIGURATIONS'][name] for name in VARIANTS], ['configuration', 'status', 'STATE_TOTAL', 'LOCAL_ACCEPTABLE_COUNT', 'RECOVERABLE_COUNT', 'LOCAL_BUT_IRRECOVERABLE_COUNT', 'MIXED_ACTION_STATE_COUNT', 'MYOPIC_FIRST_ACTION_DESTROYING_COUNT'])}

All four additional variants were predeclared. This is controlled analytical-condition robustness only—not experimental physical validation, uncertainty quantification, Monte Carlo evidence, or a generality claim.

The E2 baseline exact represented-set difference is 214 (`|L₃,h \\ R₃,h|`). The frozen quick-reproduction value 212 is unchanged and uses the existing continuous-boundary publication helper; the two values answer different formally defined classifications and are not a regression mismatch.

- Valid predeclared variants: {fmt(e2['VALID_VARIANTS'])}
- Invalid-domain predeclared variants: {fmt(e2['INVALID_DOMAIN_VARIANTS'])}
- State-level separation persists in: {fmt(e2['STATE_SEPARATION_PERSISTS_IN'])}
- Mixed preserving/destroying action structure persists in: {fmt(e2['MIXED_ACTION_STRUCTURE_PERSISTS_IN'])}

`E2_GATE={e2['E2_GATE']}`

## E3 — RPRA core construction timing

One warm-up and {REPETITIONS} measured repetitions were used for every case. `time.perf_counter_ns()` was placed externally around `build_backward_set()` and `analyze_envelope()`. CSV cells retain all raw repetitions in addition to median and IQR. RDF work is excluded.

### Grid scaling

{report_table(grid_rows, ['GRID_MM', 'ACTION_GRID_COUNT', 'R0_STATE_COUNT', 'R1_STATE_COUNT', 'R2_STATE_COUNT', 'R3_STATE_COUNT', 'TOTAL_TRANSITION_COUNT', 'ENVELOPE_CELL_COUNT', 'BACKWARD_MEDIAN_MS', 'BACKWARD_IQR_MS', 'ENVELOPE_MEDIAN_MS', 'ENVELOPE_IQR_MS', 'TOTAL_CORE_MEDIAN_MS'])}

### Horizon scaling

{report_table(horizon_rows, ['PASS_COUNT', 'R_K_STATE_COUNTS', 'TOTAL_TRANSITION_COUNT', 'ENVELOPE_CELL_COUNT', 'BACKWARD_MEDIAN_MS', 'BACKWARD_IQR_MS', 'ENVELOPE_MEDIAN_MS', 'ENVELOPE_IQR_MS', 'TOTAL_CORE_MEDIAN_MS'])}

These are descriptive measurements for the recorded environment. No real-time guarantee or asymptotic scaling-law claim is made.

`E3_GATE={e3_gate}`

## Regression and freeze decision

```text
TASK_STATUS={task_status}

GIT_COMMIT_BEFORE={args.git_commit_before}
GIT_COMMIT_AFTER={args.git_commit_after}
PUSH=false

E1_GATE={e1['E1_GATE']}
E1_RECOVERABLE_START_STATES={e1['RECOVERABLE_START_STATES']}
E1_MYOPIC_FIRST_ACTION_DESTROYING_COUNT={e1['MYOPIC_FIRST_ACTION_DESTROYING_COUNT']}
E1_MYOPIC_FIRST_ACTION_DESTROYING_RATE={fmt(e1['MYOPIC_FIRST_ACTION_DESTROYING_RATE'])}
E1_MYOPIC_COMPLETION_COUNT={e1['MYOPIC_COMPLETION_COUNT']}
E1_MYOPIC_COMPLETION_RATE={fmt(e1['MYOPIC_COMPLETION_RATE'])}
E1_RPRA_COMPLETION_COUNT={e1['RPRA_COMPLETION_COUNT']}
E1_RPRA_COMPLETION_RATE={fmt(e1['RPRA_COMPLETION_RATE'])}
E1_RPRA_INVARIANT_VIOLATION_COUNT={e1['RPRA_INVARIANT_VIOLATION_COUNT']}
E1_DEFLECTION_SACRIFICE_MEDIAN_UM={fmt(e1['DELTA_DEFLECTION_MEDIAN_UM'])}
E1_DEFLECTION_SACRIFICE_P95_UM={fmt(e1['DELTA_DEFLECTION_P95_UM'])}
E1_DEFLECTION_SACRIFICE_MAX_UM={fmt(e1['DELTA_DEFLECTION_MAX_UM'])}

E2_GATE={e2['E2_GATE']}
E2_VALID_VARIANTS={fmt(e2['VALID_VARIANTS'])}
E2_INVALID_DOMAIN_VARIANTS={fmt(e2['INVALID_DOMAIN_VARIANTS'])}
E2_STATE_SEPARATION_PERSISTS_IN={fmt(e2['STATE_SEPARATION_PERSISTS_IN'])}
E2_MIXED_ACTION_STRUCTURE_PERSISTS_IN={fmt(e2['MIXED_ACTION_STRUCTURE_PERSISTS_IN'])}

E3_GATE={e3_gate}
E3_GRID_CASES={','.join(row['GRID_MM'] for row in grid_rows)}
E3_HORIZON_CASES={','.join(row['PASS_COUNT'] for row in horizon_rows)}
E3_FINEST_GRID_TOTAL_CORE_MEDIAN_MS={finest_grid['TOTAL_CORE_MEDIAN_MS']}
E3_PRIMARY_GRID_TOTAL_CORE_MEDIAN_MS={primary_grid['TOTAL_CORE_MEDIAN_MS']}
E3_FOUR_PASS_TOTAL_CORE_MEDIAN_MS={four_pass['TOTAL_CORE_MEDIAN_MS']}

PYTEST={args.pytest_result}
QUICK_REPRODUCTION={args.quick_result}
FULL_REPRODUCTION={args.full_result}
GIT_DIFF_CHECK={args.diff_check_result}

EXPERIMENT_FREEZE_RECOMMENDATION={recommendation}

REMAINING_BLOCKERS={remaining_blockers}
```
"""
    (OUTPUT_DIR / "EXPERIMENT_FREEZE_AUDIT.md").write_text(report, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize-only", action="store_true")
    parser.add_argument("--git-commit-before", required=True)
    parser.add_argument("--git-commit-after", default="UNCOMMITTED")
    parser.add_argument("--git-status-before", required=True)
    parser.add_argument("--pytest-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    parser.add_argument("--quick-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    parser.add_argument("--full-result", choices=("PASS", "FAIL", "NOT_RUN", "PENDING"), default="PENDING")
    parser.add_argument("--diff-check-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.finalize_only:
        cfg = load_configuration(PRIMARY_CONFIG)
        run_e1(cfg)
        e1 = json.loads((OUTPUT_DIR / "E1_summary.json").read_text(encoding="utf-8"))
        if e1["RPRA_INVARIANT_VIOLATION_COUNT"] > 0:
            build_report(args)
            raise SystemExit("FAIL_SCIENTIFIC_INVARIANT")
        run_e2(cfg)
        run_e3(cfg)
        write_json(OUTPUT_DIR / "E3_environment.json", environment_record())
    build_report(args)


if __name__ == "__main__":
    main()

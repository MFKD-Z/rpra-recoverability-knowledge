"""Run the frozen RINENG B1 ONLINE-REOPT comparator audit.

This harness is intentionally outside ``src/rpra``.  It reuses the frozen E1
candidate construction and RPRA preserving-action selector, and compares that
selector with an on-demand continuous downstream re-optimization selector.

The formal run is write-once: existing B1 raw outputs are never overwritten.
Use ``--preflight`` before the formal run and ``--finalize-only`` after the
external regression gates have been executed.
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
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np
import scipy


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
for import_path in (SRC, SCRIPTS):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from rpra.envelopes import load_configuration  # noqa: E402
from rpra.optimization import full_reoptimize  # noqa: E402
from rpra.recoverable_set import build_backward_set  # noqa: E402
from run_r81_experiment_freeze_candidate import (  # noqa: E402
    action_candidates,
    mechanism_regression,
    select_action,
)


BASELINE_COMMIT = "c25540909939f65fad732420fa484f52931c02f9"
FROZEN_TAG = "v1.1.0"
OUTPUT_DIR = ROOT / "audits" / "20260828_b1_online_reopt_comparator"
PRIMARY_CONFIG = ROOT / "configs" / "3pass_100um.yaml"
FROZEN_E1_DIR = ROOT / "audits" / "20260828_r81_experiment_freeze_candidate"
FROZEN_E1_FIRST = FROZEN_E1_DIR / "E1_first_action_audit.csv"
FROZEN_E3_ENVIRONMENT = FROZEN_E1_DIR / "E3_environment.json"
EXTERNAL_GOAL = Path(
    r"E:\数值分析与优化算法-李炎炎老师\补交作业\RINENG_B1_ONLINE_REOPT_COMPARATOR_CODEX_GOAL.md"
)
DESIGN_FREEZE = Path(
    r"E:\数值分析与优化算法-李炎炎老师\补交作业\RINENG_B1_ONLINE_REOPT_COMPARATOR_DESIGN_FREEZE.md"
)
REPETITIONS = 5
WARMUPS = 1
POLICIES = ("RPRA", "ONLINE-REOPT")
RAW_OUTPUT_NAMES = (
    "B1_first_action_comparator.csv",
    "B1_rollout_trajectories.csv",
    "B1_summary.json",
    "B1_disagreement_audit.csv",
    "B1_timing_raw.csv",
    "B1_environment.json",
    "B1_continuous_solver_audit.csv",
)


def git(*args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        if not rows:
            raise ValueError(f"fieldnames required for empty CSV: {path}")
        fieldnames = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def optional(value: object | None) -> object | str:
    return "" if value is None else value


def exact_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def normalized_solver_result(result: Mapping) -> dict:
    """Keep every scientific and numerical field used by the comparator."""
    return {
        key: result.get(key)
        for key in (
            "feasible",
            "reason",
            "optimizer",
            "optimizer_success",
            "optimizer_message",
            "multistart_count",
            "current_thickness_mm",
            "remaining_pass_count",
            "required_removal_mm",
            "first_pass_ar_domain_lower_bound_mm",
            "pass_removals_mm",
            "optimal_worst_deflection_um",
            "recoverability_margin_um",
            "decision_at_limit",
            "constraint_residuals",
            "pass_details",
        )
        if key in result
    }


def residual_validity(result: Mapping) -> tuple[bool, str]:
    """Apply the frozen validity checks already used by full_reoptimize."""
    if not bool(result.get("feasible", False)):
        reason = str(result.get("reason", ""))
        return (reason == "nominal_capacity", f"capacity_reason:{reason or 'missing'}")
    residuals = result.get("constraint_residuals")
    if not isinstance(residuals, Mapping):
        return False, "missing_constraint_residuals"
    checks = {
        "removal_sum_abs_mm": float(residuals.get("removal_sum_abs_mm", float("inf"))) <= 2e-7,
        "action_bound_violation_mm": float(residuals.get("action_bound_violation_mm", float("inf"))) <= 2e-8,
        "epigraph_violation_um": float(residuals.get("epigraph_violation_um", float("inf"))) <= 2e-5,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return not failed, "residual_checks_pass" if not failed else "failed:" + ",".join(failed)


@dataclass
class DownstreamOutcome:
    status: str
    detail: str
    result: dict | None

    def normalized(self) -> dict:
        return {
            "status": self.status,
            "detail": self.detail,
            "result": None if self.result is None else normalized_solver_result(self.result),
        }


@dataclass
class DownstreamEvaluator:
    cfg: Mapping
    scale: int
    cache_enabled: bool = True
    cache: dict[tuple[int, int], DownstreamOutcome] = field(default_factory=dict)
    actual_solver_calls: int = 0
    actual_calls_by_purpose: Counter = field(default_factory=Counter)
    cache_hits_by_purpose: Counter = field(default_factory=Counter)
    numerical_unresolved_events: list[dict] = field(default_factory=list)

    def solve_uncached(self, successor_i: int, downstream_passes: int, purpose: str) -> DownstreamOutcome:
        self.actual_solver_calls += 1
        self.actual_calls_by_purpose[purpose] += 1
        successor_mm = int(successor_i) / self.scale
        try:
            result = full_reoptimize(
                successor_mm,
                int(downstream_passes),
                self.cfg,
                multistart=7,
            )
        except Exception as exc:  # retained; never converted to model FAIL
            detail = f"{type(exc).__name__}: {exc}"
            outcome = DownstreamOutcome("NUMERICAL_UNRESOLVED", detail, None)
            self.numerical_unresolved_events.append({
                "successor_mm": successor_mm,
                "downstream_passes": int(downstream_passes),
                "purpose": purpose,
                "detail": detail,
            })
            return outcome

        result = dict(result)
        if not result.get("feasible", False):
            reason = str(result.get("reason", ""))
            if reason == "nominal_capacity":
                return DownstreamOutcome("FAIL", f"model_capacity:{reason}", result)
            detail = f"unclassified_infeasible:{reason or 'missing_reason'}"
            outcome = DownstreamOutcome("NUMERICAL_UNRESOLVED", detail, result)
            self.numerical_unresolved_events.append({
                "successor_mm": successor_mm,
                "downstream_passes": int(downstream_passes),
                "purpose": purpose,
                "detail": detail,
            })
            return outcome

        residual_valid, residual_detail = residual_validity(result)
        if not residual_valid:
            detail = "residual_invalid:" + residual_detail
            outcome = DownstreamOutcome("NUMERICAL_UNRESOLVED", detail, result)
            self.numerical_unresolved_events.append({
                "successor_mm": successor_mm,
                "downstream_passes": int(downstream_passes),
                "purpose": purpose,
                "detail": detail,
            })
            return outcome

        decision = str(result.get("decision_at_limit", ""))
        if decision not in {"PASS", "FAIL"}:
            detail = f"invalid_decision_at_limit:{decision or 'missing'}"
            outcome = DownstreamOutcome("NUMERICAL_UNRESOLVED", detail, result)
            self.numerical_unresolved_events.append({
                "successor_mm": successor_mm,
                "downstream_passes": int(downstream_passes),
                "purpose": purpose,
                "detail": detail,
            })
            return outcome
        return DownstreamOutcome(
            decision,
            "continuous_reference_residual_valid"
            + ("_optimizer_reported_success" if bool(result.get("optimizer_success", False)) else "_optimizer_reported_non_success"),
            result,
        )

    def evaluate(self, successor_i: int, downstream_passes: int, purpose: str) -> DownstreamOutcome:
        key = (int(downstream_passes), int(successor_i))
        if self.cache_enabled and key in self.cache:
            self.cache_hits_by_purpose[purpose] += 1
            return self.cache[key]
        outcome = self.solve_uncached(successor_i, downstream_passes, purpose)
        if self.cache_enabled:
            self.cache[key] = outcome
        return outcome


def exact_terminal_outcome(successor_i: int, terminal_i: int) -> DownstreamOutcome:
    if int(successor_i) == int(terminal_i):
        return DownstreamOutcome("PASS", "exact_terminal_equality", None)
    return DownstreamOutcome("FAIL", "exact_terminal_mismatch", None)


def downstream_fields(outcome: DownstreamOutcome) -> dict:
    result = outcome.result or {}
    return {
        "continuous_status": outcome.status,
        "continuous_detail": outcome.detail,
        "continuous_optimizer_success": optional(result.get("optimizer_success")),
        "continuous_decision_at_limit": optional(result.get("decision_at_limit")),
        "continuous_worst_deflection_um": optional(result.get("optimal_worst_deflection_um")),
        "continuous_margin_um": optional(result.get("recoverability_margin_um")),
    }


def continuous_solver_audit_rows(evaluator: DownstreamEvaluator) -> list[dict]:
    rows: list[dict] = []
    for (downstream_passes, successor_i), outcome in sorted(evaluator.cache.items()):
        result = outcome.result or {}
        residuals = result.get("constraint_residuals") or {}
        residual_valid, residual_detail = residual_validity(result) if result else (False, "no_result")
        rows.append({
            "downstream_passes": downstream_passes,
            "successor_mm": successor_i / evaluator.scale,
            "classified_status": outcome.status,
            "classification_detail": outcome.detail,
            "feasible": optional(result.get("feasible")),
            "capacity_reason": optional(result.get("reason")),
            "optimizer_success": optional(result.get("optimizer_success")),
            "optimizer_message": optional(result.get("optimizer_message")),
            "multistart_count": optional(result.get("multistart_count")),
            "decision_at_limit": optional(result.get("decision_at_limit")),
            "residual_valid": residual_valid,
            "residual_validity_detail": residual_detail,
            "removal_sum_abs_mm": optional(residuals.get("removal_sum_abs_mm")),
            "action_bound_violation_mm": optional(residuals.get("action_bound_violation_mm")),
            "epigraph_violation_um": optional(residuals.get("epigraph_violation_um")),
            "terminal_thickness_abs_mm": optional(residuals.get("terminal_thickness_abs_mm")),
            "optimal_worst_deflection_um": optional(result.get("optimal_worst_deflection_um")),
            "recoverability_margin_um": optional(result.get("recoverability_margin_um")),
        })
    return rows


def select_online_action(
    state_i: int,
    remaining_passes: int,
    backward: Mapping,
    cfg: Mapping,
    evaluator: DownstreamEvaluator,
    *,
    purpose: str,
) -> dict:
    candidates = action_candidates(state_i, remaining_passes, backward, cfg)
    actions = np.asarray(candidates["actions"], dtype=np.int64)
    next_states = np.asarray(candidates["next_states"], dtype=np.int64)
    deflections = np.asarray(candidates["deflections"], dtype=float)
    preserving = np.asarray(candidates["preserving"], dtype=bool)
    local_indices = np.flatnonzero(np.asarray(candidates["local"], dtype=bool))
    base = {
        "status": "NO_LOCAL_CANDIDATE",
        "selected": None,
        "candidate_count": int(local_indices.size),
        "solve_call_count": 0,
        "downstream_pass_count": 0,
        "downstream_fail_count": 0,
        "downstream_unresolved_count": 0,
        "first_pass_objective_um": None,
    }
    if not local_indices.size:
        return base

    order = local_indices[np.lexsort((actions[local_indices], deflections[local_indices]))]
    terminal_i = int(round(float(cfg["final_thickness_mm"]) * evaluator.scale))
    tolerance = float(cfg.get("decision_tolerance_um", 1e-7))

    if remaining_passes == 1:
        exact = [idx for idx in order if int(next_states[idx]) == terminal_i]
        if not exact:
            return {**base, "status": "NO_EXACT_TERMINAL_ACTION"}
        best = float(deflections[exact[0]])
        tied = [idx for idx in exact if float(deflections[idx]) <= best + tolerance]
        selected_index = min(tied, key=lambda idx: int(actions[idx]))
        selected = {
            "action_i": int(actions[selected_index]),
            "next_state_i": int(next_states[selected_index]),
            "deflection_um": float(deflections[selected_index]),
            "discrete_class": "PRESERVING" if preserving[selected_index] else "DESTROYING",
            **downstream_fields(exact_terminal_outcome(next_states[selected_index], terminal_i)),
        }
        return {
            **base,
            "status": "PASS",
            "selected": selected,
            "downstream_pass_count": 1,
            "first_pass_objective_um": best,
        }

    pass_candidates: list[tuple[int, DownstreamOutcome]] = []
    first_pass_objective: float | None = None
    solve_calls = pass_count = fail_count = unresolved_count = 0
    for idx in order:
        objective = float(deflections[idx])
        if first_pass_objective is not None and objective > first_pass_objective + tolerance:
            break
        outcome = evaluator.evaluate(
            int(next_states[idx]),
            int(remaining_passes) - 1,
            purpose,
        )
        solve_calls += 1
        if outcome.status == "PASS":
            pass_count += 1
            if first_pass_objective is None:
                first_pass_objective = objective
            pass_candidates.append((int(idx), outcome))
        elif outcome.status == "FAIL":
            fail_count += 1
        else:
            unresolved_count += 1
            return {
                **base,
                "status": "NUMERICAL_UNRESOLVED",
                "solve_call_count": solve_calls,
                "downstream_pass_count": pass_count,
                "downstream_fail_count": fail_count,
                "downstream_unresolved_count": unresolved_count,
                "first_pass_objective_um": first_pass_objective,
            }

    if not pass_candidates:
        return {
            **base,
            "status": "NO_DOWNSTREAM_PASS",
            "solve_call_count": solve_calls,
            "downstream_fail_count": fail_count,
        }

    selected_index, selected_outcome = min(
        pass_candidates,
        key=lambda pair: int(actions[pair[0]]),
    )
    selected = {
        "action_i": int(actions[selected_index]),
        "next_state_i": int(next_states[selected_index]),
        "deflection_um": float(deflections[selected_index]),
        "discrete_class": "PRESERVING" if preserving[selected_index] else "DESTROYING",
        **downstream_fields(selected_outcome),
    }
    return {
        **base,
        "status": "PASS",
        "selected": selected,
        "solve_call_count": solve_calls,
        "downstream_pass_count": pass_count,
        "downstream_fail_count": fail_count,
        "downstream_unresolved_count": unresolved_count,
        "first_pass_objective_um": first_pass_objective,
    }


def audit_selected_downstream(
    selected: Mapping,
    remaining_passes: int,
    cfg: Mapping,
    evaluator: DownstreamEvaluator,
    *,
    purpose: str,
) -> DownstreamOutcome:
    terminal_i = int(round(float(cfg["final_thickness_mm"]) * evaluator.scale))
    if remaining_passes == 1:
        return exact_terminal_outcome(int(selected["next_state_i"]), terminal_i)
    return evaluator.evaluate(
        int(selected["next_state_i"]),
        int(remaining_passes) - 1,
        purpose,
    )


def first_action_audit(cfg: Mapping, backward: Mapping, evaluator: DownstreamEvaluator) -> tuple[list[dict], dict]:
    scale = int(backward["scale"])
    starts = np.asarray(backward["stages_int"][3], dtype=np.int64)
    rows: list[dict] = []
    theoretical_calls = 0
    for position, state_value in enumerate(starts):
        state_i = int(state_value)
        candidates = action_candidates(state_i, 3, backward, cfg)
        rpra = select_action(candidates, cfg, rpra=True)
        if rpra is None:
            raise RuntimeError(f"RPRA lacks a preserving action at {state_i / scale:.6f} mm")

        online_result = select_online_action(
            state_i,
            3,
            backward,
            cfg,
            evaluator,
            purpose="first_decision_online",
        )
        theoretical_calls += int(online_result["solve_call_count"])
        online = online_result["selected"]
        rpra_continuous = audit_selected_downstream(
            rpra,
            3,
            cfg,
            evaluator,
            purpose="first_decision_rpra_audit",
        )

        action_agreement = online is not None and int(rpra["action_i"]) == int(online["action_i"])
        action_delta_um = None if online is None else (int(online["action_i"]) - int(rpra["action_i"]))
        deflection_delta = None if online is None else (
            float(rpra["deflection_um"]) - float(online["deflection_um"])
        )
        tolerance = float(cfg.get("decision_tolerance_um", 1e-7))
        if online_result["status"] == "NUMERICAL_UNRESOLVED" or rpra_continuous.status == "NUMERICAL_UNRESOLVED":
            disagreement_classification = "NUMERICAL_UNRESOLVED"
        elif rpra_continuous.status == "FAIL":
            disagreement_classification = "RPRA_SELECTED_CONTINUOUS_INFEASIBLE"
        elif online is None:
            disagreement_classification = "OTHER_NO_ONLINE_ADMISSIBLE_ACTION"
        elif action_agreement:
            disagreement_classification = "EXACT_AGREEMENT"
        elif online["discrete_class"] == "DESTROYING":
            disagreement_classification = "ONLINE_FEASIBLE_BUT_DISCRETE_REJECTED"
        elif abs(float(rpra["deflection_um"]) - float(online["deflection_um"])) <= tolerance:
            disagreement_classification = "OBJECTIVE_TIE_DIFFERENCE"
        else:
            disagreement_classification = "OTHER_ADMISSIBILITY_DIFFERENCE"
        rows.append({
            "state_order": position,
            "state_mm": state_i / scale,
            "remaining_passes": 3,
            "rpra_action_mm": int(rpra["action_i"]) / scale,
            "rpra_immediate_deflection_um": float(rpra["deflection_um"]),
            "rpra_successor_mm": int(rpra["next_state_i"]) / scale,
            "rpra_discrete_class": rpra["class"],
            "rpra_selected_continuous_status": rpra_continuous.status,
            "rpra_selected_continuous_detail": rpra_continuous.detail,
            "online_decision_status": online_result["status"],
            "online_action_mm": optional(None if online is None else int(online["action_i"]) / scale),
            "online_immediate_deflection_um": optional(None if online is None else float(online["deflection_um"])),
            "online_successor_mm": optional(None if online is None else int(online["next_state_i"]) / scale),
            "online_discrete_class": optional(None if online is None else online["discrete_class"]),
            "online_selected_continuous_status": optional(None if online is None else online["continuous_status"]),
            "exact_action_agreement": action_agreement,
            "signed_action_delta_um_online_minus_rpra": optional(action_delta_um),
            "absolute_action_difference_um": optional(None if action_delta_um is None else abs(action_delta_um)),
            "immediate_deflection_delta_um_rpra_minus_online": optional(deflection_delta),
            "disagreement_classification": disagreement_classification,
            "rpra_local_candidate_count": int(np.sum(np.asarray(candidates["local"], dtype=bool))),
            "rpra_preserving_candidate_count": int(np.sum(np.asarray(candidates["preserving"], dtype=bool))),
            "online_local_candidate_count": online_result["candidate_count"],
            "online_continuous_solve_calls": online_result["solve_call_count"],
            "online_downstream_pass_count_evaluated": online_result["downstream_pass_count"],
            "online_downstream_fail_count_evaluated": online_result["downstream_fail_count"],
            "online_downstream_unresolved_count_evaluated": online_result["downstream_unresolved_count"],
        })
        if (position + 1) % 25 == 0 or position + 1 == len(starts):
            print(f"FIRST_DECISION_PROGRESS={position + 1}/{len(starts)}", flush=True)

    summary = {
        "FIRST_DECISION_ROWS": len(rows),
        "EXACT_FIRST_ACTION_AGREEMENT_COUNT": sum(bool(row["exact_action_agreement"]) for row in rows),
        "ONLINE_REOPT_TOTAL_SOLVE_CALLS_FIRST_DECISION_DOMAIN": theoretical_calls,
        "RPRA_SELECTED_CONTINUOUS_INFEASIBLE_FIRST_DECISION_COUNT": sum(
            row["rpra_selected_continuous_status"] == "FAIL" for row in rows
        ),
        "RPRA_SELECTED_CONTINUOUS_FEASIBLE_FIRST_DECISION_COUNT": sum(
            row["rpra_selected_continuous_status"] == "PASS" for row in rows
        ),
        "RPRA_SELECTED_CONTINUOUS_UNRESOLVED_FIRST_DECISION_COUNT": sum(
            row["rpra_selected_continuous_status"] == "NUMERICAL_UNRESOLVED" for row in rows
        ),
        "ONLINE_SELECTED_DISCRETE_REJECTED_FIRST_DECISION_COUNT": sum(
            row["online_discrete_class"] == "DESTROYING" for row in rows
        ),
        "ONLINE_SELECTED_INSIDE_DISCRETE_PRESERVING_ENVELOPE_FIRST_DECISION_COUNT": sum(
            row["online_discrete_class"] == "PRESERVING" for row in rows
        ),
        "ONLINE_FIRST_DECISION_UNRESOLVED_COUNT": sum(
            row["online_decision_status"] == "NUMERICAL_UNRESOLVED" for row in rows
        ),
        "ONLINE_FIRST_DECISION_NO_PASS_COUNT": sum(
            row["online_decision_status"] not in {"PASS", "NUMERICAL_UNRESOLVED"} for row in rows
        ),
    }
    return rows, summary


def rollout_policy(
    starts: np.ndarray,
    backward: Mapping,
    cfg: Mapping,
    evaluator: DownstreamEvaluator,
    policy: str,
) -> tuple[list[dict], dict, dict[float, tuple[float, ...]]]:
    scale = int(backward["scale"])
    terminal_i = int(round(float(cfg["final_thickness_mm"]) * scale))
    trajectory_rows: list[dict] = []
    sequences: dict[float, tuple[float, ...]] = {}
    completion_count = 0
    failures: Counter[str] = Counter()
    selected_continuous_infeasible = 0
    selected_continuous_unresolved = 0
    selected_discrete_rejected = 0
    preservation_violations = 0
    theoretical_calls = 0

    for start_value in starts:
        start_i = int(start_value)
        state_i = start_i
        actions_sequence: list[float] = []
        failed = False
        for step, remaining in enumerate(range(3, 0, -1), start=1):
            candidates = action_candidates(state_i, remaining, backward, cfg)
            online_result = None
            if policy == "RPRA":
                selected = select_action(candidates, cfg, rpra=True)
                decision_status = "PASS" if selected is not None else "NO_PRESERVING_ACTION"
                if selected is not None:
                    selected = {
                        **selected,
                        "discrete_class": selected["class"],
                    }
            elif policy == "ONLINE-REOPT":
                online_result = select_online_action(
                    state_i,
                    remaining,
                    backward,
                    cfg,
                    evaluator,
                    purpose=f"rollout_online_m{remaining}",
                )
                theoretical_calls += int(online_result["solve_call_count"])
                selected = online_result["selected"]
                decision_status = str(online_result["status"])
            else:
                raise ValueError(f"unknown policy: {policy}")

            if selected is None:
                failures[f"{decision_status}_M{remaining}"] += 1
                trajectory_rows.append({
                    "start_state_mm": start_i / scale,
                    "policy": policy,
                    "step": step,
                    "remaining_passes_before": remaining,
                    "state_before_mm": state_i / scale,
                    "selected_action_mm": "",
                    "immediate_deflection_um": "",
                    "selected_action_discrete_class": "",
                    "successor_mm": "",
                    "selected_action_continuous_status": "",
                    "selected_action_continuous_detail": "",
                    "online_continuous_solve_calls": 0 if online_result is None else online_result["solve_call_count"],
                    "step_status": decision_status,
                })
                failed = True
                break

            if policy == "RPRA":
                continuous = audit_selected_downstream(
                    selected,
                    remaining,
                    cfg,
                    evaluator,
                    purpose=f"rollout_rpra_audit_m{remaining}",
                )
            else:
                continuous = DownstreamOutcome(
                    str(selected["continuous_status"]),
                    str(selected["continuous_detail"]),
                    None,
                )

            if continuous.status == "FAIL":
                selected_continuous_infeasible += 1
            elif continuous.status == "NUMERICAL_UNRESOLVED":
                selected_continuous_unresolved += 1
            discrete_class = str(selected["discrete_class"])
            if policy == "ONLINE-REOPT" and discrete_class == "DESTROYING":
                selected_discrete_rejected += 1
            if policy == "RPRA" and discrete_class != "PRESERVING":
                preservation_violations += 1

            successor_i = int(selected["next_state_i"])
            actions_sequence.append(int(selected["action_i"]) / scale)
            step_status = "CONTINUE" if remaining > 1 else "TERMINAL_REACHED"
            if remaining == 1 and successor_i != terminal_i:
                step_status = "TERMINAL_MISMATCH"
                failures[step_status] += 1
                failed = True
            trajectory_rows.append({
                "start_state_mm": start_i / scale,
                "policy": policy,
                "step": step,
                "remaining_passes_before": remaining,
                "state_before_mm": state_i / scale,
                "selected_action_mm": int(selected["action_i"]) / scale,
                "immediate_deflection_um": float(selected["deflection_um"]),
                "selected_action_discrete_class": discrete_class,
                "successor_mm": successor_i / scale,
                "selected_action_continuous_status": continuous.status,
                "selected_action_continuous_detail": continuous.detail,
                "online_continuous_solve_calls": 0 if online_result is None else online_result["solve_call_count"],
                "step_status": step_status,
            })
            state_i = successor_i
            if failed:
                break

        start_mm = start_i / scale
        sequences[start_mm] = tuple(actions_sequence)
        if not failed and state_i == terminal_i and len(actions_sequence) == 3:
            completion_count += 1
        elif not failed:
            failures["INCOMPLETE_SEQUENCE"] += 1
        if len(sequences) % 50 == 0 or len(sequences) == len(starts):
            print(f"ROLLOUT_PROGRESS_{policy}={len(sequences)}/{len(starts)}", flush=True)

    summary = {
        "completion_count": completion_count,
        "completion_rate": completion_count / len(starts),
        "failure_by_stage": dict(sorted(failures.items())),
        "selected_continuous_infeasible_count": selected_continuous_infeasible,
        "selected_continuous_unresolved_count": selected_continuous_unresolved,
        "selected_discrete_rejected_count": selected_discrete_rejected,
        "preservation_invariant_violation_count": preservation_violations,
        "theoretical_online_solve_calls": theoretical_calls,
    }
    return trajectory_rows, summary, sequences


def distribution(values: Iterable[float]) -> dict:
    data = np.asarray(list(values), dtype=float)
    if not data.size:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "q1": None,
            "q3": None,
            "iqr": None,
            "p95": None,
            "max": None,
        }
    q1 = float(np.percentile(data, 25))
    q3 = float(np.percentile(data, 75))
    return {
        "count": int(data.size),
        "mean": float(np.mean(data)),
        "median": float(np.median(data)),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "p95": float(np.percentile(data, 95)),
        "max": float(np.max(data)),
    }


def build_disagreement_rows(first_rows: list[dict]) -> list[dict]:
    """Retain a classified row for every first decision, including agreements."""
    fields = (
        "state_order",
        "state_mm",
        "rpra_action_mm",
        "online_action_mm",
        "rpra_immediate_deflection_um",
        "online_immediate_deflection_um",
        "rpra_successor_mm",
        "online_successor_mm",
        "rpra_selected_continuous_status",
        "online_selected_continuous_status",
        "online_discrete_class",
        "exact_action_agreement",
        "signed_action_delta_um_online_minus_rpra",
        "absolute_action_difference_um",
        "immediate_deflection_delta_um_rpra_minus_online",
        "disagreement_classification",
    )
    return [{key: row[key] for key in fields} for row in first_rows]


def rollout_stage_agreement(trajectory_rows: list[dict]) -> dict[str, dict]:
    grouped: dict[tuple[float, int], dict[str, dict]] = defaultdict(dict)
    for row in trajectory_rows:
        grouped[(float(row["start_state_mm"]), int(row["step"]))][str(row["policy"])] = row
    result: dict[str, dict] = {}
    for step in (1, 2, 3):
        pairs = [policies for (start, row_step), policies in grouped.items() if row_step == step]
        comparable = [pair for pair in pairs if set(pair) == set(POLICIES)]
        agreements = 0
        for pair in comparable:
            rpra = pair["RPRA"]
            online = pair["ONLINE-REOPT"]
            if (
                rpra["selected_action_mm"] != ""
                and online["selected_action_mm"] != ""
                and float(rpra["selected_action_mm"]) == float(online["selected_action_mm"])
            ):
                agreements += 1
        result[f"stage_{step}"] = {
            "paired_row_count": len(comparable),
            "exact_action_agreement_count": agreements,
            "exact_action_agreement_rate": agreements / len(comparable) if comparable else None,
        }
    return result


def validate_cache_determinism(evaluator: DownstreamEvaluator) -> dict:
    mismatches: list[dict] = []
    keys = sorted(evaluator.cache)
    for position, (downstream_passes, successor_i) in enumerate(keys, start=1):
        cached = evaluator.cache[(downstream_passes, successor_i)]
        repeated = evaluator.solve_uncached(successor_i, downstream_passes, "determinism_repeat")
        if exact_json(cached.normalized()) != exact_json(repeated.normalized()):
            mismatches.append({
                "downstream_passes": downstream_passes,
                "successor_mm": successor_i / evaluator.scale,
                "cached": cached.normalized(),
                "repeated": repeated.normalized(),
            })
        if position % 100 == 0 or position == len(keys):
            print(f"DETERMINISM_PROGRESS={position}/{len(keys)}", flush=True)
    return {
        "cache_entry_count": len(keys),
        "repeat_call_count": len(keys),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "status": "PASS" if not mismatches else "FAIL",
    }


def rpra_timed_decision(state_i: int, backward: Mapping, cfg: Mapping) -> dict:
    candidates = action_candidates(state_i, 3, backward, cfg)
    selected = select_action(candidates, cfg, rpra=True)
    return {"status": "PASS" if selected is not None else "NO_PRESERVING_ACTION", "selected": selected, "solve_call_count": 0}


def run_timing(cfg: Mapping, backward: Mapping) -> tuple[list[dict], dict]:
    starts = np.asarray(backward["stages_int"][3], dtype=np.int64)
    scale = int(backward["scale"])
    subset_indices = np.unique(np.round(np.linspace(0, 406, 41)).astype(int))
    if len(starts) != 407 or len(subset_indices) != 41:
        raise RuntimeError("frozen timing subset construction did not produce 41 of 407 states")
    rows: list[dict] = []
    for subset_position, state_index in enumerate(subset_indices):
        state_i = int(starts[int(state_index)])
        for policy in POLICIES:
            for run_index in range(WARMUPS + REPETITIONS):
                is_warmup = run_index < WARMUPS
                if policy == "RPRA":
                    start_ns = time.perf_counter_ns()
                    result = rpra_timed_decision(state_i, backward, cfg)
                    elapsed_ns = time.perf_counter_ns() - start_ns
                else:
                    timing_evaluator = DownstreamEvaluator(cfg, scale, cache_enabled=False)
                    start_ns = time.perf_counter_ns()
                    result = select_online_action(
                        state_i,
                        3,
                        backward,
                        cfg,
                        timing_evaluator,
                        purpose="timing_uncached",
                    )
                    elapsed_ns = time.perf_counter_ns() - start_ns
                    if timing_evaluator.cache:
                        raise RuntimeError("timing evaluator unexpectedly populated a cache")
                selected = result["selected"]
                rows.append({
                    "subset_position": subset_position,
                    "source_state_index_0based": int(state_index),
                    "state_mm": state_i / scale,
                    "policy": policy,
                    "run_kind": "WARMUP" if is_warmup else "MEASURED",
                    "measured_repetition": 0 if is_warmup else run_index,
                    "elapsed_ns": int(elapsed_ns),
                    "elapsed_ms": elapsed_ns / 1e6,
                    "continuous_solve_calls": int(result["solve_call_count"]),
                    "decision_status": result["status"],
                    "selected_action_mm": optional(None if selected is None else int(selected["action_i"]) / scale),
                })
        if (subset_position + 1) % 5 == 0 or subset_position + 1 == len(subset_indices):
            print(f"TIMING_PROGRESS={subset_position + 1}/{len(subset_indices)}", flush=True)

    measured = [row for row in rows if row["run_kind"] == "MEASURED"]
    summary: dict[str, object] = {
        "subset_size": len(subset_indices),
        "subset_indices_0based": subset_indices.tolist(),
        "raw_row_count": len(rows),
        "measured_row_count": len(measured),
        "warmup_runs_per_policy_state": WARMUPS,
        "measured_repetitions_per_policy_state": REPETITIONS,
    }
    for policy in POLICIES:
        values = [float(row["elapsed_ms"]) for row in measured if row["policy"] == policy]
        key = policy.replace("-", "_")
        summary[f"{key}_pooled_measurement_ms"] = distribution(values)
        state_medians = []
        for state_index in subset_indices:
            state_values = [
                float(row["elapsed_ms"])
                for row in measured
                if row["policy"] == policy and int(row["source_state_index_0based"]) == int(state_index)
            ]
            state_medians.append(float(np.median(state_values)))
        summary[f"{key}_state_median_ms"] = distribution(state_medians)
    return rows, summary


def physical_core_count() -> int | None:
    try:
        import psutil

        value = psutil.cpu_count(logical=False)
        return None if value is None else int(value)
    except ImportError:
        pass
    if platform.system() == "Windows":
        try:
            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "(Get-CimInstance Win32_Processor | Measure-Object -Property NumberOfCores -Sum).Sum",
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return int(completed.stdout.strip())
        except (OSError, ValueError, subprocess.SubprocessError):
            return None
    return None


def environment_record(formal_start: str, initial_status: str) -> dict:
    current = {
        "python_version": platform.python_version(),
        "numpy_version": np.__version__,
        "scipy_version": scipy.__version__,
        "os": platform.platform(),
        "cpu": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER") or "unavailable",
        "logical_core_count": os.cpu_count(),
        "physical_core_count": physical_core_count(),
        "timer": "time.perf_counter_ns external full first-decision call boundary",
        "warmup_runs_per_case": WARMUPS,
        "measured_repetitions_per_case": REPETITIONS,
        "timing_claim_boundary": "Descriptive only; no real-time or asymptotic scaling-law claim.",
    }
    frozen = json.loads(FROZEN_E3_ENVIRONMENT.read_text(encoding="utf-8"))
    comparison_keys = (
        "python_version",
        "numpy_version",
        "scipy_version",
        "os",
        "cpu",
        "logical_core_count",
        "physical_core_count",
        "warmup_runs_per_case",
        "measured_repetitions_per_case",
    )
    comparison = {key: current[key] == frozen[key] for key in comparison_keys}
    return {
        **current,
        "formal_run_started_utc": formal_start,
        "baseline_commit": BASELINE_COMMIT,
        "formal_run_commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "git_status_at_formal_start": initial_status,
        "frozen_tag_commit": git("rev-list", "-n", "1", FROZEN_TAG),
        "primary_config_path": str(PRIMARY_CONFIG.relative_to(ROOT)).replace("\\", "/"),
        "primary_config_sha256": sha256(PRIMARY_CONFIG),
        "harness_path": str(Path(__file__).resolve().relative_to(ROOT)).replace("\\", "/"),
        "harness_sha256": sha256(Path(__file__).resolve()),
        "external_goal_path": str(EXTERNAL_GOAL),
        "external_goal_sha256": sha256(EXTERNAL_GOAL) if EXTERNAL_GOAL.exists() else None,
        "design_freeze_path": str(DESIGN_FREEZE),
        "design_freeze_sha256": sha256(DESIGN_FREEZE) if DESIGN_FREEZE.exists() else None,
        "design_freeze_recovery_source_thread": "6a90ec87-948c-83e9-944e-98bbf48766ba",
        "design_freeze_original_attachment_present_locally": DESIGN_FREEZE.exists(),
        "frozen_e3_environment": frozen,
        "environment_match_fields": comparison,
        "environment_matches_frozen_e3": all(comparison.values()),
    }


def verify_rpra_against_frozen_e1(cfg: Mapping, backward: Mapping) -> dict:
    scale = int(backward["scale"])
    frozen_rows = read_csv(FROZEN_E1_FIRST)
    starts = np.asarray(backward["stages_int"][3], dtype=np.int64)
    mismatches = []
    if len(frozen_rows) != len(starts):
        mismatches.append({"row_count": [len(starts), len(frozen_rows)]})
    for state_value, expected in zip(starts, frozen_rows):
        state_i = int(state_value)
        candidates = action_candidates(state_i, 3, backward, cfg)
        selected = select_action(candidates, cfg, rpra=True)
        observed = None if selected is None else {
            "state_mm": state_i / scale,
            "action_mm": int(selected["action_i"]) / scale,
            "successor_mm": int(selected["next_state_i"]) / scale,
            "deflection_um": float(selected["deflection_um"]),
        }
        expected_projection = {
            "state_mm": float(expected["state_mm"]),
            "action_mm": float(expected["rpra_action_mm"]),
            "successor_mm": float(expected["rpra_successor_mm"]),
            "deflection_um": float(expected["rpra_immediate_deflection_um"]),
        }
        if observed is None or any(
            not np.isclose(float(observed[key]), float(expected_projection[key]), rtol=0.0, atol=1e-12)
            for key in expected_projection
        ):
            mismatches.append({"observed": observed, "expected": expected_projection})
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "frozen_row_count": len(frozen_rows),
        "observed_row_count": len(starts),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches[:20],
    }


def forbidden_diff_check() -> dict:
    changed = set(filter(None, git("diff", "--name-only", BASELINE_COMMIT).splitlines()))
    forbidden = sorted(
        path
        for path in changed
        if path.startswith("src/rpra/")
        or path.startswith("configs/")
        or path.startswith("expected/")
        or path.startswith("supplementary/")
    )
    return {"status": "PASS" if not forbidden else "FAIL", "forbidden_paths": forbidden}


def preflight() -> dict:
    cfg = load_configuration(PRIMARY_CONFIG)
    backward = build_backward_set(3, cfg)
    starts = np.asarray(backward["stages_int"][3], dtype=np.int64)
    rpra_match = verify_rpra_against_frozen_e1(cfg, backward)
    mechanism = mechanism_regression(cfg, backward)
    tag_commit = git("rev-list", "-n", "1", FROZEN_TAG)
    baseline_is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BASELINE_COMMIT, "HEAD"],
        cwd=ROOT,
        check=False,
    ).returncode == 0
    forbidden = forbidden_diff_check()
    checks = {
        "baseline_is_ancestor": baseline_is_ancestor,
        "frozen_tag_points_to_baseline": tag_commit == BASELINE_COMMIT,
        "recoverable_start_count_407": len(starts) == 407,
        "rpra_matches_frozen_e1": rpra_match["status"] == "PASS",
        "mechanism_4p442_unchanged": bool(mechanism["MECHANISM_4P442_UNCHANGED"]),
        "forbidden_diff_absent": forbidden["status"] == "PASS",
        "multistart_frozen_7": int(cfg["optimizer_multistart"]) == 7,
        "tie_tolerance_frozen_1e_7_um": float(cfg["decision_tolerance_um"]) == 1e-7,
        "grid_frozen_0p001_mm": float(cfg["state_grid_mm"]) == 0.001,
        "design_freeze_present": DESIGN_FREEZE.exists(),
    }
    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "rpra_match": rpra_match,
        "mechanism": mechanism,
        "forbidden_diff": forbidden,
    }
    print(exact_json(result), flush=True)
    return result


def assert_write_once() -> None:
    existing = [name for name in RAW_OUTPUT_NAMES if (OUTPUT_DIR / name).exists()]
    if existing:
        raise FileExistsError(
            "formal B1 raw outputs already exist and will not be overwritten: " + ", ".join(existing)
        )


def scientific_classification(summary: Mapping) -> str:
    if int(summary["RPRA_SELECTED_CONTINUOUS_INFEASIBLE_COUNT"]) > 0:
        return "B1_SCIENTIFIC_CONFLICT"
    if int(summary["NUMERICAL_UNRESOLVED_COUNT"]) > 0:
        return "B1_NUMERICALLY_UNRESOLVED"
    starts = int(summary["RECOVERABLE_START_STATES"])
    both_complete = (
        int(summary["RPRA_COMPLETION_COUNT"]) == starts
        and int(summary["ONLINE_REOPT_COMPLETION_COUNT"]) == starts
    )
    exact_everywhere = (
        int(summary["EXACT_FIRST_ACTION_AGREEMENT_COUNT"]) == int(summary["FIRST_DECISION_ROWS"])
        and int(summary["FULL_SEQUENCE_AGREEMENT_COUNT"]) == starts
    )
    if both_complete and exact_everywhere:
        return "B1_STRONG_SUPPORT"
    if both_complete:
        return "B1_BOUNDED_SUPPORT"
    return "B1_NO_ADDED_VALUE"


def run_formal() -> None:
    assert_write_once()
    preflight_result = preflight()
    if preflight_result["status"] != "PASS":
        raise SystemExit("B1_PREFLIGHT_FAIL")
    initial_status = git("status", "--short")
    formal_start = datetime.now(timezone.utc).isoformat()
    cfg = load_configuration(PRIMARY_CONFIG)
    backward = build_backward_set(3, cfg)
    starts = np.asarray(backward["stages_int"][3], dtype=np.int64)
    evaluator = DownstreamEvaluator(cfg, int(backward["scale"]), cache_enabled=True)

    first_rows, first_summary = first_action_audit(cfg, backward, evaluator)
    print(f"FIRST_DECISION_PROGRESS={len(first_rows)}/407", flush=True)
    rpra_rows, rpra_summary, rpra_sequences = rollout_policy(
        starts, backward, cfg, evaluator, "RPRA"
    )
    online_rows, online_summary, online_sequences = rollout_policy(
        starts, backward, cfg, evaluator, "ONLINE-REOPT"
    )
    trajectory_rows = rpra_rows + online_rows
    disagreement_rows = build_disagreement_rows(first_rows)
    stage_agreement = rollout_stage_agreement(trajectory_rows)
    solver_audit_rows = continuous_solver_audit_rows(evaluator)

    actual_solver_calls_before_determinism = evaluator.actual_solver_calls
    unique_unresolved_before_determinism = {
        (
            int(event["downstream_passes"]),
            float(event["successor_mm"]),
            str(event["detail"]),
        )
        for event in evaluator.numerical_unresolved_events
    }
    cache_determinism = validate_cache_determinism(evaluator)
    timing_rows, timing_summary = run_timing(cfg, backward)
    mechanism = mechanism_regression(cfg, backward)

    full_sequence_agreement_count = sum(
        rpra_sequences[state] == online_sequences[state] for state in rpra_sequences
    )
    action_differences = [
        float(row["absolute_action_difference_um"])
        for row in first_rows
        if row["absolute_action_difference_um"] != ""
    ]
    deflection_deltas = [
        float(row["immediate_deflection_delta_um_rpra_minus_online"])
        for row in first_rows
        if row["immediate_deflection_delta_um_rpra_minus_online"] != ""
    ]
    differing_action_differences = [
        float(row["absolute_action_difference_um"])
        for row in first_rows
        if row["absolute_action_difference_um"] != "" and not bool(row["exact_action_agreement"])
    ]
    differing_deflection_deltas = [
        float(row["immediate_deflection_delta_um_rpra_minus_online"])
        for row in first_rows
        if row["immediate_deflection_delta_um_rpra_minus_online"] != "" and not bool(row["exact_action_agreement"])
    ]

    timing_unresolved_rows = sum(
        row["decision_status"] == "NUMERICAL_UNRESOLVED" for row in timing_rows
    )
    unresolved_count = (
        len(unique_unresolved_before_determinism)
        + int(cache_determinism["mismatch_count"])
        + int(timing_unresolved_rows)
    )
    summary = {
        **first_summary,
        "BASELINE_COMMIT": BASELINE_COMMIT,
        "FORMAL_RUN_COMMIT": git("rev-parse", "HEAD"),
        "RECOVERABLE_START_STATES": len(starts),
        "RPRA_COMPLETION_COUNT": rpra_summary["completion_count"],
        "RPRA_COMPLETION_RATE": rpra_summary["completion_rate"],
        "ONLINE_REOPT_COMPLETION_COUNT": online_summary["completion_count"],
        "ONLINE_REOPT_COMPLETION_RATE": online_summary["completion_rate"],
        "RPRA_FAILURE_BY_STAGE": rpra_summary["failure_by_stage"],
        "ONLINE_REOPT_FAILURE_BY_STAGE": online_summary["failure_by_stage"],
        "RPRA_PRESERVATION_INVARIANT_VIOLATION_COUNT": rpra_summary["preservation_invariant_violation_count"],
        "RPRA_SELECTED_CONTINUOUS_INFEASIBLE_COUNT": rpra_summary["selected_continuous_infeasible_count"],
        "RPRA_SELECTED_CONTINUOUS_UNRESOLVED_COUNT": rpra_summary["selected_continuous_unresolved_count"],
        "ONLINE_SELECTED_DISCRETE_REJECTED_COUNT": online_summary["selected_discrete_rejected_count"],
        "ONLINE_SELECTED_INSIDE_DISCRETE_PRESERVING_ENVELOPE_COUNT": sum(
            row["selected_action_mm"] != "" and row["selected_action_discrete_class"] == "PRESERVING"
            for row in online_rows
        ),
        "NUMERICAL_UNRESOLVED_COUNT": unresolved_count,
        "FULL_SEQUENCE_AGREEMENT_COUNT": full_sequence_agreement_count,
        "TRAJECTORY_ACTION_AGREEMENT_BY_STAGE": stage_agreement,
        "ACTION_DIFFERENCE_UM_ALL_FIRST_DECISIONS": distribution(action_differences),
        "ACTION_DIFFERENCE_UM_DIFFERING_FIRST_DECISIONS": distribution(differing_action_differences),
        "IMMEDIATE_DEFLECTION_DELTA_UM_ALL_FIRST_DECISIONS": distribution(deflection_deltas),
        "IMMEDIATE_DEFLECTION_DELTA_UM_DIFFERING_FIRST_DECISIONS": distribution(differing_deflection_deltas),
        "ONLINE_REOPT_TOTAL_SOLVE_CALLS_FULL_ROLLOUT": online_summary["theoretical_online_solve_calls"],
        "OUTCOME_COMPUTATION_ACTUAL_SOLVER_CALLS_BEFORE_DETERMINISM": actual_solver_calls_before_determinism,
        "OUTCOME_COMPUTATION_ACTUAL_SOLVER_CALLS_INCLUDING_DETERMINISM": evaluator.actual_solver_calls,
        "OUTCOME_COMPUTATION_ACTUAL_CALLS_BY_PURPOSE": dict(sorted(evaluator.actual_calls_by_purpose.items())),
        "OUTCOME_COMPUTATION_CACHE_HITS_BY_PURPOSE": dict(sorted(evaluator.cache_hits_by_purpose.items())),
        "CACHE_DETERMINISM": cache_determinism,
        "UNIQUE_NUMERICAL_UNRESOLVED_SOLVER_KEYS_BEFORE_DETERMINISM": len(unique_unresolved_before_determinism),
        "TIMING_NUMERICAL_UNRESOLVED_ROW_COUNT": timing_unresolved_rows,
        "MECHANISM_REGRESSION": mechanism,
        "TIMING": timing_summary,
        "ROW_COUNTS": {
            "first_action": len(first_rows),
            "rollout_trajectory": len(trajectory_rows),
            "disagreement_audit": len(disagreement_rows),
            "timing_raw": len(timing_rows),
            "continuous_solver_audit": len(solver_audit_rows),
        },
        "REGRESSION_GATES": {
            "pytest": "PENDING",
            "quick_reproduction": "PENDING",
            "full_reproduction": "PENDING",
            "git_diff_check": "PENDING",
        },
    }
    summary["B1_CLASSIFICATION"] = scientific_classification(summary)
    environment = environment_record(formal_start, initial_status)

    write_csv(OUTPUT_DIR / "B1_first_action_comparator.csv", first_rows)
    write_csv(OUTPUT_DIR / "B1_rollout_trajectories.csv", trajectory_rows)
    write_csv(OUTPUT_DIR / "B1_disagreement_audit.csv", disagreement_rows)
    write_csv(OUTPUT_DIR / "B1_timing_raw.csv", timing_rows)
    write_csv(OUTPUT_DIR / "B1_continuous_solver_audit.csv", solver_audit_rows)
    write_json(OUTPUT_DIR / "B1_summary.json", summary)
    write_json(OUTPUT_DIR / "B1_environment.json", environment)
    build_report(
        summary,
        environment,
        pytest_result="PENDING",
        quick_result="PENDING",
        full_result="PENDING",
        diff_check_result="PENDING",
    )
    print(f"B1_FORMAL_RUN={summary['B1_CLASSIFICATION']}", flush=True)


def fmt(value: object) -> str:
    if value is None:
        return "NA"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def build_report(
    summary: Mapping,
    environment: Mapping,
    *,
    pytest_result: str,
    quick_result: str,
    full_result: str,
    diff_check_result: str,
) -> None:
    all_gates_pass = all(
        value == "PASS"
        for value in (pytest_result, quick_result, full_result, diff_check_result)
    )
    scientific = str(summary["B1_CLASSIFICATION"])
    if scientific == "B1_SCIENTIFIC_CONFLICT":
        task_status = "B1_SCIENTIFIC_CONFLICT"
        classification = scientific
    elif scientific == "B1_NUMERICALLY_UNRESOLVED":
        task_status = "B1_NUMERICALLY_UNRESOLVED"
        classification = scientific
    elif not all_gates_pass:
        task_status = "PENDING" if "PENDING" in {
            pytest_result, quick_result, full_result, diff_check_result
        } else "BLOCKED"
        classification = scientific
    else:
        task_status = "COMPLETE"
        classification = scientific

    remaining_blockers = []
    if int(summary["RPRA_SELECTED_CONTINUOUS_INFEASIBLE_COUNT"]) > 0:
        remaining_blockers.append("RPRA_SELECTED_CONTINUOUS_INFEASIBLE")
    if int(summary["NUMERICAL_UNRESOLVED_COUNT"]) > 0:
        remaining_blockers.append("NUMERICAL_UNRESOLVED")
    for name, value in (
        ("PYTEST", pytest_result),
        ("QUICK_REPRODUCTION", quick_result),
        ("FULL_REPRODUCTION", full_result),
        ("GIT_DIFF_CHECK", diff_check_result),
    ):
        if value != "PASS":
            remaining_blockers.append(f"{name}_{value}")

    action_stats = summary["ACTION_DIFFERENCE_UM_ALL_FIRST_DECISIONS"]
    deflection_stats = summary["IMMEDIATE_DEFLECTION_DELTA_UM_ALL_FIRST_DECISIONS"]
    timing = summary["TIMING"]
    rpra_timing = timing["RPRA_pooled_measurement_ms"]
    online_timing = timing["ONLINE_REOPT_pooled_measurement_ms"]
    working_commit = git("rev-parse", "HEAD")
    public_modified = git("rev-list", "-n", "1", FROZEN_TAG) != BASELINE_COMMIT
    environment_match = bool(environment["environment_matches_frozen_e3"])
    exact_agreement = f"{summary['EXACT_FIRST_ACTION_AGREEMENT_COUNT']}/{summary['FIRST_DECISION_ROWS']}"
    full_agreement = f"{summary['FULL_SEQUENCE_AGREEMENT_COUNT']}/{summary['RECOVERABLE_START_STATES']}"

    final_block = f"""TASK_STATUS={task_status}
BASELINE_COMMIT={BASELINE_COMMIT}
WORKING_COMMIT={working_commit}
B1_CLASSIFICATION={classification}
FIRST_DECISION_ROWS={summary['FIRST_DECISION_ROWS']}
RPRA_COMPLETION={summary['RPRA_COMPLETION_COUNT']}/{summary['RECOVERABLE_START_STATES']}
ONLINE_REOPT_COMPLETION={summary['ONLINE_REOPT_COMPLETION_COUNT']}/{summary['RECOVERABLE_START_STATES']}
EXACT_FIRST_ACTION_AGREEMENT={exact_agreement}
RPRA_SELECTED_CONTINUOUS_INFEASIBLE_COUNT={summary['RPRA_SELECTED_CONTINUOUS_INFEASIBLE_COUNT']}
ONLINE_SELECTED_DISCRETE_REJECTED_COUNT={summary['ONLINE_SELECTED_DISCRETE_REJECTED_COUNT']}
NUMERICAL_UNRESOLVED_COUNT={summary['NUMERICAL_UNRESOLVED_COUNT']}
ONLINE_REOPT_TOTAL_SOLVE_CALLS_FIRST_DECISION_DOMAIN={summary['ONLINE_REOPT_TOTAL_SOLVE_CALLS_FIRST_DECISION_DOMAIN']}
FULL_SEQUENCE_AGREEMENT={full_agreement}
ACTION_DIFFERENCE_MEDIAN_UM={fmt(action_stats['median'])}
ACTION_DIFFERENCE_P95_UM={fmt(action_stats['p95'])}
IMMEDIATE_DEFLECTION_DELTA_MEDIAN_UM={fmt(deflection_stats['median'])}
TIMING_SUBSET_SIZE={timing['subset_size']}
RPRA_DECISION_MEDIAN_MS={fmt(rpra_timing['median'])}
ONLINE_REOPT_DECISION_MEDIAN_MS={fmt(online_timing['median'])}
ENVIRONMENT_MATCHES_FROZEN_E3={'PASS' if environment_match else 'FAIL'}
PYTEST={pytest_result}
QUICK_REPRODUCTION={quick_result}
FULL_REPRODUCTION={full_result}
GIT_DIFF_CHECK={diff_check_result}
PUBLIC_V1_1_0_MODIFIED={fmt(public_modified)}
REMAINING_BLOCKERS={';'.join(remaining_blockers) if remaining_blockers else 'NONE'}"""

    report = f"""# RINENG B1 ONLINE-REOPT Comparator Formal Audit

## Scope and frozen provenance

- Scientific baseline and frozen public tag target: `{BASELINE_COMMIT}` / `{FROZEN_TAG}`.
- Primary configuration: `configs/3pass_100um.yaml`.
- The harness is isolated under `scripts/`; `src/rpra/`, frozen expected results,
  the manuscript, and public release metadata were not edited.
- Design freeze SHA-256: `{environment.get('design_freeze_sha256')}`.
- External Codex Goal SHA-256: `{environment.get('external_goal_sha256')}`.
- The explicit user Goal and continuation request authorize this isolated B1
  execution; the design document's earlier `EXPERIMENT_RUN_AUTHORIZED=NO`
  records its pre-execution state rather than overriding that user request.

## Comparator definition

RPRA uses the frozen E1 preserving-action selector. ONLINE-REOPT uses the same
0.001-mm current-action grid, local feasibility mask, immediate Morelli
deflection objective, `1e-7` µm tie band, and smaller-removal tie rule. The only
difference is downstream admissibility: ONLINE-REOPT calls the frozen
`full_reoptimize(successor, m-1, cfg, multistart=7)` for `m>1`; `m=1` uses exact
terminal equality. Candidates are ordered by `(immediate_deflection,
radial_removal)` and search stops after the first PASS tie band is exhausted.

Outcome computation used an exact `(downstream pass count, integer successor)`
memo. The uncached solver is deterministic by construction and every memoized
entry was repeated uncached; determinism status is
`{summary['CACHE_DETERMINISM']['status']}` with
`{summary['CACHE_DETERMINISM']['mismatch_count']}` mismatches. The primary
online compute metric counts the uncached calls that the specified online
candidate search would require, independent of memo hits.

## Formal-domain results

- Recoverable starts: {summary['RECOVERABLE_START_STATES']}.
- Exact first actions: {exact_agreement}.
- RPRA completion: {summary['RPRA_COMPLETION_COUNT']}/{summary['RECOVERABLE_START_STATES']}.
- ONLINE-REOPT completion: {summary['ONLINE_REOPT_COMPLETION_COUNT']}/{summary['RECOVERABLE_START_STATES']}.
- Full action-sequence agreement: {full_agreement}.
- RPRA-selected continuous-infeasible actions across rollouts:
  {summary['RPRA_SELECTED_CONTINUOUS_INFEASIBLE_COUNT']}.
- ONLINE-selected actions rejected by discrete downstream membership across
  rollouts: {summary['ONLINE_SELECTED_DISCRETE_REJECTED_COUNT']}.
- Numerical unresolved count: {summary['NUMERICAL_UNRESOLVED_COUNT']}.
- First-decision online solve calls over all 407 starts:
  {summary['ONLINE_REOPT_TOTAL_SOLVE_CALLS_FIRST_DECISION_DOMAIN']}.
- Frozen 4.442-mm mechanism unchanged:
  {summary['MECHANISM_REGRESSION']['MECHANISM_4P442_UNCHANGED']}.

Action differences are absolute micrometres over all matched first decisions.
Immediate-deflection deltas follow the frozen definition, RPRA minus
ONLINE-REOPT, over the same domain.

## Timing

The subset is exactly `unique(round(linspace(0, 406, 41)))` over ascending
recoverable starts. Each policy/state has one warm-up and five measured full
first-decision calls. ONLINE-REOPT caching is disabled. Reported medians pool
the 205 measured calls per policy; all warm-up and measured rows are retained.

- RPRA pooled median/IQR/P95: {fmt(rpra_timing['median'])} /
  {fmt(rpra_timing['iqr'])} / {fmt(rpra_timing['p95'])} ms.
- ONLINE-REOPT pooled median/IQR/P95: {fmt(online_timing['median'])} /
  {fmt(online_timing['iqr'])} / {fmt(online_timing['p95'])} ms.
- Environment matches frozen E3: {'PASS' if environment_match else 'FAIL'}.

## Regression and final status

```text
{final_block}
```

## Created audit files

- `B1_first_action_comparator.csv`
- `B1_rollout_trajectories.csv`
- `B1_summary.json`
- `B1_disagreement_audit.csv`
- `B1_timing_raw.csv`
- `B1_environment.json`
- `B1_continuous_solver_audit.csv`
- `B1_FORMAL_AUDIT.md`
- `../../scripts/run_b1_online_reopt_comparator.py`
"""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "B1_FORMAL_AUDIT.md").write_text(report, encoding="utf-8")


def finalize(args: argparse.Namespace) -> None:
    summary_path = OUTPUT_DIR / "B1_summary.json"
    environment_path = OUTPUT_DIR / "B1_environment.json"
    if not summary_path.exists() or not environment_path.exists():
        raise FileNotFoundError("formal B1 outputs do not exist; cannot finalize")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    environment = json.loads(environment_path.read_text(encoding="utf-8"))
    summary["REGRESSION_GATES"] = {
        "pytest": args.pytest_result,
        "quick_reproduction": args.quick_result,
        "full_reproduction": args.full_result,
        "git_diff_check": args.diff_check_result,
    }
    write_json(summary_path, summary)
    build_report(
        summary,
        environment,
        pytest_result=args.pytest_result,
        quick_result=args.quick_result,
        full_result=args.full_result,
        diff_check_result=args.diff_check_result,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--finalize-only", action="store_true")
    parser.add_argument("--pytest-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    parser.add_argument("--quick-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    parser.add_argument("--full-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    parser.add_argument("--diff-check-result", choices=("PASS", "FAIL", "PENDING"), default="PENDING")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.preflight:
        result = preflight()
        raise SystemExit(0 if result["status"] == "PASS" else 1)
    if args.finalize_only:
        finalize(args)
        return
    run_formal()


if __name__ == "__main__":
    main()

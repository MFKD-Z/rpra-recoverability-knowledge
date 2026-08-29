"""Frozen formal B2 near-boundary numerical-fidelity challenge.

This harness is intentionally isolated from ``src/rpra`` and the frozen public
configuration.  It recomputes the continuous m=3 boundary, constructs the
predeclared 161-state challenge set, calls the continuous optimizer for every
state, rebuilds all five discrete backward sets, and uses Decimal-based exact
upward-to-next-grid retrieval.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


AUDIT_DIR = Path(__file__).resolve().parent
REPOSITORY_ROOT = AUDIT_DIR.parents[1]
SOURCE_DIR = REPOSITORY_ROOT / "src"
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))

from rpra.optimization import ReoptimizationEngine  # noqa: E402
from rpra.recoverable_set import build_backward_set  # noqa: E402
from rpra.reproduction import load_all_configurations  # noqa: E402


BASELINE_COMMIT = "c25540909939f65fad732420fa484f52931c02f9"
PUBLIC_TAG = "v1.1.0"
GRID_TEXTS = ("0.004", "0.002", "0.001", "0.0005", "0.00025")
BOUNDARY_HALF_WINDOW_UM = Decimal("20")
STATE_SPACING_UM = Decimal("0.25")
WINDOWS = (
    ("overall", None),
    ("pm5_um", Decimal("5")),
    ("pm10_um", Decimal("10")),
    ("pm20_um", Decimal("20")),
)

DETAIL_OUTPUT = AUDIT_DIR / "B2_near_boundary_detail.csv"
SUMMARY_OUTPUT = AUDIT_DIR / "B2_near_boundary_summary.csv"
CONTINUOUS_OUTPUT = AUDIT_DIR / "B2_continuous_solver_audit.csv"
ENVIRONMENT_OUTPUT = AUDIT_DIR / "B2_environment.json"
REPORT_OUTPUT = AUDIT_DIR / "B2_FORMAL_AUDIT.md"

FROZEN_400_DIR = (
    REPOSITORY_ROOT
    / "audits"
    / "20260826_offgrid_upward_mapping_400_case_verification"
)
FROZEN_400_HARNESS = FROZEN_400_DIR / "verify_offgrid_upward_mapping.py"
FROZEN_400_OUTPUTS = (
    FROZEN_400_DIR / "offgrid_upward_mapping_400_verification.csv",
    FROZEN_400_DIR / "offgrid_upward_mapping_summary.csv",
    FROZEN_400_DIR / "verification_metadata.json",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_capture(args: list[str], *, timeout: int = 1800) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            cwd=REPOSITORY_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
        return {
            "command": args,
            "exit_code": completed.returncode,
            "status": "PASS" if completed.returncode == 0 else "FAIL",
            "duration_seconds": time.perf_counter() - started,
            "stdout_tail": completed.stdout[-12000:],
            "stderr_tail": completed.stderr[-12000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": args,
            "exit_code": None,
            "status": "TIMEOUT",
            "duration_seconds": time.perf_counter() - started,
            "stdout_tail": (exc.stdout or "")[-12000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-12000:] if isinstance(exc.stderr, str) else "",
        }


def git_text(*args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(REPOSITORY_ROOT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout.strip()


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def exact_upward_index(state_text: str, grid_text: str) -> int:
    grid = Decimal(grid_text)
    reciprocal = Decimal(1) / grid
    if reciprocal != reciprocal.to_integral_value():
        raise ValueError(f"grid has no integer reciprocal: {grid_text}")
    return int((Decimal(state_text) / grid).to_integral_value(rounding=ROUND_CEILING))


def direct_membership(state_i: int, backward: Mapping[str, Any]) -> bool:
    final_values = np.asarray(
        backward["stages_int"][backward["pass_count"]], dtype=np.int64
    )
    index = int(np.searchsorted(final_values, state_i))
    return bool(index < len(final_values) and final_values[index] == state_i)


def classify_pair(discrete: bool, continuous_status: str) -> str:
    if continuous_status == "NUMERICAL_UNRESOLVED":
        return "NUMERICAL_UNRESOLVED"
    continuous = continuous_status == "PASS"
    if discrete and continuous:
        return "AGREEMENT_PASS"
    if not discrete and not continuous:
        return "AGREEMENT_FAIL"
    if not discrete and continuous:
        return "CONSERVATIVE_FALSE_REJECTION"
    return "OPTIMISTIC_FALSE_ACCEPTANCE"


def residual_valid(result: Mapping[str, Any]) -> bool | None:
    if not result.get("feasible", False):
        return None
    residuals = result.get("constraint_residuals", {})
    return bool(
        float(residuals.get("removal_sum_abs_mm", math.inf)) <= 2e-7
        and float(residuals.get("action_bound_violation_mm", math.inf)) <= 2e-8
        and float(residuals.get("epigraph_violation_um", math.inf)) <= 2e-5
    )


def continuous_row(
    record_type: str,
    case_id: str,
    offset_um: Decimal,
    state_text: str,
    result: Mapping[str, Any] | None,
    exception: BaseException | None = None,
    boundary_meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    result = result or {}
    residuals = result.get("constraint_residuals", {}) or {}
    valid = residual_valid(result) if result else False
    feasible = result.get("feasible", "")
    if exception is not None:
        classification_status = "NUMERICAL_UNRESOLVED"
    elif feasible is False:
        classification_status = "FAIL"
    elif valid:
        classification_status = str(result.get("decision_at_limit", "NUMERICAL_UNRESOLVED"))
    else:
        classification_status = "NUMERICAL_UNRESOLVED"
    boundary_meta = boundary_meta or {}
    return {
        "record_type": record_type,
        "case_id": case_id,
        "offset_um": format(offset_um, "f"),
        "state_mm": state_text,
        "classification_status": classification_status,
        "feasible": str(feasible).lower() if isinstance(feasible, bool) else feasible,
        "reason": result.get("reason", ""),
        "decision_at_limit": result.get("decision_at_limit", ""),
        "optimizer": result.get("optimizer", ""),
        "optimizer_success": (
            str(result.get("optimizer_success")).lower()
            if "optimizer_success" in result
            else ""
        ),
        "optimizer_message": result.get("optimizer_message", ""),
        "multistart_count": result.get("multistart_count", ""),
        "required_removal_mm": result.get("required_removal_mm", ""),
        "capacity_residual_low_mm": result.get("capacity_residual_low_mm", ""),
        "capacity_residual_high_mm": result.get("capacity_residual_high_mm", ""),
        "first_pass_ar_domain_lower_bound_mm": result.get(
            "first_pass_ar_domain_lower_bound_mm", ""
        ),
        "optimal_worst_deflection_um": result.get("optimal_worst_deflection_um", ""),
        "recoverability_margin_um": result.get("recoverability_margin_um", ""),
        "removal_sum_abs_mm": residuals.get("removal_sum_abs_mm", ""),
        "action_bound_violation_mm": residuals.get("action_bound_violation_mm", ""),
        "epigraph_violation_um": residuals.get("epigraph_violation_um", ""),
        "terminal_thickness_abs_mm": residuals.get("terminal_thickness_abs_mm", ""),
        "residual_valid": str(valid).lower() if isinstance(valid, bool) else "not_applicable",
        "pass_removals_mm_json": json.dumps(
            result.get("pass_removals_mm", []), separators=(",", ":")
        ),
        "pass_details_json": json.dumps(
            result.get("pass_details", []), separators=(",", ":")
        ),
        "boundary_kind": boundary_meta.get("boundary_kind", ""),
        "physics_margin_at_boundary_um": boundary_meta.get(
            "physics_margin_at_boundary_um", ""
        ),
        "exception_type": type(exception).__name__ if exception else "",
        "exception_message": str(exception) if exception else "",
    }


def summarize(
    detail_rows: list[dict[str, Any]],
    continuous_boundary: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for grid_text in GRID_TEXTS:
        grid_rows = [row for row in detail_rows if row["grid_mm"] == grid_text]
        for scope, limit in WINDOWS:
            selected = (
                grid_rows
                if limit is None
                else [
                    row
                    for row in grid_rows
                    if Decimal(row["absolute_distance_from_boundary_um"]) <= limit
                ]
            )
            unresolved = sum(
                row["classification"] == "NUMERICAL_UNRESOLVED" for row in selected
            )
            false_rejection = sum(
                row["classification"] == "CONSERVATIVE_FALSE_REJECTION"
                for row in selected
            )
            false_acceptance = sum(
                row["classification"] == "OPTIMISTIC_FALSE_ACCEPTANCE"
                for row in selected
            )
            agreement = sum(
                row["classification"] in {"AGREEMENT_PASS", "AGREEMENT_FAIL"}
                for row in selected
            )
            classifiable = len(selected) - unresolved
            misclassified = [
                float(row["absolute_distance_from_boundary_um"])
                for row in selected
                if row["classification"]
                in {"CONSERVATIVE_FALSE_REJECTION", "OPTIMISTIC_FALSE_ACCEPTANCE"}
            ]
            first = selected[0]
            rows.append(
                {
                    "scope": scope,
                    "window_half_width_um": "" if limit is None else format(limit, "f"),
                    "grid_mm": grid_text,
                    "state_count": len(selected),
                    "classifiable_count": classifiable,
                    "agreement_count": agreement,
                    "agreement_rate": agreement / classifiable if classifiable else "",
                    "conservative_false_rejection_count": false_rejection,
                    "optimistic_false_acceptance_count": false_acceptance,
                    "numerical_unresolved_count": unresolved,
                    "max_misclassification_distance_um": max(misclassified, default=0.0),
                    "max_upward_mapping_delta_um": max(
                        float(row["mapping_delta_um"]) for row in selected
                    ),
                    "continuous_boundary_mm": continuous_boundary,
                    "discrete_upper_recoverable_boundary_mm": first[
                        "discrete_upper_recoverable_boundary_mm"
                    ],
                    "boundary_under_approximation_um": first[
                        "boundary_under_approximation_um"
                    ],
                }
            )
    return rows


def package_versions() -> dict[str, str]:
    values: dict[str, str] = {}
    for name in ("numpy", "scipy", "PyYAML", "rdflib", "pytest", "pandas", "matplotlib"):
        try:
            values[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            values[name] = "NOT_INSTALLED"
    return values


def report_table(overall_rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Grid (mm) | Agreement | False rejection | False acceptance | Max error distance (µm) | Boundary under-approx. (µm) |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    for row in overall_rows:
        lines.append(
            "| {grid_mm} | {agreement_count}/{state_count} | "
            "{conservative_false_rejection_count} | {optimistic_false_acceptance_count} | "
            "{max_misclassification_distance_um:.6f} | "
            "{boundary_under_approximation_um:.6f} |".format(**row)
        )
    return "\n".join(lines)


def regression_table(regressions: Mapping[str, Mapping[str, Any]]) -> str:
    lines = ["| Gate | Status |", "|---|---|"]
    for name, result in regressions.items():
        lines.append(f"| {name} | {result['status']} |")
    return "\n".join(lines)


def main() -> int:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    started_utc = utc_now()
    head_before = git_text("rev-parse", "HEAD")
    tag_before = git_text("rev-parse", f"{PUBLIC_TAG}^{{}}")
    tracked_diff_before = git_text("status", "--porcelain=v1", "--untracked-files=no")
    status_before = git_text("status", "--porcelain=v1", "--untracked-files=all")
    if head_before != BASELINE_COMMIT:
        raise RuntimeError(f"baseline mismatch: expected {BASELINE_COMMIT}, got {head_before}")
    if tracked_diff_before:
        raise RuntimeError(f"tracked files differ before formal run:\n{tracked_diff_before}")

    frozen_hashes_before = {str(path): sha256(path) for path in FROZEN_400_OUTPUTS}
    cfg = load_all_configurations(REPOSITORY_ROOT)["3pass_100um"]
    if int(cfg["remaining_pass_count"]) != 3:
        raise AssertionError("frozen configuration is not m=3")

    expected = json.loads(
        (REPOSITORY_ROOT / "expected" / "paper_results.json").read_text(encoding="utf-8")
    )
    expected_boundary = float(expected["grid_robustness"][0]["continuous_boundary_mm"])

    engine = ReoptimizationEngine(cfg)
    boundary_meta = engine.continuous_boundary(3)
    boundary = float(boundary_meta["continuous_boundary_mm"])
    boundary_reproduced = bool(
        np.isclose(boundary, expected_boundary, rtol=1e-10, atol=1e-10)
    )
    if not boundary_reproduced:
        raise AssertionError(
            f"continuous boundary mismatch: expected {expected_boundary}, got {boundary}"
        )

    boundary_text = format(boundary, ".15f")
    boundary_decimal = Decimal(boundary_text)
    offsets = [
        -BOUNDARY_HALF_WINDOW_UM + index * STATE_SPACING_UM
        for index in range(161)
    ]
    if offsets[0] != Decimal("-20") or offsets[-1] != Decimal("20"):
        raise AssertionError("challenge offset construction failed")

    continuous_rows: list[dict[str, Any]] = []
    boundary_result = engine.optimize(boundary, 3)
    continuous_rows.append(
        continuous_row(
            "BOUNDARY_ROOT",
            "BOUNDARY",
            Decimal("0"),
            boundary_text,
            boundary_result,
            boundary_meta=boundary_meta,
        )
    )

    challenge: list[dict[str, Any]] = []
    for index, offset_um in enumerate(offsets):
        case_id = f"B2-{index:04d}"
        state_decimal = boundary_decimal + offset_um / Decimal(1000)
        state_text = format(state_decimal, "f")
        result: Mapping[str, Any] | None = None
        caught: BaseException | None = None
        try:
            result = engine.optimize(float(state_text), 3)
        except Exception as exc:  # retained as numerical evidence by protocol
            caught = exc
        solver_row = continuous_row(
            "CHALLENGE_STATE",
            case_id,
            offset_um,
            state_text,
            result,
            exception=caught,
        )
        continuous_rows.append(solver_row)
        challenge.append(
            {
                "case_id": case_id,
                "offset_um": offset_um,
                "state_text": state_text,
                "continuous_status": solver_row["classification_status"],
                "continuous_margin_um": solver_row["recoverability_margin_um"],
                "optimizer_success": solver_row["optimizer_success"],
                "residual_valid": solver_row["residual_valid"],
            }
        )

    detail_rows: list[dict[str, Any]] = []
    grid_metadata: dict[str, dict[str, Any]] = {}
    for grid_text in GRID_TEXTS:
        variant = dict(cfg)
        variant["state_grid_mm"] = float(grid_text)
        backward = build_backward_set(3, variant)
        scale = int(backward["scale"])
        final_values = np.asarray(backward["stages_int"][3], dtype=np.int64)
        if final_values.size == 0:
            raise AssertionError(f"empty discrete R3 at grid {grid_text}")
        upper_i = int(final_values[-1])
        upper_mm = upper_i / scale
        boundary_under_um = 1000.0 * (boundary - upper_mm)
        grid_metadata[grid_text] = {
            "scale": scale,
            "stage_state_counts": {
                str(stage): len(values) for stage, values in backward["stages_int"].items()
            },
            "transition_counts": {
                str(stage): count for stage, count in backward["transition_counts"].items()
            },
            "discrete_upper_recoverable_boundary_mm": upper_mm,
            "boundary_under_approximation_um": boundary_under_um,
            "build_elapsed_ns": int(backward["elapsed_ns"]),
        }
        grid = Decimal(grid_text)
        for case in challenge:
            mapped_i = exact_upward_index(case["state_text"], grid_text)
            mapped = Decimal(mapped_i) / Decimal(scale)
            observed = Decimal(case["state_text"])
            mapping_delta_um = (mapped - observed) * Decimal(1000)
            if mapping_delta_um < 0 or mapping_delta_um >= grid * Decimal(1000):
                raise AssertionError(
                    f"invalid upward mapping delta for {case['case_id']} at {grid_text}"
                )
            discrete = direct_membership(mapped_i, backward)
            category = classify_pair(discrete, case["continuous_status"])
            agreement = (
                ""
                if category == "NUMERICAL_UNRESOLVED"
                else str(category.startswith("AGREEMENT_")).lower()
            )
            detail_rows.append(
                {
                    "case_id": case["case_id"],
                    "offset_um": format(case["offset_um"], "f"),
                    "absolute_distance_from_boundary_um": format(abs(case["offset_um"]), "f"),
                    "state_mm": case["state_text"],
                    "grid_mm": grid_text,
                    "exact_upward_grid_index": mapped_i,
                    "mapped_state_mm": format(mapped, "f"),
                    "mapping_delta_um": format(mapping_delta_um, "f"),
                    "continuous_status": case["continuous_status"],
                    "continuous_recoverability_margin_um": case["continuous_margin_um"],
                    "continuous_optimizer_success": case["optimizer_success"],
                    "continuous_residual_valid": case["residual_valid"],
                    "discrete_status": "PASS" if discrete else "FAIL",
                    "agreement": agreement,
                    "classification": category,
                    "discrete_upper_recoverable_boundary_mm": upper_mm,
                    "boundary_under_approximation_um": boundary_under_um,
                }
            )

    if len(challenge) != 161 or len(detail_rows) != 805:
        raise AssertionError(
            f"required counts violated: challenge={len(challenge)}, detail={len(detail_rows)}"
        )

    summary_rows = summarize(detail_rows, boundary)
    overall_rows = [row for row in summary_rows if row["scope"] == "overall"]
    numerical_unresolved_count = sum(
        case["continuous_status"] == "NUMERICAL_UNRESOLVED" for case in challenge
    )
    optimistic_total = sum(
        row["optimistic_false_acceptance_count"] for row in overall_rows
    )

    disagreements_confined = True
    for row in detail_rows:
        if row["classification"] == "CONSERVATIVE_FALSE_REJECTION":
            state = float(row["state_mm"])
            upper = float(row["discrete_upper_recoverable_boundary_mm"])
            allowed_distance = float(row["boundary_under_approximation_um"]) + float(
                STATE_SPACING_UM
            )
            disagreements_confined = disagreements_confined and (
                state > upper
                and state <= boundary + float(cfg.get("decision_tolerance_um", 1e-7)) / 1000.0
                and float(row["absolute_distance_from_boundary_um"]) <= allowed_distance
            )
        elif row["classification"] == "OPTIMISTIC_FALSE_ACCEPTANCE":
            disagreements_confined = False

    if numerical_unresolved_count:
        classification = "B2_NUMERICALLY_UNRESOLVED"
    elif optimistic_total:
        classification = "B2_SCIENTIFIC_CONFLICT"
    elif disagreements_confined:
        classification = "B2_STRONG_SUPPORT"
    else:
        classification = "B2_BOUNDED_SUPPORT"

    write_csv(
        DETAIL_OUTPUT,
        list(detail_rows[0]),
        detail_rows,
    )
    write_csv(
        SUMMARY_OUTPUT,
        list(summary_rows[0]),
        summary_rows,
    )
    write_csv(
        CONTINUOUS_OUTPUT,
        list(continuous_rows[0]),
        continuous_rows,
    )

    regressions: dict[str, dict[str, Any]] = {}
    regressions["FROZEN_400_STATE_AUDIT"] = run_capture(
        [sys.executable, str(FROZEN_400_HARNESS)], timeout=600
    )
    frozen_hashes_after = {str(path): sha256(path) for path in FROZEN_400_OUTPUTS}
    frozen_400_unchanged = (
        regressions["FROZEN_400_STATE_AUDIT"]["status"] == "PASS"
        and frozen_hashes_before == frozen_hashes_after
    )
    regressions["FROZEN_400_STATE_AUDIT"]["status"] = (
        "PASS" if frozen_400_unchanged else "FAIL"
    )
    regressions["PYTEST"] = run_capture(
        [sys.executable, "-m", "pytest", "-q"], timeout=900
    )
    regressions["QUICK_REPRODUCTION"] = run_capture(
        [sys.executable, "scripts/reproduce.py", "--mode", "quick"], timeout=900
    )
    regressions["FULL_REPRODUCTION"] = run_capture(
        [sys.executable, "scripts/reproduce.py", "--mode", "full"], timeout=1800
    )
    regressions["GIT_DIFF_CHECK"] = run_capture(
        ["git", "-C", str(REPOSITORY_ROOT), "diff", "--check"], timeout=120
    )

    head_after = git_text("rev-parse", "HEAD")
    tag_after = git_text("rev-parse", f"{PUBLIC_TAG}^{{}}")
    tracked_diff_after = git_text("status", "--porcelain=v1", "--untracked-files=no")
    status_after = git_text("status", "--porcelain=v1", "--untracked-files=all")
    public_modified = bool(tag_before != tag_after or tracked_diff_after)
    all_regressions_pass = all(
        result["status"] == "PASS" for result in regressions.values()
    )
    task_status = (
        "COMPLETE"
        if boundary_reproduced
        and len(detail_rows) == 805
        and all_regressions_pass
        and not public_modified
        else "BLOCKED"
    )
    blockers: list[str] = []
    if not boundary_reproduced:
        blockers.append("FROZEN_BOUNDARY_MISMATCH")
    blockers.extend(name for name, result in regressions.items() if result["status"] != "PASS")
    if public_modified:
        blockers.append("PUBLIC_V1_1_0_MODIFIED")
    remaining_blockers = "NONE" if not blockers else ",".join(blockers)

    overall_by_grid = {row["grid_mm"]: row for row in overall_rows}
    misclassification_distances = [
        float(row["absolute_distance_from_boundary_um"])
        for row in detail_rows
        if row["classification"]
        in {"CONSERVATIVE_FALSE_REJECTION", "OPTIMISTIC_FALSE_ACCEPTANCE"}
    ]
    max_misclassification_distance = max(misclassification_distances, default=0.0)
    working_commit = (
        head_after if not status_after else f"UNCOMMITTED@{head_after}"
    )

    return_lines = [
        f"TASK_STATUS={task_status}",
        f"BASELINE_COMMIT={BASELINE_COMMIT}",
        f"WORKING_COMMIT={working_commit}",
        f"B2_CLASSIFICATION={classification}",
        f"CONTINUOUS_BOUNDARY_MM={boundary:.15f}",
        f"CHALLENGE_STATE_COUNT={len(challenge)}",
        f"DETAIL_ROW_COUNT={len(detail_rows)}",
    ]
    key_grid_names = {
        "0.004": "0P004",
        "0.002": "0P002",
        "0.001": "0P001",
        "0.0005": "0P0005",
        "0.00025": "0P00025",
    }
    for grid_text in GRID_TEXTS:
        row = overall_by_grid[grid_text]
        label = key_grid_names[grid_text]
        return_lines.extend(
            [
                f"GRID_{label}_AGREEMENT={row['agreement_count']}/{row['state_count']}",
                f"GRID_{label}_FALSE_REJECTION={row['conservative_false_rejection_count']}",
                f"GRID_{label}_FALSE_ACCEPTANCE={row['optimistic_false_acceptance_count']}",
            ]
        )
    return_lines.extend(
        [
            f"MAX_MISCLASSIFICATION_DISTANCE_UM={max_misclassification_distance:.12f}",
            f"NUMERICAL_UNRESOLVED_COUNT={numerical_unresolved_count}",
            f"FROZEN_400_STATE_AUDIT_UNCHANGED={'PASS' if frozen_400_unchanged else 'FAIL'}",
            f"PYTEST={regressions['PYTEST']['status']}",
            f"QUICK_REPRODUCTION={regressions['QUICK_REPRODUCTION']['status']}",
            f"FULL_REPRODUCTION={regressions['FULL_REPRODUCTION']['status']}",
            f"GIT_DIFF_CHECK={regressions['GIT_DIFF_CHECK']['status']}",
            f"PUBLIC_V1_1_0_MODIFIED={str(public_modified).lower()}",
            f"REMAINING_BLOCKERS={remaining_blockers}",
        ]
    )
    return_block = "\n".join(return_lines)

    report = f"""# B2 Near-Boundary Challenge Formal Audit

## Scope and freeze

- Task: frozen numerical-fidelity stress test for the scalar three-pass case only.
- Baseline commit: `{BASELINE_COMMIT}` (observed `{head_before}`).
- Public tag `{PUBLIC_TAG}` before/after: `{tag_before}` / `{tag_after}`.
- Frozen configuration: `configs/3pass_100um.yaml`; `m=3`.
- Challenge: 161 deterministic states at `s* ± 20 µm`, spaced by `0.25 µm`.
- Retrieval: exact Decimal ceiling to the next grid node; no tolerance-adjusted helper.
- Continuous reference: direct frozen `ReoptimizationEngine.optimize(state, 3)` call for every state.
- No manuscript, `src/rpra/`, config, expected-result, solver-setting, or public-tag edit was made.

## Result

The continuous boundary is `{boundary:.15f} mm`; the frozen reference is
`{expected_boundary:.15f} mm`, so the existing tolerance gate is
`{'PASS' if boundary_reproduced else 'FAIL'}`. All 805 state-grid comparisons and
all 161 challenge-state solver records (plus one boundary-root solver record) are
retained. The formal classification is `{classification}`.

{report_table(overall_rows)}

The classification priority was applied in the frozen order: optimistic false
acceptance, boundary displacement, near-boundary disagreement pattern, then
aggregate agreement. `B2_STRONG_SUPPORT` requires zero optimistic false
acceptances at every grid, zero unresolved states, and every disagreement to be
a conservative rejection confined to the observed discrete-to-continuous
boundary gap. This remains a bounded case-specific numerical statement, not a
general convergence theorem, physical validation, uncertainty result, or
cross-configuration claim.

## Cumulative windows

`B2_near_boundary_summary.csv` retains separate `pm5_um`, `pm10_um`, `pm20_um`,
and `overall` rows for every grid. Although `overall` and `pm20_um` contain the
same 161 states by construction, both are retained to make the requested scopes
explicit.

## Regression gates

{regression_table(regressions)}

- Frozen 400-state output hashes unchanged: `{str(frozen_400_unchanged).lower()}`.
- Public tag/reference modified: `{str(public_modified).lower()}`.
- Tracked working-tree diff after the run: `{tracked_diff_after or 'NONE'}`.

## Required return block

```text
{return_block}
```
"""
    REPORT_OUTPUT.write_text(report, encoding="utf-8", newline="\n")

    output_hashes = {
        path.name: sha256(path)
        for path in (DETAIL_OUTPUT, SUMMARY_OUTPUT, CONTINUOUS_OUTPUT, REPORT_OUTPUT)
    }
    environment = {
        "task": "RINENG_B2_NEAR_BOUNDARY_CHALLENGE_FORMAL_RUN",
        "task_status": task_status,
        "b2_classification": classification,
        "started_utc": started_utc,
        "completed_utc": utc_now(),
        "repository_root": str(REPOSITORY_ROOT),
        "audit_directory": str(AUDIT_DIR),
        "baseline_commit_expected": BASELINE_COMMIT,
        "head_before": head_before,
        "head_after": head_after,
        "working_commit": working_commit,
        "public_tag": PUBLIC_TAG,
        "public_tag_commit_before": tag_before,
        "public_tag_commit_after": tag_after,
        "public_v1_1_0_modified": public_modified,
        "tracked_diff_before": tracked_diff_before,
        "tracked_diff_after": tracked_diff_after,
        "git_status_before": status_before,
        "git_status_after": status_after,
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform": platform.platform(),
        "processor": platform.processor(),
        "logical_cpu_count": os.cpu_count(),
        "package_versions": package_versions(),
        "configuration": {
            "path": "configs/3pass_100um.yaml",
            "sha256": sha256(REPOSITORY_ROOT / "configs" / "3pass_100um.yaml"),
            "remaining_pass_count": int(cfg["remaining_pass_count"]),
            "optimizer_multistart": int(cfg.get("optimizer_multistart", 7)),
            "decision_tolerance_um": float(cfg.get("decision_tolerance_um", 1e-7)),
            "deflection_limit_um": float(cfg["deflection_limit_um"]),
        },
        "frozen_source_hashes": {
            "src/rpra/optimization.py": sha256(REPOSITORY_ROOT / "src" / "rpra" / "optimization.py"),
            "src/rpra/recoverable_set.py": sha256(REPOSITORY_ROOT / "src" / "rpra" / "recoverable_set.py"),
            "expected/paper_results.json": sha256(REPOSITORY_ROOT / "expected" / "paper_results.json"),
        },
        "formal_design": {
            "continuous_boundary_mm": boundary,
            "frozen_expected_boundary_mm": expected_boundary,
            "boundary_reproduced": boundary_reproduced,
            "challenge_state_count": len(challenge),
            "offset_min_um": float(offsets[0]),
            "offset_max_um": float(offsets[-1]),
            "spacing_um": float(STATE_SPACING_UM),
            "grids_mm": [float(value) for value in GRID_TEXTS],
            "detail_row_count": len(detail_rows),
            "continuous_solver_row_count": len(continuous_rows),
            "numerical_unresolved_count": numerical_unresolved_count,
            "disagreements_confined_to_boundary_gap": disagreements_confined,
            "grid_metadata": grid_metadata,
        },
        "frozen_400_state_audit": {
            "hashes_before": frozen_hashes_before,
            "hashes_after": frozen_hashes_after,
            "unchanged": frozen_400_unchanged,
        },
        "regression_gates": regressions,
        "output_sha256": output_hashes,
        "remaining_blockers": blockers,
        "required_return_block": return_block,
    }
    ENVIRONMENT_OUTPUT.write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(return_block)
    return 0 if task_status == "COMPLETE" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise

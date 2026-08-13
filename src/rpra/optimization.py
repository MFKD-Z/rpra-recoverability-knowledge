"""Independent continuous constrained reoptimization reference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
from scipy.optimize import brentq, minimize

from .morelli_model import pass_deflection_um


def evaluate_sequence(current_thickness_mm: float, removals_mm: np.ndarray, cfg: Mapping) -> list[dict]:
    before = float(current_thickness_mm)
    rows: list[dict] = []
    for idx, removal in enumerate(np.asarray(removals_mm, dtype=float), start=1):
        after = before - float(removal)
        delta = pass_deflection_um(float(removal), after, cfg)
        rows.append({
            "pass_index": idx,
            "before_thickness_mm": before,
            "after_thickness_mm": after,
            "radial_removal_mm": float(removal),
            "radial_immersion": float(removal) / cfg["tool_diameter_mm"],
            "deflection_um": delta,
        })
        before = after
    return rows


def _project_bounded_sum(candidate: np.ndarray, required: float, lower: np.ndarray, upper: np.ndarray) -> np.ndarray:
    candidate = np.asarray(candidate, dtype=float).copy()
    for _ in range(30):
        candidate = np.clip(candidate, lower, upper)
        residual = required - float(np.sum(candidate))
        if abs(residual) < 1e-12:
            return candidate
        if residual > 0:
            free = candidate < upper - 1e-12
        else:
            free = candidate > lower + 1e-12
        if not np.any(free):
            break
        candidate[free] += residual / int(np.sum(free))
    return np.clip(candidate, lower, upper)


def _deterministic_starts(
    required: float, lower: np.ndarray, upper: np.ndarray, count: int,
) -> list[np.ndarray]:
    n = int(lower.size)
    equal = _project_bounded_sum(np.full(n, required / n, dtype=float), required, lower, upper)
    starts = [equal]
    patterns = []
    base_patterns = [
        np.linspace(-1.0, 1.0, n), np.linspace(1.0, -1.0, n),
        np.sin(np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)),
        np.cos(np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)),
    ]
    for p in base_patterns:
        p = p - np.mean(p)
        if np.linalg.norm(p) > 0:
            patterns.append(p / np.max(np.abs(p)))
    for scale in (0.20, 0.45, 0.70):
        for p in patterns:
            room = float(np.min(np.minimum(equal - lower, upper - equal)))
            if room <= 0.0:
                room = float(np.max(upper - lower)) * 0.1
            candidate = _project_bounded_sum(equal + scale * room * p, required, lower, upper)
            if abs(float(np.sum(candidate)) - required) < 1e-8:
                starts.append(candidate.copy())
            if len(starts) >= count:
                return starts
    return starts[:count]


def full_reoptimize(
    current_thickness_mm: float,
    remaining_pass_count: int,
    cfg: Mapping,
    *,
    multistart: int | None = None,
) -> dict:
    """Minimize the worst remaining-pass deflection independently of RPRA."""
    n = int(remaining_pass_count)
    if n <= 0 or n != remaining_pass_count:
        raise ValueError("remaining_pass_count must be a positive integer")
    tf = float(cfg["final_thickness_mm"])
    lo = float(cfg["legal_radial_removal_min_mm"])
    hi = float(cfg["legal_radial_removal_max_mm"])
    required = float(current_thickness_mm) - tf
    # Eq. (32) is stated for AR=h/t_e >= 10. Because t_e is the post-cut
    # thickness, only the first pass needs an additional lower bound; all
    # later post-cut states are thinner.
    max_postcut_thickness = float(cfg["workpiece_height_mm"]) / 10.0
    first_lower = max(lo, float(current_thickness_mm) - max_postcut_thickness)
    if first_lower <= hi + 1e-10:
        first_lower = min(first_lower, hi)
    lower_bounds = np.full(n, lo, dtype=float)
    lower_bounds[0] = first_lower
    upper_bounds = np.full(n, hi, dtype=float)
    capacity_residual_low = required - float(np.sum(lower_bounds))
    capacity_residual_high = n * hi - required
    if first_lower > hi + 1e-10 or required < float(np.sum(lower_bounds)) - 1e-10 or required > n * hi + 1e-10:
        return {
            "feasible": False,
            "reason": "nominal_capacity",
            "current_thickness_mm": float(current_thickness_mm),
            "remaining_pass_count": n,
            "required_removal_mm": required,
            "capacity_residual_low_mm": capacity_residual_low,
            "capacity_residual_high_mm": capacity_residual_high,
            "first_pass_ar_domain_lower_bound_mm": first_lower,
            "optimal_worst_deflection_um": None,
            "recoverability_margin_um": None,
            "decision_at_limit": "FAIL",
            "pass_details": [],
        }
    start_count = int(multistart or cfg.get("optimizer_multistart", 7))
    starts = _deterministic_starts(required, lower_bounds, upper_bounds, max(1, start_count))
    best = None

    def pass_values(x: np.ndarray) -> np.ndarray:
        return np.asarray(
            [row["deflection_um"] for row in evaluate_sequence(current_thickness_mm, x[:n], cfg)],
            dtype=float,
        )

    def objective(x: np.ndarray) -> float:
        return float(x[-1])

    def equality(x: np.ndarray) -> float:
        return float(np.sum(x[:n]) - required)

    def epigraph(x: np.ndarray) -> np.ndarray:
        return x[-1] - pass_values(x)

    for removal0 in starts:
        z0 = float(np.max(pass_values(np.r_[removal0, 0.0]))) * 1.02 + 1e-6
        x0 = np.r_[removal0, z0]
        result = minimize(
            objective,
            x0,
            method="SLSQP",
            bounds=list(zip(lower_bounds, upper_bounds)) + [(0.0, None)],
            constraints=[
                {"type": "eq", "fun": equality},
                {"type": "ineq", "fun": epigraph},
            ],
            options={"ftol": 1e-11, "maxiter": 500, "disp": False},
        )
        removals = np.asarray(result.x[:n], dtype=float)
        details = evaluate_sequence(current_thickness_mm, removals, cfg)
        worst = max(row["deflection_um"] for row in details)
        eq_resid = abs(float(np.sum(removals)) - required)
        bound_violation = max(
            0.0,
            float(np.max(lower_bounds - removals)),
            float(np.max(removals - upper_bounds)),
        )
        epi_violation = max(0.0, worst - float(result.x[-1]))
        valid = eq_resid <= 2e-7 and bound_violation <= 2e-8 and epi_violation <= 2e-5
        candidate = (worst, valid, result, removals, details, eq_resid, bound_violation, epi_violation)
        if valid and (best is None or worst < best[0]):
            best = candidate
    if best is None:
        raise RuntimeError(
            f"SLSQP failed to produce a feasible {n}-pass solution at t={current_thickness_mm}"
        )
    worst, _, result, removals, details, eq_resid, bound_violation, epi_violation = best
    limit = float(cfg["deflection_limit_um"])
    margin = limit - worst
    return {
        "feasible": True,
        "optimizer": "scipy.optimize.SLSQP epigraph multi-start",
        "optimizer_success": bool(result.success),
        "optimizer_message": str(result.message),
        "multistart_count": len(starts),
        "current_thickness_mm": float(current_thickness_mm),
        "remaining_pass_count": n,
        "final_thickness_mm": tf,
        "required_removal_mm": required,
        "first_pass_ar_domain_lower_bound_mm": first_lower,
        "pass_removals_mm": removals.tolist(),
        "optimal_worst_deflection_um": float(worst),
        "recoverability_margin_um": float(margin),
        "decision_at_limit": "PASS" if margin >= -float(cfg.get("decision_tolerance_um", 1e-7)) else "FAIL",
        "constraint_residuals": {
            "removal_sum_abs_mm": eq_resid,
            "action_bound_violation_mm": bound_violation,
            "epigraph_violation_um": epi_violation,
            "terminal_thickness_abs_mm": abs(details[-1]["after_thickness_mm"] - tf),
        },
        "pass_details": details,
    }


@dataclass
class ReoptimizationEngine:
    cfg: Mapping

    def __post_init__(self) -> None:
        self._cache: dict[tuple[int, float], dict] = {}

    def optimize(self, current_thickness_mm: float, pass_count: int, *, use_cache: bool = True) -> dict:
        key = (int(pass_count), round(float(current_thickness_mm), 10))
        if use_cache and key in self._cache:
            return self._cache[key]
        result = full_reoptimize(current_thickness_mm, pass_count, self.cfg)
        if use_cache:
            self._cache[key] = result
        return result

    def continuous_boundary(self, pass_count: int) -> dict:
        n = int(pass_count)
        tf = float(self.cfg["final_thickness_mm"])
        lo = tf + n * float(self.cfg["legal_radial_removal_min_mm"])
        nominal_hi = tf + n * float(self.cfg["legal_radial_removal_max_mm"])
        # Largest current state for which one legal first action can enter the
        # paper's AR>=10 post-cut domain.
        source_domain_hi = (
            float(self.cfg["workpiece_height_mm"]) / 10.0
            + float(self.cfg["legal_radial_removal_max_mm"])
        )
        hi = min(nominal_hi, source_domain_hi)
        limit = float(self.cfg["deflection_limit_um"])

        def physics_margin(t: float) -> float:
            result = self.optimize(float(t), n)
            if not result["feasible"]:
                return -float("inf")
            return limit - float(result["optimal_worst_deflection_um"])

        margin_lo = physics_margin(lo)
        margin_hi = physics_margin(hi)
        if margin_lo < 0.0:
            raise RuntimeError(f"lower nominal {n}-pass state is already physically infeasible")
        if margin_hi >= 0.0:
            boundary = hi
            kind = "nominal_capacity_upper_bound"
        else:
            boundary = float(brentq(physics_margin, lo, hi, xtol=2e-10, rtol=2e-12, maxiter=100))
            kind = "physics_root"
        at_boundary = self.optimize(boundary, n)
        return {
            "remaining_pass_count": n,
            "continuous_boundary_mm": boundary,
            "boundary_kind": kind,
            "nominal_domain_mm": [lo, nominal_hi],
            "source_model_usable_domain_upper_mm": hi,
            "physics_margin_at_boundary_um": float(
                limit - at_boundary["optimal_worst_deflection_um"]
            ),
            "optimal_worst_deflection_at_boundary_um": at_boundary["optimal_worst_deflection_um"],
        }

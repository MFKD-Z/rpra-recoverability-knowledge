"""True discrete backward propagation of RPRA recoverable sets."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Mapping

import numpy as np

from .morelli_model import pass_deflection_um_vectorized


def _grid_scale(cfg: Mapping) -> int:
    grid = float(cfg["state_grid_mm"])
    scale = int(round(1.0 / grid))
    if abs(scale * grid - 1.0) > 1e-10:
        raise ValueError("state_grid_mm must have an integer reciprocal")
    return scale


def build_backward_set(pass_count: int, cfg: Mapping) -> dict:
    """Construct R_k from R_0 by integer-grid actions and exact transitions."""
    start_ns = time.perf_counter_ns()
    n = int(pass_count)
    scale = _grid_scale(cfg)
    tf_i = int(round(float(cfg["final_thickness_mm"]) * scale))
    action_min_i = int(round(float(cfg["legal_radial_removal_min_mm"]) * scale))
    action_max_i = int(round(float(cfg["legal_radial_removal_max_mm"]) * scale))
    action_i = np.arange(action_min_i, action_max_i + 1, dtype=np.int64)
    actions_mm = action_i / scale
    limit = float(cfg["deflection_limit_um"])
    previous = np.array([tf_i], dtype=np.int64)
    stages: dict[int, np.ndarray] = {0: previous.copy()}
    transition_counts: dict[int, int] = {}

    for stage in range(1, n + 1):
        possible_min = tf_i + stage * action_min_i
        possible_max = tf_i + stage * action_max_i
        membership = np.zeros(possible_max - possible_min + 1, dtype=bool)
        transitions = 0
        for next_i in previous:
            thickness_after = float(next_i) / scale
            # The Morelli model is defined only for AR=h/t_e >= 10.  At
            # relaxed deflection limits a backward stage can otherwise carry
            # post-cut states above that source-model domain into the next
            # propagation step.  Exclude those states before evaluating the
            # model; this is a domain intersection, not a physics verdict.
            if float(cfg["workpiece_height_mm"]) / thickness_after < 10.0 - 1e-12:
                continue
            deflections = pass_deflection_um_vectorized(actions_mm, thickness_after, cfg)
            feasible_actions = action_i[deflections <= limit + float(cfg.get("decision_tolerance_um", 1e-7))]
            states_i = next_i + feasible_actions
            valid = (states_i >= possible_min) & (states_i <= possible_max)
            membership[states_i[valid] - possible_min] = True
            transitions += int(np.sum(valid))
        current = np.flatnonzero(membership).astype(np.int64) + possible_min
        stages[stage] = current
        transition_counts[stage] = transitions
        previous = current
    elapsed_ns = time.perf_counter_ns() - start_ns
    return {
        "pass_count": n,
        "grid_mm": 1.0 / scale,
        "scale": scale,
        "terminal_state_mm": tf_i / scale,
        "action_grid_mm": [action_min_i / scale, action_max_i / scale, 1.0 / scale],
        "transition_semantics": "integer-grid exact: next_state = state - action",
        "stages_int": stages,
        "recoverable_states_mm": stages[n].astype(float) / scale,
        "transition_counts": transition_counts,
        "elapsed_ns": elapsed_ns,
    }


def save_backward_set(result: Mapping, path: str | Path) -> None:
    arrays = {
        "pass_count": np.array([result["pass_count"]], dtype=np.int64),
        "grid_mm": np.array([result["grid_mm"]], dtype=float),
        "terminal_state_mm": np.array([result["terminal_state_mm"]], dtype=float),
        "action_grid_mm": np.asarray(result["action_grid_mm"], dtype=float),
        "recoverable_states_mm": np.asarray(result["recoverable_states_mm"], dtype=float),
    }
    for stage, values in result["stages_int"].items():
        arrays[f"stage_{stage}_states_int"] = np.asarray(values, dtype=np.int64)
    np.savez_compressed(path, **arrays)


def lookup_membership(state_mm: float, result: Mapping, *, snap: str = "ceil") -> tuple[bool, float]:
    """Lookup a continuous state using an explicit conservative grid snap."""
    scale = int(result["scale"])
    raw = float(state_mm) * scale
    if snap == "ceil":
        state_i = int(np.ceil(raw - 1e-12))
    elif snap == "nearest":
        state_i = int(round(raw))
    elif snap == "floor":
        state_i = int(np.floor(raw + 1e-12))
    else:
        raise ValueError("snap must be ceil, nearest, or floor")
    final_values = np.asarray(result["stages_int"][result["pass_count"]], dtype=np.int64)
    index = int(np.searchsorted(final_values, state_i))
    member = bool(index < len(final_values) and final_values[index] == state_i)
    return member, state_i / scale


def contiguous_intervals(states_mm: np.ndarray, grid_mm: float) -> list[list[float]]:
    states = np.asarray(states_mm, dtype=float)
    if states.size == 0:
        return []
    gaps = np.where(np.diff(states) > grid_mm * 1.5)[0]
    starts = np.r_[0, gaps + 1]
    ends = np.r_[gaps, len(states) - 1]
    return [[float(states[i]), float(states[j])] for i, j in zip(starts, ends)]

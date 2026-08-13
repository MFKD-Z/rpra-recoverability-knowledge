"""State-action recoverability envelopes on the configured integer grid."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np
import yaml

from .morelli_model import pass_deflection_um_vectorized
from .recoverable_set import build_backward_set


INFEASIBLE = 0
PRESERVING = 1
DESTROYING = 2


@dataclass(frozen=True)
class ActionEnvelope:
    pass_count: int
    scale: int
    states_int: np.ndarray
    actions_int: np.ndarray
    next_states_int: np.ndarray
    locally_feasible: np.ndarray
    downstream_recoverable: np.ndarray
    classes: np.ndarray
    summary: dict


def load_configuration(path: str | Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"configuration must be a mapping: {path}")
    return value


def evaluated_states(backward: Mapping, cfg: Mapping) -> np.ndarray:
    """Return the paper's reader-facing state domain for a configuration."""
    count = int(cfg["remaining_pass_count"])
    scale = int(backward["scale"])
    if count == 3:
        lower = int(round(float(cfg["evaluation_state_min_mm"]) * scale))
        upper = int(round(float(cfg["evaluation_state_max_mm"]) * scale))
        return np.arange(lower, upper + 1, dtype=np.int64)
    if count == 4:
        return np.asarray(backward["stages_int"][count], dtype=np.int64)
    raise ValueError("the published configurations use three or four remaining passes")


def analyze_envelope(backward: Mapping, cfg: Mapping) -> ActionEnvelope:
    count = int(cfg["remaining_pass_count"])
    scale = int(backward["scale"])
    states = np.asarray(backward["stages_int"][count], dtype=np.int64)
    downstream = np.asarray(backward["stages_int"][count - 1], dtype=np.int64)
    action_min = int(round(float(cfg["legal_radial_removal_min_mm"]) * scale))
    action_max = int(round(float(cfg["legal_radial_removal_max_mm"]) * scale))
    actions = np.arange(action_min, action_max + 1, dtype=np.int64)
    terminal = int(round(float(cfg["final_thickness_mm"]) * scale))
    next_min = terminal + (count - 1) * action_min
    next_max = terminal + (count - 1) * action_max
    model_max = float(cfg["workpiece_height_mm"]) / 10.0
    tolerance = float(cfg.get("decision_tolerance_um", 1e-7))

    next_states = states[:, None] - actions[None, :]
    transition_legal = (next_states >= next_min) & (next_states <= next_max)
    model_applicable = next_states / scale <= model_max + 1e-12
    evaluable = transition_legal & model_applicable
    physical = np.zeros(next_states.shape, dtype=bool)
    for row_index in range(states.size):
        mask = evaluable[row_index]
        if np.any(mask):
            values = pass_deflection_um_vectorized(
                actions[mask].astype(float) / scale,
                next_states[row_index, mask].astype(float) / scale,
                cfg,
            )
            physical[row_index, mask] = (
                values <= float(cfg["deflection_limit_um"]) + tolerance
            )
    local = transition_legal & physical
    downstream_member = np.isin(next_states, downstream, assume_unique=False)
    preserving = local & downstream_member
    destroying = local & ~downstream_member
    classes = np.full(next_states.shape, INFEASIBLE, dtype=np.uint8)
    classes[preserving] = PRESERVING
    classes[destroying] = DESTROYING

    preserving_by_state = np.sum(preserving, axis=1)
    destroying_by_state = np.sum(destroying, axis=1)
    if np.any(preserving_by_state == 0):
        raise RuntimeError("a recoverable state has no preserving action")
    fully = preserving_by_state.size - int(np.count_nonzero(destroying_by_state))
    mixed = int(np.count_nonzero(destroying_by_state))
    summary = {
        "recoverable_states": int(states.size),
        "fully_preserving_states": int(fully),
        "mixed_action_states": mixed,
        "action_total": int(np.sum(local)),
        "preserving_actions": int(np.sum(preserving)),
        "destroying_actions": int(np.sum(destroying)),
    }
    return ActionEnvelope(
        count, scale, states, actions, next_states, local,
        downstream_member, classes, summary,
    )


def configuration_results(cfg: Mapping) -> tuple[dict, Mapping, ActionEnvelope]:
    backward = build_backward_set(int(cfg["remaining_pass_count"]), cfg)
    envelope = analyze_envelope(backward, cfg)
    domain = evaluated_states(backward, cfg)
    recoverable = np.isin(
        domain,
        backward["stages_int"][int(cfg["remaining_pass_count"])],
    )
    result = {
        "state_total": int(domain.size),
        "recoverable": int(np.sum(recoverable)),
        "irrecoverable": int(domain.size - np.sum(recoverable)),
        **envelope.summary,
    }
    if int(cfg["remaining_pass_count"]) == 3:
        from .optimization import ReoptimizationEngine

        local_ok = local_feasible_states(domain, cfg)
        boundary = float(
            ReoptimizationEngine(cfg).continuous_boundary(3)["continuous_boundary_mm"]
        )
        continuous_irrecoverable = domain.astype(float) / int(backward["scale"]) > boundary
        result["local_feasible_irrecoverable"] = int(
            np.sum(local_ok & continuous_irrecoverable)
        )
    return result, backward, envelope


def local_feasible_states(states_int: np.ndarray, cfg: Mapping) -> np.ndarray:
    """Whether at least one legal current action satisfies the physical limit."""
    scale = int(round(1.0 / float(cfg["state_grid_mm"])))
    count = int(cfg["remaining_pass_count"])
    action_min = int(round(float(cfg["legal_radial_removal_min_mm"]) * scale))
    action_max = int(round(float(cfg["legal_radial_removal_max_mm"]) * scale))
    actions = np.arange(action_min, action_max + 1, dtype=np.int64)
    terminal = int(round(float(cfg["final_thickness_mm"]) * scale))
    next_min = terminal + (count - 1) * action_min
    next_max = terminal + (count - 1) * action_max
    model_max = float(cfg["workpiece_height_mm"]) / 10.0
    result = np.zeros(len(states_int), dtype=bool)
    for row, state in enumerate(np.asarray(states_int, dtype=np.int64)):
        next_states = state - actions
        mask = (
            (next_states >= next_min)
            & (next_states <= next_max)
            & (next_states / scale <= model_max + 1e-12)
        )
        if np.any(mask):
            values = pass_deflection_um_vectorized(
                actions[mask].astype(float) / scale,
                next_states[mask].astype(float) / scale,
                cfg,
            )
            result[row] = bool(np.any(
                values <= float(cfg["deflection_limit_um"])
                + float(cfg.get("decision_tolerance_um", 1e-7))
            ))
    return result

"""Generate reader-facing tables and figures from recomputed results."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Mapping

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap
import numpy as np
from rdflib import Graph

from knowledge.graph import build_base_graph, materialize_rules, merged_graph
from knowledge.queries import execute_query_examples
from .envelopes import DESTROYING, PRESERVING, evaluated_states, local_feasible_states
from .optimization import ReoptimizationEngine
from .reproduction import compute_public_results, load_all_configurations, write_csv, write_json


def _combined_graph(configs, computed) -> Graph:
    union = Graph()
    for name, (_, backward, envelope) in computed.items():
        base = build_base_graph(configs[name], backward, envelope)
        for triple in merged_graph(base, materialize_rules(base)):
            union.add(triple)
    return union


def generate_tables(
    root: Path,
    actual: dict | None = None,
    computed: dict | None = None,
) -> list[Path]:
    if actual is None or computed is None:
        actual, computed = compute_public_results(root)
    configs = load_all_configurations(root)
    output = root / "reproduced_outputs" / "tables"
    config_rows = [{"configuration": name, **values[0]} for name, values in computed.items()]
    write_csv(output / "configuration_results.csv", config_rows)

    three = set(map(int, computed["3pass_100um"][1]["stages_int"][3]))
    four = set(map(int, computed["4pass_100um"][1]["stages_int"][4]))
    collision_rows = []
    for value in range(4540, 4801):
        three_status = "RECOVERABLE" if value in three else "IRRECOVERABLE"
        four_status = "RECOVERABLE" if value in four else "IRRECOVERABLE"
        if three_status != four_status:
            collision_rows.append({
                "state_mm": value / 1000.0,
                "three_pass_100um": three_status,
                "four_pass_100um": four_status,
            })
    write_csv(output / "configuration_dependent_states.csv", collision_rows)

    graph = _combined_graph(configs, computed)
    examples = execute_query_examples(root, graph, configs)
    write_json(output / "query_examples.json", examples)
    shutil.copyfile(
        root / "data" / "reference" / "knowledge_conditions.csv",
        output / "knowledge_conditions.csv",
    )
    return [
        output / "configuration_results.csv",
        output / "configuration_dependent_states.csv",
        output / "query_examples.json",
        output / "knowledge_conditions.csv",
    ]


def _save_figure(fig, output: Path, name: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output / f"{name}.png", dpi=220)
    fig.savefig(output / f"{name}.pdf")
    plt.close(fig)


def generate_figures(
    root: Path,
    actual: dict | None = None,
    computed: dict | None = None,
) -> list[Path]:
    if actual is None or computed is None:
        actual, computed = compute_public_results(root)
    configs = load_all_configurations(root)
    output = root / "reproduced_outputs" / "figures"
    cfg = configs["3pass_100um"]
    _, backward, envelope = computed["3pass_100um"]
    domain = evaluated_states(backward, cfg)
    states = domain.astype(float) / int(backward["scale"])
    local = local_feasible_states(domain, cfg)
    boundary = float(ReoptimizationEngine(cfg).continuous_boundary(3)["continuous_boundary_mm"])
    global_ok = states <= boundary
    category = np.where(local & ~global_ok, 2, np.where(global_ok, 1, 0))
    fig, axis = plt.subplots(figsize=(8.2, 3.4))
    for value, color, label in (
        (1, "#1b7f4b", "remaining process recoverable"),
        (2, "#c23b33", "locally feasible, no feasible continuation"),
        (0, "#737373", "locally infeasible"),
    ):
        mask = category == value
        if np.any(mask):
            axis.scatter(states[mask], np.full(np.sum(mask), value), s=11, color=color, label=label)
    axis.axvline(boundary, color="#2358a5", linestyle="--", linewidth=1.4)
    axis.set_xlabel("WIP thickness (mm)")
    axis.set_yticks([])
    axis.set_title("Local feasibility and remaining-process recoverability")
    axis.legend(loc="upper left", fontsize=8)
    _save_figure(fig, output, "Fig3_state_recoverability")

    fig, axis = plt.subplots(figsize=(8.2, 4.2))
    for name, color in (
        ("3pass_100um", "#2358a5"),
        ("3pass_105um", "#1b7f4b"),
        ("3pass_110um", "#d28b1d"),
        ("4pass_100um", "#8a4da8"),
    ):
        config = configs[name]
        _, back, _ = computed[name]
        count = int(config["remaining_pass_count"])
        values = np.asarray(back["stages_int"][count], dtype=float) / int(back["scale"])
        axis.plot(values, np.full(values.size, len(axis.lines)), ".", ms=2.2, color=color, label=name.replace("_", " "))
    axis.set_xlabel("Recoverable WIP thickness (mm)")
    axis.set_yticks([])
    axis.set_title("Configuration-indexed recoverable states")
    axis.legend(fontsize=8)
    _save_figure(fig, output, "Fig5_configuration_dependence")

    fig, axis = plt.subplots(figsize=(8.4, 4.6))
    matrix = envelope.classes.astype(float)
    matrix[matrix == 0] = np.nan
    cmap = ListedColormap(["#2a8c68", "#d05b48"])
    norm = BoundaryNorm([0.5, 1.5, 2.5], cmap.N)
    axis.imshow(
        matrix,
        origin="lower",
        aspect="auto",
        interpolation="nearest",
        cmap=cmap,
        norm=norm,
        extent=[
            envelope.actions_int[0] / envelope.scale,
            envelope.actions_int[-1] / envelope.scale,
            envelope.states_int[0] / envelope.scale,
            envelope.states_int[-1] / envelope.scale,
        ],
    )
    axis.set_xlabel("Current action (mm)")
    axis.set_ylabel("Recoverable WIP state (mm)")
    axis.set_title("Three-pass preserving and destroying action envelope")
    _save_figure(fig, output, "Fig6_action_envelope")

    with (root / "data" / "reference" / "knowledge_conditions.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        conditions = list(csv.DictReader(handle))
    status_value = {"UNKNOWN": 0, "IRRECOVERABLE": 1, "RECOVERABLE": 2}
    fig, axis = plt.subplots(figsize=(8.2, 4.2))
    x = np.arange(len(conditions))
    y = [status_value[row["returned_status"]] for row in conditions]
    colors = ["#d28b1d" if row["requires_integrity_review"] == "true" else "#2358a5" for row in conditions]
    axis.bar(x, y, color=colors)
    axis.set_xticks(x, [row["case"] for row in conditions], rotation=40, ha="right")
    axis.set_yticks([0, 1, 2], ["UNKNOWN", "IRRECOVERABLE", "RECOVERABLE"])
    axis.set_title("Knowledge-condition behavior")
    _save_figure(fig, output, "Fig7_knowledge_conditions")
    return sorted(output.glob("Fig*.*"))


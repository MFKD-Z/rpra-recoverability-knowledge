from __future__ import annotations

from pathlib import Path
import argparse
import csv
import json
import sys
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from scipy.optimize import brentq


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate reproducible RINENG data figures directly from the frozen "
            "RPRA repository data. Exports PNG/TIFF at 900 dpi and vector PDF."
        )
    )
    parser.add_argument(
        "--repo-root", type=Path, default=None,
        help="Repository root; default is the parent of the scripts directory.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Output directory; default is reproduced_outputs/rineng_data_figures.",
    )
    parser.add_argument(
        "--migration-check-root", type=Path, default=None,
        help=(
            "Optional historical experiment root used only to compare recomputed "
            "state/action data against the legacy EXP1/EXP4 tables."
        ),
    )
    return parser.parse_args()

ARGS = parse_args()
HERE = Path(__file__).resolve().parent
REPO = ARGS.repo_root.resolve() if ARGS.repo_root else HERE.parent.resolve()
OUT = (ARGS.output_dir.resolve() if ARGS.output_dir else
       REPO / "reproduced_outputs" / "rineng_data_figures")
OUT.mkdir(parents=True, exist_ok=True)

SRC = REPO / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from rpra.envelopes import (  # noqa: E402
    DESTROYING,
    INFEASIBLE,
    PRESERVING,
    analyze_envelope,
    configuration_results,
    evaluated_states,
    load_configuration,
    local_feasible_states,
)
from rpra.morelli_model import pass_deflection_um  # noqa: E402
from rpra.optimization import ReoptimizationEngine  # noqa: E402
from rpra.recoverable_set import build_backward_set  # noqa: E402

SOURCE = {
    "grid_robustness.csv": REPO / "data" / "reference" / "grid_robustness.csv",
    "B2_near_boundary_summary.csv": REPO / "audits" / "20260829_b2_near_boundary_challenge" / "B2_near_boundary_summary.csv",
    "B3_terminal_tolerance_summary.csv": REPO / "audits" / "20260829_b3_terminal_tolerance_sensitivity" / "B3_terminal_tolerance_summary.csv",
    "E2_configuration_robustness.csv": REPO / "audits" / "20260828_r81_experiment_freeze_candidate" / "E2_configuration_robustness.csv",
    "E3_grid_scalability.csv": REPO / "audits" / "20260828_r81_experiment_freeze_candidate" / "E3_grid_scalability.csv",
    "E3_horizon_scalability.csv": REPO / "audits" / "20260828_r81_experiment_freeze_candidate" / "E3_horizon_scalability.csv",
    "B1_final_comparison_table.csv": REPO / "audits" / "20260828_b1_online_reopt_comparator" / "key_result_tables" / "final_comparison_table.csv",
    "3pass_100um.yaml": REPO / "configs" / "3pass_100um.yaml",
    "paper_results.json": REPO / "expected" / "paper_results.json",
}

missing = [str(p) for p in SOURCE.values() if not p.is_file()]
if missing:
    raise FileNotFoundError("Missing frozen source data:\n  - " + "\n  - ".join(missing))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


repo_resolved = REPO.resolve()
outside_repo = [
    str(path) for path in SOURCE.values()
    if not _is_relative_to(path.resolve(), repo_resolved)
]
if outside_repo:
    raise AssertionError(
        "Scientific inputs must be contained in the repository:\n  - "
        + "\n  - ".join(outside_repo)
    )

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Liberation Serif", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": 150,
    "savefig.dpi": 900,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

def read_csv(name):
    with SOURCE[name].open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))

def save(fig, stem):
    fig.tight_layout()
    fig.savefig(OUT / f"{stem}.png", dpi=900, bbox_inches="tight", pad_inches=0.04)
    fig.savefig(OUT / f"{stem}.tif", dpi=900, bbox_inches="tight", pad_inches=0.04,
                pil_kwargs={"compression": "tiff_lzw"})
    fig.savefig(OUT / f"{stem}.pdf", dpi=900, bbox_inches="tight", pad_inches=0.04)
    plt.close(fig)

# 1. Grid refinement: boundary under-approximation
rows = read_csv("grid_robustness.csv")
labels = [r["grid_mm"] for r in rows]
err = [float(r["boundary_error_um"]) for r in rows]
x = np.arange(len(rows))
fig, ax = plt.subplots(figsize=(6.6, 3.8))
ax.plot(x, err, marker="o", linewidth=1.8)
ax.set_xticks(x, labels)
ax.set_xlabel("Grid interval, $h$ [mm] (coarse → fine)")
ax.set_ylabel("Boundary under-approximation [µm]")
ax.set_title("Grid refinement narrows the discrete-to-continuous boundary gap")
ax.grid(axis="y", alpha=0.25)
for xi, yi in zip(x, err):
    ax.annotate(f"{yi:.2f}", (xi, yi), xytext=(0, 5), textcoords="offset points",
                ha="center", fontsize=7)
save(fig, "F3a_grid_boundary_fidelity_900dpi")

# 2. Near-boundary challenge: agreement vs conservative rejection
rows = [r for r in read_csv("B2_near_boundary_summary.csv") if r["scope"] == "overall"]
labels = [r["grid_mm"] for r in rows]
agreement = np.array([int(r["agreement_count"]) for r in rows])
conservative = np.array([int(r["conservative_false_rejection_count"]) for r in rows])
optimistic = np.array([int(r["optimistic_false_acceptance_count"]) for r in rows])
near_boundary_totals = agreement + conservative + optimistic
if not np.all(near_boundary_totals == near_boundary_totals[0]):
    raise AssertionError("Near-boundary sample size must be constant across grids")
near_boundary_count = int(near_boundary_totals[0])
x = np.arange(len(rows))
fig, ax = plt.subplots(figsize=(6.6, 3.8))
ax.bar(x, agreement, label="Agreement")
ax.bar(x, conservative, bottom=agreement, label="Conservative false rejection")
ax.set_xticks(x, labels)
ax.set_xlabel("Grid interval, $h$ [mm] (coarse → fine)")
ax.set_ylabel(f"Near-boundary states (n = {near_boundary_count})")
ax.set_title("Near-boundary disagreements remain conservative under grid refinement")
ax.legend(frameon=False)
ax.text(0.99, 0.03, "Optimistic false acceptance = 0 at all five grids",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=7)
save(fig, "F3b_near_boundary_classification_900dpi")

# 3. Terminal-set sensitivity: state populations
rows = read_csv("B3_terminal_tolerance_summary.csv")
labels = ["Exact", "±5 µm", "±10 µm", "±20 µm"]
rec = np.array([int(r["recoverable_state_count"]) for r in rows])
irr = np.array([int(r["local_but_irrecoverable_count"]) for r in rows])
evaluated_state_totals = rec + irr
if not np.all(evaluated_state_totals == evaluated_state_totals[0]):
    raise AssertionError("Evaluated state count must be constant across terminal settings")
evaluated_state_count = int(evaluated_state_totals[0])
x = np.arange(len(rows))
fig, ax = plt.subplots(figsize=(6.6, 3.8))
ax.bar(x, rec, label="Recoverable")
ax.bar(x, irr, bottom=rec, label="Locally acceptable but irrecoverable")
ax.set_xticks(x, labels)
ax.set_xlabel("Terminal condition")
ax.set_ylabel(f"Evaluated WIP states (n = {evaluated_state_count})")
ax.set_title("Terminal-band relaxation enlarges recoverability but does not remove the gap")
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.01), ncol=2)
save(fig, "F4a_terminal_state_sensitivity_900dpi")

# 4. Terminal-set sensitivity: rollout completion
myopic = np.array([int(r["myopic_completion_count"]) for r in rows])
rpra = np.array([int(r["rpra_completion_count"]) for r in rows])
den = np.array([int(r["recoverable_state_count"]) for r in rows])
myopic_rate = 100.0 * myopic / den
rpra_rate = 100.0 * rpra / den
w = 0.36
fig, ax = plt.subplots(figsize=(6.6, 3.8))
ax.bar(x - w/2, myopic_rate, width=w, label="MYOPIC")
ax.bar(x + w/2, rpra_rate, width=w, label="RPRA-filtered")
ax.set_xticks(x, labels)
ax.set_xlabel("Terminal condition")
ax.set_ylabel("Completion rate [%]")
ax.set_ylim(0, 112)
ax.set_title("Policy completion across terminal-band settings")
ax.legend(frameon=False)
for xi, a, b, d in zip(x, myopic, rpra, den):
    ax.text(xi - w/2, 100*a/d + 2, f"{a}/{d}", ha="center", va="bottom", fontsize=7)
    ax.text(xi + w/2, 102, f"{b}/{d}", ha="center", va="bottom", fontsize=7)
save(fig, "F4b_terminal_policy_completion_900dpi")

# 5. Analytical-condition sensitivity
rows2 = read_csv("E2_configuration_robustness.csv")
labels2 = ["Baseline", "Feed −10%", "Feed +10%", "Axial depth −10%", "Axial depth +10%"]
rec2 = np.array([int(r["RECOVERABLE_COUNT"]) for r in rows2])
irr2 = np.array([int(r["LOCAL_BUT_IRRECOVERABLE_COUNT"]) for r in rows2])
configuration_state_totals = rec2 + irr2
if not np.all(configuration_state_totals == configuration_state_totals[0]):
    raise AssertionError("Evaluated state count must be constant across configurations")
configuration_state_count = int(configuration_state_totals[0])
x2 = np.arange(len(rows2))
fig, ax = plt.subplots(figsize=(7.0, 3.9))
ax.bar(x2, rec2, label="Recoverable")
ax.bar(x2, irr2, bottom=rec2, label="Locally acceptable but irrecoverable")
ax.set_xticks(x2, labels2)
ax.set_xlabel("Analytical cutting condition")
ax.set_ylabel(f"Evaluated WIP states (n = {configuration_state_count})")
ax.set_title("Recoverability can collapse while current-stage acceptance remains unchanged")
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.01), ncol=2)
save(fig, "F4c_cutting_condition_sensitivity_900dpi")

# 6. Grid scalability of RPRA numerical core
rows3 = read_csv("E3_grid_scalability.csv")
labels3 = [r["GRID_MM"] for r in rows3]
runtime3 = np.array([float(r["TOTAL_CORE_MEDIAN_MS"]) for r in rows3])
x3 = np.arange(len(rows3))
fig, ax = plt.subplots(figsize=(6.6, 3.8))
ax.plot(x3, runtime3, marker="o", linewidth=1.8)
ax.set_xticks(x3, labels3)
ax.set_xlabel("Grid interval, $h$ [mm] (coarse → fine)")
ax.set_ylabel("Median core construction time [ms]")
ax.set_title("RPRA construction cost increases with grid refinement")
ax.grid(axis="y", alpha=0.25)
save(fig, "F5a_grid_runtime_scaling_900dpi")

# 7. Horizon scalability of RPRA numerical core
rows4 = read_csv("E3_horizon_scalability.csv")
passes = np.array([int(r["PASS_COUNT"]) for r in rows4])
runtime4 = np.array([float(r["TOTAL_CORE_MEDIAN_MS"]) for r in rows4])
fig, ax = plt.subplots(figsize=(6.6, 3.8))
ax.plot(passes, runtime4, marker="o", linewidth=1.8)
ax.set_xticks(passes)
ax.set_xlabel("Remaining-pass horizon")
ax.set_ylabel("Median core construction time [ms]")
ax.set_title("RPRA construction cost across one- to four-pass horizons")
ax.grid(axis="y", alpha=0.25)
save(fig, "F5b_horizon_runtime_scaling_900dpi")

# 8. Checkpoint latency: RPRA vs ONLINE-REOPT (descriptive, excludes offline RPRA build cost)
rows5 = read_csv("B1_final_comparison_table.csv")
metric = {r["metric"]: r for r in rows5}
vals = [
    float(metric["decision_latency_median_ms"]["RPRA"]),
    float(metric["decision_latency_median_ms"]["ONLINE_REOPT"]),
]
fig, ax = plt.subplots(figsize=(5.6, 3.8))
bars = ax.bar(["RPRA lookup/filter", "ONLINE-REOPT"], vals)
ax.set_yscale("log")
ax.set_ylabel("Median first-decision latency [ms] (log scale)")
ax.set_title("Checkpoint computation is shifted from repeated re-optimization to lookup/filtering")
for b, v in zip(bars, vals):
    ax.text(b.get_x() + b.get_width()/2, v*1.12, f"{v:g}", ha="center", va="bottom", fontsize=7)
save(fig, "F5c_checkpoint_latency_900dpi")



# ---------------------------------------------------------------------------
# Main-text composite Fig. 3 — numerical fidelity
# ---------------------------------------------------------------------------
def panel_title(ax, text):
    ax.set_title(text, loc="left", fontweight="bold", pad=6)

grid_rows = read_csv("grid_robustness.csv")
boundary_rows = [r for r in read_csv("B2_near_boundary_summary.csv") if r["scope"] == "overall"]
grid_labels = [r["grid_mm"] for r in grid_rows]
grid_x = np.arange(len(grid_rows))
boundary_error = np.array([float(r["boundary_error_um"]) for r in grid_rows])
agreement = np.array([int(r["agreement_count"]) for r in boundary_rows])
conservative = np.array([int(r["conservative_false_rejection_count"]) for r in boundary_rows])
optimistic = np.array([int(r["optimistic_false_acceptance_count"]) for r in boundary_rows])
near_boundary_totals = agreement + conservative + optimistic
if not np.all(near_boundary_totals == near_boundary_totals[0]):
    raise AssertionError("Near-boundary sample size must be constant across grids")
near_boundary_count = int(near_boundary_totals[0])
assert np.all(agreement + conservative == near_boundary_count)
assert np.all(optimistic == 0)

fig, axes = plt.subplots(1, 2, figsize=(7.15, 3.15))
ax = axes[0]
ax.plot(grid_x, boundary_error, marker="o")
ax.set_xticks(grid_x, grid_labels)
ax.set_xlabel("Grid interval, $h$ [mm] (coarse → fine)")
ax.set_ylabel("Boundary under-approximation [µm]")
panel_title(ax, "(a) Boundary approximation")
ax.grid(axis="y", alpha=0.22)
ax.margins(x=0.06)
for xi, yi in zip(grid_x, boundary_error):
    ax.annotate(f"{yi:.2f}", (xi, yi), xytext=(0, 5), textcoords="offset points",
                ha="center", va="bottom", fontsize=7)

ax = axes[1]
ax.bar(grid_x, agreement, label="Agreement")
ax.bar(grid_x, conservative, bottom=agreement, label="Conservative rejection")
ax.set_xticks(grid_x, grid_labels)
ax.set_xlabel("Grid interval, $h$ [mm] (coarse → fine)")
ax.set_ylabel(f"Near-boundary states (n = {near_boundary_count})")
panel_title(ax, "(b) Near-boundary classification")
ax.set_ylim(0, 190)
ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 0.995), ncol=2)
for xi, a, r in zip(grid_x, agreement, conservative):
    ax.text(xi, a + r/2, f"{r}", ha="center", va="center", fontsize=7)
fig.subplots_adjust(left=0.09, right=0.995, bottom=0.19, top=0.84, wspace=0.34)
fig.savefig(OUT / "Fig3_numerical_fidelity_900dpi.png", dpi=900, bbox_inches="tight", pad_inches=0.04)
fig.savefig(OUT / "Fig3_numerical_fidelity_900dpi.tif", dpi=900, bbox_inches="tight", pad_inches=0.04,
            pil_kwargs={"compression": "tiff_lzw"})
fig.savefig(OUT / "Fig3_numerical_fidelity_900dpi.pdf", dpi=900, bbox_inches="tight", pad_inches=0.04)
plt.close(fig)

# ---------------------------------------------------------------------------
# Main-text composite Fig. 4 — terminal and analytical-condition sensitivity
# ---------------------------------------------------------------------------
terminal_rows = read_csv("B3_terminal_tolerance_summary.csv")
labels = ["Exact", "±5 µm", "±10 µm", "±20 µm"]
rec = np.array([int(r["recoverable_state_count"]) for r in terminal_rows])
irr = np.array([int(r["local_but_irrecoverable_count"]) for r in terminal_rows])
myopic = np.array([int(r["myopic_completion_count"]) for r in terminal_rows])
rpra = np.array([int(r["rpra_completion_count"]) for r in terminal_rows])
den = rec.copy()
evaluated_state_totals = rec + irr
if not np.all(evaluated_state_totals == evaluated_state_totals[0]):
    raise AssertionError("Evaluated state count must be constant across terminal settings")
evaluated_state_count = int(evaluated_state_totals[0])
assert np.all(rpra == den)
myopic_rate = 100.0 * myopic / den
rpra_rate = 100.0 * rpra / den

cut_rows = read_csv("E2_configuration_robustness.csv")
cut_labels = ["Baseline", "Feed −10%", "Feed +10%", "Axial depth −10%", "Axial depth +10%"]
cut_rec = np.array([int(r["RECOVERABLE_COUNT"]) for r in cut_rows])
cut_irr = np.array([int(r["LOCAL_BUT_IRRECOVERABLE_COUNT"]) for r in cut_rows])
cut_state_totals = cut_rec + cut_irr
if not np.all(cut_state_totals == evaluated_state_count):
    raise AssertionError("Terminal and analytical-condition state domains differ")

fig = plt.figure(figsize=(7.15, 5.35))
gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.03], hspace=0.43, wspace=0.32)
a = fig.add_subplot(gs[0, 0]); b = fig.add_subplot(gs[0, 1]); c = fig.add_subplot(gs[1, :])
x = np.arange(4)
a.bar(x, rec, label="Recoverable")
a.bar(x, irr, bottom=rec, label="Local but irrecoverable")
a.set_xticks(x, labels); a.set_xlabel("Terminal condition"); a.set_ylabel(f"WIP states (n = {evaluated_state_count})")
panel_title(a, "(a) State recoverability"); a.set_ylim(0, 720)
a.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 0.995), ncol=1)

w = 0.36
b.bar(x-w/2, myopic_rate, width=w, label="MYOPIC")
b.bar(x+w/2, rpra_rate, width=w, label="RPRA-filtered")
b.set_xticks(x, labels); b.set_xlabel("Terminal condition"); b.set_ylabel("Completion rate [%]")
panel_title(b, "(b) Policy completion"); b.set_ylim(0, 130)
b.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 0.995), ncol=2)
for xi, rate, n, d in zip(x, myopic_rate, myopic, den):
    b.annotate(f"{n}/{d}", (xi-w/2, rate), xytext=(0, 4), textcoords="offset points",
               ha="center", va="bottom", fontsize=6.5)
for xi, rate, n, d in zip(x, rpra_rate, rpra, den):
    b.annotate(f"{n}/{d}", (xi+w/2, rate), xytext=(0, 3), textcoords="offset points",
               ha="center", va="bottom", fontsize=6.5)

x2 = np.arange(5)
c.bar(x2, cut_rec, label="Recoverable")
c.bar(x2, cut_irr, bottom=cut_rec, label="Local but irrecoverable")
c.set_xticks(x2, cut_labels); c.set_xlabel("Analytical cutting condition"); c.set_ylabel(f"WIP states (n = {evaluated_state_count})")
panel_title(c, "(c) Cutting-condition sensitivity"); c.set_ylim(0, 720)
c.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, 0.995), ncol=2)
fig.subplots_adjust(left=0.09, right=0.995, bottom=0.10, top=0.92)
fig.savefig(OUT / "Fig4_sensitivity_900dpi.png", dpi=900, bbox_inches="tight", pad_inches=0.04)
fig.savefig(OUT / "Fig4_sensitivity_900dpi.tif", dpi=900, bbox_inches="tight", pad_inches=0.04,
            pil_kwargs={"compression": "tiff_lzw"})
fig.savefig(OUT / "Fig4_sensitivity_900dpi.pdf", dpi=900, bbox_inches="tight", pad_inches=0.04)
plt.close(fig)

def _uniform_half_step(values: np.ndarray, name: str) -> float:
    steps = np.diff(values)
    if steps.size == 0 or not np.allclose(steps, steps[0], rtol=0.0, atol=1e-12):
        raise AssertionError(f"{name} must be a nontrivial uniform grid")
    return float(steps[0] / 2.0)


def _continuous_local_feasible_interval(
    state_mm: float,
    remaining_pass_count: int,
    configuration: dict,
) -> tuple[float, float]:
    """Recompute the historical continuous local interval from public physics."""
    state = float(state_mm)
    count = int(remaining_pass_count)
    terminal = float(configuration["final_thickness_mm"])
    action_min = float(configuration["legal_radial_removal_min_mm"])
    action_max = float(configuration["legal_radial_removal_max_mm"])
    downstream_min = terminal + (count - 1) * action_min
    downstream_max = terminal + (count - 1) * action_max
    model_max = float(configuration["workpiece_height_mm"]) / 10.0
    lower = max(action_min, state - downstream_max, state - model_max)
    upper = min(action_max, state - downstream_min)
    if lower > upper + 1e-12:
        raise RuntimeError(f"Empty continuous local transition interval at s={state}")

    limit = float(configuration["deflection_limit_um"])

    def margin(action: float) -> float:
        return pass_deflection_um(action, state - action, configuration) - limit

    probes = np.linspace(lower, upper, 257)
    deflections = np.asarray(
        [pass_deflection_um(float(action), state - float(action), configuration)
         for action in probes],
        dtype=float,
    )
    if np.min(np.diff(deflections)) < -1e-9:
        raise RuntimeError(
            f"Continuous local feasibility is not a monotone interval at s={state}"
        )
    if margin(lower) > 1e-9:
        raise RuntimeError(f"Recoverable state has no continuous feasible action at s={state}")
    if margin(upper) <= 0.0:
        return float(lower), float(upper)
    return float(lower), float(
        brentq(margin, lower, upper, xtol=2e-12, rtol=2e-14, maxiter=100)
    )


def _continuous_action_boundaries(
    states: np.ndarray,
    remaining_pass_count: int,
    configuration: dict,
    engine: ReoptimizationEngine,
) -> tuple[np.ndarray, np.ndarray]:
    """Rebuild the two curves formerly loaded from the EXP4 boundary table."""
    downstream_count = remaining_pass_count - 1
    downstream_lower = (
        float(configuration["final_thickness_mm"])
        + downstream_count * float(configuration["legal_radial_removal_min_mm"])
    )
    downstream_upper = float(
        engine.continuous_boundary(downstream_count)["continuous_boundary_mm"]
    )
    separating_boundary: list[float] = []
    upper_envelope: list[float] = []
    tolerance = float(configuration.get("boundary_tolerance_mm", 1e-7))
    for state in states:
        local_lower, local_upper = _continuous_local_feasible_interval(
            float(state), remaining_pass_count, configuration
        )
        preserving_lower = max(local_lower, float(state) - downstream_upper)
        preserving_upper = min(local_upper, float(state) - downstream_lower)
        if preserving_lower > preserving_upper + tolerance:
            raise RuntimeError(
                f"Recoverable state has no continuous preserving action at s={state}"
            )
        separating_boundary.append(float(preserving_lower))
        upper_envelope.append(float(preserving_upper))
    return (
        np.asarray(separating_boundary, dtype=float),
        np.asarray(upper_envelope, dtype=float),
    )


def _single_contiguous_region(
    domain_mm: np.ndarray,
    mask: np.ndarray,
    code: str,
    classification: str,
) -> dict[str, object]:
    indices = np.flatnonzero(mask)
    if indices.size == 0 or np.any(np.diff(indices) != 1):
        raise AssertionError(f"State region {code} must be nonempty and contiguous")
    return {
        "region": code,
        "classification": classification,
        "lower_state_mm": float(domain_mm[indices[0]]),
        "upper_state_mm": float(domain_mm[indices[-1]]),
        "state_count": int(indices.size),
    }


def _run_migration_check(
    migration_root: Path,
    region_rows: list[dict[str, object]],
    envelope,
    boundary_states: np.ndarray,
    preserving_lower: np.ndarray,
    feasible_upper: np.ndarray,
) -> dict[str, object]:
    """Compare recomputed values with legacy tables without making them inputs."""
    region_path = migration_root / "tables" / "EXP1_local_vs_global_regions.csv"
    cell_path = (
        migration_root / "exp4_action_envelope" / "tables"
        / "EXP4_state_action_details.csv"
    )
    curve_path = (
        migration_root / "exp4_action_envelope" / "tables"
        / "EXP4_continuous_discrete_action_boundaries.csv"
    )
    missing = [str(path) for path in (region_path, cell_path, curve_path) if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing migration-check tables:\n  - " + "\n  - ".join(missing)
        )

    with region_path.open("r", encoding="utf-8-sig", newline="") as handle:
        historical_regions = sorted(
            csv.DictReader(handle), key=lambda row: float(row["lower_state_mm"])
        )
    region_equivalent = len(historical_regions) == len(region_rows)
    if region_equivalent:
        for current, historical in zip(region_rows, historical_regions):
            region_equivalent = region_equivalent and (
                str(current["region"]) == historical["region"]
                and str(current["classification"]) == historical["classification"]
                and int(current["state_count"]) == int(historical["state_count"])
                and np.isclose(
                    float(current["lower_state_mm"]),
                    float(historical["lower_state_mm"]), rtol=0.0, atol=1e-12,
                )
                and np.isclose(
                    float(current["upper_state_mm"]),
                    float(historical["upper_state_mm"]), rtol=0.0, atol=1e-12,
                )
            )

    class_code = {
        "LOCAL_INFEASIBLE": INFEASIBLE,
        "LOCAL_FEASIBLE_RECOVERABILITY_PRESERVING": PRESERVING,
        "LOCAL_FEASIBLE_RECOVERABILITY_DESTROYING": DESTROYING,
    }
    seen = np.zeros(envelope.classes.shape, dtype=bool)
    cell_diff_count = 0
    historical_preserving = 0
    historical_destroying = 0
    selected_rows = 0
    with cell_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if int(row["remaining_pass_count"]) != envelope.pass_count:
                continue
            state_int = int(round(float(row["state_mm"]) * envelope.scale))
            action_int = int(round(float(row["action_mm"]) * envelope.scale))
            state_index = int(np.searchsorted(envelope.states_int, state_int))
            action_index = int(np.searchsorted(envelope.actions_int, action_int))
            if (
                state_index >= envelope.states_int.size
                or envelope.states_int[state_index] != state_int
                or action_index >= envelope.actions_int.size
                or envelope.actions_int[action_index] != action_int
            ):
                cell_diff_count += 1
                continue
            if seen[state_index, action_index]:
                raise AssertionError("Duplicate cell in historical EXP4 table")
            seen[state_index, action_index] = True
            selected_rows += 1
            historical_class = class_code[row["action_class"]]
            cell_diff_count += int(
                int(envelope.classes[state_index, action_index]) != historical_class
            )
            historical_preserving += int(historical_class == PRESERVING)
            historical_destroying += int(historical_class == DESTROYING)
    cell_diff_count += int(seen.size - np.count_nonzero(seen))

    with curve_path.open("r", encoding="utf-8-sig", newline="") as handle:
        curve_rows = sorted(
            (
                row for row in csv.DictReader(handle)
                if int(row["remaining_pass_count"]) == envelope.pass_count
            ),
            key=lambda row: float(row["state_mm"]),
        )
    historical_states = np.asarray([float(row["state_mm"]) for row in curve_rows])
    if not np.array_equal(
        np.rint(historical_states * envelope.scale).astype(np.int64),
        np.rint(boundary_states * envelope.scale).astype(np.int64),
    ):
        raise AssertionError("Historical and recomputed continuous-curve states differ")
    historical_lower = np.asarray([
        float(row["continuous_preserving_action_lower_mm"]) for row in curve_rows
    ])
    historical_upper = np.asarray([
        float(row["continuous_preserving_action_upper_mm"]) for row in curve_rows
    ])
    return {
        "PANEL_A_REGION_EQUIVALENCE": "PASS" if region_equivalent else "FAIL",
        "PANEL_B_CELL_DIFF_COUNT": int(cell_diff_count),
        "PANEL_B_PRESERVING_COUNT_DIFF": int(
            np.sum(envelope.classes == PRESERVING) - historical_preserving
        ),
        "PANEL_B_DESTROYING_COUNT_DIFF": int(
            np.sum(envelope.classes == DESTROYING) - historical_destroying
        ),
        "CONTINUOUS_UPPER_ENVELOPE_MAX_ABS_DIFF": float(
            np.max(np.abs(feasible_upper - historical_upper))
        ),
        "PRESERVING_DESTROYING_BOUNDARY_MAX_ABS_DIFF": float(
            np.max(np.abs(preserving_lower - historical_lower))
        ),
        "MIGRATION_CELL_ROW_COUNT": int(selected_rows),
    }


def build_state_action_structure_figure() -> dict[str, object]:
    """Build state/action structure solely from the public RPRA implementation."""
    configuration = load_configuration(SOURCE["3pass_100um.yaml"])
    remaining_pass_count = int(configuration["remaining_pass_count"])
    result, result_backward, result_envelope = configuration_results(configuration)
    backward = build_backward_set(remaining_pass_count, configuration)
    envelope = analyze_envelope(backward, configuration)
    if (
        int(result_backward["scale"]) != int(backward["scale"])
        or not np.array_equal(result_envelope.states_int, envelope.states_int)
        or not np.array_equal(result_envelope.actions_int, envelope.actions_int)
        or not np.array_equal(result_envelope.classes, envelope.classes)
    ):
        raise AssertionError("Canonical configuration and direct envelope paths differ")
    adopted_grid = float(backward["grid_mm"])
    scale = int(backward["scale"])
    domain_int = evaluated_states(backward, configuration)
    domain_mm = domain_int.astype(float) / scale
    local_ok = local_feasible_states(domain_int, configuration)
    recoverable = np.isin(
        domain_int,
        np.asarray(backward["stages_int"][remaining_pass_count], dtype=np.int64),
    )
    engine = ReoptimizationEngine(configuration)
    continuous_boundary = float(
        engine.continuous_boundary(remaining_pass_count)["continuous_boundary_mm"]
    )
    discrete_boundary = float(
        np.max(backward["stages_int"][remaining_pass_count]) / scale
    )

    grid_matches = [
        row for row in read_csv("grid_robustness.csv")
        if np.isclose(float(row["grid_mm"]), adopted_grid, rtol=0.0, atol=1e-12)
    ]
    if len(grid_matches) != 1:
        raise AssertionError("Expected one frozen grid-robustness row for the adopted grid")
    grid_row = grid_matches[0]
    continuous_boundary_diff = continuous_boundary - float(
        grid_row["continuous_boundary_mm"]
    )
    discrete_boundary_diff = discrete_boundary - float(grid_row["discrete_upper_mm"])

    conservative = local_ok & ~recoverable & (domain_mm <= continuous_boundary)
    irrecoverable = local_ok & (domain_mm > continuous_boundary)
    if not np.all(recoverable | conservative | irrecoverable):
        raise AssertionError("The three plotted regions must cover the evaluated domain")
    region_rows = [
        _single_contiguous_region(
            domain_mm, recoverable, "A",
            "LOCAL PASS / FULL REOPT PASS / RPRA PASS",
        ),
        _single_contiguous_region(
            domain_mm, conservative, "B", "CONSERVATIVE_DISCRETIZATION_BAND",
        ),
        _single_contiguous_region(
            domain_mm, irrecoverable, "C", "GENUINE_LOCAL_PASS_GLOBAL_FAIL",
        ),
    ]
    region_style = {
        "LOCAL PASS / FULL REOPT PASS / RPRA PASS":
            ("recoverable", "#E1EFE4"),
        "CONSERVATIVE_DISCRETIZATION_BAND":
            ("discretization band", "#F4E8C7"),
        "GENUINE_LOCAL_PASS_GLOBAL_FAIL":
            ("locally acceptable but irrecoverable", "#F4DEDE"),
    }
    paper_results = json.loads(
        SOURCE["paper_results.json"].read_text(encoding="utf-8")
    )["three_pass_100um"]
    for key, expected in paper_results.items():
        if key in result and int(result[key]) != int(expected):
            raise AssertionError(
                f"Canonical result {key}={result[key]} differs from expected {expected}"
            )
    region_by_code = {row["region"]: row for row in region_rows}
    if int(region_by_code["A"]["state_count"]) != int(paper_results["recoverable"]):
        raise AssertionError("EXP1 recoverable count does not match the frozen manuscript result")
    if int(region_by_code["C"]["state_count"]) != int(
        paper_results["local_feasible_irrecoverable"]
    ):
        raise AssertionError("EXP1 irrecoverable-region count does not match the manuscript")
    if sum(int(row["state_count"]) for row in region_rows) != int(
        paper_results["state_total"]
    ):
        raise AssertionError("EXP1 state-region counts do not cover the frozen domain")
    if not np.isclose(
        discrete_boundary,
        float(region_by_code["A"]["upper_state_mm"]),
        rtol=0.0,
        atol=1e-12,
    ):
        raise AssertionError("EXP1 recoverable endpoint and adopted discrete boundary differ")

    states = envelope.states_int.astype(float) / scale
    actions = envelope.actions_int.astype(float) / scale
    matrix = envelope.classes.T
    if states.size != int(paper_results["recoverable"]):
        raise AssertionError("EXP4 state count does not match the frozen manuscript result")
    if int(np.sum(matrix == PRESERVING)) != int(paper_results["preserving_actions"]):
        raise AssertionError("EXP4 preserving-action count does not match the manuscript")
    if int(np.sum(matrix == DESTROYING)) != int(paper_results["destroying_actions"]):
        raise AssertionError("EXP4 destroying-action count does not match the manuscript")

    boundary_states = states.copy()
    preserving_lower, feasible_upper = _continuous_action_boundaries(
        boundary_states, remaining_pass_count, configuration, engine
    )

    migration = {
        "PANEL_A_REGION_EQUIVALENCE": "NOT_RUN",
        "PANEL_B_CELL_DIFF_COUNT": "NOT_RUN",
        "PANEL_B_PRESERVING_COUNT_DIFF": "NOT_RUN",
        "PANEL_B_DESTROYING_COUNT_DIFF": "NOT_RUN",
        "CONTINUOUS_UPPER_ENVELOPE_MAX_ABS_DIFF": "NOT_RUN",
        "PRESERVING_DESTROYING_BOUNDARY_MAX_ABS_DIFF": "NOT_RUN",
    }
    if ARGS.migration_check_root is not None:
        migration = _run_migration_check(
            ARGS.migration_check_root.resolve(),
            region_rows,
            envelope,
            boundary_states,
            preserving_lower,
            feasible_upper,
        )
        equivalence_failed = (
            migration["PANEL_A_REGION_EQUIVALENCE"] != "PASS"
            or migration["PANEL_B_CELL_DIFF_COUNT"] != 0
            or migration["PANEL_B_PRESERVING_COUNT_DIFF"] != 0
            or migration["PANEL_B_DESTROYING_COUNT_DIFF"] != 0
            or migration["CONTINUOUS_UPPER_ENVELOPE_MAX_ABS_DIFF"] > 1e-12
            or migration["PRESERVING_DESTROYING_BOUNDARY_MAX_ABS_DIFF"] > 1e-12
        )
        if equivalence_failed:
            raise AssertionError(f"Scientific migration equivalence failed: {migration}")

    pale_gray = "#E8ECEF"
    green = "#3A7D44"
    red = "#B6423A"
    blue = "#2C6EAA"
    ink = "#20252B"
    state_half_step = _uniform_half_step(states, "canonical state values")
    action_half_step = _uniform_half_step(actions, "canonical action values")

    with plt.rc_context({"pdf.fonttype": 42, "ps.fonttype": 42}):
        fig, (state_axis, action_axis) = plt.subplots(
            1,
            2,
            figsize=(7.15, 2.85),
            gridspec_kw={"width_ratios": [0.95, 1.55]},
        )

        for row in region_rows:
            label, color = region_style[row["classification"]]
            state_axis.axvspan(
                float(row["lower_state_mm"]),
                float(row["upper_state_mm"]),
                color=color,
                ec=ink,
                linewidth=0.6,
                label=label,
            )
        state_axis.axvline(
            continuous_boundary,
            color=blue,
            linestyle="--",
            linewidth=1.2,
            label="continuous boundary",
        )
        state_axis.axvline(
            discrete_boundary,
            color=ink,
            linestyle=":",
            linewidth=1.2,
            label="discrete boundary",
        )
        state_axis.set_xlim(
            min(float(row["lower_state_mm"]) for row in region_rows),
            max(float(row["upper_state_mm"]) for row in region_rows),
        )
        state_axis.set_ylim(0.0, 1.0)
        state_axis.set_yticks([])
        state_axis.set_xlabel("WIP thickness, $s$ [mm]")
        panel_title(state_axis, "(a) State-level decision structure")
        state_axis.legend(
            loc="upper left",
            frameon=False,
            fontsize=8,
            handlelength=1.55,
            borderpad=0.15,
            labelspacing=0.25,
        )

        colors = (pale_gray, green, red)
        vertices: list[list[tuple[float, float]]] = []
        facecolors: list[str] = []
        for row_index, action in enumerate(actions):
            row = matrix[row_index]
            run_start = 0
            for column_index in range(1, states.size + 1):
                if column_index == states.size or row[column_index] != row[run_start]:
                    x0 = float(states[run_start] - state_half_step)
                    x1 = float(states[column_index - 1] + state_half_step)
                    y0 = float(action - action_half_step)
                    y1 = float(action + action_half_step)
                    vertices.append([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])
                    facecolors.append(colors[int(row[run_start])])
                    run_start = column_index
        action_axis.add_collection(
            PolyCollection(
                vertices,
                facecolors=facecolors,
                edgecolors="none",
                rasterized=False,
            )
        )
        lower_line, = action_axis.plot(
            boundary_states,
            preserving_lower,
            color=ink,
            linewidth=1.15,
            label="preserving/destroying boundary",
        )
        upper_line, = action_axis.plot(
            boundary_states,
            feasible_upper,
            color=ink,
            linewidth=1.15,
            linestyle="--",
            label="upper feasible envelope",
        )
        action_axis.set_xlim(states[0] - state_half_step, states[-1] + state_half_step)
        action_axis.set_ylim(actions[0] - action_half_step, actions[-1] + action_half_step)
        action_axis.set_xlabel("WIP thickness, $s$ [mm]")
        action_axis.set_ylabel("Radial material-removal action, $u$ [mm]")
        panel_title(action_axis, "(b) State-indexed action envelope")
        action_axis.legend(
            handles=[
                Patch(facecolor=pale_gray, edgecolor="none", label="locally infeasible"),
                Patch(facecolor=green, edgecolor="none", label="recoverability-preserving"),
                Patch(facecolor=red, edgecolor="none", label="recoverability-destroying"),
                Line2D([], [], color=upper_line.get_color(), linestyle="--",
                       linewidth=1.15, label="upper feasible envelope"),
                Line2D([], [], color=lower_line.get_color(), linestyle="-",
                       linewidth=1.15, label="preserving/destroying boundary"),
            ],
            loc="upper left",
            frameon=True,
            fontsize=8,
            handlelength=1.55,
            borderpad=0.3,
            labelspacing=0.25,
        )

        fig.subplots_adjust(
            left=0.075,
            right=0.995,
            bottom=0.22,
            top=0.86,
            wspace=0.32,
        )
        stem = "Fig_state_action_structure_900dpi"
        fig.savefig(
            OUT / f"{stem}.png",
            dpi=900,
            bbox_inches="tight",
            pad_inches=0.04,
            facecolor="white",
        )
        fig.savefig(
            OUT / f"{stem}.tif",
            dpi=900,
            bbox_inches="tight",
            pad_inches=0.04,
            facecolor="white",
            pil_kwargs={"compression": "tiff_lzw"},
        )
        fig.savefig(
            OUT / f"{stem}.pdf",
            bbox_inches="tight",
            pad_inches=0.04,
            facecolor="white",
            metadata={
                "Creator": "scripts/build_rineng_data_figures.py",
                "CreationDate": None,
                "ModDate": None,
            },
        )
        plt.close(fig)

    return {
        "remaining_pass_count": remaining_pass_count,
        "adopted_grid_mm": adopted_grid,
        "continuous_boundary_mm": continuous_boundary,
        "discrete_boundary_mm": discrete_boundary,
        "state_count": int(sum(int(row["state_count"]) for row in region_rows)),
        "recoverable_state_count": int(states.size),
        "preserving_action_count": int(np.sum(matrix == PRESERVING)),
        "destroying_action_count": int(np.sum(matrix == DESTROYING)),
        "PANEL_A_REGION_EQUIVALENCE": migration["PANEL_A_REGION_EQUIVALENCE"],
        "PANEL_A_CONTINUOUS_BOUNDARY_DIFF": float(continuous_boundary_diff),
        "PANEL_A_DISCRETE_BOUNDARY_DIFF": float(discrete_boundary_diff),
        "PANEL_B_CELL_DIFF_COUNT": migration["PANEL_B_CELL_DIFF_COUNT"],
        "PANEL_B_PRESERVING_COUNT_DIFF": migration["PANEL_B_PRESERVING_COUNT_DIFF"],
        "PANEL_B_DESTROYING_COUNT_DIFF": migration["PANEL_B_DESTROYING_COUNT_DIFF"],
        "CONTINUOUS_UPPER_ENVELOPE_MAX_ABS_DIFF": migration[
            "CONTINUOUS_UPPER_ENVELOPE_MAX_ABS_DIFF"
        ],
        "PRESERVING_DESTROYING_BOUNDARY_MAX_ABS_DIFF": migration[
            "PRESERVING_DESTROYING_BOUNDARY_MAX_ABS_DIFF"
        ],
    }


state_action_audit = build_state_action_structure_figure()

print(f"Generated {len(list(OUT.glob('*.png')))} PNG, {len(list(OUT.glob('*.tif')))} TIFF, "
      f"and {len(list(OUT.glob('*.pdf')))} PDF files.")
print("STATE_ACTION_STRUCTURE=PASS")
print(f"STATE_ACTION_AUDIT={json.dumps(state_action_audit, sort_keys=True)}")
for key in (
    "PANEL_A_REGION_EQUIVALENCE",
    "PANEL_A_CONTINUOUS_BOUNDARY_DIFF",
    "PANEL_A_DISCRETE_BOUNDARY_DIFF",
    "PANEL_B_CELL_DIFF_COUNT",
    "PANEL_B_PRESERVING_COUNT_DIFF",
    "PANEL_B_DESTROYING_COUNT_DIFF",
    "CONTINUOUS_UPPER_ENVELOPE_MAX_ABS_DIFF",
    "PRESERVING_DESTROYING_BOUNDARY_MAX_ABS_DIFF",
):
    print(f"{key}={state_action_audit[key]}")

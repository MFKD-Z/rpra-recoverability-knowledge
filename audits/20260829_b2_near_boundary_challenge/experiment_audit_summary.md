# B2 Experiment Output Audit Summary

Decision question: Do the retained formal outputs support the bounded statement that, for the frozen scalar `3pass_100um` case, exact upward-mapped discrete RPRA status tracks the continuous `m=3` boundary without optimistic false acceptance over the predeclared ±20 µm challenge?

Overall grade: **ready for manuscript** within the evidence-supported claim boundary below. No manuscript integration was performed in this task.

## Raw experimental facts

- The recomputed continuous boundary is `4.588030453165504 mm`, exactly matching the frozen serialized reference at the reported precision.
- The challenge contains all 161 predeclared offsets from −20 to +20 µm at 0.25 µm spacing. The detail table contains all `161 × 5 = 805` state-grid comparisons.
- The continuous audit contains 161 challenge-state records plus one boundary-root record. Numerical unresolved count is zero.
- Agreement counts from coarse to fine are `112`, `144`, `152`, `154`, and `158` of 161.
- Conservative false-rejection counts are `49`, `17`, `9`, `7`, and `3`. Optimistic false-acceptance count is zero at every grid.
- Maximum misclassification distances are `12`, `4`, `2`, `1.5`, and `0.5 µm`; the corresponding discrete boundary under-approximations are `12.030453`, `4.030453`, `2.030453`, `1.530453`, and `0.530453 µm`.
- Frozen 400-state audit hashes are unchanged. Pytest, quick reproduction, full reproduction, and `git diff --check` all pass. The public `v1.1.0` tag/reference is unchanged.

## Statistical diagnostics

- This is a deterministic finite enumeration, not a random sample or inferential study; a random seed is therefore not applicable. All predeclared points and grids are retained, limiting result-dependent selection risk.
- The frozen config exists and is hashed in `B2_environment.json`. The baseline comparison is fair because HEAD equals the declared scientific baseline and tracked files were clean before and after execution.
- Metric definitions are consistent across grids and cumulative windows. Each overall row reconciles exactly as agreement + false rejection + false acceptance + unresolved = 161.
- Unit scaling is explicit: states/grids are in millimetres; offsets, mapping deltas, margins, and boundary displacement are in micrometres.
- Summary and report values trace to the 805-row detail table; continuous classifications trace to the 162-row solver audit. No figure was generated, so figure/table consistency is not applicable.
- The nonzero coarse-grid disagreement is retained rather than hidden. It is entirely conservative and confined to the discrete-to-continuous boundary gap.

## Paper framing recommendations

Recommended wording: “For the frozen scalar three-pass case, a deterministic 161-state challenge within ±20 µm of the recomputed continuous boundary found zero optimistic false acceptances at all five declared grids. Disagreements were conservative false rejections confined to the grid-specific boundary under-approximation, decreasing from 49 cases at 0.004 mm to 3 cases at 0.00025 mm.”

Evidence-supported claim boundary: numerical classification fidelity near the continuous boundary for the frozen `3pass_100um`, `m=3` configuration, the five declared grids, exact upward mapping, and the fixed deterministic challenge set.

## Unsupported or exaggerated conclusions

Avoid wording that claims a general convergence theorem, universal conservative mapping, cross-configuration validity, physical validation, uncertainty robustness, or independence from the frozen solver/model assumptions. Do not describe aggregate agreement as uniformly high without also reporting the 49 coarse-grid conservative false rejections.

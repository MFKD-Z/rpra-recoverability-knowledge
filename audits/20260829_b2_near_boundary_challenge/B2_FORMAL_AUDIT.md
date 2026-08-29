# B2 Near-Boundary Challenge Formal Audit

## Scope and freeze

- Task: frozen numerical-fidelity stress test for the scalar three-pass case only.
- Baseline commit: `c25540909939f65fad732420fa484f52931c02f9` (observed `c25540909939f65fad732420fa484f52931c02f9`).
- Public tag `v1.1.0` before/after: `c25540909939f65fad732420fa484f52931c02f9` / `c25540909939f65fad732420fa484f52931c02f9`.
- Frozen configuration: `configs/3pass_100um.yaml`; `m=3`.
- Challenge: 161 deterministic states at `s* ± 20 µm`, spaced by `0.25 µm`.
- Retrieval: exact Decimal ceiling to the next grid node; no tolerance-adjusted helper.
- Continuous reference: direct frozen `ReoptimizationEngine.optimize(state, 3)` call for every state.
- No manuscript, `src/rpra/`, config, expected-result, solver-setting, or public-tag edit was made.

## Result

The continuous boundary is `4.588030453165504 mm`; the frozen reference is
`4.588030453165504 mm`, so the existing tolerance gate is
`PASS`. All 805 state-grid comparisons and
all 161 challenge-state solver records (plus one boundary-root solver record) are
retained. The formal classification is `B2_STRONG_SUPPORT`.

| Grid (mm) | Agreement | False rejection | False acceptance | Max error distance (µm) | Boundary under-approx. (µm) |
|---:|---:|---:|---:|---:|---:|
| 0.004 | 112/161 | 49 | 0 | 12.000000 | 12.030453 |
| 0.002 | 144/161 | 17 | 0 | 4.000000 | 4.030453 |
| 0.001 | 152/161 | 9 | 0 | 2.000000 | 2.030453 |
| 0.0005 | 154/161 | 7 | 0 | 1.500000 | 1.530453 |
| 0.00025 | 158/161 | 3 | 0 | 0.500000 | 0.530453 |

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

| Gate | Status |
|---|---|
| FROZEN_400_STATE_AUDIT | PASS |
| PYTEST | PASS |
| QUICK_REPRODUCTION | PASS |
| FULL_REPRODUCTION | PASS |
| GIT_DIFF_CHECK | PASS |

- Frozen 400-state output hashes unchanged: `true`.
- Public tag/reference modified: `false`.
- Tracked working-tree diff after the run: `NONE`.

## Required return block

```text
TASK_STATUS=COMPLETE
BASELINE_COMMIT=c25540909939f65fad732420fa484f52931c02f9
WORKING_COMMIT=UNCOMMITTED@c25540909939f65fad732420fa484f52931c02f9
B2_CLASSIFICATION=B2_STRONG_SUPPORT
CONTINUOUS_BOUNDARY_MM=4.588030453165504
CHALLENGE_STATE_COUNT=161
DETAIL_ROW_COUNT=805
GRID_0P004_AGREEMENT=112/161
GRID_0P004_FALSE_REJECTION=49
GRID_0P004_FALSE_ACCEPTANCE=0
GRID_0P002_AGREEMENT=144/161
GRID_0P002_FALSE_REJECTION=17
GRID_0P002_FALSE_ACCEPTANCE=0
GRID_0P001_AGREEMENT=152/161
GRID_0P001_FALSE_REJECTION=9
GRID_0P001_FALSE_ACCEPTANCE=0
GRID_0P0005_AGREEMENT=154/161
GRID_0P0005_FALSE_REJECTION=7
GRID_0P0005_FALSE_ACCEPTANCE=0
GRID_0P00025_AGREEMENT=158/161
GRID_0P00025_FALSE_REJECTION=3
GRID_0P00025_FALSE_ACCEPTANCE=0
MAX_MISCLASSIFICATION_DISTANCE_UM=12.000000000000
NUMERICAL_UNRESOLVED_COUNT=0
FROZEN_400_STATE_AUDIT_UNCHANGED=PASS
PYTEST=PASS
QUICK_REPRODUCTION=PASS
FULL_REPRODUCTION=PASS
GIT_DIFF_CHECK=PASS
PUBLIC_V1_1_0_MODIFIED=false
REMAINING_BLOCKERS=NONE
```

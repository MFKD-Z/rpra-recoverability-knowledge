# RINENG B1 ONLINE-REOPT Comparator Formal Audit

## Scope and frozen provenance

- Scientific baseline and frozen public tag target: `c25540909939f65fad732420fa484f52931c02f9` / `v1.1.0`.
- Primary configuration: `configs/3pass_100um.yaml`.
- The harness is isolated under `scripts/`; `src/rpra/`, frozen expected results,
  the manuscript, and public release metadata were not edited.
- The original standalone design-freeze attachment was not present on disk.
  Its generating task (`6a90ec87-948c-83e9-944e-98bbf48766ba`) and the external
  Codex Goal (SHA-256 `e99ec07e7f8f3d1dcd7748abd85c11961a026510b038d2cc0ed466faf1b72abb`) were
  cross-checked before the run. Both freeze the same comparator, search rule,
  domain, timing subset, failure handling, and prohibitions.

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
`PASS` with
`0` mismatches. The primary
online compute metric counts the uncached calls that the specified online
candidate search would require, independent of memo hits.

## Formal-domain results

- Recoverable starts: 407.
- Exact first actions: 140/407.
- RPRA completion: 407/407.
- ONLINE-REOPT completion: 139/407.
- Full action-sequence agreement: 139/407.
- RPRA-selected continuous-infeasible actions across rollouts:
  0.
- ONLINE-selected actions rejected by discrete downstream membership across
  rollouts: 0.
- Numerical unresolved count: 187.
- First-decision online solve calls over all 407 starts:
  10741.
- Frozen 4.442-mm mechanism unchanged:
  True.

Action differences are absolute micrometres over all matched first decisions.
Immediate-deflection deltas are signed as ONLINE-REOPT minus RPRA over the same
domain.

## Timing

The subset is exactly `unique(round(linspace(0, 406, 41)))` over ascending
recoverable starts. Each policy/state has one warm-up and five measured full
first-decision calls. ONLINE-REOPT caching is disabled. Reported medians pool
the 205 measured calls per policy; all warm-up and measured rows are retained.

- RPRA pooled median: 0.1731 ms.
- ONLINE-REOPT pooled median: 1644.1286 ms.
- Environment matches frozen E3: PASS.

## Regression and final status

```text
TASK_STATUS=B1_NUMERICALLY_UNRESOLVED
BASELINE_COMMIT=c25540909939f65fad732420fa484f52931c02f9
WORKING_COMMIT=43819fd4d21e440f9e7d8ea3bacffdad62732797
B1_CLASSIFICATION=B1_NUMERICALLY_UNRESOLVED
FIRST_DECISION_ROWS=407
RPRA_COMPLETION=407/407
ONLINE_REOPT_COMPLETION=139/407
EXACT_FIRST_ACTION_AGREEMENT=140/407
RPRA_SELECTED_CONTINUOUS_INFEASIBLE_COUNT=0
ONLINE_SELECTED_DISCRETE_REJECTED_COUNT=0
NUMERICAL_UNRESOLVED_COUNT=187
ONLINE_REOPT_TOTAL_SOLVE_CALLS_FIRST_DECISION_DOMAIN=10741
FULL_SEQUENCE_AGREEMENT=139/407
ACTION_DIFFERENCE_MEDIAN_UM=0
ACTION_DIFFERENCE_P95_UM=0
IMMEDIATE_DEFLECTION_DELTA_MEDIAN_UM=0
TIMING_SUBSET_SIZE=41
RPRA_DECISION_MEDIAN_MS=0.1731
ONLINE_REOPT_DECISION_MEDIAN_MS=1644.1286
ENVIRONMENT_MATCHES_FROZEN_E3=PASS
PYTEST=PENDING
QUICK_REPRODUCTION=PENDING
FULL_REPRODUCTION=PENDING
GIT_DIFF_CHECK=PENDING
PUBLIC_V1_1_0_MODIFIED=false
REMAINING_BLOCKERS=NUMERICAL_UNRESOLVED;PYTEST_PENDING;QUICK_REPRODUCTION_PENDING;FULL_REPRODUCTION_PENDING;GIT_DIFF_CHECK_PENDING
```

## Created audit files

- `B1_first_action_comparator.csv`
- `B1_rollout_trajectories.csv`
- `B1_summary.json`
- `B1_disagreement_audit.csv`
- `B1_timing_raw.csv`
- `B1_environment.json`
- `B1_FORMAL_AUDIT.md`
- `../../scripts/run_b1_online_reopt_comparator.py`

# RINENG B1 ONLINE-REOPT Comparator Formal Audit

## Scope and frozen provenance

- Scientific baseline and frozen public tag target: `c25540909939f65fad732420fa484f52931c02f9` / `v1.1.0`.
- Primary configuration: `configs/3pass_100um.yaml`.
- The harness is isolated under `scripts/`; `src/rpra/`, frozen expected results,
  the manuscript, and public release metadata were not edited.
- Design freeze SHA-256: `eebbfcd6a88ec111f86013231bb81da74c545d3507a205165a6cb30aa877e061`.
- External Codex Goal SHA-256: `e99ec07e7f8f3d1dcd7748abd85c11961a026510b038d2cc0ed466faf1b72abb`.
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
`PASS` with
`0` mismatches. The primary
online compute metric counts the uncached calls that the specified online
candidate search would require, independent of memo hits.

## Formal-domain results

- Recoverable starts: 407.
- Exact first actions: 407/407.
- RPRA completion: 407/407.
- ONLINE-REOPT completion: 407/407.
- Full action-sequence agreement: 407/407.
- RPRA-selected continuous-infeasible actions across rollouts:
  0.
- ONLINE-selected actions rejected by discrete downstream membership across
  rollouts: 0.
- Numerical unresolved count: 0.
- First-decision online solve calls over all 407 starts:
  42312.
- Frozen 4.442-mm mechanism unchanged:
  True.

Action differences are absolute micrometres over all matched first decisions.
Immediate-deflection deltas follow the frozen definition, RPRA minus
ONLINE-REOPT, over the same domain.

## Timing

The subset is exactly `unique(round(linspace(0, 406, 41)))` over ascending
recoverable starts. Each policy/state has one warm-up and five measured full
first-decision calls. ONLINE-REOPT caching is disabled. Reported medians pool
the 205 measured calls per policy; all warm-up and measured rows are retained.

- RPRA pooled median/IQR/P95: 0.1717 /
  0.0156 / 0.21758 ms.
- ONLINE-REOPT pooled median/IQR/P95: 7080.9788 /
  15598.2814 / 23069.61692 ms.
- Environment matches frozen E3: PASS.

## Regression and final status

```text
TASK_STATUS=COMPLETE
BASELINE_COMMIT=c25540909939f65fad732420fa484f52931c02f9
WORKING_COMMIT=dc38b09d97b7f24f01010931af042d1993959ceb
B1_CLASSIFICATION=B1_STRONG_SUPPORT
FIRST_DECISION_ROWS=407
RPRA_COMPLETION=407/407
ONLINE_REOPT_COMPLETION=407/407
EXACT_FIRST_ACTION_AGREEMENT=407/407
RPRA_SELECTED_CONTINUOUS_INFEASIBLE_COUNT=0
ONLINE_SELECTED_DISCRETE_REJECTED_COUNT=0
NUMERICAL_UNRESOLVED_COUNT=0
ONLINE_REOPT_TOTAL_SOLVE_CALLS_FIRST_DECISION_DOMAIN=42312
FULL_SEQUENCE_AGREEMENT=407/407
ACTION_DIFFERENCE_MEDIAN_UM=0
ACTION_DIFFERENCE_P95_UM=0
IMMEDIATE_DEFLECTION_DELTA_MEDIAN_UM=0
TIMING_SUBSET_SIZE=41
RPRA_DECISION_MEDIAN_MS=0.1717
ONLINE_REOPT_DECISION_MEDIAN_MS=7080.9788
ENVIRONMENT_MATCHES_FROZEN_E3=PASS
PYTEST=PASS
QUICK_REPRODUCTION=PASS
FULL_REPRODUCTION=PASS
GIT_DIFF_CHECK=PASS
PUBLIC_V1_1_0_MODIFIED=false
REMAINING_BLOCKERS=NONE
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

# B3 Terminal-Tolerance Sensitivity Formal Audit

## Scope and protocol

This audit executes the frozen B3 design only. The production RPRA implementation,
configuration, expected results, manuscript, and public `v1.1.0` content were not
changed. The only analytical change is the preregistered inclusive terminal base
set for `T0`, `T5`, `T10`, and `T20`; the state/action grid remains 0.001 mm and
all metrics use the fixed 621-state evaluation domain `[4.180, 4.800]` mm.

The rollout population is the intersection of each tolerance-specific `R3` with
that frozen evaluation domain. Failure rows and incomplete trajectories are kept
in `B3_rollout_trajectories.csv`; no cases, states, or actions were excluded.

## Results

| Case | |L| | |R| | |L \ R| | Mixed | All preserving | Preserving actions | Destroying actions | Myopic completion | RPRA completion |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| T0 | 621 | 407 | 214 | 289 | 118 | 31549 | 41905 | 3/407 | 407/407 |
| T5 | 621 | 419 | 202 | 293 | 126 | 35089 | 43071 | 9/419 | 419/419 |
| T10 | 621 | 431 | 190 | 431 | 0 | 38454 | 44419 | 16/431 | 431/431 |
| T20 | 621 | 457 | 164 | 457 | 0 | 43874 | 49054 | 29/457 | 457/457 |

`B3_CLASSIFICATION=B3_STRONG_SUPPORT`

The declared local-versus-recoverable and preserving-versus-destroying structure
is interpreted only within this frozen scalar three-pass case. This is not
uncertainty robustness, measurement-error tolerance, physical validation,
cross-configuration generality, or a tolerance-design theory.

## Regression gates

- T0 frozen state/action counts: PASS
- T0 MYOPIC completion `3/407`: PASS
- T0 RPRA completion `407/407`: PASS
- Frozen 4.442-mm mechanism: PASS
- pytest: PASS
- quick reproduction: PASS
- full reproduction: PASS
- git diff --check: PASS
- public v1.1.0 protected content unchanged: PASS
- independent output audit: PASS

## Governance status

The C*-Focused Action Registry, Canonicalizer, detector, held-out, FOR, and cluster
bootstrap fields are not part of this RPRA experiment and are `NOT_APPLICABLE`.
The applicable freeze, fixed-denominator, no-exclusion, provenance, and regression
controls are satisfied as recorded above. This corrective rerun changes only
evidence granularity and the required report block; it does not change a verdict
boundary or any frozen experiment semantics.

```text
TASK_STATUS=PASS
BASELINE_COMMIT=c25540909939f65fad732420fa484f52931c02f9
WORKING_COMMIT=c25540909939f65fad732420fa484f52931c02f9
B3_CLASSIFICATION=B3_STRONG_SUPPORT

T0_LOCAL_FEASIBLE=621
T0_RECOVERABLE=407
T0_LOCAL_BUT_IRRECOVERABLE=214
T0_MIXED_ACTION=289
T0_MYOPIC_COMPLETION=3/407
T0_RPRA_COMPLETION=407/407

T5_LOCAL_FEASIBLE=621
T5_RECOVERABLE=419
T5_LOCAL_BUT_IRRECOVERABLE=202
T5_MIXED_ACTION=293
T5_MYOPIC_COMPLETION=9/419
T5_RPRA_COMPLETION=419/419

T10_LOCAL_FEASIBLE=621
T10_RECOVERABLE=431
T10_LOCAL_BUT_IRRECOVERABLE=190
T10_MIXED_ACTION=431
T10_MYOPIC_COMPLETION=16/431
T10_RPRA_COMPLETION=431/431

T20_LOCAL_FEASIBLE=621
T20_RECOVERABLE=457
T20_LOCAL_BUT_IRRECOVERABLE=164
T20_MIXED_ACTION=457
T20_MYOPIC_COMPLETION=29/457
T20_RPRA_COMPLETION=457/457

T0_BASELINE_REGRESSION=PASS
MECHANISM_4P442_UNCHANGED=PASS
PYTEST=PASS
QUICK_REPRODUCTION=PASS
FULL_REPRODUCTION=PASS
GIT_DIFF_CHECK=PASS
PUBLIC_V1_1_0_MODIFIED=false
REMAINING_BLOCKERS=NONE

TERMINAL_CASE_COUNT=4
EVALUATION_STATE_COUNT_PER_CASE=621
STATE_ACTION_AUDIT_ROW_COUNT=1343844
ROLLOUT_TRAJECTORY_ROW_COUNT=10284
EXCLUDED_CASE_COUNT=0
EXCLUDED_STATE_COUNT=0
EXCLUDED_ACTION_COUNT=0
FAILURE_ROWS_RETAINED=true
INFEASIBLE_ACTION_ROWS_RETAINED=true
NO_CHANGE_ROWS_RETAINED=true
EXPERIMENT_OUTPUT_AUDITOR_STATUS=PASS
```

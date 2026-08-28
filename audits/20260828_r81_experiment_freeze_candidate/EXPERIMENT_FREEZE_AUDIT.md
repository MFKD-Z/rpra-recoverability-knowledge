# R8.1 Main-Line Experiment Freeze Candidate Audit

## Scope and provenance

- Frozen configuration: `configs/3pass_100um.yaml`
- `GIT_COMMIT_BEFORE=1df7638583f1c9f0bc57a4ab5d9d61326c49d0d6`
- `GIT_STATUS_BEFORE=?? AEI_SUBMISSION_FREEZE.md | ?? scripts/reproduce_rineng_figures.py`
- Baseline before experiment changes: `pytest -q` PASS (10 tests); quick reproduction PASS.
- No RPRA definition, Morelli model, frozen expected result, manuscript, supplementary manuscript, README/CITATION/release metadata, or numerical tolerance was modified.
- The existing untracked files named in `GIT_STATUS_BEFORE` were left untouched.

## E1 — decision consequence

Both policies minimize the same immediate Morelli deflection. The myopic policy uses the frozen local-feasibility mask; the RPRA policy differs only by intersecting that mask with exact downstream membership. Objective ties within `decision_tolerance_um` select the smaller radial-removal action.

- Recoverable start states audited: 407
- First-action rows: 407; rollout trajectory rows: 2442
- Myopic first actions: 118 preserving, 289 destroying (0.710073710074).
- Myopic completions: 3 (0.00737100737101); failures: `{"NO_LOCALLY_FEASIBLE_ACTION_M1": 404}`.
- RPRA completions: 407 (1); invariant violations: 0.
- Deflection sacrifice over all starts (mean/median/P95/max, µm): 21.3023296647 / 17.4939198216 / 56.2330381477 / 60.6540763821.
- Selected actions differ in 289 states. Conditional sacrifice (mean/median/P95/max, µm): 30.0001666904 / 29.785467292 / 57.5157316888 / 60.6540763821.
- Frozen mechanism: 0.432 → 4.010 DESTROYING; 0.557 → 3.885 PRESERVING; unchanged = True.

`E1_GATE=PASS`

## E2 — controlled analytical-condition robustness

| configuration | status | STATE_TOTAL | LOCAL_ACCEPTABLE_COUNT | RECOVERABLE_COUNT | LOCAL_BUT_IRRECOVERABLE_COUNT | MIXED_ACTION_STATE_COUNT | MYOPIC_FIRST_ACTION_DESTROYING_COUNT |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E2_BASELINE | VALID | 621 | 621 | 407 | 214 | 289 | 289 |
| E2_FZ_LOW | VALID | 621 | 621 | 592 | 29 | 386 | 386 |
| E2_FZ_HIGH | VALID | 621 | 621 | 0 | 621 | 0 | 0 |
| E2_AP_LOW | VALID | 621 | 621 | 451 | 170 | 312 | 312 |
| E2_AP_HIGH | VALID | 621 | 621 | 0 | 621 | 0 | 0 |

All four additional variants were predeclared. This is controlled analytical-condition robustness only—not experimental physical validation, uncertainty quantification, Monte Carlo evidence, or a generality claim.

The E2 baseline exact represented-set difference is 214 (`|L₃,h \ R₃,h|`). The frozen quick-reproduction value 212 is unchanged and uses the existing continuous-boundary publication helper; the two values answer different formally defined classifications and are not a regression mismatch.

- Valid predeclared variants: E2_FZ_LOW,E2_FZ_HIGH,E2_AP_LOW,E2_AP_HIGH
- Invalid-domain predeclared variants: NONE
- State-level separation persists in: E2_FZ_LOW,E2_FZ_HIGH,E2_AP_LOW,E2_AP_HIGH
- Mixed preserving/destroying action structure persists in: E2_FZ_LOW,E2_AP_LOW

`E2_GATE=PASS`

## E3 — RPRA core construction timing

One warm-up and 5 measured repetitions were used for every case. `time.perf_counter_ns()` was placed externally around `build_backward_set()` and `analyze_envelope()`. CSV cells retain all raw repetitions in addition to median and IQR. RDF work is excluded.

### Grid scaling

| GRID_MM | ACTION_GRID_COUNT | R0_STATE_COUNT | R1_STATE_COUNT | R2_STATE_COUNT | R3_STATE_COUNT | TOTAL_TRANSITION_COUNT | ENVELOPE_CELL_COUNT | BACKWARD_MEDIAN_MS | BACKWARD_IQR_MS | ENVELOPE_MEDIAN_MS | ENVELOPE_IQR_MS | TOTAL_CORE_MEDIAN_MS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.004 | 136 | 1 | 1 | 29 | 100 | 1972 | 13600 | 3.5655 | 0.024499999999999744 | 10.5656 | 0.44570000000000043 | 14.0308 |
| 0.002 | 271 | 1 | 2 | 59 | 203 | 8014 | 55013 | 6.5017 | 0.043099999999999916 | 21.6308 | 0.06099999999999994 | 28.1681 |
| 0.001 | 541 | 1 | 3 | 118 | 407 | 31898 | 220187 | 13.7327 | 0.1623000000000001 | 47.7165 | 0.7702999999999989 | 61.8811 |
| 0.0005 | 1081 | 1 | 5 | 235 | 814 | 126703 | 879934 | 29.6286 | 0.034199999999998454 | 112.6455 | 4.935199999999995 | 144.1812 |
| 0.00025 | 2161 | 1 | 10 | 471 | 1631 | 507832 | 3524591 | 70.125 | 2.124500000000012 | 281.0841 | 4.924800000000005 | 352.5967 |

### Horizon scaling

| PASS_COUNT | R_K_STATE_COUNTS | TOTAL_TRANSITION_COUNT | ENVELOPE_CELL_COUNT | BACKWARD_MEDIAN_MS | BACKWARD_IQR_MS | ENVELOPE_MEDIAN_MS | ENVELOPE_IQR_MS | TOTAL_CORE_MEDIAN_MS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | {"0":1,"1":3} | 3 | 1623 | 0.1441 | 0.001700000000000007 | 0.4242 | 0.07329999999999998 | 0.5804 |
| 2 | {"0":1,"1":3,"2":118} | 349 | 63838 | 0.5241 | 0.03649999999999998 | 12.6935 | 0.08110000000000106 | 13.249 |
| 3 | {"0":1,"1":3,"2":118,"3":407} | 31898 | 220187 | 13.6677 | 0.09779999999999944 | 46.708 | 0.36479999999999535 | 60.3266 |
| 4 | {"0":1,"1":3,"2":118,"3":407,"4":947} | 227187 | 512327 | 59.8788 | 1.4842999999999975 | 119.1767 | 0.5772999999999939 | 178.8355 |

These are descriptive measurements for the recorded environment. No real-time guarantee or asymptotic scaling-law claim is made.

`E3_GATE=PASS`

## Regression and freeze decision

```text
TASK_STATUS=COMPLETE

GIT_COMMIT_BEFORE=1df7638583f1c9f0bc57a4ab5d9d61326c49d0d6
GIT_COMMIT_AFTER=UNCOMMITTED
PUSH=false

E1_GATE=PASS
E1_RECOVERABLE_START_STATES=407
E1_MYOPIC_FIRST_ACTION_DESTROYING_COUNT=289
E1_MYOPIC_FIRST_ACTION_DESTROYING_RATE=0.710073710074
E1_MYOPIC_COMPLETION_COUNT=3
E1_MYOPIC_COMPLETION_RATE=0.00737100737101
E1_RPRA_COMPLETION_COUNT=407
E1_RPRA_COMPLETION_RATE=1
E1_RPRA_INVARIANT_VIOLATION_COUNT=0
E1_DEFLECTION_SACRIFICE_MEDIAN_UM=17.4939198216
E1_DEFLECTION_SACRIFICE_P95_UM=56.2330381477
E1_DEFLECTION_SACRIFICE_MAX_UM=60.6540763821

E2_GATE=PASS
E2_VALID_VARIANTS=E2_FZ_LOW,E2_FZ_HIGH,E2_AP_LOW,E2_AP_HIGH
E2_INVALID_DOMAIN_VARIANTS=NONE
E2_STATE_SEPARATION_PERSISTS_IN=E2_FZ_LOW,E2_FZ_HIGH,E2_AP_LOW,E2_AP_HIGH
E2_MIXED_ACTION_STRUCTURE_PERSISTS_IN=E2_FZ_LOW,E2_AP_LOW

E3_GATE=PASS
E3_GRID_CASES=0.004,0.002,0.001,0.0005,0.00025
E3_HORIZON_CASES=1,2,3,4
E3_FINEST_GRID_TOTAL_CORE_MEDIAN_MS=352.5967
E3_PRIMARY_GRID_TOTAL_CORE_MEDIAN_MS=61.8811
E3_FOUR_PASS_TOTAL_CORE_MEDIAN_MS=178.8355

PYTEST=PASS
QUICK_REPRODUCTION=PASS
FULL_REPRODUCTION=PASS
GIT_DIFF_CHECK=PASS

EXPERIMENT_FREEZE_RECOMMENDATION=FREEZE

REMAINING_BLOCKERS=NONE
```

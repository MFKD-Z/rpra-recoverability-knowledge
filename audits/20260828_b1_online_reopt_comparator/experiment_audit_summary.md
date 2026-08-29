# B1 experiment-output audit summary

## Overall grade

`ready for manuscript`

Decision question: whether the frozen B1 evidence supports a bounded statement
that RPRA reproduces on-demand continuous downstream-feasibility decisions on
the primary scalar domain while externalizing repeated continuous solves.

## Raw experimental facts

- Baseline: `c25540909939f65fad732420fa484f52931c02f9`, tag
  `v1.1.0`, configuration `configs/3pass_100um.yaml`.
- The matched first-decision audit is a census of all 407 frozen recoverable
  states. Exact selected-action agreement is 407/407.
- RPRA and ONLINE-REOPT both complete 407/407 rollouts. The two policies agree
  on all 407 action sequences and at all three stages (407/407 per stage).
- Absolute first-action difference and the frozen signed immediate-deflection
  difference (RPRA minus ONLINE-REOPT) are identically zero: mean, median, P95,
  and maximum are all 0.
- No RPRA-selected action is continuously downstream-infeasible. No
  ONLINE-REOPT-selected action is rejected by discrete RPRA membership. There
  are zero numerical-unresolved outcomes.
- ONLINE-REOPT requires 42,312 downstream continuous solves over the 407 first
  decisions: mean 103.961, median 87, P95 269.7, range 1–290 calls/state.
- The fixed 41-state timing subset contains 41 warm-ups and 205 measured calls
  per policy. Pooled measured median/IQR/P95 are 0.1717/0.0156/0.21758 ms for
  RPRA and 7080.9788/15598.2814/23069.61692 ms for ONLINE-REOPT.
- The B1 environment matches the frozen E3 environment field-for-field.
- `pytest`, quick reproduction, full reproduction, and `git diff --check` all
  pass. The frozen 4.442-mm mechanism is unchanged.

## Statistical diagnostics

- This is a deterministic full-domain census, not a sampled population
  estimate; no confidence interval is needed for the 407-state agreement
  fraction. Random seed is not applicable. The timing subset is deterministic
  and predeclared by index.
- Comparator fairness is strong: current states, current-action grid, local
  physics, objective, tie tolerance, and tie rule are identical. Only the
  downstream-feasibility source differs.
- Metric signs and units match the design freeze: action differences are
  absolute µm; deflection delta is RPRA minus ONLINE-REOPT in µm.
- All 525 unique continuous-solver keys are retained with status and residual
  fields. They contain 121 PASS and 404 valid FAIL results; all 525 satisfy the
  frozen validity checks. Thirty-one rows report SciPy
  `optimizer_success=False` but remain residual-valid and are correctly
  classified from `decision_at_limit` under the frozen rule.
- Exact memo determinism was checked by 525 uncached repeats with zero
  mismatches. The reported 42,312 structural calls are reconstructed from the
  frozen online candidate-search rule, not from cache misses.
- Traceability is complete from config and harness SHA-256 through row-level
  first actions, trajectories, solver audit, raw timing, JSON summary, and
  formal report.
- Cherry-picking risk is low: the scientific domain is all 407 states, the
  timing subset is predeclared, and failures/disagreements are not excluded.
- The exact-agreement result is a null policy-difference result, not evidence
  that RPRA improves solution quality over ONLINE-REOPT. Its value is the
  matched decision equivalence plus the measured repeated-solve burden.

## Paper framing recommendations

Recommended wording:

> On the frozen 407-state primary finite domain, the precomputed RPRA
> preserving-action filter selected exactly the same first actions and full
> three-pass action sequences as on-demand continuous remaining-horizon
> re-optimization under the same current-action grid, physics, objective, and
> tie rule. The online comparator required 42,312 downstream continuous solves
> for the matched first decisions, while RPRA used its precomputed discrete
> admissibility structure.

Timing may be reported only as descriptive evidence for the recorded
environment and fixed subset. Keep offline RPRA construction cost separate
from these B1 decision latencies.

Evidence-supported claim boundary: exact decision and completion agreement on
the frozen deterministic scalar 3-pass/100-µm represented domain, plus
descriptive repeated-solve burden under the frozen implementation.

## Unsupported or exaggerated conclusions

Do not claim universal equivalence to continuous optimization, superiority to
MPC, global optimality of SLSQP, general real-time performance, asymptotic
complexity advantage, physical validation, or cross-geometry/general
manufacturing validity. Do not present the 31 non-success SciPy diagnostics as
unresolved failures; their returned solutions passed the frozen residual
checks. Do not use the invalid pre-authority attempt as scientific evidence.

`WORKLOG_STATUS=NOT_PRESENT_NOT_CREATED`

# B3 Experiment Output Audit

Overall grade: **ready for manuscript**, within the frozen B3 claim boundary.

Decision question: Do the exhaustive B3 outputs support the narrow statement
that the local-feasibility/recoverability separation and mixed preserving-action
structure persist across the preregistered ±5, ±10, and ±20 µm terminal bands?

## Raw experimental facts

- All four cases contain exactly 621 fixed-domain states and 541 candidate
  actions per state. The corrected evidence contains exactly 335,961 rows per
  case and 1,343,844 state/action rows overall; no case, state, action, or
  infeasible candidate was excluded.
- From T0 through T20, recoverable states are 407, 419, 431, and 457, while
  local-but-irrecoverable states are 214, 202, 190, and 164.
- Mixed-action recoverable states are 289, 293, 431, and 457. Fully preserving
  recoverable states are 118, 126, 0, and 0.
- MYOPIC completes 3/407, 9/419, 16/431, and 29/457 starts. All other MYOPIC
  trajectories stop at the last pass with no locally feasible action.
- RPRA completes every fixed-domain recoverable start: 407/407, 419/419,
  431/431, and 457/457.
- T0 exactly reproduces the frozen state/action counts, 3/407 and 407/407
  rollout counts, and the 4.442-mm mechanism.

## Statistical diagnostics

This is a deterministic exhaustive grid sensitivity study, so random seeds,
sampling uncertainty, confidence intervals, and significance tests are not
applicable. The same configuration, 0.001-mm grid, 621-state domain, action
objective, tie rule, physical checks, and decision tolerance are used in every
case; only the preregistered inclusive terminal base set changes.

Independent streaming aggregation of `B3_state_action_audit.csv` reproduces
every summary count. Each state has exactly 541 unique actions spanning 0.360 to
0.900 mm. Classification partition, local-feasibility, downstream-membership,
deflection-presence, and policy-selection invariants all have zero errors.
Independent trajectory grouping reproduces all completion and failure counts,
and all 10,284 trajectory rows are retained. The corrected summary and rollout
files have the same SHA-256 hashes as the initial run, confirming that the
evidence correction did not change numerical results or policy trajectories.
There are no figures to cross-check. Config and harness SHA-256 values are
recorded in `B3_environment.json`. The full regression suite, quick and full
reproduction, diff check, and public-content check pass.

Cherry-picking risk is low because all four frozen cases and all fixed-domain
states are retained. The main result nuance is not hidden: the all-preserving
subset vanishes at T10 and T20 even though mixed structure becomes universal
among recoverable states.

## Paper framing recommendations

Recommended wording:

> In the frozen scalar three-pass case, the local-feasibility versus downstream-
> recoverability separation and mixed preserving/destroying action structure
> persist when the terminal requirement is relaxed to the preregistered ±5,
> ±10, and ±20 µm bands.

Also report the monotone reduction in `|L ∖ R|` and the disappearance of the
all-preserving subset at T10/T20; both are material features of the sensitivity.

Evidence-supported claim boundary: deterministic behavior on the frozen
3pass_100um scalar grid and declared tolerance bands only.

## Unsupported or exaggerated conclusions

Avoid claims of uncertainty robustness, measurement-error tolerance, physical
validation, cross-configuration generality, optimizer superiority, or a general
tolerance-design theory. The outputs do not support extrapolation beyond the
four declared terminal conditions.

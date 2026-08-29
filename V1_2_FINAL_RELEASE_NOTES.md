# RPRA Reproducibility Package v1.2.0 — Tier-B evidence release

Version 1.2.0 extends the retained manuscript evidence without changing the RPRA production semantics, Morelli analytical model, state/action transition rule, decision tolerances, or the frozen v1.1.0 evidence.

## Added evidence

### B1 — matched online remaining-horizon re-optimization comparator
- complete 407-state primary-domain census;
- RPRA and ONLINE-REOPT select identical first actions: 407/407;
- identical complete three-pass action sequences: 407/407;
- both policies complete 407/407 starts;
- zero RPRA-selected continuous-infeasible actions;
- zero ONLINE-selected actions rejected by the discrete preserving envelope;
- ONLINE-REOPT requires 42,312 downstream continuous solves for the 407 matched first decisions;
- fixed-subset decision timing and continuous-solver audit retained with exact environment provenance.

### B2 — near-boundary numerical-fidelity challenge
- 161 deterministic states within ±20 µm of the recomputed continuous boundary;
- five declared grids and 805 state-grid comparisons;
- zero optimistic false acceptances at every grid;
- conservative false rejections decrease from 49 to 3 from 0.004 to 0.00025 mm;
- at the adopted 0.001-mm grid, 152/161 states agree and all nine disagreements are confined within 2.0 µm of the continuous boundary.

### B3 — terminal-tolerance sensitivity
- exact, ±5, ±10, and ±20 µm terminal sets on the fixed 621-state / 0.001-mm domain;
- local-but-irrecoverable states: 214, 202, 190, 164;
- mixed-action recoverable states: 289, 293, 431, 457;
- MYOPIC completions: 3/407, 9/419, 16/431, 29/457;
- RPRA completions: 407/407, 419/419, 431/431, 457/457;
- exhaustive B3 state/action and rollout evidence retained.

## Claim boundary

This release supports bounded numerical and decision evidence for the frozen deterministic scalar thin-wall case. It does not establish universal equivalence to continuous optimization, superiority to MPC, a general convergence theorem, measurement-error robustness, uncertainty quantification, physical validation, or cross-configuration generality.

## Compatibility

The public v1.1.0 archive remains unchanged and permanently citable. v1.2.0 is an evidence expansion, not a replacement of the historical record.

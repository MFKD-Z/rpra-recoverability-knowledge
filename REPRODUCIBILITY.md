# Claim-to-command reproducibility map

Run commands from the repository root after installing `requirements.txt`.

## State recoverability and local/global distinction

**Claim.** The three-pass/100 µm domain contains 621 evaluated states: 407 are
discretely recoverable. The formal finite-grid local-but-irrecoverable set
difference is `|L_3,h \ R_3,h| = 214`. Under the adopted analytical model and
constraints, 212 of those states are also irrecoverable on the independent
continuous reference; the remaining 2 are conservative discrete false
rejections.

**Command.**

```bash
python scripts/reproduce.py --mode quick
```

**Expected output.**

```text
THREEPASSSTATES=407/621 recoverable
THREEPASSLOCALFEASIBLEIRRECOVERABLE=212
```

The second output line is the frozen historical continuous-boundary helper
value. It must not be interpreted as the formal discrete set difference. The
214/212/2 decomposition is retained explicitly in
`audits/20260828_r81_experiment_freeze_candidate/experiment_audit_summary.md`
and in `supplementary/Supplementary_Data_FINAL.xlsx`.

## Frozen E1 decision-consequence audit

**Claim.** Across all 407 represented recoverable starts, the myopic first
action is destroying in 289 cases and completes the full horizon in 3 cases.
RPRA-preserving rollout completes in 407/407 cases with zero preservation-
invariant violations. This is operational verification of preserving-action
semantics, not generic optimizer superiority or physical validation.

**Retained evidence.**

- `audits/20260828_r81_experiment_freeze_candidate/E1_first_action_audit.csv`
  (407 rows)
- `audits/20260828_r81_experiment_freeze_candidate/E1_rollout_trajectories.csv`
  (2,442 rows)
- `audits/20260828_r81_experiment_freeze_candidate/E1_summary.json`

## Frozen E2 analytical-condition robustness

**Claim.** All four additional variants were predeclared and pass the explicit
analytical-model applicability checks. `E2_FZ_HIGH` and `E2_AP_HIGH` are valid
domains with empty recoverable sets. Consequently, no general mixed-action
persistence claim is made across those two domains. E2 is not physical
experimental validation, uncertainty quantification, or Monte Carlo evidence.

**Retained evidence.**

- `audits/20260828_r81_experiment_freeze_candidate/E2_configuration_robustness.csv`
- `audits/20260828_r81_experiment_freeze_candidate/E2_summary.json`

## Frozen E3 numerical-core timing

**Claim.** The grid and horizon timing tables retain all five measured
repetitions after one warm-up for each case. The primary three-pass/0.001-mm
total-core median is 61.8811 ms, the four-pass/0.001-mm median is 178.8355 ms,
and the three-pass/0.00025-mm median is 352.5967 ms. These are descriptive
measurements for the recorded environment, not a real-time guarantee or an
asymptotic scaling-law claim.

**Retained evidence.**

- `audits/20260828_r81_experiment_freeze_candidate/E3_grid_scalability.csv`
- `audits/20260828_r81_experiment_freeze_candidate/E3_horizon_scalability.csv`
- `audits/20260828_r81_experiment_freeze_candidate/E3_environment.json`

Exact environment: Python 3.11.9; NumPy 2.4.6; SciPy 1.17.1; OS
Windows-10-10.0.19045-SP0; CPU AMD64 Family 25 Model 80 Stepping 0,
AuthenticAMD; 6 physical/12 logical cores; timing method `time.perf_counter_ns
external call boundary`; 1 warm-up and 5 measured repetitions per case.

The reusable harness is
`scripts/run_r81_experiment_freeze_candidate.py`. Do not run it as a routine
reproduction step; use it only to investigate a retained-file integrity
failure, with frozen inputs and byte/value comparison before replacement.

## Mixed-action states and action counts

**Claim.** Of 407 three-pass recoverable states, 118 have only preserving
locally feasible actions and 289 have both preserving and destroying actions.
The envelope contains 73,454 locally feasible actions: 31,549 preserving and
41,905 destroying.

**Command.**

```bash
python scripts/reproduce.py --mode quick
```

**Expected output.**

```text
THREEPASSACTIONS=31549 preserving,41905 destroying
```

The fully preserving and mixed-action counts are written to
`reproduced_outputs/paper_results_reproduced.json` by full mode.

## Four-pass configuration

**Claim.** The four-pass/100 µm recoverable domain contains 947 states and
288,058 locally feasible actions: 195,289 preserving and 92,769 destroying.

**Command.**

```bash
python scripts/reproduce.py --mode quick
```

**Expected output.**

```text
FOURPASSRECOVERABLESTATES=947
FOURPASSACTIONS=195289 preserving,92769 destroying
```

## Configuration dependence

**Claim.** There are 214 configuration-dependent state decisions on the
reported 621-value comparison basis. The three-pass/100 µm and four-pass/100 µm
overlap contains 261 grid states, of which 214 differ.

**Commands.**

```bash
python scripts/reproduce.py --mode quick
python scripts/reproduce_tables.py
```

**Expected output.**

```text
CONFIGURATION_DEPENDENT_VALUES=214/621
```

The 214 rows are written to
`reproduced_outputs/tables/configuration_dependent_states.csv`.

## Mechanism at 4.442 mm

**Claim.** At the 4.442 mm state, the 0.432 mm action reaches 4.010 mm and
destroys recoverability, while the 0.557 mm action reaches 3.885 mm and
preserves recoverability.

**Command.**

```bash
python scripts/reproduce.py --mode quick
```

**Expected output.**

```text
MECHANISM_4P442=0.432->4.010 destroying;0.557->3.885 preserving
```

## Semantic conformance and knowledge conditions

**Claim.** On complete represented domains, state and action meanings agree
with the numerical RPRA decisions. A preserving witness is sufficient for a
RECOVERABLE conclusion; a negative conclusion requires complete candidate and
downstream-membership evidence; otherwise the state remains UNKNOWN.

**Commands.**

```bash
pytest -q
python scripts/reproduce.py --mode full
```

**Expected output.**

```text
COMPLETE_DOMAIN_STATE_SEMANTICS=UNCHANGED
COMPLETE_DOMAIN_ACTION_SEMANTICS=UNCHANGED
```

Full mode writes the nine reader-facing cases to
`reproduced_outputs/tables/knowledge_conditions.csv`.

## Five query forms

**Claim.** The representation supports state status, preserving actions,
action explanation, configuration comparison, and provenance queries while
retaining their expected scientific answers.

**Command.**

```bash
python scripts/benchmark_queries.py
```

**Expected output.**

```text
QUERY_BENCHMARK=PASS
```

The command writes per-query row counts and measured latencies without using a
wall-clock acceptance threshold.

## Grid robustness and continuous comparison

**Claim.** Grid refinement reduces the discrete boundary underapproximation
from 12.0305 µm at 0.004 mm spacing to 0.5305 µm at 0.00025 mm spacing, with
no unsafe optimistic classifications on the 400 off-grid reference states.

**Command.**

```bash
python scripts/reproduce.py --mode full
```

**Expected artifact.**

`reproduced_outputs/tables/grid_robustness.csv` matches the five rows in
`data/reference/grid_robustness.csv` within numerical tolerance.

The continuous reference uses independent differential-evolution
re-optimization. Together with the formal-grid audit above, it supports the
214/212/2 classification while preserving the distinction between discrete
set membership and continuous analytical feasibility.

## Knowledge-reuse and construct-grounding assets

The RDF/SPARQL conformance and five reuse-query forms are exercised by the
semantic and query commands above. The external Zhang et al. figure-label
transcription in `data/external/zhang_fig13_transcription.csv` is retained for
construct grounding only and is not used as a physical validation dataset.

## Figures and tables

**Claim.** Reader-facing counterparts of Figs. 3, 5, 6, and 7 and their source
tables can be generated from repository code and data.

**Commands.**

```bash
python scripts/reproduce_figures.py
python scripts/reproduce_tables.py
```

**Expected artifacts.**

- `reproduced_outputs/figures/Fig3_state_recoverability.*`
- `reproduced_outputs/figures/Fig5_configuration_dependence.*`
- `reproduced_outputs/figures/Fig6_action_envelope.*`
- `reproduced_outputs/figures/Fig7_knowledge_conditions.*`
- `reproduced_outputs/tables/configuration_results.csv`
- `reproduced_outputs/tables/query_examples.json`

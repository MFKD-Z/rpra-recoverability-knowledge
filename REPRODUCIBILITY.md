# Claim-to-command reproducibility map

Run commands from the repository root after installing `requirements.txt`.

## State recoverability and local/global distinction

**Claim.** The three-pass/100 µm domain contains 621 evaluated states: 407 are
discretely recoverable and 214 are discretely irrecoverable. On the independent
continuous reference, 212 locally feasible states have no feasible remaining
continuation.

**Command.**

```bash
python scripts/reproduce.py --mode quick
```

**Expected output.**

```text
THREEPASSSTATES=407/621 recoverable
THREEPASSLOCALFEASIBLEIRRECOVERABLE=212
```

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

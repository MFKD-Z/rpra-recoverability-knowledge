# RPRA Recoverability Knowledge Representation Reproducibility Package

This repository contains the reproducibility package for the numerical
recoverability and engineering knowledge representation evidence reported in
“Physics-grounded remaining-process state-action recoverability for multi-stage
machining decisions.”

## Overview

The package reconstructs remaining-process recoverability analysis (RPRA) for
thin-wall peripheral milling. It includes the Morelli analytical deflection
model, grid-based backward recoverable sets, recoverability-preserving action
envelopes, RDF decision certificates, evidence-conditioned reasoning, five
SPARQL query forms, and scripts for the reported tables and supporting numerical
presentation artifacts.

The package distinguishes three evidence levels used in the manuscript:
1. numerical-source validation against continuous constrained re-optimization;
2. representation conformance between RPRA outputs and compact certificates /
   complete-domain action predicates;
3. semantic negative-control tests under information loss and integrity violations.

## Release

Version 1.1.0 expands the retained evidence and synchronizes the
manuscript-facing documentation. It does not change the RPRA production
semantics, Morelli implementation, decision tolerances, or frozen numerical
results.

## Archived release

Version 1.0.0 is permanently archived on Zenodo:
https://doi.org/10.5281/zenodo.21917007

## Paper

The accompanying paper is:

Y. Zhou, Y. Chen, Q. Wang, S. Chen, and M. Yu, “Engineering Knowledge
Representation and Reasoning with Explicit Validity Conditions for
Physics-Grounded State–Action Recoverability in Multi-Stage Machining.”

The analytical deflection implementation follows:

L. Morelli, F. Caldini, M. Sanz-Calle, and N. Grossi, “Static deflection of
cantilever thin wall workpieces in peripheral milling: An analytical model,”
*Journal of Manufacturing Processes*, 143, 369–386 (2025).
https://doi.org/10.1016/j.jmapro.2025.04.029

## What this repository reproduces

The package reproduces:

- three-pass and four-pass recoverable sets at a 100 µm deflection limit;
- 105 µm and 110 µm three-pass configuration variants;
- locally feasible states without a feasible remaining continuation;
- preserving and destroying action envelopes;
- the 4.442 mm state mechanism example;
- configuration-dependent state decisions;
- compact state-certificate conformance and complete-domain action-predicate conformance;
- evidence-conditioned RECOVERABLE, IRRECOVERABLE, and UNKNOWN behavior;
- five decision-reuse query forms and their provenance trace;
- grid/continuous comparison and the numerical results underlying the reported tables;
- the frozen R8.1 E1 complete-domain decision audit, E2 predeclared
  analytical-condition variants, and E3 numerical-core timing study;
- an independent differential-evolution continuous-reference cross-check; and
- a reader-facing supplementary workbook that summarizes the retained evidence
  without replacing row-level or raw-repetition audit files.

The figure-generation scripts retain historical/supporting output filenames for
reproducibility. These filenames should not be interpreted as the current
manuscript figure numbering.

## Repository structure

```text
configs/              Four reader-facing configurations
audits/               Protocol verification and closure evidence
data/reference/       Reference summaries and timing context
data/external/        Secondary numeric transcription and provenance
expected/             Published expected results
queries/              Five SPARQL query forms
rules/                Four final reasoning rules
scripts/              Reproduction and benchmark entry points
src/rpra/             Numerical analysis and output generation
src/knowledge/        RDF schema, graph construction, reasoning, queries
tests/                Scientific semantic and key-result tests
supplementary/        Reader-facing summary workbook
```

Generated artifacts are written to `reproduced_outputs/`; the directory need
not exist before execution and is excluded from version control.

## Installation

Python 3.11.9 is the reference interpreter. Create an environment and install
the exact dependencies:

```bash
python -m venv .venv
python -m pip install -r requirements.txt
```

## Quick reproduction

```bash
python scripts/reproduce.py --mode quick
```

The command recomputes the four discrete configurations, checks the key state
and action counts, verifies the 4.442 mm mechanism, and checks key
state-certificate and action-predicate conformance results. Success ends with:

```text
QUICK_REPRODUCTION=PASS
```

Any mismatch returns a nonzero exit code.

## Full reproduction

```bash
python scripts/reproduce.py --mode full
```

Full mode writes numerical action tensors, compact RDF state certificates,
derived decisions, four configuration summaries, grid robustness results,
query examples, knowledge-condition outputs, and figures/tables to
`reproduced_outputs/`. The RDF files retain all evaluated state conclusions,
one positive witness for each recoverable state, and complete action details
for the published query examples; the compressed numerical arrays retain the
complete state-action classification.

The continuous comparison includes 400 deterministic off-grid WIP states and
can take longer than quick mode.

## Expected outputs

Reader-facing expected values are stored in
`expected/paper_results.json`. Principal checks include:

- 407 of 621 three-pass states recoverable;
- a formal finite-grid local-but-irrecoverable gap
  `|L_3,h \ R_3,h| = 214` on the adopted 0.001-mm grid;
- a 212-state subset that is also irrecoverable under the adopted continuous
  analytical model and constraints, leaving 2 conservative discrete false
  rejections;
- 289 of 407 recoverable three-pass states containing both preserving and
  destroying locally feasible actions;
- 31,549 preserving and 41,905 destroying three-pass actions;
- 947 four-pass recoverable states within the reported `R4` evaluation domain;
- 195,289 preserving and 92,769 destroying four-pass actions;
- 214 of the 261 WIP values shared by the three-pass/100-µm and
  four-pass/100-µm configurations receiving different recoverability decisions.

The historical `local_feasible_irrecoverable = 212` field in
`expected/paper_results.json` is intentionally retained because it records the
continuous-boundary publication helper output. It is not the formal discrete
set difference, which is 214.

## R8.1 evidence expansion

The frozen evidence package is retained under
`audits/20260828_r81_experiment_freeze_candidate/`. It contains the complete
407-row E1 first-action audit, all 2,442 E1 rollout rows, the four predeclared
E2 analytical-condition variants, and E3 grid/horizon timing tables with raw
repetition vectors and exact environment metadata. The two high-condition E2
variants, `E2_FZ_HIGH` and `E2_AP_HIGH`, are valid analytical domains with empty
recoverable sets; those null results are retained rather than replaced.

The reusable frozen harness is
`scripts/run_r81_experiment_freeze_candidate.py`. The retained files are the
release evidence and the harness need not be rerun during ordinary
reproduction. It should be rerun only to investigate a file-integrity failure,
using its frozen inputs and comparing the regenerated values with the retained
summaries before any replacement.

The release also retains the existing RDF/SPARQL reuse and conformance assets.
The Zhang et al. Fig. 13 label transcription is included only for construct
grounding and provenance; it is not a physical validation dataset. The final
reader-facing summary is `supplementary/Supplementary_Data_FINAL.xlsx`; the
row-level E1 CSVs and E3 raw timing vectors remain authoritative audit assets.

Interpretation is deliberately limited:

- E1, E2, and E3 do not provide physical experimental validation;
- E2 is not uncertainty quantification or Monte Carlo evidence, and mixed-action
  persistence is not claimed across the two empty high-condition domains;
- E3 provides environment-specific descriptive timings, not a real-time
  guarantee or asymptotic scaling law; and
- the 407/407 RPRA rollout is operational verification of preserving-action
  semantics, not evidence of generic optimizer superiority.

Separate entry points regenerate presentation artifacts:

```bash
python scripts/reproduce_tables.py
python scripts/reproduce_figures.py
```

## Off-grid upward-mapping verification

A dedicated protocol audit is provided under:

`audits/20260826_offgrid_upward_mapping_400_case_verification/`

The audit verifies the manuscript's upward-to-next-grid retrieval convention
against the frozen 400-state continuous-reference dataset.

Across the five reported grid resolutions, exact upward mapping produced:

| Grid (mm) | Agreement | Conservative false rejection | Optimistic false acceptance |
|-----------|-----------|------------------------------|-----------------------------|
| 0.004 | 391/400 | 9 | 0 |
| 0.002 | 397/400 | 3 | 0 |
| 0.001 | 399/400 | 1 | 0 |
| 0.0005 | 399/400 | 1 | 0 |
| 0.00025 | 400/400 | 0 | 0 |

For all 2,000 held-out state-grid evaluations, the historical retrieval
implementation and the exact upward-to-next-grid rule selected identical
represented grid states.

The historical helper uses a tolerance-adjusted ceiling. Therefore, the audit
supports the reported case-specific retrieval results but does not establish
an exact-ceiling implementation for arbitrary near-grid floating-point inputs
or a general monotonicity theorem.

## Performance benchmark

```bash
python scripts/benchmark_queries.py
```

The benchmark uses 10 warmups and 30 measured repetitions for each query form.
It verifies returned scientific results and writes timing metrics to
`reproduced_outputs/benchmark_results.csv`. Timing values depend on hardware,
operating system, and the Python environment; they are not pass/fail
wall-clock thresholds. Reference measurements are provided in
`data/reference/performance_reference.csv`.

## Archived supporting external-data provenance

`data/external/zhang_fig13_transcription.csv` contains numeric observations
transcribed from figure labels in Fig. 13 of:

R. Zhang, J. Zhou, J. Ren, Q. Qi, and Y. Xu, “Inverse tolerance design method
of thin-walled blades in multi-stage machining process,” *Results in
Engineering*, 31, 111604 (2026).
https://doi.org/10.1016/j.rineng.2026.111604

This transcription is retained as supporting provenance in the reproducibility
package and is not used as a separate main-text validation dataset in the
current manuscript. The IDs are author-assigned traceability identifiers, not source
specimen identifiers. The source image is not redistributed. See
`data/external/README.md` for details.

## Citation

Software citation metadata for version 1.1.0 and the repository URL are provided
in `CITATION.cff`. A version-specific 1.1.0 DOI will be added only after it is
reserved. The archived version 1.0.0 DOI is listed above and is not reused as
the DOI for version 1.1.0.

## License

Code is licensed under the BSD 3-Clause License (`LICENSE`). Original project
data and documentation are licensed under CC BY 4.0 (`LICENSE-DATA`). The
external numeric transcription retains its source attribution and does not
include the source figure.

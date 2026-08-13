# RPRA Recoverability Knowledge Representation Reproducibility Package

This repository contains the minimal reproducibility package for the numerical
recoverability and engineering knowledge representation experiments reported in
“Engineering Knowledge Representation and Reasoning with Explicit Validity
Conditions for Physics-Grounded State–Action Recoverability in Multi-Stage
Machining.”

## Overview

The package reconstructs remaining-process recoverability analysis (RPRA) for
thin-wall peripheral milling. It includes the Morelli analytical deflection
model, grid-based backward recoverable sets, recoverability-preserving action
envelopes, RDF decision certificates, evidence-conditioned reasoning, five
SPARQL query forms, and scripts for the reported tables and figures.

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
- complete-domain state and action semantic equivalence;
- evidence-conditioned RECOVERABLE, IRRECOVERABLE, and UNKNOWN behavior;
- five decision-reuse query forms and their provenance trace;
- grid/continuous comparison, reported tables, and Figs. 3, 5, 6, and 7.

## Repository structure

```text
configs/              Four reader-facing configurations
data/reference/       Reference summaries and timing context
data/external/        Secondary numeric transcription and provenance
expected/             Published expected results
queries/              Five SPARQL query forms
rules/                Four final reasoning rules
scripts/              Reproduction and benchmark entry points
src/rpra/             Numerical analysis and output generation
src/knowledge/        RDF schema, graph construction, reasoning, queries
tests/                Scientific semantic and key-result tests
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
and action counts, verifies the 4.442 mm mechanism, and checks state/action
semantic equivalence. Success ends with:

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
- 212 locally feasible states without a feasible remaining continuation;
- 31,549 preserving and 41,905 destroying three-pass actions;
- 947 four-pass recoverable states;
- 195,289 preserving and 92,769 destroying four-pass actions;
- 214 configuration-dependent decisions on the reported 621-value basis.

Separate entry points regenerate presentation artifacts:

```bash
python scripts/reproduce_tables.py
python scripts/reproduce_figures.py
```

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

## External-data provenance

`data/external/zhang_fig13_transcription.csv` contains numeric observations
transcribed from figure labels in Fig. 13 of:

R. Zhang, J. Zhou, J. Ren, Q. Qi, and Y. Xu, “Inverse tolerance design method
of thin-walled blades in multi-stage machining process,” *Results in
Engineering*, 31, 111604 (2026).
https://doi.org/10.1016/j.rineng.2026.111604

The IDs are author-assigned traceability identifiers, not source specimen
identifiers. The source image is not redistributed. See
`data/external/README.md` for details.

## Citation

Software citation metadata are provided in `CITATION.cff`. No repository URL or
DOI is prefilled before public hosting and archival deposit exist.

## License

Code is licensed under the BSD 3-Clause License (`LICENSE`). Original project
data and documentation are licensed under CC BY 4.0 (`LICENSE-DATA`). The
external numeric transcription retains its source attribution and does not
include the source figure.


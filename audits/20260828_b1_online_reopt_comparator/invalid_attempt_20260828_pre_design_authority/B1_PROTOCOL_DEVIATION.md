# B1 invalid first-attempt protocol deviation

## Status

`INVALID_PROTOCOL_IMPLEMENTATION_DO_NOT_INTERPRET`

The files in this directory preserve the first B1 implementation attempt.
They are retained to prevent silent deletion or result selection, but they are
not valid B1 scientific evidence.

## Cause

The standalone design-freeze attachment was unavailable when the first harness
was frozen. The external Codex Goal stated that optimizer failures not
corresponding to valid model/capacity FAILs must be unresolved. The initial
harness conservatively interpreted every `optimizer_success=False` diagnostic
as an optimizer failure.

The original design freeze was supplied while that attempt's final timing case
was running. Section 7 resolves the ambiguity explicitly:

- a residual-valid solution with `decision_at_limit=PASS` is PASS;
- a residual-valid solution with `decision_at_limit=FAIL` is FAIL;
- a thrown optimizer/runtime failure is `NUMERICAL_UNRESOLVED`.

The first attempt therefore misclassified residual-valid returned solutions.
For example, the 3.825-mm/two-pass call returned zero sum, bound, and terminal
residuals and epigraph violation `1.6213164144573966e-10` µm with
`decision_at_limit=PASS`, while SciPy reported `optimizer_success=False`
(`Positive directional derivative for linesearch`). The initial harness
incorrectly labeled it unresolved.

## Consequence

The invalid attempt reported 267 unresolved first decisions, only 139 complete
ONLINE-REOPT rollouts, and 156 unresolved timing rows. Those are harness
classification artifacts and must not be interpreted as solver or scientific
outcomes.

## Corrective boundary

The corrected harness changes no solver tolerance, multistart count, action or
state domain, objective, tie rule, candidate order, stopping rule, physical
model, or RPRA production semantics. It only:

1. applies the design's residual-valid PASS/FAIL rule;
2. corrects the predeclared deflection-delta sign to RPRA minus ONLINE-REOPT;
3. adds IQR, RPRA candidate counts, stage agreement, and a complete unique-key
   continuous-solver residual audit required by the supplied design.

The corrected formal run is executed from a new committed harness revision.
The files here remain unchanged as deviation evidence.

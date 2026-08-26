# Experiment audit summary

Overall grade: **ready for manuscript**

Decision question: Do the frozen 400-state numerical-fidelity results support the manuscript's case-specific claim that held-out continuous states were retrieved by upward-to-next-grid mapping before comparison with the continuous constrained reference?

## raw experimental facts

- Seed `20260810` regenerates the 400 frozen observation floats in the same order.
- All 400 observations are inside `[4.18, 4.80]` mm and off-grid at all five tested resolutions.
- The historical helper implements `ceil(state * scale - 1e-12)`.
- Exact Decimal/integer mapping and the historical helper select the same grid index for all 2,000 frozen state-grid evaluations.
- Verified agreements are 391, 397, 399, 399, and 400 of 400 from coarsest to finest grid.
- Optimistic false acceptances are zero at every grid.
- The frozen continuous-reference table hash is unchanged before and after verification.

## statistical diagnostics

This is a deterministic finite-case verification, not an inferential statistical study. Agreement increases from 97.75% to 100% over the tested grids, but the five points do not support a general convergence rate. At 0.001 mm, the only error is one conservative false rejection. Summary values trace exactly to the 2,000-row detail CSV and match both the historical EXP-2 summary and public reference table. No sample selection, threshold, optimizer, normalization, or baseline changed. Cherry-picking risk is controlled by exact reuse of all 400 frozen states.

## paper framing recommendations

Recommended wording: “For each held-out continuous WIP state, state-status retrieval used the same upward grid mapping defined in Section 3.1 before comparison with the continuous constrained reference.”

Evidence-supported claim boundary: the statement is validated for the frozen scalar-thickness case, these 400 observations, the five declared grids, and the unchanged model/configuration. The verification supports `399/400` and zero optimistic false acceptances at 0.001 mm.

## unsupported or exaggerated conclusions

Wording to avoid: claims of a general monotonicity theorem, universal zero-error behavior, a convergence order, or correctness of the historical tolerance-adjusted helper for arbitrary inputs infinitesimally above grid nodes. Those claims are not established by this finite verification.

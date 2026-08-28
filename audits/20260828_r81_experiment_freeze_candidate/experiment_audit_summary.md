# R8.1 Experiment Output Decision Audit

Overall grade: **ready for manuscript**

Decision question: Can the remaining E1 decision-consequence, E2 controlled analytical-condition robustness, and E3 RPRA-core timing evidence be frozen as the main-line experiment package, subject to successful post-run regression?

## Raw experimental facts

- The frozen primary configuration has 407 represented recoverable starting states.
- The myopic first action is destroying in 289/407 states (0.710073710074). The complete myopic rollout reaches the terminal state for 3/407 starts; 404 fail because no locally feasible action remains at the final stage.
- The RPRA-filtered rollout reaches the exact represented terminal state for 407/407 starts. The invariant-violation count is zero.
- Immediate-deflection sacrifice over all starts has median 17.4939198216 µm, P95 56.2330381477 µm, and maximum 60.6540763821 µm. The selected actions differ in 289 states.
- The frozen 4.442-mm mechanism remains unchanged: 0.432 → 4.010 is DESTROYING; 0.557 → 3.885 is PRESERVING.
- All four predeclared E2 variants pass the explicit Morelli applicability checks. E2_FZ_LOW and E2_AP_LOW retain non-empty recoverable sets and mixed preserving/destroying action structure. E2_FZ_HIGH and E2_AP_HIGH have empty recoverable sets from stage 1 onward, although all 621 evaluation states remain locally acceptable at the current pass.
- The E2 primary exact represented-set difference is 214 (`|L₃,h \ R₃,h|`). The unchanged frozen quick-reproduction value 212 uses the existing continuous-boundary publication helper; these are distinct classifications rather than a numerical regression.
- E3 measures all five grids and all four horizons using one warm-up and five measured repetitions per case. Raw repetition vectors, medians, and IQRs are retained. At h=0.001 mm the grid-scaling total-core median is 61.8811 ms; at h=0.00025 mm it is 352.5967 ms; at four passes it is 178.8355 ms.

## Statistical diagnostics

- E1 is a complete finite-population audit of all represented primary start states, not a sample; no random seed is applicable.
- E2 uses exactly the four predeclared single-parameter variants. No variant was substituted, removed, or selected after observing results. The baseline comparison uses the same evaluation domain, action bounds, grid, geometry, material, tool, and terminal settings.
- Metric denominators are explicit. E2 mixed-action rates use recoverable-state counts; the rate is undefined when the recoverable set is empty and is stored as null rather than zero.
- E3 is deterministic core construction with repeated wall-clock measurements. Medians and IQRs recompute exactly from the retained five-value raw vectors.
- Independent mask checks confirmed that the harness reproduces the production local-feasibility and preserving-action classifications at remaining horizons 1, 2, and 3.
- E1 summary counts trace to 407 first-action rows and 2,442 rollout rows. E3 tables trace to raw per-repetition timings. No figure was generated, so there is no table/figure consistency risk.
- Null-result risk is material in E2: both high-condition variants remove the recoverable and mixed-action domains. This is evidence against an unqualified robustness or generality claim, not a reason to alter the variants.

## Paper framing recommendations

Recommended wording: “Across the two lower-condition perturbations, both state-level local-versus-recoverable separation and mixed preserving/destroying action structure remained present. Under both higher-condition perturbations, the three-pass recoverable set became empty, while current-pass local acceptability remained non-empty; consequently, no recoverable-state action envelope existed in which mixed action classes could be evaluated.”

For E1, state directly that the two policies share the same immediate-deflection objective and differ only in admissible-action filtering. Report the complete-domain counts without turning the myopic failure rate into a pass criterion.

For E3, report medians and IQRs as environment-specific descriptive timings. The results support a reproducible numerical-core timing table, not a real-time guarantee or asymptotic law.

Evidence-supported claim boundary: the outputs establish exact represented-grid behavior for the frozen analytical model and the four predeclared single-parameter perturbations. They do not establish physical validation, probabilistic uncertainty quantification, Monte Carlo robustness, or general behavior outside these configurations.

## Unsupported or exaggerated conclusions

- Do not claim that the action-level mixed structure persists across all four E2 variants.
- Do not describe the empty high-condition recoverable sets as INVALID_DOMAIN; their inputs are valid and their emptiness is a scientific result.
- Do not claim physical validation, empirical machining robustness, universal superiority, or generality from these analytical runs.
- Do not infer an asymptotic complexity exponent or a real-time performance guarantee from E3.
- Do not suppress the two high-condition null domains or substitute milder perturbations.

The experiment outputs are ready for manuscript use with the conservative boundaries above. Post-run `pytest -q`, quick reproduction, full reproduction, and `git diff --check` all passed; frozen key numerical results remained unchanged. No project-root `WORKLOG.md` exists, so the skill-required worklog update could not be made without creating a new project artifact.

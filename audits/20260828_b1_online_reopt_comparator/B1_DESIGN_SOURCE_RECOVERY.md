# B1 design-source recovery note

The Codex Goal names `RINENG_B1_ONLINE_REOPT_COMPARATOR_DESIGN_FREEZE.md`
as its design authority. That standalone attachment was not present in the
provided directory, the repository, Git history, the final submission ZIP, or
the local Codex/ChatGPT caches.

Before implementation, the generating ChatGPT task was located by its task ID:

`6a90ec87-948c-83e9-944e-98bbf48766ba`

Its completed design-freeze response was read through the Codex task-history
interface and cross-checked against the complete external Codex Goal. The two
sources agree on all executable design facts:

- primary 3-pass/100-µm configuration only;
- all 407 frozen recoverable starts;
- matched first decisions and full rollouts;
- identical 0.001-mm current-action grid, local-feasibility mask,
  immediate-deflection objective, `1e-7` µm tie band, and smaller-removal tie
  rule;
- RPRA downstream membership versus ONLINE-REOPT calls to the unchanged
  continuous `full_reoptimize(successor, m-1, cfg, multistart=7)`;
- exact terminal equality for `m=1`;
- candidates ordered by `(immediate deflection, radial removal)`, with search
  continuing only through the first-PASS objective tie band;
- exact theoretical online solve-call accounting over all 407 first decisions;
- the predeclared 41-state timing subset, one warm-up and five measured calls,
  `perf_counter_ns()`, and disabled timing cache;
- explicit scientific-conflict and numerical-unresolved stop classifications;
- no edits to production RPRA semantics, the manuscript, the public v1.1.0
  release, frozen expected results, solver tolerances, or action/state domains.

This note does not claim to be a byte-for-byte copy of the missing attachment.
It preserves the recovery provenance and prevents the recovered summary from
being silently presented as the original file. The external Codex Goal remains
the exact runnable instruction source and its SHA-256 is recorded in
`B1_environment.json` by the formal harness.

## Addendum after attachment delivery

The user supplied the original standalone design freeze while the first
implementation attempt was completing. The original file is now available at
the path named by the Codex Goal. Its full text confirmed the recovered design,
but exposed one implementation mismatch: a residual-valid solution must be
classified from `decision_at_limit` even when SciPy's diagnostic
`optimizer_success` is false. The first harness attempt had treated every such
diagnostic as `NUMERICAL_UNRESOLVED`.

That attempt is retained under
`invalid_attempt_20260828_pre_design_authority/` and is not interpreted as a B1
result. The correction is authority-driven, does not change any frozen solver
setting or scientific rule, and is recorded in the adjacent protocol-deviation
note before the corrected formal run.

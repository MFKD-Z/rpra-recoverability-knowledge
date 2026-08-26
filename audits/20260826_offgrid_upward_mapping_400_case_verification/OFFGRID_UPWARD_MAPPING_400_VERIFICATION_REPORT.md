# 1. Purpose

This audit verifies whether the 400 held-out continuous WIP states underlying the manuscript's numerical-fidelity results use the Section 3.1 retrieval convention: for an observation inside the represented domain, retrieve status at the smallest represented grid state not below the observation.

# 2. Existing protocol audit

Repository and environment:

- Repository root: `G:\rpra_experiments\public_release\rpra-recoverability-knowledge`
- Branch: `main`
- HEAD before verification: `1967e2317a711067fd18476b76432eb3cb190641`
- Initial repository status: clean
- Python: 3.11.9
- The parent experiment workspace `G:\rpra_experiments` is not itself a Git repository. It contains the frozen detailed EXP-0/EXP-2 evidence used to assemble the public reproducibility package.

Source trace:

- Original 400-state generator: `G:\rpra_experiments\src\run_exp0.py::_heldout`; public reproduction counterpart: `src/rpra/reproduction.py::_heldout_states`. Both use NumPy `default_rng` seed `20260810`, sample 400 continuous states uniformly in `[4.18, 4.80]` mm, and reject construction-grid nodes.
- Frozen held-out detail and continuous reference: `G:\rpra_experiments\tables\heldout_400_agreement.csv`. In the originating code, `src/run_exp0.py::_heldout` obtains each reference from `ReoptimizationEngine.optimize(state, 3)`. The public counterpart calls the same optimizer in `src/rpra/reproduction.py::reproduce_grid_robustness`.
- Discrete grid comparison: `G:\rpra_experiments\src\run_exp2.py::_heldout_grid_row` and `_run_grid_sensitivity`; public counterpart: `src/rpra/reproduction.py::reproduce_grid_robustness`.
- Original mapping function: `src/rpra/recoverable_set.py::lookup_membership`, byte-identical to `G:\rpra_experiments\src\recoverable_set.py` (SHA-256 `63e6a0d597d0ae8f833373191aeb871523f658a2387bc322676f4a4c8cc93789`).
- Original grid-summary outputs: `G:\rpra_experiments\tables\EXP2_grid_sensitivity.csv`, `G:\rpra_experiments\outputs\EXP2_grid_sensitivity.json`, and `data/reference/grid_robustness.csv`.

The traced historical mapping code is:

```python
raw = float(state_mm) * scale
state_i = int(np.ceil(raw - 1e-12))
```

It then tests exact integer membership in the final backward set with `np.searchsorted`. This is a tolerance-adjusted ceiling, not the exact mathematical ceiling for every possible floating input. A minimally above-grid float such as `np.nextafter(4.586, +inf)` is mapped to `4.586` by the historical function rather than `4.587`.

For the frozen evidence, the repository generator reproduces all 400 serialized observations exactly. Every observation lies inside `[4.18, 4.80]` mm and is off-grid at all five tested resolutions. The historical and exact upward indices are identical for all 2,000 state-grid evaluations.

# 3. Audit classification

DIFFERENT_MAPPING_USED

The historical implementation uses tolerance-adjusted ceiling rather than an exact ceiling operation in the general boundary case. This distinction does not affect any of the 400 frozen observations at any tested grid.

# 4. Verification method

The isolated verification path `verify_offgrid_upward_mapping.py` parses each frozen observation and each grid spacing with `Decimal`. For an observation `s_obs` inside `[4.18, 4.80]` mm, it computes the integer grid index

```text
k_up = ceil(Decimal(s_obs) / Decimal(h))
s_up = k_up / (1 / h)
```

and retrieves membership directly from the unchanged integer-encoded RPRA backward set. Values outside the domain are reported, not clamped. The continuous decision and margin are copied unchanged from the frozen EXP-0 table; continuous optimization is not rerun. The source CSV SHA-256 remained `43d6646f2d1f1df756e9091b4c25133ef0190327b0b06d9e8344e10fe2d25d56` before and after verification.

Focused checks passed for an exact grid point, a minimally above-grid value, a value below the next grid point, the upper domain boundary, and an outside-domain value. The last is rejected without clamping.

# 5. Results

| Grid (mm) | Agreement | Conservative false rejection | Optimistic false acceptance |
|-----------|-----------|------------------------------|-----------------------------|
| 0.004 | 391/400 | 9 | 0 |
| 0.002 | 397/400 | 3 | 0 |
| 0.001 | 399/400 | 1 | 0 |
| 0.0005 | 399/400 | 1 | 0 |
| 0.00025 | 400/400 | 0 | 0 |

All grids have `N_total = N_valid = 400`, zero outside-domain cases, and zero invalid references. Maximum upward mapping deltas are 3.998666877138, 1.999917210872, 0.999917210872, 0.499917210872, and 0.249917210872 µm, respectively.

# 6. 0.001-mm adopted-grid closure

Agreement is 399/400. The single disagreement is `HO-0373`:

- Observed state: 4.5868043086666415 mm
- Exact upward-mapped state: 4.587 mm
- Discrete RPRA status: IRRECOVERABLE
- Continuous constrained-reference status: RECOVERABLE
- Continuous physical margin: 0.07543706474405099 µm
- Error direction: CONSERVATIVE_FALSE_REJECTION

The optimistic false acceptance count is 0.

# 7. Manuscript implication

EXISTING_MANUSCRIPT_CLAIM_SUPPORTED

The case-specific manuscript statement is supported because the historical tolerance-adjusted implementation and exact upward mapping select the same grid state for every one of the 400 frozen observations at every reported grid. This does not validate the historical helper for arbitrary near-grid inputs and does not establish a general monotonicity theorem.

# 8. Recommended manuscript sentence

For each held-out continuous WIP state, state-status retrieval used the same upward grid mapping defined in Section 3.1 before comparison with the continuous constrained reference.

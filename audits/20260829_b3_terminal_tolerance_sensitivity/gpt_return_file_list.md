# Minimal Return File List

Return these five decision-critical files:

1. `B3_FORMAL_AUDIT.md` — formal run status, regression gates, classification,
   and provenance-facing return block.
2. `experiment_audit_summary.md` — independent separation of raw facts,
   diagnostics, conservative wording, and unsupported claims.
3. `key_result_tables/final_comparison_table.csv` — smallest complete comparison
   across the four preregistered terminal cases.
4. `risk_and_next_step.md` — remaining claim risk and the next useful action.
5. `gpt_return_file_list.md` — defines the minimal package and documents which
   bulky evidence was intentionally withheld from the default return.

Five files are justified here because the formal status, independent audit,
compact comparison, claim-risk note, and package manifest serve distinct
acceptance functions; dropping any one would obscure either evidence or scope.

Inspected locally but intentionally not returned by default:

- `B3_terminal_tolerance_summary.csv` (source summary behind the compact table)
- `B3_state_action_audit.csv` (1,343,844-row complete state/action evidence)
- `B3_rollout_trajectories.csv` (10,284-row trajectory and failure evidence)
- `B3_environment.json` (environment and SHA-256 provenance)
- `B3_evidence_manifest.json` (checksums, row counts, and gate status)
- `B3_CORRECTIVE_RERUN_NOTE.md` (initial-run hashes and supersession record)
- `key_result_tables/anomaly_or_failure_table.csv`
- `key_result_tables/claim_boundary_table.csv`

The larger CSVs remain necessary reproducibility artifacts but are not needed
for the next manuscript judgment.

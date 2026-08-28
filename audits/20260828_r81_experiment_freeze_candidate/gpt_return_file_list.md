# Minimal Return File List

Return these four decision-critical files:

1. `EXPERIMENT_FREEZE_AUDIT.md` — authoritative gate summary, requested final block, and compact E1/E2/E3 results.
2. `experiment_audit_summary.md` — separates raw facts, diagnostics, paper framing, and unsupported conclusions; assigns the readiness grade.
3. `key_result_tables/final_comparison_table.csv` — smallest cross-experiment table needed to see the decisive counts and timings.
4. `risk_and_next_step.md` — records the null-result/overclaim risks and the single next action.

Inspected locally but intentionally excluded from the default return: the 407-row E1 first-action CSV, the 2,442-row trajectory CSV, E1/E2 JSON summaries, detailed E2 CSV, both detailed E3 timing CSVs with raw repetitions, environment JSON, and the two anomaly/claim-boundary tables. These remain in the audit directory for external traceability but are not needed in the minimal handoff.

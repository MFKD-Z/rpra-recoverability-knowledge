# B2 Minimal Return File List

Return these decision-critical files:

1. `B2_FORMAL_AUDIT.md` — authoritative formal-run result, regression gates, scope boundary, and required return block.
2. `experiment_audit_summary.md` — independent separation of raw facts, diagnostics, paper framing, and unsupported conclusions.
3. `key_result_tables/final_comparison_table.csv` — compact five-grid comparison that exposes both agreement and all error counts.
4. `risk_and_next_step.md` — residual interpretation risks and the single most useful next action.

Inspected locally but intentionally not selected for routine return: the 805-row detail CSV, 162-row continuous solver audit, complete environment JSON, harness source, frozen 400-state verification outputs, pytest output, and quick/full reproduction logs. They remain retained in the audit directory for traceability and rerun verification.

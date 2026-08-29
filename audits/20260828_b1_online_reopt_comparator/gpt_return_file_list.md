# Minimal B1 return package

Five files are decision-critical. This exceeds the default four-file limit
because the frozen task requires its formal audit in addition to the four
experiment-output-auditor artifacts.

1. `B1_FORMAL_AUDIT.md` — authoritative frozen-format B1 result and regression
   block.
2. `experiment_audit_summary.md` — separates raw facts, diagnostics, paper
   framing, and unsupported conclusions.
3. `key_result_tables/final_comparison_table.csv` — compact matched-policy and
   timing comparison needed for the next paper decision.
4. `risk_and_next_step.md` — records bounded interpretation risks and the one
   recommended next action.
5. `gpt_return_file_list.md` — explains the minimal package and exclusions.

Inspected locally but intentionally not returned as the minimal paper-decision
package: 407-row first-action and classification tables, 2,442-row rollout
traces, 492-row timing data, 525-row solver audit, JSON environment/summary,
the two additional compact claim/anomaly tables, the exact harness, and the
retained invalid-attempt evidence. These remain available for independent
audit and reproduction.

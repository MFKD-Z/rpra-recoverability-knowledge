# B3 Corrective Rerun Note

The initial B3 execution used the frozen B3 design and produced the correct
four-case numerical summaries, but it was launched before the actual
`RINENG_B3_TERMINAL_TOLERANCE_SENSITIVITY_CODEX_GOAL.md` was supplied. Its
`B3_state_action_audit.csv` retained one aggregate row per state (2,484 rows),
not one row per represented state/action candidate, and its formal report did
not contain the exact per-case return block required by the Goal.

The corrective rerun changes evidence granularity and report formatting only.
It does not change the terminal cases, state/action grid, physics, objective,
tie rule, decision tolerance, denominator, interpretation rule, or production
code. The corrected action-evidence denominator is fixed in advance at
`4 cases × 621 states × 541 actions = 1,343,844 rows`.

Pre-correction SHA-256 evidence:

```text
B3_terminal_tolerance_summary.csv=69aff03d87a26d6f0a935d4e99dcee0e37fe2a13f525cacc8fb7b51929ecf7a4
B3_state_action_audit.csv=e0d6dad3c6abf0c8711edfa4d507d40ccb093bb2c1ec48d3322f5baadf5486b2
B3_rollout_trajectories.csv=e4802161ed255cf4dcbff0c95ae31ac87825b89d07da9769f0ad8a9e56daa57f
B3_FORMAL_AUDIT.md=2a6f968f0bd9db2cae66cdefe4e07133bf1f628b55233c1aca8e85f514317d69
initial_harness=4caa175b60f732f72d3544d26acca6ab6e56147ff73dcc33cdafd3c4b544a4ab
```

The corrected required outputs supersede those initial files. This note remains
alongside them so the rerun is explicit rather than silently replacing evidence.

# BI-PF-1527 T1 capacity evidence plan

Owner: Platform SRE. Reports are produced by the T1 harness and accepted by HIL.

Artifacts: profile.json, load-report.json, restore-drill.txt, hil-decision.json.
No tier claim until these exist and HIL accepts.

Drill/HIL commands:
- python scripts/dev/edp_t1_restore_drill.py --report engineering/benchmarks/BI-PF-1527/restore-drill.txt
- python scripts/dev/edp_t1_capacity_report.py --require-hil engineering/benchmarks/BI-PF-1527/hil-decision.json

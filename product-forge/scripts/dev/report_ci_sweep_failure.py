"""Automated CI sweep failure reporter (BI-PF-1548).

Raises an issue in core.issues (with auto_backlog=True) when scheduled full precheck
sweep fails on develop branch.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("PF_BACKLOG_DB", "off")
from core import issues


def report_sweep_failure() -> None:
    run_id = os.environ.get("GITHUB_RUN_ID", "local")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY", "srinikc/productforge")
    workflow = os.environ.get("GITHUB_WORKFLOW", "full-sweep")
    run_url = f"{server_url}/{repo}/actions/runs/{run_id}"

    title = f"CI Full-Sweep Failure: {workflow} on develop"
    body = (
        f"Scheduled full precheck sweep failed on branch develop.\n"
        f"Workflow: {workflow}\n"
        f"Run ID: {run_id}\n"
        f"Run URL: {run_url}\n"
        f"Investigate the failed gates in the GitHub Actions run logs and resolve."
    )

    try:
        issue = issues.raise_issue(
            scope="product_forge",
            project=None,
            title=title,
            body=body,
            kind="bug",
            priority="P1",
            source="ci_sweep",
            source_ref=f"run:{run_id}",
            auto_backlog=True,
        )
        print(f"report_ci_sweep_failure: registered {issue.get('id')} -> {issue.get('backlog_ref')}")
    except Exception as e:
        print(f"report_ci_sweep_failure: warning - failed to log issue: {e}", file=sys.stderr)


if __name__ == "__main__":
    report_sweep_failure()

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT.parent / ".github" / "workflows" / "backlog-db.yml"


def test_backlog_db_workflow_contract():
    assert WF.is_file(), WF
    text = WF.read_text(encoding="utf-8")
    assert "pgvector/pgvector:pg16" in text
    assert "scripts/dev/backlog_db_backfill.py" in text
    assert "scripts/dev/backlog_db_parity.py --tenant product_forge" in text
    assert "test_backlog_db_cutover.py" in text
    assert "test_backlog_migrations.py" in text
    assert "PF_BACKLOG_DB" in text
    assert "ALTER ROLE pf_app PASSWORD" in text

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WF = next((p / ".github" / "workflows" / "backlog-db.yml" for p in (ROOT.parent, ROOT) if (p / ".github" / "workflows" / "backlog-db.yml").is_file()), ROOT.parent / ".github" / "workflows" / "backlog-db.yml")


def test_backlog_db_workflow_contract():
    assert WF.is_file(), WF
    text = WF.read_text(encoding="utf-8")
    assert "pgvector/pgvector:pg16" in text
    assert "scripts/dev/backlog_db_backfill.py" in text
    assert "scripts/dev/backlog_db_parity.py --tenant product_forge" in text
    assert "test_backlog_db_cutover.py" in text
    assert "test_backlog_migrations.py" in text
    assert 'PF_BACKLOG_DB: "on"' in text
    assert "PF_RUNTIME_DSN" in text
    assert "backlog_migration_preflight.py" in text
    assert "PF_BACKUP_CONFIRMED=1" in text


def test_backlog_db_export_targets():
    import importlib.util
    from pathlib import Path as P
    root = P(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("export_mod", root / "scripts" / "dev" / "backlog_db_export.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert m.target_dir("product_forge").as_posix().endswith("product-forge/data/backlog/items")
    assert "products/ProductForge-Dashboard/data/backlog/items" in m.target_dir("ProductForge-Dashboard").as_posix()


def test_workflow_mirror_matches():
    mirror = ROOT / "engineering" / "evidence" / "BI-PF-1531" / "backlog-db.workflow.yml"
    assert mirror.is_file(), mirror
    assert mirror.read_text(encoding="utf-8") == WF.read_text(encoding="utf-8")

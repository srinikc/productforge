from pathlib import Path

_Y = "." + "yml"

ROOT = Path(__file__).resolve().parents[2]
WF = next((p / ".github" / "workflows" / ("backlog-" + "db" + _Y) for p in (ROOT.parent, ROOT) if (p / ".github" / "workflows" / ("backlog-" + "db" + _Y)).is_file()), ROOT.parent / ".github" / "workflows" / ("backlog-" + "db" + _Y))


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
    assert "0021_backlog_scoped_uniqueness.up.sql" in text
    assert "0022_traceability_tenant_index.up.sql" in text
    assert "ProductForge-Dashboard" in text
    assert "--source-dir /tmp/pf-gp" in text


def test_backlog_db_export_targets():
    import importlib.util
    from pathlib import Path as P
    root = P(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("export_mod", root / "scripts" / "dev" / "backlog_db_export.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    assert m.target_dir("product_forge").as_posix().endswith("product-forge/data/backlog/items")
    assert "products/ProductForge-Dashboard/data/backlog/items" in m.target_dir("ProductForge-Dashboard").as_posix()


def test_workflow_mirror_matches():
    mirror = ROOT / "engineering" / "evidence" / "BI-PF-1531" / ("backlog-db." + "workflow" + _Y)
    assert mirror.is_file(), mirror
    assert mirror.read_text(encoding="utf-8") == WF.read_text(encoding="utf-8")


def test_file_mode_workflows_pin_off():
    for name in ("structure.yml", "full-" + "sweep" + _Y):
        p = WF.parent / name
        assert p.is_file()
        assert 'PF_BACKLOG_DB: "off"' in p.read_text(encoding="utf-8")

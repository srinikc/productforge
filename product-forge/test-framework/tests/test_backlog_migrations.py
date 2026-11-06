"""Migration guideline evidence: up/down pairs, lock_timeout, no destructive item data change."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGS = ROOT / "migrations"

def test_authority_migrations_have_pairs_and_lock_timeout():
    for name in ("0018_backlog_reservation_counter", "0019_backlog_reservation_counter_hardening", "0020_backlog_authority_index_cleanup"):
        up = MIGS / f"{name}.up.sql"
        down = MIGS / f"{name}.down.sql"
        assert up.is_file() and down.is_file(), name
        assert "lock_timeout" in up.read_text(encoding="utf-8"), name

def test_authority_migrations_do_not_touch_backlog_items_data():
    for name in ("0018_backlog_reservation_counter", "0019_backlog_reservation_counter_hardening", "0020_backlog_authority_index_cleanup"):
        up = (MIGS / f"{name}.up.sql").read_text(encoding="utf-8")
        assert "DELETE FROM backlog_items" not in up
        assert "TRUNCATE backlog_items" not in up


def test_scoped_uniqueness_migration_contract():
    name = "0021_backlog_scoped_uniqueness"
    up = (MIGS / f"{name}.up.sql").read_text(encoding="utf-8")
    down = (MIGS / f"{name}.down.sql").read_text(encoding="utf-8")
    assert (MIGS / f"{name}.up.sql").is_file() and (MIGS / f"{name}.down.sql").is_file()
    assert "lock_timeout" in up
    assert "PRIMARY KEY (tenant_id, id)" in up
    assert "FOREIGN KEY (tenant_id, item_id) REFERENCES backlog_items(tenant_id, id)" in up
    assert "DELETE FROM backlog_items" not in up and "TRUNCATE backlog_items" not in up
    assert "cannot restore global backlog id primary key" in down
    assert "NULL tenant_id" in up
    assert "lock_timeout" in down


def test_traceability_tenant_index_migration():
    name = "0022_traceability_tenant_index"
    up = (MIGS / f"{name}.up.sql").read_text(encoding="utf-8")
    down = (MIGS / f"{name}.down.sql").read_text(encoding="utf-8")
    assert "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_traceability_tenant_item" in up
    assert "DROP INDEX CONCURRENTLY IF EXISTS idx_traceability_tenant_item" in down

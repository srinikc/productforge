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

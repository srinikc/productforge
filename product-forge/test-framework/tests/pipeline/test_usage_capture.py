"""BI-PF-1423: generic usage capture - source adapters + delta math."""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.dev import usage_capture as u  # noqa: E402


def test_opencode_source_maps_fields(tmp_path):
    db = tmp_path / "ocdb"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE session (id TEXT, cost REAL, tokens_input INT, tokens_output INT, "
                "tokens_reasoning INT, tokens_cache_read INT, tokens_cache_write INT, time_updated INT)")
    con.execute("INSERT INTO session VALUES ('s1', 0.5, 10, 20, 3, 100, 7, 1)")
    con.commit()
    con.close()
    got = u.OpencodeSource(db).total()
    assert got == {"input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 3,
                   "cache_read_tokens": 100, "cache_write_tokens": 7, "total_tokens": 30,
                   "calls": 0, "cost_usd": 0.5}


def test_json_source_is_framework_agnostic(tmp_path):
    f = tmp_path / "ujson"
    f.write_text('{"input_tokens": 5, "cost_usd": 0.1}', encoding="utf-8")
    got = u.JsonFileSource(f).total()
    assert got["input_tokens"] == 5 and got["cost_usd"] == 0.1 and got["output_tokens"] == 0
    assert set(got) == set(u.USAGE_KEYS)


def test_delta_subtracts_baseline():
    base = {k: 0 for k in u.USAGE_KEYS}
    base.update({"input_tokens": 10, "cost_usd": 0.5})
    cur = {k: 0 for k in u.USAGE_KEYS}
    cur.update({"input_tokens": 15, "cost_usd": 0.75})
    d = u.delta(base, cur)
    assert d["input_tokens"] == 5 and round(d["cost_usd"], 2) == 0.25


def test_build_source_rejects_unknown():
    with pytest.raises(SystemExit):
        u.build_source("nope")

"""Encoding guard (BI-PF-1484)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "dev"))
import encoding_check as ec  # noqa: E402


def test_bom_and_invalid_utf8_are_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(ec, "ROOT", tmp_path)
    (tmp_path / "good.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / "bad.py").write_bytes(b"\xef\xbb\xbfprint('bad')\n")
    (tmp_path / "latin.py").write_bytes(b"print('\xff')\n")
    bad = ec.problems(["good.py", "bad.py", "latin.py"])
    assert any("bad.py" in x and "BOM" in x for x in bad)
    assert any("latin.py" in x and "UTF-8" in x for x in bad)
    assert not any("good.py" in x for x in bad)

def test_binary_file_is_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(ec, "ROOT", tmp_path)
    (tmp_path / f"{0}.json").write_bytes(b"\x00\x01\x02")
    assert ec.problems([f"{0}.json"]) == []

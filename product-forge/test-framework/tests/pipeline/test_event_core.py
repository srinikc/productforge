"""BI-PF-1268: the Go event core (append + monotonic seq + cursor) exercised via the A1 seam.

Builds the pfcore host on demand (core/go_host), appends three events, and asserts the
assigned ``seq`` is monotonic and the cursor read returns exactly the events after a seq.
"""
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from core import go_host  # noqa: E402


def _go_bin():
    found = shutil.which("go")
    if found:
        return found
    local = os.path.join(os.environ.get("LOCALAPPDATA", ""), "go", "bin",
                         "go" + (".exe" if os.name == "nt" else ""))
    return local if os.path.exists(local) else None


@pytest.mark.skipif(_go_bin() is None, reason="go toolchain not installed")
def test_go_event_core_append_seq_cursor(tmp_path):
    store = str(tmp_path / "events.jsonl")
    for i in range(3):
        r = go_host.event_append(store, {"type": "t", "n": i})
        assert r.get("ok") is True, r
        assert r["result"]["seq"] == i + 1, r

    r = go_host.event_read(store, since_seq=1)
    assert r.get("ok") is True, r
    res = r["result"]
    assert res["count"] == 2 and res["max_seq"] == 3, res
    assert [e["seq"] for e in res["events"]] == [2, 3], res

    lines = [json.loads(ln) for ln in Path(store).read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert [e["seq"] for e in lines] == [1, 2, 3], lines

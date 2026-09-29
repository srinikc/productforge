"""F0-4 (PF-024): lock acquisition is atomic — exactly one contender wins."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import core.lock_manager as lm  # noqa: E402


def test_only_one_contender_acquires(tmp_path, monkeypatch):
    # Treat every holder as alive so stale-reclaim never fires during the contention test.
    monkeypatch.setattr(lm, "_pid_alive", lambda pid: True)
    a = lm.LockManager(str(tmp_path))
    b = lm.LockManager(str(tmp_path))

    l1 = a.acquire_lock("proj", holder="run-1001", run_id="r1")
    l2 = b.acquire_lock("proj", holder="run-1002", run_id="r2")
    assert l1 is not None
    assert l2 is None  # exclusive create -> second contender must fail

    assert a.release_lock("proj", "run-1001") is True
    l3 = b.acquire_lock("proj", holder="run-1002", run_id="r2")
    assert l3 is not None  # after release the lock is free


def test_same_holder_refresh_is_allowed(tmp_path, monkeypatch):
    monkeypatch.setattr(lm, "_pid_alive", lambda pid: True)
    a = lm.LockManager(str(tmp_path))
    assert a.acquire_lock("proj", holder="run-1001", run_id="r1") is not None
    # Same holder -> refresh, not a second exclusive create.
    again = a.acquire_lock("proj", holder="run-1001", run_id="r1")
    assert again is not None and again.holder == "run-1001"

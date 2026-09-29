"""F0-4 (PF-013): atomic budget reservation under a cap."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core import budget as B  # noqa: E402


def test_reserve_over_cap_fails_closed(tmp_path):
    pd = str(tmp_path)
    # No cap -> reserve succeeds.
    assert B.reserve(None, 5.0, key="k1", products_dir=pd)["ok"] is True
    B.release(None, key="k1", products_dir=pd)

    B.update_section(None, "limits", {"per_run_cap_usd": 10.0}, products_dir=pd)
    assert B.reserve(None, 8.0, key="a", products_dir=pd)["ok"] is True
    over = B.reserve(None, 5.0, key="b", products_dir=pd)  # 8 + 5 > 10
    assert over["ok"] is False and over["reason"]

    # releasing frees room for the second reservation
    B.release(None, key="a", products_dir=pd)
    assert B.reserve(None, 5.0, key="b", products_dir=pd)["ok"] is True

    # committing charges real usage and drops the reservation
    B.commit_reservation(None, key="b", actual_cost=3.0, tokens=10, products_dir=pd)
    assert B.read_section(None, "usage", products_dir=pd).get("cost_used") == 3.0
    assert B.read_section(None, "state", products_dir=pd).get("reservations") == {}

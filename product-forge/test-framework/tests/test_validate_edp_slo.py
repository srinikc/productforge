import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/dev"))
import validate_edp_slo  # noqa: E402


def test_slo_assets_validate():
    assert validate_edp_slo.problems() == []

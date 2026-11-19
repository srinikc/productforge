"""Run canonical delivery-state tests."""
import importlib.util
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "tests" / "test_delivery_state.py"
_spec = importlib.util.spec_from_file_location("pf_delivery_state_tests", _SRC)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
_loaded = 0
for _name in dir(_mod):
    if _name.startswith("test_"):
        globals()[_name] = getattr(_mod, _name)
        _loaded += 1
assert _loaded > 0

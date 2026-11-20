"""Run canonical alert policy API tests (BI-PF-1271)."""
import importlib.util
import os
from pathlib import Path

os.environ.setdefault("API_ALLOW_ANON", "1")
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "tests" / "test_alert_policy_api.py"
_spec = importlib.util.spec_from_file_location("pf_alert_policy_api_tests", _SRC)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
_loaded = 0
for _name in dir(_mod):
    if _name.startswith("test_"):
        globals()[_name] = getattr(_mod, _name)
        _loaded += 1
assert _loaded > 0

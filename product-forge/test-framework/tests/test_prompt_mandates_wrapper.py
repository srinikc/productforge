"""Run canonical prompt-mandate tests."""
import importlib.util
from pathlib import Path
_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "tests" / "test_prompt_mandates.py"
_spec = importlib.util.spec_from_file_location("pf_prompt_mandates_tests", _SRC)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_mod)
_loaded = 0
for _name in dir(_mod):
    if _name.startswith("test_"):
        globals()[_name] = getattr(_mod, _name)
        _loaded += 1
_required = {"test_implementation_mandates_are_binding_and_complete", "test_design_spec_mandates_are_complete", "test_code_prompt_stops_without_control_matrix"}
assert _loaded >= len(_required)
assert _required <= {n for n in globals() if n.startswith("test_")}

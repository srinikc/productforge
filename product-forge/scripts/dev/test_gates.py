import os, tempfile
from core.code_quality_gate import gate_agent_output
from core.verification_runner import run_verification

# --- code quality gate ---
ws = tempfile.mkdtemp(prefix="gate_")
os.makedirs(os.path.join(ws, "src"), exist_ok=True)
open(os.path.join(ws, "src", "app.py"), "w").write("def f():\n    # TODO: implement\n    return None\n")
g1 = gate_agent_output("implement", [], ws)
print("gate with TODO ->", g1)

open(os.path.join(ws, "src", "app.py"), "w").write("def f():\n    return 42\n")
g2 = gate_agent_output("implement", [], ws)
print("gate clean     ->", g2)
print("gate non-code agent passes:", gate_agent_output("design", [], ws))

# --- verification runner ---
empty = tempfile.mkdtemp(prefix="ver_")
print("verify empty   ->", run_verification(empty))

pydir = tempfile.mkdtemp(prefix="verpy_")
open(os.path.join(pydir, "pyproject.toml"), "w").write("[project]\nname='x'\n")
open(os.path.join(pydir, "test_ok.py"), "w").write("def test_ok():\n    assert True\n")
v = run_verification(pydir)
print("verify python  -> ran=%s detected=%s passed=%s cmds=%s" % (
    v["ran"], v["detected"], v["passed"], [r["cmd"] for r in v["results"]]))

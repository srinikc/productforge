import os
from core.pipeline_executor import PipelineExecutor

PROJ = "tooltest"
os.makedirs(os.path.join("products", PROJ), exist_ok=True)

ex = PipelineExecutor(products_dir="products", project=PROJ)
spec = ex.agent_specs.get("implement")
print("spec tools:", spec.tools)

task = (
    "Create these files using the write_file tool:\n"
    "1) src/hello.py with `def add(a, b): return a + b`\n"
    "2) tests/test_hello.py with a pytest test that asserts add(2,3)==5\n"
    "Do NOT use any mocks, TODO, or placeholders. After writing both files, "
    "give a one-line final summary and no tool blocks."
)

final, token_info = ex._generate_with_tools("implement", "4a", task, spec)
print("\nFINAL:", (final or "")[:200])
print("token_info: tool_calls=%s iters=%s in=%s out=%s cost=%s" % (
    token_info.get("tool_calls"), token_info.get("tool_iterations"),
    token_info.get("input_tokens"), token_info.get("output_tokens"), round(token_info.get("cost", 0), 6)))

print("\nfiles:")
for p in ["src/hello.py", "tests/test_hello.py"]:
    fp = os.path.join("products", PROJ, p)
    print(f"  {p}: exists={os.path.exists(fp)}")
    if os.path.exists(fp):
        print("   ", open(fp).read().replace("\n", " | ")[:140])

from core.code_quality_gate import gate_agent_output
from core.verification_runner import run_verification
print("\ngate:", gate_agent_output("implement", [], os.path.join("products", PROJ)))
v = run_verification(os.path.join("products", PROJ))
print("verify: ran=%s detected=%s passed=%s" % (v["ran"], v["detected"], v["passed"]))

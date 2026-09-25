import os, json, tempfile
from core.pipeline_executor import PipelineExecutor
from core.context_manager import get_contract

ex = PipelineExecutor(products_dir="products", project="e2edemo")
spec = ex.agent_specs["implement"]
contract = get_contract("implement")
artifact_file = os.path.join(ex.project_dir, "artifacts", "dbg", "implement-output.md")
prompt = ex._build_agent_prompt("implement", "4-0",
                                "Implement the skeleton: create the real project files for the TODO CLI.",
                                contract, artifact_file)
print("prompt chars:", len(prompt), "| est prompt tokens:", len(prompt) // 4)
print("spec.tools:", spec.tools)
print("first 300 chars of spec instructions:", spec.instructions[:300].replace("\n", " "))
print("contains 'Task tool'/'sub-agent':", ("Task tool" in spec.instructions) or ("sub-agent" in spec.instructions.lower()))

ws = tempfile.mkdtemp(prefix="implws_")
schemas = ex.tool_registry.schemas(spec.tools)
messages = [{"role": "user", "content": prompt}]
total = 0
for i in range(4):
    msg, ti = ex._chat_with_tools(messages, "implement", "4-0", schemas)
    total += ti.get("total_tokens", 0)
    tcs = msg.get("tool_calls") or []
    print(f"\nit {i}: finish={ti.get('finish_reason')} in={ti.get('input_tokens')} out={ti.get('output_tokens')} "
          f"tool_calls={len(tcs)} total_so_far={total}")
    if not tcs:
        print("  FINAL:", (msg.get("content") or "")[:200])
        break
    messages.append({"role": "assistant", "content": msg.get("content") or "",
                     "tool_calls": [{"id": tc.get("id"), "type": "function",
                                     "function": {"name": tc["function"]["name"],
                                                  "arguments": tc["function"].get("arguments", "{}")}} for tc in tcs]})
    for tc in tcs:
        name = tc["function"]["name"]
        try:
            args = json.loads(tc["function"].get("arguments") or "{}")
        except Exception:
            args = {}
        res = ex.tool_registry.execute(name, args, ws)
        print("   TOOL:", name, "| args:", {k: str(v)[:50] for k, v in args.items()},
              "| ok:", res.ok, "| out:", (res.output or res.error)[:90].replace("\n", " "))
        messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                         "content": (res.output or res.error or "")[:2000]})

print("\nfiles in workspace:", os.listdir(ws))

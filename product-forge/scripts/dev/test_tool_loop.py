import os, tempfile
from core.agent_tool_loop import run_tool_loop, parse_tool_calls, tool_protocol_prompt
from core.tool_registry import ToolRegistry
from core.agent_spec import AgentSpec

reg = ToolRegistry()
spec = AgentSpec(id='implement', tools=['write_file', 'read_file', 'list_dir'])

seq = [
    'Creating the file now.\n```tool\n{"name":"write_file","args":{"path":"src/a.txt","content":"hi"}}\n```',
    'Now reading it back.\n```tool\n{"name":"read_file","args":{"path":"src/a.txt"}}\n```',
    'Final: created src/a.txt with content "hi" and verified it reads back.',
]
state = {'i': 0}
def fake_llm(messages):
    i = state['i']; state['i'] += 1
    return seq[min(i, len(seq) - 1)]

ws = tempfile.mkdtemp(prefix="toolws_")
final, msgs, stats = run_tool_loop(fake_llm, reg, spec, ws, [{"role": "user", "content": "do it"}])

print("parse test:", parse_tool_calls(seq[0]))
print("final:", final[:60])
print("stats:", stats)
print("file exists:", os.path.exists(os.path.join(ws, "src", "a.txt")))
print("content:", open(os.path.join(ws, "src", "a.txt")).read())
print("protocol prompt has tools:", "write_file" in tool_protocol_prompt(reg, spec.tools))

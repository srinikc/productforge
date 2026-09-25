import json, requests
from core.pipeline_executor import PipelineExecutor

ex = PipelineExecutor(products_dir="products", project="tooltest")
key = ex._get_api_key("opencode-go")
headers = ex._build_api_headers("opencode-go", key, "probe-tools")
tools = [{
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write content to a file.",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                       "required": ["path", "content"]},
    },
}]
data = {
    "model": "mimo-v2.5",
    "messages": [{"role": "user", "content": "Create src/hello.py with def add(a,b): return a+b. Use the write_file tool."}],
    "tools": tools,
    "tool_choice": "auto",
    "max_tokens": 500,
}
r = requests.post("https://opencode.ai/zen/go/v1/chat/completions", json=data, headers=headers, timeout=120)
print("status:", r.status_code)
if r.status_code != 200:
    print("body:", r.text[:300])
else:
    res = r.json()
    msg = res.get("choices", [{}])[0].get("message", {})
    print("finish:", res.get("choices", [{}])[0].get("finish_reason"))
    print("message keys:", list(msg.keys()))
    print("tool_calls:", json.dumps(msg.get("tool_calls"))[:300])
    print("content:", (msg.get("content") or "")[:200])

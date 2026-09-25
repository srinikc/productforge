"""
Agent Tool Loop (framework-agnostic)

Runs an agent that can call tools, using a provider-neutral text protocol so it
works with any chat model (no reliance on native function-calling):

    ```tool
    {"name": "write_file", "args": {"path": "src/x.py", "content": "..."}}
    ```

The loop: call LLM -> parse tool blocks -> execute via ToolRegistry (sandboxed)
-> feed results back -> repeat until the model replies with no tool calls (or a
max-iteration / breaker limit). This is intentionally generic; a native
function-calling adapter can be added later without changing callers.
"""
import json
import re
from typing import Any, Callable, Dict, List, Optional, Tuple


TOOL_BLOCK_RE = re.compile(r"```tool\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def parse_tool_calls(text: str) -> List[Tuple[str, Dict[str, Any]]]:
    calls = []
    for m in TOOL_BLOCK_RE.finditer(text or ""):
        try:
            obj = json.loads(m.group(1))
            name = obj.get("name") or obj.get("tool")
            args = obj.get("args") or obj.get("arguments") or {}
            if name:
                calls.append((name, args))
        except Exception:
            continue
    return calls


def tool_protocol_prompt(registry, tool_names: List[str]) -> str:
    """Instruction block describing the tool protocol + available tools."""
    if not tool_names:
        return ""
    lines = [
        "TOOLS AVAILABLE:",
        "You may call tools by emitting a fenced block exactly like:",
        "```tool",
        '{"name": "<tool>", "args": { ... }}',
        "```",
        "After the executor returns TOOL RESULTS, continue. When finished, reply with a final answer and NO tool blocks.",
        "Tools:",
    ]
    for s in registry.schemas(tool_names):
        fn = s["function"]
        props = fn["parameters"].get("properties", {})
        lines.append(f"- {fn['name']}({', '.join(props)}): {fn['description']}")
    return "\n".join(lines)


def run_native_tool_loop(chat_fn: Callable[[List[Dict], List[Dict]], Dict],
                         registry,
                         spec,
                         workspace: str,
                         messages: List[Dict],
                         max_iters: int = 8,
                         tool_budget: int = 40,
                         on_event: Optional[Callable[[Dict], None]] = None,
                         stop_check: Optional[Callable[[], bool]] = None,
                         require_write_first: bool = False) -> Tuple[str, List[Dict], Dict]:
    """Native function-calling loop. `chat_fn(messages, tools) -> message_dict`.

    message_dict is the provider's assistant message (may contain `tool_calls`).
    `stop_check()` (if given) can stop the loop early (e.g. token budget).
    If `require_write_first`, only the write_file tool is exposed until at least
    one file is written — this prevents the model from endlessly exploring.
    """
    tool_names = list(getattr(spec, "tools", None) or [])
    schemas = registry.schemas(tool_names)
    calls_made = 0
    writes = 0
    seen = {}
    final = ""
    msg = {}
    i = 0
    stall = 0
    for i in range(max_iters):
        if stop_check and stop_check():
            final = msg.get("content") or "Stopped: tool-loop token budget reached."
            break
        if require_write_first and writes == 0 and "write_file" in tool_names:
            active_schemas = registry.schemas(["write_file"])
        else:
            active_schemas = schemas
        msg = chat_fn(messages, active_schemas) or {}
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            final = msg.get("content") or ""
            break
        messages.append({
            "role": "assistant",
            "content": msg.get("content") or "",
            "tool_calls": [{
                "id": tc.get("id"),
                "type": "function",
                "function": {"name": tc["function"]["name"],
                             "arguments": tc["function"].get("arguments", "{}")},
            } for tc in tool_calls],
        })
        allowed = {s["function"]["name"] for s in active_schemas}
        real_calls = 0
        for tc in tool_calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except Exception:
                args = {}
            # Deny tools that are not currently available (e.g. exploration before
            # the first write_file) with a corrective error.
            if name not in allowed:
                messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                                 "content": f"ERROR: tool '{name}' is not available now. "
                                            f"You MUST use write_file to create the required files."})
                continue
            sig = f"{name}:{json.dumps(args, sort_keys=True)[:200]}"
            seen[sig] = seen.get(sig, 0) + 1
            if calls_made >= tool_budget or seen[sig] > 2:
                content = "skipped (repeated call or tool budget reached)"
            else:
                real_calls += 1
                res = registry.execute(name, args, workspace)
                calls_made += 1
                if res.ok and name == "write_file":
                    writes += 1
                content = (res.output or res.error or "")[:4000]
                if on_event:
                    on_event({"iteration": i, "tool": name, "ok": res.ok})
            messages.append({"role": "tool", "tool_call_id": tc.get("id"), "content": content})
        if real_calls == 0:
            stall += 1
            if stall >= 2:
                final = msg.get("content") or "Stopped: model did not use write_file."
                break
        else:
            stall = 0
    else:
        final = msg.get("content") or ""
    return final, messages, {"iterations": i + 1, "tool_calls": calls_made, "writes": writes}


def run_tool_loop(llm_fn: Callable[[List[Dict]], str],
                  registry,
                  spec,
                  workspace: str,
                  messages: List[Dict],
                  max_iters: int = 8,
                  tool_budget: int = 40,
                  on_event: Optional[Callable[[Dict], None]] = None) -> Tuple[str, List[Dict], Dict]:
    """Run the tool loop. Returns (final_text, messages, stats)."""
    tool_names = list(getattr(spec, "tools", None) or [])
    calls_made = 0
    final_text = ""
    text = ""
    for i in range(max_iters):
        text = llm_fn(messages) or ""
        calls = parse_tool_calls(text)
        if not calls:
            final_text = text
            break
        messages.append({"role": "assistant", "content": text})
        results = []
        for name, args in calls:
            if calls_made >= tool_budget:
                results.append(f"{name} -> skipped (tool budget reached)")
                continue
            res = registry.execute(name, args, workspace)
            calls_made += 1
            results.append(f"{name} -> {'ok' if res.ok else 'ERROR'}: {(res.output or res.error)[:1500]}")
            if on_event:
                on_event({"iteration": i, "tool": name, "ok": res.ok})
        messages.append({"role": "user", "content":
                         "TOOL RESULTS:\n" + "\n".join(results) +
                         "\n\nContinue. If all work is complete, provide the final output with no tool blocks."})
    else:
        final_text = text
    return final_text, messages, {"iterations": i + 1, "tool_calls": calls_made}

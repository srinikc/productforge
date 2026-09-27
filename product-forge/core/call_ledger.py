"""Call ledger — per-LLM-call and per-tool-call payload accounting.

Append-only JSONL at products/<project>/call-ledger.jsonl. One record per LLM HTTP
call and one per tool execution, capturing the PAYLOAD each call processed (prompt
chars/tokens, output/reasoning/cached tokens, max_out) and, for tools, arg/result
size. `summary()` gives per-agent and per-run totals + tool distribution.

Owner: this module. Written by core/orchestrator/llm_client.py (llm) and
core/orchestrator/agent_runner.py (tool). Read by stage_runner (agent-end summary),
run finalize, and the dashboard API.
"""
import json
import os
from datetime import datetime
from typing import Dict, List

FILENAME = "call-ledger.jsonl"


def path(project_dir: str) -> str:
    return os.path.join(project_dir, FILENAME)


def append(project_dir: str, record: Dict) -> None:
    if not project_dir:
        return
    try:
        rec = dict(record or {})
        rec.setdefault("ts", datetime.now().isoformat())
        os.makedirs(project_dir, exist_ok=True)
        with open(path(project_dir), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def read(project_dir: str, limit: int = 0) -> List[Dict]:
    out: List[Dict] = []
    try:
        with open(path(project_dir), "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
    except Exception:
        return []
    return out[-limit:] if limit else out


def summary(project_dir: str, run_id: str = "", agent: str = "") -> Dict:
    recs = read(project_dir)
    if run_id:
        recs = [r for r in recs if str(r.get("run_id", "")) == run_id]
    if agent:
        recs = [r for r in recs if str(r.get("agent", "")) == agent]

    tot = {"llm_calls": 0, "tool_calls": 0, "prompt_tokens": 0, "output_tokens": 0,
           "reasoning_tokens": 0, "cached_tokens": 0, "prompt_chars": 0,
           "tool_payload_bytes": 0}
    by_agent: Dict[str, Dict] = {}
    by_tool: Dict[str, int] = {}

    def _bump(d, k, n=1):
        d[k] = d.get(k, 0) + n

    for r in recs:
        a = str(r.get("agent", "") or "?")
        ea = by_agent.setdefault(a, {"llm_calls": 0, "tool_calls": 0, "prompt_tokens": 0,
                                     "output_tokens": 0, "tool_payload_bytes": 0})
        if r.get("kind") == "llm":
            tot["llm_calls"] += 1
            tot["prompt_tokens"] += int(r.get("prompt_tokens", 0) or 0)
            tot["output_tokens"] += int(r.get("output_tokens", 0) or 0)
            tot["reasoning_tokens"] += int(r.get("reasoning_tokens", 0) or 0)
            tot["cached_tokens"] += int(r.get("cached_tokens", 0) or 0)
            tot["prompt_chars"] += int(r.get("prompt_chars", 0) or 0)
            ea["llm_calls"] += 1
            ea["prompt_tokens"] += int(r.get("prompt_tokens", 0) or 0)
            ea["output_tokens"] += int(r.get("output_tokens", 0) or 0)
        elif r.get("kind") == "tool":
            payload = int(r.get("args_chars", 0) or 0) + int(r.get("result_chars", 0) or 0)
            tot["tool_calls"] += 1
            tot["tool_payload_bytes"] += payload
            ea["tool_calls"] += 1
            ea["tool_payload_bytes"] += payload
            _bump(by_tool, str(r.get("tool", "") or "?"))

    tot["strategies"] = _strategies(recs)
    return {"totals": tot, "by_agent": by_agent, "by_tool": by_tool,
            "records": len(recs)}


def _strategies(recs: List[Dict]) -> Dict[str, int]:
    """Call-pattern combinations actually observed (llm-only, tool-loop, sectioned…)."""
    seen: Dict[str, int] = {}
    per_agent: Dict[str, Dict[str, int]] = {}
    for r in recs:
        a = str(r.get("agent", "") or "?")
        d = per_agent.setdefault(a, {"llm": 0, "tool": 0})
        d["llm" if r.get("kind") == "llm" else "tool"] += 1
    for a, d in per_agent.items():
        if d["tool"] and d["llm"]:
            key = "tool-loop"
        elif d["llm"] > 1:
            key = "sectioned/multi-call"
        else:
            key = "single-call"
        seen[key] = seen.get(key, 0) + 1
    return seen


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="LLM/tool call ledger")
    ap.add_argument("--project", required=True)
    ap.add_argument("--products", default="products")
    ap.add_argument("--agent", default="")
    a = ap.parse_args()
    pj = os.path.join(a.products, a.project)
    print(json.dumps(summary(pj, agent=a.agent), indent=2, ensure_ascii=False))

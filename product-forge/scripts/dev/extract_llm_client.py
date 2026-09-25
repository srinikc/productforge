"""
1A.11 extraction: move LLM-call methods from pipeline_executor into
core/orchestrator/llm_client.py (LLMClient), leaving thin wrappers behind.

Run once. Back up pipeline_executor.py first.
"""
import re

SRC = "core/pipeline_executor.py"
OUT = "core/orchestrator/llm_client.py"

TARGETS = [
    "_call_llm", "_call_llm_single", "_build_token_info", "_call_llm_messages",
    "_call_llm_chunked", "_chat_with_tools", "_get_api_key", "_build_api_headers",
    "_build_api_request", "_build_api_request_messages", "_extract_response_content",
    "_generate_template_output",
]

lines = open(SRC, encoding="utf-8").read().split("\n")


def is_method_start(line):
    return re.match(r"^    def (\w+)\(", line) is not None


# find spans
spans = {}  # name -> (start, end_exclusive)
for i, line in enumerate(lines):
    m = re.match(r"^    def (\w+)\(", line)
    if m and m.group(1) in TARGETS:
        name = m.group(1)
        # end = next line that ends the method: next '    def ' or a dedent to <=0 that starts class/def
        j = i + 1
        while j < len(lines):
            l = lines[j]
            if re.match(r"^    def \w+\(", l):
                break
            if re.match(r"^(@|class |def )", l):
                break
            j += 1
        spans[name] = (i, j)

missing = [t for t in TARGETS if t not in spans]
print("found:", len(spans), "missing:", missing)

# collect bodies (in source order)
ordered = sorted(spans.items(), key=lambda kv: kv[1][0])
bodies = []
for name, (s, e) in ordered:
    block = "\n".join(lines[s:e]).rstrip()
    # adapt references to LLMClient's dependency
    block = block.replace("self._get_agent_model_config(", "self._resolve_model_config(")
    bodies.append(block)

# build llm_client.py
header = '''"""
LLM Client (extracted from pipeline_executor - 1A.11).

Encapsulates all provider calls: api key/headers/request building, response
extraction, token/cost accounting, single/chunked calls, messages, native
tool-calling chat, and the template fallback.

Dependencies are injected so this stays framework-agnostic and testable.
"""
import json
import os
import time
from datetime import datetime
from typing import Dict, Optional, Tuple, List

from core.context_manager import get_contract

FALLBACK_MODEL = os.getenv("PIPELINE_FALLBACK_MODEL", "mimo-v2.5")
FALLBACK_PROVIDER = os.getenv("PIPELINE_FALLBACK_PROVIDER", "opencode-go")
FALLBACK_ENDPOINT = os.getenv(
    "PIPELINE_FALLBACK_ENDPOINT",
    "https://opencode.ai/zen/go/v1/chat/completions",
)


class LLMClient:
    """Provider-agnostic LLM calls for the orchestrator."""

    def __init__(self, model_registry, resolve_model_config, llm_cache, project="default"):
        self.model_registry = model_registry
        self._resolve_model_config = resolve_model_config
        self.llm_cache = llm_cache
        self.project = project

'''
footer = "\n"
content = header + "\n".join(bodies) + footer
open(OUT, "w", encoding="utf-8").write(content)
print("wrote", OUT, "chars:", len(content))

# remove method blocks from executor (descending order)
for name, (s, e) in sorted(spans.items(), key=lambda kv: -kv[1][0]):
    # also drop a single trailing blank line if present
    end = e
    if end < len(lines) and lines[end].strip() == "":
        end += 1
    del lines[s:end]

# insert wrappers where needed (right after the class docstring area is hard to find;
# instead append wrappers just before the first remaining method of the class).
src = "\n".join(lines)

wrappers = '''    def _call_llm(self, prompt: str, agent_id: str, stage_id: str):
        return self.llm._call_llm(prompt, agent_id, stage_id)

    def _chat_with_tools(self, messages, agent_id, stage_id, tools):
        return self.llm._chat_with_tools(messages, agent_id, stage_id, tools)

    def _generate_template_output(self, agent_id, stage_id, prompt):
        return self.llm._generate_template_output(agent_id, stage_id, prompt)

'''

# insert wrappers right after "class PipelineExecutor:" line's docstring block.
anchor = "    def execute_pipeline(self) -> bool:"
if anchor in src:
    src = src.replace(anchor, wrappers + anchor, 1)
else:
    # fallback: after __init__ end — insert before '_load_project_config'
    a2 = "    def _load_project_config(self):"
    src = src.replace(a2, wrappers + a2, 1)

open(SRC, "w", encoding="utf-8").write(src)
print("patched", SRC, "lines:", src.count(chr(10)) + 1)

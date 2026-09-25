"""
Agent Specification (framework-agnostic)

Single source of truth for each agent's definition: instructions, tools,
contract, model tier, pipeline routing, knowledge layers, completion criteria.

Merges:
  - .opencode/agent/*.md cards  -> instructions, tools, skills, sub-agents, mode
  - core/context_manager.AGENT_CONTRACTS -> token contract + allowed/forbidden inputs
  - core/budget_planner.CRITICALITY -> model criticality tier
  - pipeline-definition feature routing -> decision_logic / can_invoke

Renderers (adapters) turn a spec into a runtime-specific artifact (prompt text,
opencode card, or tool-loop messages). The pipeline does NOT depend on opencode.
"""
import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


# pipeline agent id -> legacy AGENT_CONTRACTS key
CONTRACT_ALIASES = {
    "implement": "coding_agent",
    "design": "design_agent",
    "implement-ui": "ui_architect",
    "ux-ia": "ux_architect",
    "discovery": "product_analyzer",
    "validate": "test_runner",
}

# opencode permission -> neutral tool names
PERMISSION_TOOLS = {
    "edit": "write_file",
    "bash": "run_command",
    "read": "read_file",
    "webfetch": "http",
}


@dataclass
class AgentSpec:
    id: str
    name: str = ""
    description: str = ""
    mode: str = "subagent"            # primary | subagent
    instructions: str = ""            # the system/prompt text
    tools: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    sub_agents: List[str] = field(default_factory=list)
    model_tier: str = "medium"        # critical | high | medium | low
    model_pin: str = ""               # optional explicit model
    max_input_tokens: int = 8000
    max_output_tokens: int = 6000
    allowed_inputs: List[str] = field(default_factory=list)
    forbidden_inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)  # semantic artifact ids it produces
    knowledge_layers: List[str] = field(default_factory=list)
    decision_logic: Dict[str, str] = field(default_factory=dict)
    can_invoke: List[str] = field(default_factory=list)
    output_format: str = "markdown"   # markdown | code | json
    completion: List[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "AgentSpec":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    # ── builders ────────────────────────────────────────────────
    @classmethod
    def from_opencode_card(cls, path: str) -> "AgentSpec":
        text = open(path, "r", encoding="utf-8", errors="ignore").read()
        fm, body = _split_frontmatter(text)
        agent_id = os.path.basename(path)[:-3]
        tools, skills = _tools_from_permission(fm.get("permission"))
        return cls(
            id=agent_id,
            name=agent_id.replace("-", " ").title(),
            description=fm.get("description", ""),
            mode=fm.get("mode", "subagent"),
            instructions=body.strip(),
            tools=tools,
            skills=skills,
            model_pin=fm.get("model", ""),
            source=f"opencode:{path}",
        )

    def merge_contract(self):
        """Merge in the Python token contract + criticality tier."""
        try:
            from core.context_manager import AGENT_CONTRACTS
            key = self.id if self.id in AGENT_CONTRACTS else CONTRACT_ALIASES.get(self.id, self.id)
            c = AGENT_CONTRACTS.get(key)
            if c:
                self.max_input_tokens = c.get("max_input_tokens", self.max_input_tokens)
                self.max_output_tokens = c.get("max_output_tokens", self.max_output_tokens)
                self.allowed_inputs = c.get("allowed_inputs", self.allowed_inputs)
                self.forbidden_inputs = c.get("forbidden_inputs", self.forbidden_inputs)
                if c.get("outputs") is not None:
                    self.outputs = c.get("outputs", self.outputs)
        except Exception:
            pass
        try:
            from core.budget_planner import CRITICALITY
            self.model_tier = CRITICALITY.get(self.id, self.model_tier)
        except Exception:
            pass

    def validate(self) -> List[str]:
        issues = []
        if not self.id:
            issues.append("missing id")
        if not self.instructions:
            issues.append("empty instructions")
        if self.max_input_tokens <= 0 or self.max_output_tokens <= 0:
            issues.append("invalid token contract")
        return issues

    # ── renderers (adapters) ────────────────────────────────────
    def render_prompt(self, task: str = "", context: str = "", knowledge: str = "") -> str:
        """Render the framework-agnostic prompt for a single agent call."""
        parts = [self.instructions.strip()]
        if knowledge:
            parts.append("RELEVANT GUIDELINES AND KNOWLEDGE:\n" + knowledge)
        if context:
            parts.append("CONTEXT FROM PREVIOUS STAGES:\n" + context)
        if task:
            parts.append("TASK:\n" + task)
        parts.append("OUTPUT FORMAT:\n" + self.output_format)
        if self.completion:
            parts.append("COMPLETION CRITERIA (must all hold):\n- " + "\n- ".join(self.completion))
        return "\n\n".join(p for p in parts if p)


def _split_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    fm_raw, body = m.group(1), m.group(2)
    fm: Dict[str, Any] = {}
    # minimal YAML: top-level scalars + nested permission.{edit,bash,skill}
    current = None
    for line in fm_raw.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if v == "":
                current = k
                fm[k] = {}
            else:
                current = None
                fm[k] = v
        elif indent > 0 and current:
            s = line.strip()
            if ":" in s:
                k, v = s.split(":", 1)
                fm[current][k.strip()] = v.strip()
    return fm, body


def _tools_from_permission(perm) -> (List[str], List[str]):
    tools, skills = [], []
    if isinstance(perm, dict):
        for k, v in perm.items():
            if k == "skill" and isinstance(v, dict):
                for sk, allow in v.items():
                    if allow == "allow" and sk != "*":
                        skills.append(sk)
            elif k == "edit" and v == "allow":
                tools += ["write_file", "read_file", "list_dir"]
            elif k == "bash" and v == "allow":
                tools.append("run_command")
            elif k in ("read",) and v == "allow":
                tools.append("read_file")
            elif k in ("webfetch", "fetch") and v == "allow":
                tools.append("http_get")
    return sorted(set(tools)), sorted(set(skills))


# ── load/save ────────────────────────────────────────────────────
def load_specs(specs_dir: str = "agents") -> Dict[str, AgentSpec]:
    specs = {}
    if not os.path.isdir(specs_dir):
        return specs
    for fn in os.listdir(specs_dir):
        if fn.endswith(".agent.json"):
            try:
                with open(os.path.join(specs_dir, fn), "r", encoding="utf-8") as f:
                    data = json.load(f)
                specs[data["id"]] = AgentSpec.from_dict(data)
            except Exception:
                pass
    return specs


def save_spec(spec: AgentSpec, specs_dir: str = "agents"):
    os.makedirs(specs_dir, exist_ok=True)
    path = os.path.join(specs_dir, f"{spec.id}.agent.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec.to_dict(), f, indent=2, ensure_ascii=False)
    return path

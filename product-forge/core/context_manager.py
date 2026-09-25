"""Context Manager - builds minimum context packages per agent.
Per the Product Forge strategy document, section 8.
Agents should not automatically receive the entire project context.
"""
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


AGENT_CONTRACTS = {
    "product_analyzer": {
        "max_input_tokens": 8000, "max_output_tokens": 4000,
        "allowed_inputs": ["requirement", "product_spec", "knowledge_index"],
        "forbidden_inputs": ["full_source_tree", "unrelated_skills"],
    },
    "ux_architect": {
        "max_input_tokens": 12000, "max_output_tokens": 6000,
        "allowed_inputs": ["requirement", "product_spec", "design_tokens"],
        "forbidden_inputs": ["full_source_tree"],
    },
    "design_agent": {
        "max_input_tokens": 12000, "max_output_tokens": 6000,
        "allowed_inputs": ["product_spec", "ux_spec", "design_tokens"],
        "forbidden_inputs": ["full_source_tree"],
    },
    "ui_architect": {
        "max_input_tokens": 12000, "max_output_tokens": 6000,
        "allowed_inputs": ["product_spec", "ux_spec", "design_spec", "design_tokens"],
        "forbidden_inputs": ["unrelated_source_files"],
    },
    "coding_agent": {
        "max_input_tokens": 16000, "max_output_tokens": 12000,
        "allowed_inputs": ["product_spec", "design_spec", "component_plan", "api_contract", "design_tokens"],
        "forbidden_inputs": ["unrelated_source_files"],
    },
    "design_critic": {
        "max_input_tokens": 12000, "max_output_tokens": 5000,
        "allowed_inputs": ["design_spec", "design_tokens", "screenshot", "component_tree"],
        "forbidden_inputs": ["full_project_history"],
    },
    "test_runner": {
        "max_input_tokens": 8000, "max_output_tokens": 4000,
        "allowed_inputs": ["component_plan", "api_contract", "test_specs"],
        "forbidden_inputs": ["all_artifacts"],
    },
    "visual_qa": {
        "max_input_tokens": 16000, "max_output_tokens": 5000,
        "allowed_inputs": ["screenshot", "design_spec", "design_tokens"],
        "forbidden_inputs": ["full_source_tree"],
    },
    "orchestrator": {
        "max_input_tokens": 20000, "max_output_tokens": 8000,
        "allowed_inputs": ["project_state", "budget_state", "all_artifacts_metadata"],
        "forbidden_inputs": ["agent_full_conversations"],
    },
    "ideation": {
        "max_input_tokens": 8000, "max_output_tokens": 6000,
        "allowed_inputs": ["requirement", "product_spec"],
        "forbidden_inputs": ["full_project_state"],
    },
    "design": {
        "max_input_tokens": 10000, "max_output_tokens": 16000,
        "allowed_inputs": ["product_spec", "design_tokens"],
        "forbidden_inputs": ["full_source_tree"],
    },
    "architect": {
        "max_input_tokens": 12000, "max_output_tokens": 10000,
        "allowed_inputs": ["product_spec", "design_spec", "tech_stack"],
        "forbidden_inputs": ["all_artifacts"],
    },
    "implement": {
        "max_input_tokens": 16000, "max_output_tokens": 16000,
        "allowed_inputs": ["design_spec", "component_plan", "design_tokens"],
        "forbidden_inputs": ["all_artifacts"],
    },
    "code-review": {
        "max_input_tokens": 12000, "max_output_tokens": 8000,
        "allowed_inputs": ["component_plan", "source_diff", "design_spec"],
        "forbidden_inputs": ["unrelated_files"],
    },
    "validate": {
        "max_input_tokens": 8000, "max_output_tokens": 12000,
        "allowed_inputs": ["component_plan", "test_results"],
        "forbidden_inputs": ["all_artifacts"],
    },
    "fix": {
        "max_input_tokens": 12000, "max_output_tokens": 8000,
        "allowed_inputs": ["test_results", "source_diff", "design_spec"],
        "forbidden_inputs": ["unrelated_files"],
    },
    "document": {
        "max_input_tokens": 10000, "max_output_tokens": 8000,
        "allowed_inputs": ["product_spec", "component_plan", "api_contract"],
        "forbidden_inputs": ["all_artifacts"],
    },
    "security": {
        "max_input_tokens": 10000, "max_output_tokens": 8000,
        "allowed_inputs": ["component_plan", "source_diff"],
        "forbidden_inputs": ["unrelated_files"],
    },
    "devops": {
        "max_input_tokens": 8000, "max_output_tokens": 4000,
        "allowed_inputs": ["component_plan", "deploy_config"],
        "forbidden_inputs": ["all_artifacts"],
    },
    "package": {
        "max_input_tokens": 8000, "max_output_tokens": 4000,
        "allowed_inputs": ["component_plan", "build_config"],
        "forbidden_inputs": ["all_artifacts"],
    },
}

DEFAULT_CONTRACT = {
    "max_input_tokens": 8000, "max_output_tokens": 6000,
    "allowed_inputs": ["product_spec"],
    "forbidden_inputs": ["unrelated_files"],
}


def get_contract(agent_name: str) -> Dict:
    return AGENT_CONTRACTS.get(agent_name, DEFAULT_CONTRACT)


def build_context_package(agent_name: str, project: str, stage: str,
                           artifacts: Optional[Dict[str, Any]] = None,
                           knowledge_routing: Optional[List[str]] = None) -> Dict:
    contract = get_contract(agent_name)
    allowed = contract["allowed_inputs"]
    package = {
        "agent": agent_name,
        "project": project,
        "stage": stage,
        "max_input_tokens": contract["max_input_tokens"],
        "max_output_tokens": contract["max_output_tokens"],
        "context": {},
        "skills": [],
        "tokens_used": 0,
        "built_at": datetime.now().isoformat(),
    }
    artifacts = artifacts or {}
    for key, content in artifacts.items():
        if key in allowed:
            content_str = json.dumps(content) if not isinstance(content, str) else content
            tokens = len(content_str) // 4
            if package["tokens_used"] + tokens <= contract["max_input_tokens"]:
                package["context"][key] = content
                package["tokens_used"] += tokens
            else:
                remaining = (contract["max_input_tokens"] - package["tokens_used"]) * 4
                package["context"][key] = content[:remaining] + "...[truncated]" if isinstance(content, str) else {"_truncated": True}
                package["tokens_used"] = contract["max_input_tokens"]
    if knowledge_routing:
        package["skills"] = knowledge_routing[:5]
    return package


def check_budget(agent_name: str, current_tokens: int, max_tokens: Optional[int] = None) -> bool:
    contract = get_contract(agent_name)
    if max_tokens is None:
        max_tokens = contract["max_input_tokens"]
    return current_tokens <= max_tokens

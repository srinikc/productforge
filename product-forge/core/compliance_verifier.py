"""LLM-as-verifier compliance checker.

Uses a cheap/free model as a second pair of eyes to verify agent work.
Configurable per project. Reports pass/fail with reasoning.
"""
from __future__ import annotations

try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

_REPO_ROOT = _PF_ROOT


def _default_model() -> str:
    """Resolve a verifier model from the shared tier config (no hardcoding)."""
    p = _REPO_ROOT / "config" / "model-tier.json"
    try:
        with open(p, "r", encoding="utf-8-sig") as f:
            cfg = json.load(f)
        agents = cfg.get("agents", {})
        if agents:
            return next(iter(agents.values())).get("model", "")
    except Exception:
        pass
    return os.getenv("PIPELINE_FALLBACK_MODEL", "")


_PROVIDER_ENDPOINTS = {
    "opencode-go": "https://opencode.ai/zen/v1/chat/completions",
    "opencode-zen": "https://opencode.ai/zen/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "openai": "https://api.openai.com/v1/chat/completions",
}

_KEY_ENV = {
    "opencode-go": "OPENCODE_ZEN_API_KEY",
    "opencode-zen": "OPENCODE_ZEN_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
}


def _resolve_api_key(provider: str) -> str:
    """Resolve the API key for a provider from the environment (no hardcoding)."""
    from dotenv import load_dotenv
    load_dotenv()
    return os.getenv(_KEY_ENV.get(provider, "OPENCODE_ZEN_API_KEY"), "")


def _build_headers(provider: str, api_key: str) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "product-forge-pipeline/1.0",
    }
    if provider in ("opencode-go", "opencode-zen"):
        headers["x-opencode-session"] = "verifier"
    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://opencode.ai"
        headers["X-Title"] = "ProductForgePipeline"
    return headers


@dataclass
class VerifierResult:
    """Result from LLM verification."""
    agent: str
    check_name: str
    passed: bool
    confidence: float  # 0.0 - 1.0
    reasoning: str
    suggestion: str = ""
    model_used: str = ""


@dataclass
class VerificationReport:
    """Full verification report for an agent run."""
    agent: str
    project: str
    timestamp: str
    model_used: str
    results: List[VerifierResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def pass_count(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    @property
    def total(self) -> int:
        return len(self.results)

    def summary(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"[{status}] {self.agent} verification ({self.pass_count}/{self.total})",
            f"Model: {self.model_used}",
            "",
        ]
        for r in self.results:
            icon = "✓" if r.passed else "✗"
            lines.append(f"  {icon} {r.check_name}: {r.reasoning[:100]}")
            if not r.passed and r.suggestion:
                lines.append(f"    Suggestion: {r.suggestion}")
        return "\n".join(lines)

    def to_dict(self) -> Dict:
        return {
            "agent": self.agent,
            "project": self.project,
            "timestamp": self.timestamp,
            "model_used": self.model_used,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "total": self.total,
            "passed": self.passed,
            "results": [
                {
                    "check_name": r.check_name,
                    "passed": r.passed,
                    "confidence": r.confidence,
                    "reasoning": r.reasoning,
                    "suggestion": r.suggestion,
                }
                for r in self.results
            ],
        }


# Verification prompts per agent type
VERIFICATION_PROMPTS: Dict[str, List[Dict]] = {
    "design": [
        {
            "check_name": "all_features_covered",
            "prompt": "Does the design document cover ALL features listed in product-plan.md? Look for any features that are missing from requirements.md or design.md.",
        },
        {
            "check_name": "no_scope_reduction",
            "prompt": "Has the design agent reduced scope without explicit user approval? Check for phrases like 'out of scope', 'deferred to Phase 2', 'MVP only' that weren't authorized by the user.",
        },
        {
            "check_name": "fr_has_acceptance_criteria",
            "prompt": "Does each Functional Requirement (FR) have testable acceptance criteria? Check that FR-001 through FR-N all have acceptance criteria defined.",
        },
        {
            "check_name": "no_todos_or_placeholders",
            "prompt": "Are there any TODO, PLACEHOLDER, or FIXME comments left in the design documents? These indicate incomplete work.",
        },
    ],
    "architect": [
        {
            "check_name": "nfrs_addressed",
            "prompt": "Does the architecture address all NFR subsections (security, performance, scalability, etc.)? Check that no subsection is marked 'TODO' or 'N/A' without justification.",
        },
        {
            "check_name": "tech_stack_matches_plan",
            "prompt": "Does the tech stack in architecture.md match what was selected in product-plan.json? Check for consistency.",
        },
        {
            "check_name": "no_missing_layers",
            "prompt": "Are all implementation layers (DB, API, Logic, UI) addressed in the architecture? Check that each layer has a section.",
        },
    ],
    "implement": [
        {
            "check_name": "all_features_implemented",
            "prompt": "Are all features from requirements.md implemented in the code? Check that each FR has corresponding implementation code.",
        },
        {
            "check_name": "no_stubs_or_mocks",
            "prompt": "Are there any stub functions, mock implementations, or placeholder code? Check for functions that return hardcoded values or raise NotImplementedError.",
        },
        {
            "check_name": "tests_exist",
            "prompt": "Do test files exist for the implemented code? Check that test-framework/tests/<project>/ has relevant test files.",
        },
    ],
    "code-review": [
        {
            "check_name": "security_issues",
            "prompt": "Are there any security issues in the code? Check for SQL injection, hardcoded secrets, missing input validation, insecure HTTP usage.",
        },
        {
            "check_name": "performance_issues",
            "prompt": "Are there any performance issues? Check for N+1 queries, unbounded loops, missing indexes, unnecessary file I/O.",
        },
        {
            "check_name": "code_quality",
            "prompt": "Is the code quality acceptable? Check for dead code, duplicated logic, missing error handling, inconsistent naming.",
        },
    ],
    "validate": [
        {
            "check_name": "all_tests_pass",
            "prompt": "Do all tests in the test results file show as passed? Check the test results JSON for any failures.",
        },
        {
            "check_name": "coverage_adequate",
            "prompt": "Is test coverage adequate? Check that the coverage report shows at least 80% for the implemented code.",
        },
    ],
    "orchestrator": [
        {
            "check_name": "audit_log_complete",
            "prompt": "Is the audit log complete for all agent runs? Check that agent-audit.md has entries for every stage that was executed.",
        },
        {
            "check_name": "stage_flow_correct",
            "prompt": "Are stages being invoked in the correct order? Check that the pipeline flow follows the stage definitions.",
        },
    ],
}


def _get_verification_prompt(agent_id: str) -> List[Dict]:
    """Get verification prompts for an agent."""
    return VERIFICATION_PROMPTS.get(agent_id, [])


def verify_agent_work(
    agent_id: str,
    project: str,
    artifact_paths: Optional[Dict[str, str]] = None,
    model: str = "",
) -> VerificationReport:
    """Verify an agent's work using LLM-as-verifier.

    This generates verification prompts but does NOT call an LLM directly.
    The orchestrator should use these prompts with the configured model.
    If `model` is empty it is resolved from the shared tier config.

    Args:
        agent_id: Agent to verify
        project: Project name
        artifact_paths: Dict of artifact name → file path
        model: Model to use for verification
"""
    model = model or _default_model()
    from datetime import datetime

    checks = _get_verification_prompt(agent_id)
    if not checks:
        # No verification defined for this agent
        return VerificationReport(
            agent=agent_id,
            project=project,
            timestamp=datetime.now().isoformat(),
            model_used=model,
            results=[],
        )

    results = []
    for check in checks:
        results.append(VerifierResult(
            agent=agent_id,
            check_name=check["check_name"],
            passed=False,  # Will be filled by LLM
            confidence=0.0,
            reasoning="Awaiting LLM verification",
            model_used=model,
        ))

    return VerificationReport(
        agent=agent_id,
        project=project,
        timestamp=datetime.now().isoformat(),
        model_used=model,
        results=results,
    )


def build_verification_prompt(
    agent_id: str,
    project: str,
    artifact_paths: Optional[Dict[str, str]] = None,
) -> str:
    """Build the full verification prompt for an LLM to execute.

    Returns a prompt string that the orchestrator can send to the
    configured model for verification.
    """
    checks = _get_verification_prompt(agent_id)
    if not checks:
        return f"No verification defined for agent '{agent_id}'."

    lines = [
        f"You are verifying the work of the '{agent_id}' agent for project '{project}'.",
        "",
        "Read the following files and answer each verification question:",
        "",
    ]

    if artifact_paths:
        lines.append("Files to read:")
        for name, path in artifact_paths.items():
            lines.append(f"  - {name}: {path}")
        lines.append("")
        # Embed contents so a model without filesystem access can actually verify.
        lines.append("File contents:")
        total = 0
        for name, path in artifact_paths.items():
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue
            snippet = content[:6000]
            total += len(snippet)
            lines.append(f"\n--- {name} ---\n{snippet}")
            if total > 24000:
                lines.append("... (remaining files omitted for length)")
                break
        lines.append("")

    lines.append("Verification checks:")
    lines.append("")

    for i, check in enumerate(checks, 1):
        lines.append(f"{i}. {check['check_name']}: {check['prompt']}")

    lines.extend([
        "",
        "Respond with ONLY a JSON array (no markdown fences, no prose), one object per check:",
        '[{"check_name": "<name>", "passed": true, "confidence": 0.0, '
        '"reasoning": "<short>", "suggestion": "<fix or empty>"}]',
        "",
        "Use passed=true only if you are confident the work is complete and correct.",
        "confidence is 0.0-1.0.",
    ])

    return "\n".join(lines)


def save_verification_report(
    report: VerificationReport,
    output_dir: Optional[Path] = None,
) -> str:
    """Save verification report to a JSON file."""
    if output_dir is None:
        output_dir = _REPO_ROOT / "products" / report.project / "compliance"

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{report.agent}-verification.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report.to_dict(), f, indent=2)

    return str(output_path)


def execute_verification(
    agent_id: str,
    project: str,
    artifact_paths: Optional[Dict[str, str]] = None,
    model: str = "",
    provider: str = "",
    api_endpoint: str = "",
    api_key: str = "",
) -> VerificationReport:
    """Execute verification by calling LLM and parsing results.

    This actually calls the LLM to verify the agent's work. Provider, endpoint
    and key are resolved from the caller (tier config) or environment defaults;
    nothing is hardcoded to a single provider.
    """
    import requests
    from datetime import datetime

    model = model or _default_model()
    provider = provider or os.getenv("PIPELINE_FALLBACK_PROVIDER", "opencode-go")
    api_endpoint = (api_endpoint or _PROVIDER_ENDPOINTS.get(provider, "")
                    or os.getenv("PIPELINE_FALLBACK_ENDPOINT", ""))
    api_key = api_key or _resolve_api_key(provider)

    # Build verification prompt
    prompt = build_verification_prompt(agent_id, project, artifact_paths)
    if not prompt or "No verification defined" in prompt:
        return VerificationReport(
            agent=agent_id,
            project=project,
            timestamp=datetime.now().isoformat(),
            model_used=model,
            results=[],
        )

    if not api_key or not api_endpoint:
        print(f"[LLMVerifier] No API key/endpoint for provider '{provider}', skipping LLM verification")
        return verify_agent_work(agent_id, project, artifact_paths, model)

    # Call LLM
    try:
        headers = _build_headers(provider, api_key)
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4000,
            "temperature": 0.3,
        }

        response = requests.post(api_endpoint, json=data, headers=headers, timeout=120)

        if response.status_code == 200:
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parse LLM response
            return _parse_verification_response(agent_id, project, content, model)
        else:
            print(f"[LLMVerifier] API error: {response.status_code}")
            return verify_agent_work(agent_id, project, artifact_paths, model)
    except Exception as e:
        print(f"[LLMVerifier] Error: {e}")
        return verify_agent_work(agent_id, project, artifact_paths, model)


def _parse_verification_response(
    agent_id: str,
    project: str,
    content: str,
    model: str,
) -> VerificationReport:
    """Parse LLM verification response into VerificationReport."""
    from datetime import datetime
    import re
    
    results = []
    checks = _get_verification_prompt(agent_id)

    # Prefer JSON parsing (reliable); fall back to text patterns.
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()
    parsed: Dict[str, Dict] = {}
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            obj = obj.get("results") or obj.get("checks") or []
        for item in obj:
            if isinstance(item, dict) and item.get("check_name"):
                parsed[str(item["check_name"])] = item
    except Exception:
        parsed = {}

    for check in checks:
        check_name = check["check_name"]

        passed = False
        confidence = 0.5
        reasoning = ""
        suggestion = ""

        if check_name in parsed:
            item = parsed[check_name]
            passed = bool(item.get("passed"))
            try:
                confidence = float(item.get("confidence", 0.7))
            except (TypeError, ValueError):
                confidence = 0.7
            reasoning = str(item.get("reasoning", ""))
            suggestion = str(item.get("suggestion", "")) if not passed else ""
        else:
            # Fall back to "check_name: PASS/FAIL: reasoning (confidence: 0.XX)"
            pattern = rf"{check_name}[:\s]+(PASS|FAIL)[:\s]+(.+?)(?:\(confidence:\s*(\d+\.\d+)\))?"
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                passed = match.group(1).upper() == "PASS"
                reasoning = match.group(2).strip()
                confidence = float(match.group(3)) if match.group(3) else 0.7
                if not passed:
                    suggestion_match = re.search(r"suggestion:\s*(.+?)(?:\)|$)", reasoning, re.IGNORECASE)
                    if suggestion_match:
                        suggestion = suggestion_match.group(1).strip()
            else:
                reasoning = "Not addressed in verifier response"
                confidence = 0.3

        results.append(VerifierResult(
            agent=agent_id,
            check_name=check_name,
            passed=passed,
            confidence=confidence,
            reasoning=reasoning,
            suggestion=suggestion,
            model_used=model,
        ))
    
    return VerificationReport(
        agent=agent_id,
        project=project,
        timestamp=datetime.now().isoformat(),
        model_used=model,
        results=results,
    )


def load_verification_report(
    project: str,
    agent_id: str,
) -> Optional[VerificationReport]:
    """Load a previously saved verification report."""
    report_path = _REPO_ROOT / "products" / project / "compliance" / f"{agent_id}-verification.json"
    if not report_path.exists():
        return None

    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = []
    for r in data.get("results", []):
        results.append(VerifierResult(
            agent=data["agent"],
            check_name=r["check_name"],
            passed=r["passed"],
            confidence=r.get("confidence", 0.0),
            reasoning=r.get("reasoning", ""),
            suggestion=r.get("suggestion", ""),
            model_used=data.get("model_used", ""),
        ))

    return VerificationReport(
        agent=data["agent"],
        project=data["project"],
        timestamp=data["timestamp"],
        model_used=data.get("model_used", ""),
        results=results,
    )


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage:")
        print("  python -m core.compliance_verifier <agent_id> <project>")
        print("  python -m core.compliance_verifier list-checks")
        sys.exit(1)

    if sys.argv[1] == "list-checks":
        for agent_id, checks in VERIFICATION_PROMPTS.items():
            print(f"\n{agent_id}:")
            for check in checks:
                print(f"  - {check['check_name']}")
        sys.exit(0)

    agent_id = sys.argv[1]
    project = sys.argv[2]
    report = verify_agent_work(agent_id, project)
    print(report.summary())

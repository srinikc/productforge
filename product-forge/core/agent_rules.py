"""Parse new-format agent .md files into structured data.

Reads agent .md files (post-migration) and extracts frontmatter, sections,
rules, and quality checks. Used by compliance_check.py and orchestrator.
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

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.agent_structure import (
    AgentContract,
    AgentFrontmatter,
    AgentSection,
    REQUIRED_SECTIONS,
    OPTIONAL_SECTIONS,
    WHITELISTED_SECTIONS,
    SectionLevel,
)

_REPO_ROOT = _PF_ROOT


def _neutral_agent_path(agent_id: str) -> Path:
    """Resolve an agent card path neutral-first (BI-0201); legacy only if allowed."""
    try:
        from core.agent_spec import resolve_card_path
        p = resolve_card_path(agent_id)
        if p:
            return Path(p)
    except Exception:
        pass
    return _REPO_ROOT / ".opencode" / "agent" / f"{agent_id}.md"


def _spec_json_to_card_md(raw_json: str) -> str:
    """Render an AgentSpec JSON (neutral canonical) into the card markdown shape.

    Lets the existing section/rule parser work without any .opencode dependency (BI-0201)."""
    import json as _json
    try:
        d = _json.loads(raw_json)
    except Exception:
        return raw_json
    aid = str(d.get("id") or d.get("name") or "")
    desc = str(d.get("description") or d.get("name") or "")
    mode = str(d.get("mode") or "subagent")
    tier = str(d.get("model_tier") or "medium")
    tools = ", ".join(d.get("tools") or []) or "none"
    rules = d.get("rules") or []
    if isinstance(rules, list):
        rules_txt = "\n".join(f"- {r}" for r in rules)
    else:
        rules_txt = str(rules)
    if not rules_txt:
        rules_txt = "- No mocks, TODOs, placeholders, or `pass` in production output."
    checks = d.get("completion") or []
    checks_txt = "\n".join(f"- {c}" for c in checks) if isinstance(checks, list) else str(checks)
    if not checks_txt:
        checks_txt = "- Output matches the declared contract and passes validation."
    return (
        "---\n"
        f"description: {desc}\n"
        f"mode: {mode}\n"
        f"agent_id: {aid}\n"
        "version: 1.0.0\n"
        "---\n\n"
        f"# {d.get('name') or aid}\n\n"
        "## 0. METADATA\n"
        f"- **Agent ID**: {aid}\n"
        f"- **Model tier**: {tier}\n"
        f"- **Tools**: {tools}\n\n"
        "## 1. ROLE\n"
        f"{desc}\n\n"
        "## 2. INPUTS\n"
        f"- Allowed: {', '.join(d.get('allowed_inputs') or []) or 'any'}\n"
        f"- Forbidden: {', '.join(d.get('forbidden_inputs') or []) or 'none'}\n\n"
        "## 3. OUTPUTS\n"
        f"- Format: {d.get('output_format') or 'markdown'}\n\n"
        "## 4. RULES\n"
        f"{rules_txt}\n\n"
        "## 7. QUALITY CHECKS\n"
        f"{checks_txt}\n"
    )


@dataclass
class ParsedRule:
    """A single rule extracted from section 4."""
    text: str
    type: str  # "do", "dont", "conditional"
    severity: str  # "critical", "high", "medium", "low"
    section: int = 4
    line_number: int = 0


@dataclass
class ParsedCheck:
    """A single quality check extracted from section 7."""
    text: str
    verify: str  # "auto", "llm", "human"
    severity: str = "high"
    section: int = 7
    line_number: int = 0


@dataclass
class ParsedAgent:
    """Fully parsed agent .md file."""
    agent_id: str
    title: str
    version: str
    spec_version: str
    mode: str
    model: str
    description: str
    frontmatter_raw: Dict[str, str]
    sections: List[AgentSection]
    rules: List[ParsedRule]
    checks: List[ParsedCheck]
    section_numbers: List[int]
    raw_content: str
    file_path: str = ""

    @property
    def has_required_sections(self) -> bool:
        """Check all required sections (0-8) are present."""
        for num in REQUIRED_SECTIONS:
            if num not in self.section_numbers:
                return False
        return True

    @property
    def missing_required_sections(self) -> List[int]:
        """Return list of missing required section numbers."""
        return [n for n in REQUIRED_SECTIONS if n not in self.section_numbers]

    @property
    def has_whitelisted_violations(self) -> List[str]:
        """Return list of non-whitelisted sections found."""
        violations = []
        for num in self.section_numbers:
            if num >= 13 and num not in WHITELISTED_SECTIONS:
                violations.append(f"Section {num} not in whitelist")
        return violations

    def get_section(self, number: int) -> Optional[AgentSection]:
        """Get a section by number."""
        for s in self.sections:
            if s.number == number:
                return s
        return None

    def get_rules_by_severity(self, severity: str) -> List[ParsedRule]:
        """Get all rules of a given severity."""
        return [r for r in self.rules if r.severity == severity]

    def get_checks_by_verify(self, verify: str) -> List[ParsedCheck]:
        """Get all checks of a given verification type."""
        return [c for c in self.checks if c.verify == verify]


def _extract_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Extract YAML frontmatter and remaining content."""
    if not content.startswith("---"):
        return {}, content

    lines = content.split("\n")
    fm_lines = []
    end_idx = 1
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i + 1
            break
        fm_lines.append(line)

    frontmatter = {}
    for fm_line in fm_lines:
        if ":" in fm_line:
            key, _, val = fm_line.partition(":")
            frontmatter[key.strip()] = val.strip().strip('"').strip("'")

    remaining = "\n".join(lines[end_idx:])
    return frontmatter, remaining


def _extract_sections(content: str) -> List[AgentSection]:
    """Extract all ## sections from markdown content."""
    sections = []
    lines = content.split("\n")

    current_section = None
    current_content = []

    for line in lines:
        match = re.match(r"^(#{2,3})\s+(\d+)\.\s+(.+)$", line)
        if match:
            if current_section:
                current_section.content = "\n".join(current_content).strip()
                sections.append(current_section)

            level = SectionLevel.H2 if len(match.group(1)) == 2 else SectionLevel.H3
            num = int(match.group(2))
            title = match.group(3).strip()
            required = num in REQUIRED_SECTIONS
            agent_specific = num in WHITELISTED_SECTIONS

            current_section = AgentSection(
                number=num,
                title=title,
                level=level,
                required=required,
                agent_specific=agent_specific,
            )
            current_content = []
        elif current_section is not None:
            current_content.append(line)

    if current_section:
        current_section.content = "\n".join(current_content).strip()
        sections.append(current_section)

    return sections


def _extract_rules(section_content: str, section_num: int) -> List[ParsedRule]:
    """Extract rules from section 4 (RULES) content."""
    rules = []
    current_severity = "high"  # default
    lines = section_content.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect severity subheadings
        lower = stripped.lower()
        if "critical" in lower and ("###" in line or "####" in line):
            current_severity = "critical"
            continue
        if "high" in lower and ("###" in line or "####" in line):
            current_severity = "high"
            continue
        if "medium" in lower and ("###" in line or "####" in line):
            current_severity = "medium"
            continue
        if "low" in lower and ("###" in line or "####" in line):
            current_severity = "low"
            continue

        # Extract rule lines (numbered or bulleted)
        rule_match = re.match(r"^\d+\.\s+(.+)$", stripped)
        if not rule_match:
            rule_match = re.match(r"^[-*]\s+(.+)$", stripped)

        if rule_match:
            text = rule_match.group(1).strip()

            # Determine rule type
            if text.startswith("❌") or text.upper().startswith("NO ") or "CANNOT" in text.upper():
                rule_type = "dont"
            elif text.startswith("✅") or "MUST" in text.upper():
                rule_type = "do"
            elif "IF " in text.upper():
                rule_type = "conditional"
            else:
                rule_type = "do"

            rules.append(ParsedRule(
                text=text,
                type=rule_type,
                severity=current_severity,
                section=section_num,
                line_number=i,
            ))

    return rules


def _extract_checks(section_content: str, section_num: int) -> List[ParsedCheck]:
    """Extract quality checks from section 7 content."""
    checks = []
    current_verify = "auto"
    lines = section_content.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Detect verification type subheadings
        lower = stripped.lower()
        if "auto-verifiable" in lower or "automated" in lower:
            current_verify = "auto"
            continue
        if "llm-verifiable" in lower or "llm" in lower:
            current_verify = "llm"
            continue
        if "human" in lower and ("###" in line or "####" in line):
            current_verify = "human"
            continue

        # Extract checkbox items
        check_match = re.match(r"^- \[([ x])\]\s+(.+)$", stripped)
        if check_match:
            checked = check_match.group(1) == "x"
            text = check_match.group(2).strip()

            if not checked:
                checks.append(ParsedCheck(
                    text=text,
                    verify=current_verify,
                    severity="high",
                    section=section_num,
                    line_number=i,
                ))

    return checks


def parse_agent_md(agent_id: str) -> ParsedAgent:
    """Parse an agent .md file into structured data.

    Args:
        agent_id: The agent identifier (e.g., 'design')

    Returns:
        ParsedAgent with all extracted data

    Raises:
        FileNotFoundError: If agent .md file doesn't exist
    """
    file_path = _neutral_agent_path(agent_id)
    if not file_path.exists():
        raise FileNotFoundError(f"Agent file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # Neutral canonical source is a JSON spec (agents/*.agent.json): render it to the
    # card markdown shape so the same section/rule parser applies (BI-0201).
    if file_path.suffix == ".json":
        raw_content = _spec_json_to_card_md(raw_content)

    frontmatter, remaining = _extract_frontmatter(raw_content)
    sections = _extract_sections(remaining)

    # Extract rules from section 4
    rules = []
    section_4 = None
    for s in sections:
        if s.number == 4:
            section_4 = s
            break
    if section_4:
        rules = _extract_rules(section_4.content, 4)

    # Extract checks from section 7
    checks = []
    section_7 = None
    for s in sections:
        if s.number == 7:
            section_7 = s
            break
    if section_7:
        checks = _extract_checks(section_7.content, 7)

    # Extract title from H1
    title = ""
    for line in raw_content.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
            break

    return ParsedAgent(
        agent_id=agent_id,
        title=title,
        version=frontmatter.get("version", "1.0.0"),
        spec_version=frontmatter.get("spec_version", "1.0"),
        mode=frontmatter.get("mode", "subagent"),
        model=frontmatter.get("model", ""),
        description=frontmatter.get("description", ""),
        frontmatter_raw=frontmatter,
        sections=sections,
        rules=rules,
        checks=checks,
        section_numbers=[s.number for s in sections],
        raw_content=raw_content,
        file_path=str(file_path),
    )


def parse_agent_from_string(agent_id: str, content: str) -> ParsedAgent:
    """Parse agent content from a string (for testing/migration)."""
    frontmatter, remaining = _extract_frontmatter(content)
    sections = _extract_sections(remaining)

    rules = []
    for s in sections:
        if s.number == 4:
            rules = _extract_rules(s.content, 4)
            break

    checks = []
    for s in sections:
        if s.number == 7:
            checks = _extract_checks(s.content, 7)
            break

    title = ""
    for line in content.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            title = line[2:].strip()
            break

    return ParsedAgent(
        agent_id=agent_id,
        title=title,
        version=frontmatter.get("version", "1.0.0"),
        spec_version=frontmatter.get("spec_version", "1.0"),
        mode=frontmatter.get("mode", "subagent"),
        model=frontmatter.get("model", ""),
        description=frontmatter.get("description", ""),
        frontmatter_raw=frontmatter,
        sections=sections,
        rules=rules,
        checks=checks,
        section_numbers=[s.number for s in sections],
        raw_content=content,
    )


def list_all_agents() -> List[str]:
    """List all agent IDs from the neutral source (agnostic; .opencode only if allowed)."""
    try:
        from core.agent_spec import list_agent_ids
        return list_agent_ids()
    except Exception:
        agents_dir = _REPO_ROOT / ".opencode" / "agent"
        if not agents_dir.exists():
            return []
        return sorted([f.stem for f in agents_dir.glob("*.md")])


def parse_all_agents() -> Dict[str, ParsedAgent]:
    """Parse all agent .md files. Returns dict of agent_id → ParsedAgent."""
    agents = {}
    for agent_id in list_all_agents():
        try:
            agents[agent_id] = parse_agent_md(agent_id)
        except Exception as e:
            print(f"Warning: Failed to parse {agent_id}: {e}")
    return agents

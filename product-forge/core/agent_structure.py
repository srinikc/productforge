"""Common structure definition for all agent .md files.

Defines the canonical section ordering, whitelisted agent-specific sections,
and the mapping from section numbers to titles. Used by agent_migrator.py,
agent_rules.py, and compliance_check.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SectionLevel(Enum):
    H2 = 2
    H3 = 3


class RuleType(Enum):
    DO = "do"
    DONT = "dont"
    CONDITIONAL = "conditional"


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Canonical section numbers 0-12 (required for all agents)
REQUIRED_SECTIONS: Dict[int, str] = {
    0: "METADATA",
    1: "ROLE",
    2: "INPUTS",
    3: "OUTPUTS",
    4: "RULES",
    5: "WORKFLOW",
    6: "ARTIFACTS",
    7: "QUALITY CHECKS",
    8: "STATE UPDATES",
}

OPTIONAL_SECTIONS: Dict[int, str] = {
    9: "TIMING",
    10: "DEPENDENCIES",
    11: "ERRORS",
    12: "EXAMPLES",
}

# Whitelisted agent-specific sections (13+)
# Maps section number to (title, applicable_agents)
# If applicable_agents is None, any agent can use it.
WHITELISTED_SECTIONS: Dict[int, tuple[str, Optional[List[str]]]] = {
    13: ("PROMPTS", None),
    14: ("TOOLS", None),
    15: ("INTEGRATION", None),
    16: ("SECURITY", ["security", "security-audit"]),
    17: ("PERFORMANCE", ["performance"]),
    18: ("BILLING", ["finops"]),
    19: ("STAGE FLOWS", ["orchestrator"]),
    20: ("COMPLIANCE GATES", ["orchestrator"]),
    21: ("PARALLEL EXECUTION", ["orchestrator"]),
    22: ("RECOVERY", ["orchestrator"]),
}

# Sections 23-30 are reserved for future use
RESERVED_SECTIONS = list(range(23, 31))


@dataclass
class AgentSection:
    """Represents a single section in an agent .md file."""
    number: int
    title: str
    level: SectionLevel = SectionLevel.H2
    required: bool = True
    agent_specific: bool = False
    content: str = ""
    rules: List[Dict] = field(default_factory=list)
    checks: List[Dict] = field(default_factory=list)


@dataclass
class AgentFrontmatter:
    """Parsed frontmatter from an agent .md file."""
    description: str = ""
    mode: str = "subagent"
    model: str = ""
    agent_id: str = ""
    version: str = "1.0.0"
    spec_version: str = "1.0"
    permission: Dict = field(default_factory=dict)


@dataclass
class AgentContract:
    """Complete parsed agent contract."""
    frontmatter: AgentFrontmatter
    title: str
    sections: List[AgentSection]
    raw_md: str = ""


def get_all_section_numbers() -> List[int]:
    """Return all valid section numbers (0-30)."""
    nums = list(REQUIRED_SECTIONS.keys()) + list(OPTIONAL_SECTIONS.keys())
    nums += list(WHITELISTED_SECTIONS.keys())
    nums += RESERVED_SECTIONS
    return sorted(set(nums))


def is_section_required(number: int) -> bool:
    """Check if a section number is required (0-8)."""
    return number in REQUIRED_SECTIONS


def is_section_whitelisted(number: int, agent_id: str) -> bool:
    """Check if an agent is allowed to use a whitelisted section."""
    if number not in WHITELISTED_SECTIONS:
        return False
    _, applicable = WHITELISTED_SECTIONS[number]
    if applicable is None:
        return True
    return agent_id in applicable


def section_title(number: int) -> str:
    """Get the canonical title for a section number."""
    if number in REQUIRED_SECTIONS:
        return REQUIRED_SECTIONS[number]
    if number in OPTIONAL_SECTIONS:
        return OPTIONAL_SECTIONS[number]
    if number in WHITELISTED_SECTIONS:
        return WHITELISTED_SECTIONS[number][0]
    return f"SECTION-{number}"


def validate_section_ordering(sections: List[AgentSection]) -> List[str]:
    """Validate that sections are in correct order. Returns list of errors."""
    errors = []
    numbers = [s.number for s in sections]

    # Check for required sections
    for num, title in REQUIRED_SECTIONS.items():
        if num not in numbers:
            errors.append(f"Missing required section {num}: {title}")

    # Check ordering
    for i in range(len(numbers) - 1):
        if numbers[i] >= numbers[i + 1]:
            errors.append(
                f"Section {numbers[i]} must come before section {numbers[i + 1]}"
            )

    # Check for duplicate sections
    seen = set()
    for num in numbers:
        if num in seen:
            errors.append(f"Duplicate section {num}")
        seen.add(num)

    return errors


def build_agent_structure(
    agent_id: str,
    title: str,
    sections: List[AgentSection],
    frontmatter: Optional[AgentFrontmatter] = None,
) -> str:
    """Build a new-format agent .md file from structured data."""
    if frontmatter is None:
        frontmatter = AgentFrontmatter(agent_id=agent_id)

    lines = []

    # Frontmatter
    lines.append("---")
    lines.append(f"description: {frontmatter.description}")
    lines.append(f"mode: {frontmatter.mode}")
    lines.append(f"model: {frontmatter.model}")
    lines.append(f"agent_id: {frontmatter.agent_id}")
    lines.append(f"version: {frontmatter.version}")
    lines.append(f'spec_version: "{frontmatter.spec_version}"')
    if frontmatter.permission:
        lines.append("permission:")
        for k, v in frontmatter.permission.items():
            if isinstance(v, dict):
                lines.append(f"  {k}:")
                for sk, sv in v.items():
                    lines.append(f'    "{sk}": "{sv}"')
            else:
                lines.append(f"  {k}: {v}")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"# {title}")
    lines.append("")

    # Sections
    for section in sections:
        prefix = "##" if section.level == SectionLevel.H2 else "###"
        lines.append(f"{prefix} {section.number}. {section.title}")
        lines.append("")
        if section.content:
            lines.append(section.content)
            lines.append("")

    return "\n".join(lines)


# All known agents (for reference)
KNOWN_AGENTS = [
    "orchestrator", "ideation", "design", "architect", "implement",
    "code-review", "fix", "validate", "document", "package", "devops",
    "security", "security-audit", "performance", "brainstorming",
    "spec", "tdd", "compliance-check", "product-designer",
    "threat-modeling", "heuristic-evaluation", "architecture-review",
    "architecture", "test-strategy", "a11y-audit", "review",
    "customer-onboarding", "marketing", "finops", "maintenance",
]

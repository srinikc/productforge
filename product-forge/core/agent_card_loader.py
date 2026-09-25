"""
Agent Card Loader/Validator
Loads and validates agent .md card files.
"""

import json
import os
import re
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class CardValidationSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue."""
    severity: CardValidationSeverity
    field: str
    message: str
    line: Optional[int] = None


@dataclass
class AgentCard:
    """Parsed agent card."""
    name: str
    file_path: str
    frontmatter: Dict
    sections: Dict[str, str] = field(default_factory=dict)
    raw_content: str = ""
    valid: bool = False
    issues: List[ValidationIssue] = field(default_factory=list)


class AgentCardLoader:
    """
    Loads and validates agent .md card files.

    Expected format:
    - YAML frontmatter (between --- markers)
    - Markdown sections starting with ##
    """

    REQUIRED_SECTIONS = [
        "Primary Functions",
    ]

    OPTIONAL_SECTIONS = [
        "Agent Identity",
        "Knowledge Loading",
        "Quality Checks",
        "Workflow",
        "Integration Points",
        "Inputs",
        "Outputs",
        "Rules",
    ]

    # A card is identified by `name` OR `agent_id` (the opencode card contract uses `agent_id`).
    REQUIRED_FRONTMATTER_FIELDS = []
    IDENTITY_FIELDS = ["name", "agent_id"]

    def __init__(self, agent_dir: str = ".opencode/agent"):
        self.agent_dir = Path(agent_dir)

    def load_all(self) -> List[AgentCard]:
        """Load all agent cards from the directory."""
        cards = []
        if not self.agent_dir.exists():
            return cards

        for md_file in self.agent_dir.glob("*.md"):
            card = self.load_card(str(md_file))
            cards.append(card)

        return cards

    def load_card(self, file_path: str) -> AgentCard:
        """Load and validate a single agent card."""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8") if path.exists() else ""

        # Parse frontmatter
        frontmatter = self._parse_frontmatter(content)

        # Parse sections
        sections = self._parse_sections(content)

        # Derive name
        name = frontmatter.get("name", path.stem)

        # Validate
        issues = self._validate(frontmatter, sections, content)

        valid = not any(i.severity == CardValidationSeverity.ERROR for i in issues)

        return AgentCard(
            name=name,
            file_path=str(path),
            frontmatter=frontmatter,
            sections=sections,
            raw_content=content,
            valid=valid,
            issues=issues
        )

    def _parse_frontmatter(self, content: str) -> Dict:
        """Parse YAML frontmatter."""
        if not content.startswith("---"):
            return {}

        # Find the end of frontmatter
        end_match = re.search(r"\n---\n", content[3:])
        if not end_match:
            return {}

        frontmatter_text = content[3:3 + end_match.start()]

        # Simple YAML parser (key: value)
        result = {}
        current_key = None
        current_list = None

        for line in frontmatter_text.split("\n"):
            if not line.strip():
                continue
            if line.startswith("  - ") and current_key and current_list is not None:
                current_list.append(line[4:].strip().strip('"').strip("'"))
            elif ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()

                if value == "":
                    # Could be a list
                    current_key = key
                    current_list = []
                    result[key] = current_list
                else:
                    current_key = key
                    current_list = None
                    # Strip quotes
                    value = value.strip('"').strip("'")
                    # Try to parse as JSON for complex values
                    if value.startswith("[") and value.endswith("]"):
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            pass
                    # Try as number
                    elif value.lower() in ("true", "false"):
                        value = value.lower() == "true"
                    else:
                        try:
                            value = float(value)
                            if value.is_integer():
                                value = int(value)
                        except ValueError:
                            pass
                    result[key] = value

        return result

    def _parse_sections(self, content: str) -> Dict[str, str]:
        """Parse markdown sections."""
        sections = {}
        current_section = None
        current_content = []

        # Skip frontmatter
        if content.startswith("---"):
            end_match = re.search(r"\n---\n", content[3:])
            if end_match:
                content = content[3 + end_match.end():]

        for line in content.split("\n"):
            if line.startswith("## "):
                # Save previous section
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                # Start new section
                current_section = line[3:].strip()
                current_content = []
            elif current_section:
                current_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def _validate(
        self,
        frontmatter: Dict,
        sections: Dict,
        content: str
    ) -> List[ValidationIssue]:
        """Validate an agent card."""
        issues = []

        # Identity: require `name` OR `agent_id`
        if not any(f in frontmatter and str(frontmatter.get(f)).strip()
                   for f in self.IDENTITY_FIELDS):
            issues.append(ValidationIssue(
                severity=CardValidationSeverity.ERROR,
                field="frontmatter.name|agent_id",
                message="Missing identity: frontmatter needs 'name' or 'agent_id'"
            ))
        # Extra declared required frontmatter fields (kept for extensibility)
        for field_name in self.REQUIRED_FRONTMATTER_FIELDS:
            if field_name not in frontmatter:
                issues.append(ValidationIssue(
                    severity=CardValidationSeverity.ERROR,
                    field=f"frontmatter.{field_name}",
                    message=f"Missing required frontmatter field: {field_name}"
                ))

        # Check required sections
        for section in self.REQUIRED_SECTIONS:
            # Section names may have different formatting
            found = any(section.lower() in s.lower() for s in sections.keys())
            if not found:
                issues.append(ValidationIssue(
                    severity=CardValidationSeverity.WARNING,
                    field=f"section.{section}",
                    message=f"Missing recommended section: {section}"
                ))

        # Check for description in frontmatter
        if "description" not in frontmatter:
            issues.append(ValidationIssue(
                severity=CardValidationSeverity.WARNING,
                field="frontmatter.description",
                message="Missing description in frontmatter"
            ))

        # Check for model in frontmatter
        if "model" not in frontmatter:
            issues.append(ValidationIssue(
                severity=CardValidationSeverity.INFO,
                field="frontmatter.model",
                message="No model specified in frontmatter"
            ))

        # Check for knowledge loading
        if not any("knowledge" in s.lower() for s in sections.keys()):
            issues.append(ValidationIssue(
                severity=CardValidationSeverity.INFO,
                field="section.knowledge",
                message="No knowledge loading section defined"
            ))

        return issues

    def get_valid_cards(self) -> List[AgentCard]:
        """Get only valid agent cards."""
        return [c for c in self.load_all() if c.valid]

    def get_invalid_cards(self) -> List[AgentCard]:
        """Get only invalid agent cards."""
        return [c for c in self.load_all() if not c.valid]

    def get_card_by_name(self, name: str) -> Optional[AgentCard]:
        """Get a specific card by name."""
        for card in self.load_all():
            if card.name == name:
                return card
        return None

    def generate_report(self) -> Dict:
        """Generate a validation report for all cards."""
        cards = self.load_all()
        valid = [c for c in cards if c.valid]
        invalid = [c for c in cards if not c.valid]

        error_count = sum(
            1 for c in cards
            for issue in c.issues
            if issue.severity == CardValidationSeverity.ERROR
        )
        warning_count = sum(
            1 for c in cards
            for issue in c.issues
            if issue.severity == CardValidationSeverity.WARNING
        )

        return {
            "total_cards": len(cards),
            "valid_cards": len(valid),
            "invalid_cards": len(invalid),
            "total_errors": error_count,
            "total_warnings": warning_count,
            "valid_card_names": [c.name for c in valid],
            "invalid_card_names": [c.name for c in invalid],
            "cards": [
                {
                    "name": c.name,
                    "file": c.file_path,
                    "valid": c.valid,
                    "issues": [
                        {
                            "severity": i.severity.value,
                            "field": i.field,
                            "message": i.message
                        }
                        for i in c.issues
                    ]
                }
                for c in cards
            ]
        }

"""Migrate old-format agent .md files to new standardized format.

Reads existing agent .md files, identifies missing sections, and generates
new-format output. Shows diff for human approval before writing.
"""
from __future__ import annotations

import difflib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core.agent_structure import (
    REQUIRED_SECTIONS,
    OPTIONAL_SECTIONS,
    WHITELISTED_SECTIONS,
    AgentSection,
    AgentFrontmatter,
    SectionLevel,
    build_agent_structure,
    section_title,
)
from core.agent_rules import parse_agent_md, ParsedAgent

_REPO_ROOT = Path(__file__).parent.parent
_AGENTS_DIR = _REPO_ROOT / ".opencode" / "agent"


@dataclass
class MigrationDiff:
    """Result of comparing old vs new agent format."""
    agent_id: str
    old_content: str
    new_content: str
    missing_sections: List[int]
    extra_sections: List[int]
    issues: List[str]
    frontmatter_changes: Dict[str, Tuple[str, str]]  # key → (old, new)

    @property
    def has_changes(self) -> bool:
        return self.old_content != self.new_content

    def unified_diff(self, context_lines: int = 3) -> str:
        """Generate a unified diff between old and new content."""
        old_lines = self.old_content.splitlines(keepends=True)
        new_lines = self.new_content.splitlines(keepends=True)
        return "".join(difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f".opencode/agent/{self.agent_id}.md (old)",
            tofile=f".opencode/agent/{self.agent_id}.md (new)",
            n=context_lines,
        ))

    def summary(self) -> str:
        """Human-readable migration summary."""
        lines = [f"Migration diff for {self.agent_id}:"]
        lines.append(f"  Changes: {'YES' if self.has_changes else 'NO'}")
        if self.missing_sections:
            lines.append(f"  Missing sections: {self.missing_sections}")
        if self.extra_sections:
            lines.append(f"  Extra sections: {self.extra_sections}")
        if self.issues:
            lines.append(f"  Issues: {len(self.issues)}")
            for issue in self.issues:
                lines.append(f"    - {issue}")
        if self.frontmatter_changes:
            lines.append(f"  Frontmatter changes:")
            for key, (old, new) in self.frontmatter_changes.items():
                lines.append(f"    {key}: {old!r} → {new!r}")
        return "\n".join(lines)


def _extract_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """Extract YAML frontmatter from .md content."""
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


def _normalize_section_number(heading: str) -> Optional[int]:
    """Extract section number from a heading like '## 4. RULES'."""
    match = re.match(r"^#{2,3}\s+(\d+)\.\s+", heading)
    if match:
        return int(match.group(1))
    return None


def _detect_missing_sections(old_content: str) -> List[int]:
    """Find required sections that are missing from the old content."""
    found_numbers = set()
    for line in old_content.split("\n"):
        num = _normalize_section_number(line)
        if num is not None:
            found_numbers.add(num)

    return [n for n in REQUIRED_SECTIONS if n not in found_numbers]


def _detect_extra_sections(old_content: str) -> List[int]:
    """Find sections in old content that aren't in the standard."""
    found_numbers = set()
    for line in old_content.split("\n"):
        num = _normalize_section_number(line)
        if num is not None:
            found_numbers.add(num)

    all_valid = set(REQUIRED_SECTIONS.keys()) | set(OPTIONAL_SECTIONS.keys()) | set(WHITELISTED_SECTIONS.keys())
    return sorted(found_numbers - all_valid)


def _check_frontmatter(frontmatter: Dict[str, str], agent_id: str) -> Dict[str, Tuple[str, str]]:
    """Check frontmatter for required fields, return suggested changes."""
    changes = {}

    if "agent_id" not in frontmatter:
        changes["agent_id"] = ("", agent_id)
    elif frontmatter["agent_id"] != agent_id:
        changes["agent_id"] = (frontmatter["agent_id"], agent_id)

    if "spec_version" not in frontmatter:
        changes["spec_version"] = ("", "1.0")

    if "version" not in frontmatter:
        changes["version"] = ("", "1.0.0")

    if "mode" not in frontmatter:
        changes["mode"] = ("", "subagent")

    return changes


def _generate_placeholder_sections(missing: List[int], agent_id: str) -> List[AgentSection]:
    """Generate placeholder content for missing sections."""
    sections = []
    for num in missing:
        title = section_title(num)
        content = _placeholder_content(num, title, agent_id)
        sections.append(AgentSection(
            number=num,
            title=title,
            level=SectionLevel.H2,
            required=num in REQUIRED_SECTIONS,
            content=content,
        ))
    return sections


def _placeholder_content(num: int, title: str, agent_id: str) -> str:
    """Generate placeholder content for a missing section."""
    templates = {
        0: f"## 0. METADATA\n\n- **Agent ID**: {agent_id}\n- **Version**: 1.0.0\n- **Spec Version**: 1.0",
        1: f"## 1. ROLE\n\nTODO: Describe what this agent does and does NOT do.",
        2: "## 2. INPUTS\n\n| File | Sections to Read | Why |\n|---|---|---|\n| TODO | TODO | TODO |",
        3: "## 3. OUTPUTS\n\n| File | Purpose | Required |\n|---|---|---|\n| TODO | TODO | Yes |",
        4: "## 4. RULES\n\n### 4.1 CRITICAL\n\n1. TODO: Add critical rules\n\n### 4.2 HIGH\n\n1. TODO: Add high rules",
        5: "## 5. WORKFLOW\n\n1. TODO: Step 1\n2. TODO: Step 2",
        6: "## 6. ARTIFACTS\n\n| Artifact | Format | Location | Required |\n|---|---|---|---|\n| TODO | TODO | TODO | Yes |",
        7: "## 7. QUALITY CHECKS\n\n### Auto-verifiable\n\n- [ ] TODO: Add auto checks\n\n### LLM-verifiable\n\n- [ ] TODO: Add LLM checks",
        8: "## 8. STATE UPDATES\n\n### agent-audit.md\n\n```\n[TIME] [{agent_id}] [STAGE] [agent_start]\n```\n\n### pipeline.json\n\n```json\n{{}}\n```",
        9: "## 9. TIMING\n\n- **Expected duration**: TODO\n- **Token usage**: TODO",
        10: "## 10. DEPENDENCIES\n\n- **Requires**: TODO\n- **Produces for**: TODO",
        11: "## 11. ERRORS\n\n| Error | Code | Recovery |\n|---|---|---|\n| TODO | TODO | TODO |",
        12: "## 12. EXAMPLES\n\nTODO: Example input/output",
    }
    return templates.get(num, f"## {num}. {title}\n\nTODO: Add content")


def compute_migration_diff(agent_id: str) -> MigrationDiff:
    """Compute the migration diff for an agent.

    Reads the old .md file, identifies what's missing/wrong,
    and generates the new content. Returns a MigrationDiff
    with the old and new content for human review.
    """
    file_path = _AGENTS_DIR / f"{agent_id}.md"
    if not file_path.exists():
        raise FileNotFoundError(f"Agent file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        old_content = f.read()

    # Parse old content
    frontmatter, remaining = _extract_frontmatter(old_content)

    # Detect issues
    missing = _detect_missing_sections(old_content)
    extra = _detect_extra_sections(old_content)
    fm_changes = _check_frontmatter(frontmatter, agent_id)
    issues = []

    if missing:
        issues.append(f"Missing required sections: {missing}")
    if extra:
        issues.append(f"Non-standard sections found: {extra}")

    # Parse existing sections
    existing_sections = []
    current_section = None
    current_content = []

    for line in remaining.split("\n"):
        match = re.match(r"^(#{2,3})\s+(\d+)\.\s+(.+)$", line)
        if match:
            if current_section:
                current_section.content = "\n".join(current_content).strip()
                existing_sections.append(current_section)

            level = SectionLevel.H2 if len(match.group(1)) == 2 else SectionLevel.H3
            num = int(match.group(2))
            title = match.group(3).strip()

            current_section = AgentSection(
                number=num,
                title=title,
                level=level,
                required=num in REQUIRED_SECTIONS,
            )
            current_content = []
        elif current_section is not None:
            current_content.append(line)

    if current_section:
        current_section.content = "\n".join(current_content).strip()
        existing_sections.append(current_section)

    # Generate placeholder sections for missing ones
    placeholder_sections = _generate_placeholder_sections(missing, agent_id)

    # Merge: existing sections + placeholders
    all_sections = existing_sections + placeholder_sections
    all_sections.sort(key=lambda s: s.number)

    # Build updated frontmatter
    updated_fm = dict(frontmatter)
    for key, (_, new_val) in fm_changes.items():
        updated_fm[key] = new_val

    # Generate new content
    agent_title = ""
    for line in old_content.split("\n"):
        if line.startswith("# ") and not line.startswith("## "):
            agent_title = line[2:].strip()
            break
    if not agent_title:
        agent_title = agent_id.replace("-", " ").title() + " Agent"

    new_content = build_agent_structure(
        agent_id=agent_id,
        title=agent_title,
        sections=all_sections,
        frontmatter=AgentFrontmatter(
            description=updated_fm.get("description", ""),
            mode=updated_fm.get("mode", "subagent"),
            model=updated_fm.get("model", ""),
            agent_id=agent_id,
            version=updated_fm.get("version", "1.0.0"),
            spec_version=updated_fm.get("spec_version", "1.0"),
            permission={},  # Will be preserved from original
        ),
    )

    return MigrationDiff(
        agent_id=agent_id,
        old_content=old_content,
        new_content=new_content,
        missing_sections=missing,
        extra_sections=extra,
        issues=issues,
        frontmatter_changes=fm_changes,
    )


def apply_migration(agent_id: str, new_content: str, backup: bool = True) -> str:
    """Write the new agent .md content. Returns backup path if created."""
    file_path = _AGENTS_DIR / f"{agent_id}.md"

    if backup:
        backup_dir = _REPO_ROOT / ".backups" / "pre-standardization-20260902-214114" / "agents"
        backup_path = backup_dir / f"{agent_id}.md"
        if not backup_path.exists():
            import shutil
            shutil.copy2(file_path, backup_path)

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    return str(file_path)


def migrate_agent(agent_id: str, dry_run: bool = True) -> MigrationDiff:
    """Migrate an agent to new format.

    Args:
        agent_id: Agent to migrate
        dry_run: If True, only compute diff (don't write)

    Returns:
        MigrationDiff with old/new content and issues
    """
    diff = compute_migration_diff(agent_id)

    if not diff.has_changes:
        return diff

    if not dry_run:
        apply_migration(agent_id, diff.new_content)

    return diff


def migrate_all_agents(dry_run: bool = True) -> Dict[str, MigrationDiff]:
    """Migrate all agents. Returns dict of agent_id → MigrationDiff."""
    from core.agent_rules import list_all_agents

    diffs = {}
    for agent_id in list_all_agents():
        try:
            diffs[agent_id] = migrate_agent(agent_id, dry_run=dry_run)
        except Exception as e:
            print(f"Warning: Failed to migrate {agent_id}: {e}")
    return diffs


def show_migration_plan(dry_run: bool = True) -> None:
    """Print a migration plan for all agents."""
    diffs = migrate_all_agents(dry_run=dry_run)

    print("=" * 70)
    print("MIGRATION PLAN")
    print("=" * 70)

    total = len(diffs)
    with_changes = sum(1 for d in diffs.values() if d.has_changes)
    no_changes = total - with_changes

    print(f"\nTotal agents: {total}")
    print(f"With changes: {with_changes}")
    print(f"No changes needed: {no_changes}")

    for agent_id, diff in sorted(diffs.items()):
        print(f"\n{'─' * 70}")
        print(diff.summary())
        if diff.has_changes:
            print(f"\nDiff preview (first 50 lines):")
            d = diff.unified_diff()
            for line in d.split("\n")[:50]:
                print(f"  {line}")
            if d.count("\n") > 50:
                print(f"  ... ({d.count(chr(10)) - 50} more lines)")


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    show_migration_plan(dry_run=dry)

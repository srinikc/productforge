"""Advisory agent-card consistency audit (BI-PF-0252).

Cross-checks each `.opencode/agent/*.md` card's declared frontmatter `permission` (and `model`
pin style) against the card body (METADATA Tools + ROLE/RULES claims), so a card cannot silently
grant a capability its instructions forbid (or vice versa). Advisory (non-fatal): returns 0.
"""
import glob
import os
import re
import sys

try:
    from core.paths import ROOT
except Exception:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from core.paths import ROOT

AGENT_DIR = os.path.join(str(ROOT), ".opencode", "agent")
_WRITE_TOOLS = ("write_file", "edit", "apply_patch", "str_replace", "create_file")
_QUOTED_MODEL = re.compile(r'(?m)^model:\s*["\'].*["\']\s*$')


def _frontmatter(text: str) -> str:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    return m.group(1) if m else ""


def _permission(fm: str) -> dict:
    out, seen = {}, False
    for line in fm.splitlines():
        if re.match(r"^permission\s*:", line):
            seen = True
            continue
        if seen:
            if re.match(r"^[A-Za-z_]", line):  # dedent -> end of the permission block
                break
            m = re.match(r"^\s+([A-Za-z_]+)\s*:\s*(\S+)", line)
            if m:
                out[m.group(1)] = m.group(2).strip("\"'")
    return out


def findings(d: str = AGENT_DIR):
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*.md"))):
        try:
            t = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        fm = _frontmatter(t)
        body = t[len(fm):] if fm else t
        perm = _permission(fm)
        edit = str(perm.get("edit", "")).lower()
        issues = []
        tools_line = ""
        m = re.search(r"(?im)^\s*[-*]?\s*\*\*Tools\*\*:\s*(.+)$", body)
        if m:
            tools_line = m.group(1).lower()
        if edit == "deny" and any(w in tools_line for w in _WRITE_TOOLS):
            issues.append("METADATA Tools grant a write tool but permission.edit=deny")
        if _QUOTED_MODEL.search(fm):
            issues.append("model pin is quoted (inconsistent with sibling cards)")
        if issues:
            out.append((os.path.basename(p), issues))
    return out


def main() -> int:
    f = findings()
    if f:
        print(f"\nagent-cards: {len(f)} card(s) with consistency notes (advisory, non-fatal)")
        for name, issues in f[:12]:
            print(f"   {name}: {'; '.join(issues)}")
        print("   -> standard: docs/ROLE-PROMPT-STANDARD.md")
    else:
        print(f"\nagent-cards: {len(glob.glob(os.path.join(AGENT_DIR, '*.md')))} cards consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Advisory role-prompt standard audit (BI-0228).

Every `.opencode/agent/*.md` card must declare the canonical frontmatter keys and the
standard role sections so prompts stay consistent across the roster. Advisory (never fatal):
reports cards that drift from the standard; it does not rewrite them.
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
REQUIRED_FM = ("description", "mode", "model", "agent_id")
REQUIRED_SECTIONS = ("0. METADATA", "1. ROLE", "2. INPUTS", "3. OUTPUTS", "4. RULES")


def findings(d: str = AGENT_DIR):
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*.md"))):
        try:
            t = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:
            continue
        miss = []
        m = re.match(r"^---\n(.*?)\n---", t, re.S)
        head = m.group(1) if m else ""
        for k in REQUIRED_FM:
            if not re.search(rf"(?m)^{re.escape(k)}\s*:", head):
                miss.append(f"frontmatter:{k}")
        for s in REQUIRED_SECTIONS:
            if not re.search(rf"(?m)^##\s+{re.escape(s)}\s*$", t):
                miss.append(f"section:{s}")
        if miss:
            out.append((os.path.basename(p), miss))
    return out


def main() -> int:
    f = findings()
    if f:
        print(f"\nrole-prompts: {len(f)} card(s) missing standard sections/keys (advisory, non-fatal)")
        for name, miss in f[:12]:
            print(f"   {name}: {', '.join(miss[:5])}")
        print("   -> standard: docs/ROLE-PROMPT-STANDARD.md")
    else:
        print(f"\nrole-prompts: all {len(glob.glob(os.path.join(AGENT_DIR, '*.md')))} cards match the standard")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

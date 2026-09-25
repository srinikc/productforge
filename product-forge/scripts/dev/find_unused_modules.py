"""Find core/ modules that are not imported anywhere in the repo (triage helper)."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CORE = ROOT / "core"

# collect module names
modules = {p.stem for p in CORE.glob("*.py") if p.stem != "__init__"}

# gather all text under relevant dirs
search_roots = ["core", "dashboard", "scripts", "adapters"]
text = []
for r in search_roots:
    for p in (ROOT / r).rglob("*.py"):
        try:
            text.append(p.read_text(encoding="utf-8", errors="ignore"))
        except Exception:
            pass
blob = "\n".join(text)

unused = []
for m in sorted(modules):
    pats = [rf"\bimport\s+{re.escape(m)}\b",
            rf"\bfrom\s+core\.{re.escape(m)}\b",
            rf"\bfrom\s+core\.{re.escape(m)}\s+import\b",
            rf"\bfrom\s+\.{re.escape(m)}\s+import\b"]
    if not any(re.search(p, blob) for p in pats):
        unused.append(m)

print("total core modules:", len(modules))
print("unreferenced:", len(unused))
for m in unused:
    print("  ", m)

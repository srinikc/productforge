import os
import re

ROOTS = ["core", "dashboard", "scripts"]
EXCLUDE_DIRS = {"node_modules", ".backups", "__pycache__", "guidelines", "docs", "agents"}
EXCLUDE_FILE_HINTS = ("test_", "analyze_agent_cards", "compare_agents", "build_agent_specs",
                      "generate_agent_cards", "extend_schemas")

PATTERNS = {
    "TODO/FIXME": re.compile(r"\b(TODO|FIXME|XXX|HACK)\b"),
    "placeholder/for-now": re.compile(r"\b(placeholder|for now|not implemented|coming soon|stub)\b", re.I),
    "hardcoded project name": re.compile(r"myworld", re.I),
    "hardcoded model name": re.compile(r"\b(mimo-v2\.5|deepseek-v4|minimax-m3|qwen|gpt-4|claude-3|gemini)\b", re.I),
    "hardcoded tech (logic)": re.compile(r"\b(fastapi|react|postgresql)\b", re.I),
    "localhost/port": re.compile(r"localhost:\d+|127\.0\.0\.1:\d+"),
}

hits = {k: [] for k in PATTERNS}
scanned = 0
for root in ROOTS:
    for dp, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            if any(h in fn for h in EXCLUDE_FILE_HINTS):
                continue
            path = os.path.join(dp, fn)
            scanned += 1
            try:
                lines = open(path, encoding="utf-8", errors="ignore").read().splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                for name, pat in PATTERNS.items():
                    if pat.search(line):
                        hits[name].append(f"{path}:{i}: {line.strip()[:110]}")

print("scanned py files:", scanned)
for name, h in hits.items():
    print(f"\n=== {name} ({len(h)}) ===")
    for x in h[:25]:
        print("  " + x)

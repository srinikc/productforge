"""
Code Quality Gate (no mocks / stubs / placeholders)

Scans REAL source files produced in the project workspace for scaffolding
markers (TODO/FIXME/placeholder/NotImplementedError/"not implemented"/stub).
Only scans source directories (e.g. src/, apps/) and code extensions, and
excludes test files — so it activates once agents actually write code (tool
loop) and stays neutral for markdown-only runs.
"""
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List


CODE_AGENTS = {
    "implement", "implement-db", "implement-api", "implement-logic", "implement-ui",
    "devops", "package", "fix",
}

SOURCE_DIRS = ["src", "apps", "server", "client", "backend", "frontend", "packages"]
CODE_EXTS = {".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".cs",
             ".dart", ".php", ".rb", ".kt", ".swift", ".c", ".cpp", ".h"}

FORBIDDEN = [
    (r"#\s*TODO", "TODO comment"),
    (r"//\s*TODO", "TODO comment"),
    (r"\bFIXME\b", "FIXME marker"),
    (r"NotImplementedError", "NotImplementedError"),
    (r"\bnot implemented\b", "not implemented"),
    (r"\bplaceholder\b", "placeholder"),
    (r"coming soon", "coming soon"),
    (r"#\s*stub\b", "stub"),
    (r"//\s*stub\b", "stub"),
    # Hardcoded secrets (6.6)
    (r"(?i)\b(api[_-]?key|secret|password|passwd|access[_-]?token)\b\s*[:=]\s*[\"'][A-Za-z0-9_\-]{16,}[\"']", "possible hardcoded secret"),
    (r"AKIA[0-9A-Z]{16}", "AWS access key"),
    (r"sk-[A-Za-z0-9]{20,}", "OpenAI-style key"),
    (r"(?i)bearer\s+[A-Za-z0-9\-_.]{24,}", "hardcoded bearer token"),
]


@dataclass
class GateFinding:
    file: str
    pattern: str
    severity: str = "high"

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class GateResult:
    passed: bool = True
    scanned_files: int = 0
    findings: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {"passed": self.passed, "scanned_files": self.scanned_files,
                "findings": self.findings}


def _iter_source_files(project_dir: str):
    for base in SOURCE_DIRS:
        root = os.path.join(project_dir, base)
        if not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in CODE_EXTS:
                    continue
                low = fn.lower()
                if "test" in low or "spec" in low or "mock" in low:
                    continue  # tests/mocks are legitimate
                yield os.path.join(dirpath, fn)


def gate_agent_output(agent_id: str, artifacts: List[str], project_dir: str) -> Dict:
    """Return a gate result for code-producing agents (else trivially pass)."""
    if agent_id not in CODE_AGENTS:
        return GateResult(passed=True).to_dict()

    import re
    res = GateResult()
    for path in _iter_source_files(project_dir):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except Exception:
            continue
        res.scanned_files += 1
        for pat, label in FORBIDDEN:
            if re.search(pat, text, re.IGNORECASE | re.MULTILINE):
                res.findings.append(GateFinding(os.path.relpath(path, project_dir), label).to_dict())
    res.passed = len(res.findings) == 0
    return res.to_dict()

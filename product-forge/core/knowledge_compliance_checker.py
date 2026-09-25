"""
Knowledge-Based Compliance Checker

Loads relevant guidelines from docs/guidelines/ based on what was built,
then checks code/artifacts against those guidelines.

Detects layers (API, DB, frontend, backend, etc.) from artifacts,
loads corresponding guidelines, and validates compliance.
"""
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
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime


@dataclass
class GuidelineViolation:
    """A single guideline violation."""
    violation_id: str
    guideline_file: str
    guideline_section: str
    severity: str  # critical, high, medium, low
    description: str
    file_path: str = ""
    line_number: int = 0
    suggestion: str = ""
    
    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class ComplianceResult:
    """Compliance check result for an agent."""
    agent_id: str
    stage_id: str
    project: str
    timestamp: str
    layers_detected: List[str] = field(default_factory=list)
    guidelines_loaded: List[str] = field(default_factory=list)
    violations: List[GuidelineViolation] = field(default_factory=list)
    total_checks: int = 0
    passed_checks: int = 0
    
    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "critical")
    
    @property
    def high_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "high")
    
    @property
    def medium_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "medium")
    
    @property
    def low_count(self) -> int:
        return sum(1 for v in self.violations if v.severity == "low")
    
    @property
    def passed(self) -> bool:
        return self.critical_count == 0
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "stage_id": self.stage_id,
            "project": self.project,
            "timestamp": self.timestamp,
            "layers_detected": self.layers_detected,
            "guidelines_loaded": self.guidelines_loaded,
            "violations": [v.to_dict() for v in self.violations],
            "summary": {
                "total_violations": len(self.violations),
                "critical": self.critical_count,
                "high": self.high_count,
                "medium": self.medium_count,
                "low": self.low_count,
                "passed": self.passed,
                "total_checks": self.total_checks,
                "passed_checks": self.passed_checks,
            }
        }


# Layer detection patterns - maps artifact content to layers
LAYER_PATTERNS = {
    "api": [
        r"@(app|router|api)\.",
        r"(GET|POST|PUT|DELETE|PATCH)\s+['\"]/",
        r"def\s+(get|post|put|delete|patch)\s*\(",
        r"router\.(get|post|put|delete)\(",
        r"api_endpoint|api_route|fastapi",
        r"request\.|response\.",
        r"status_code|HTTPException",
    ],
    "database": [
        r"(CREATE|ALTER|DROP)\s+TABLE",
        r"SELECT\s+.*\s+FROM",
        r"INSERT\s+INTO|UPDATE\s+.*\s+SET|DELETE\s+FROM",
        r"model\s*\(|class\s+\w+\(Model\)",
        r"db\.(execute|query|session)",
        r"migration|alembic|schema",
        r"postgresql|postgres|sqlite|mysql",
        r"relationship\(|ForeignKey|Column\(",
    ],
    "frontend": [
        r"import\s+.*\s+from\s+['\"]react",
        r"jsx|tsx|<\w+\s",
        r"useState|useEffect|useContext",
        r"component|Component",
        r"render\s*\(|return\s*\(",
        r"className|style=",
        r"onClick|onChange|onSubmit",
        r"NextPage|GetServerSideProps",
    ],
    "backend": [
        r"from\s+fastapi\s+import|from\s+flask\s+import|from\s+django",
        r"@(app|blueprint)\.(route|get|post)",
        r"def\s+\w+\(.*request",
        r"response\.json|jsonify|JsonResponse",
        r"middleware|decorator",
        r"service|repository|handler",
    ],
    "caching": [
        r"cache|redis|memcached",
        r"@cache|cache_control|cache_page",
        r"set_cache|get_cache|invalidate_cache",
        r"ttl|expire|timeout",
        r"lru_cache|functools\.cache",
    ],
    "packaging": [
        r"setup\.py|pyproject\.toml|package\.json",
        r"requirements\.txt|Pipfile|poetry",
        r"Dockerfile|docker-compose",
        r"Makefile|build\.sh",
        r"__init__\.py|index\.ts|index\.js",
        r"export\s+default|module\.exports",
    ],
    "business_logic": [
        r"def\s+(calculate|validate|process|handle|execute)",
        r"class\s+\w+(Service|Manager|Handler|Processor)",
        r"if\s+.*:\s*#.*business|logic|rule",
        r"discount|price|payment|order|user|account",
        r"permission|role|auth|access",
    ],
    "security": [
        r"password|secret|token|api_key",
        r"hash|encrypt|decrypt|bcrypt",
        r"authenticate|authorize|login|logout",
        r"csrf|xss|sql.?injection",
        r"cors|helmet|sanitize|escape",
        r"jwt|oauth|session",
    ],
    "testing": [
        r"def\s+test_|class\s+Test",
        r"describe\(|it\(|test\(|expect\(",
        r"assert|assertEqual|assertTrue",
        r"mock|patch|fixture",
        r"pytest|unittest|jest|mocha",
    ],
    "performance": [
        r"async|await|concurrent|parallel",
        r"batch|bulk|chunk",
        r"index|optimize|cache",
        r"lazy|eager|prefetch|select_related",
        r"timeout|limit|throttle",
    ],
}

# Guideline file mapping - maps layers to guideline files
LAYER_GUIDELINE_MAP = {
    "api": [
        "docs/guidelines/api/rest.md",
        "docs/guidelines/backend/fastapi.md",
    ],
    "database": [
        "docs/guidelines/database/postgresql.md",
    ],
    "frontend": [
        "docs/guidelines/frontend/react.md",
        "docs/guidelines/ui-ux/accessibility.md",
    ],
    "backend": [
        "docs/guidelines/backend/fastapi.md",
        "docs/guidelines/architecture/decisions.md",
    ],
    "caching": [
        "docs/guidelines/caching/strategies.md",
    ],
    "packaging": [
        "docs/guidelines/packaging/distribution.md",
        "docs/guidelines/infrastructure/docker.md",
    ],
    "business_logic": [
        "docs/guidelines/shared/cross-cutting.md",
    ],
    "security": [
        "docs/guidelines/security/owasp.md",
        "docs/guidelines/compliance/regulations.md",
    ],
    "testing": [
        "docs/guidelines/testing/standards.md",
    ],
    "performance": [
        "docs/guidelines/performance/optimization.md",
        "docs/guidelines/scaling/strategies.md",
    ],
    "python": [
        "docs/guidelines/coding/python/style-guide.md",
    ],
    "typescript": [
        "docs/guidelines/coding/typescript/style-guide.md",
    ],
    "go": [
        "docs/guidelines/coding/go/style-guide.md",
    ],
}

# Guideline check patterns - what to check in each guideline
GUIDELINE_CHECKS = {
    "docs/guidelines/api/rest.md": [
        {"id": "rest-naming", "pattern": r"(GET|POST|PUT|DELETE|PATCH)", "check": "HTTP methods used correctly"},
        {"id": "rest-status", "pattern": r"status_code|HTTPException", "check": "Proper status codes"},
        {"id": "rest-pagination", "pattern": r"page|limit|offset|cursor", "check": "Pagination implemented"},
    ],
    "docs/guidelines/database/postgresql.md": [
        {"id": "db-naming", "pattern": r"CREATE\s+TABLE|class\s+\w+\(Model\)", "check": "Table/model naming"},
        {"id": "db-index", "pattern": r"index|INDEX", "check": "Indexes defined"},
        {"id": "db-migration", "pattern": r"migration|alembic", "check": "Migrations used"},
    ],
    "docs/guidelines/frontend/react.md": [
        {"id": "react-component", "pattern": r"function\s+\w+|const\s+\w+\s*=\s*\(", "check": "Functional components"},
        {"id": "react-hooks", "pattern": r"useState|useEffect|useContext", "check": "Hooks used correctly"},
        {"id": "react-types", "pattern": r":\s*(string|number|boolean|any|\w+Props)", "check": "TypeScript types"},
    ],
    "docs/guidelines/security/owasp.md": [
        {"id": "sec-input", "pattern": r"validate|sanitize|escape", "check": "Input validation"},
        {"id": "sec-auth", "pattern": r"authenticate|authorize|login", "check": "Authentication"},
        {"id": "sec-secrets", "pattern": r"os\.environ|dotenv|env\(", "check": "Secrets not hardcoded"},
    ],
    "docs/guidelines/testing/standards.md": [
        {"id": "test-coverage", "pattern": r"def\s+test_|describe\(|it\(", "check": "Tests exist"},
        {"id": "test-assert", "pattern": r"assert|expect\(", "check": "Assertions used"},
    ],
}


class KnowledgeComplianceChecker:
    """Check compliance using knowledge base guidelines."""
    
    def __init__(self, products_dir: str = "products", guidelines_dir: str = "docs/guidelines"):
        self.products_dir = Path(products_dir)
        self.guidelines_dir = Path(guidelines_dir)
    
    def check_agent_compliance(
        self, 
        agent_id: str, 
        stage_id: str, 
        project: str,
        artifact_paths: List[str]
    ) -> ComplianceResult:
        """Run knowledge-based compliance check for an agent."""
        result = ComplianceResult(
            agent_id=agent_id,
            stage_id=stage_id,
            project=project,
            timestamp=datetime.now().isoformat(),
        )
        
        # 1. Detect layers from artifacts
        layers = self._detect_layers_from_artifacts(artifact_paths)
        # Role-driven: ALSO include the agent's DECLARED knowledge domains (SSOT:
        # agent-capabilities.json + the knowledge registry), and flag declared layers with no
        # guidelines (needs sourcing — OSS/HuggingFace) so coverage is role-complete.
        try:
            role_layers = []
            try:
                import json as _json
                _repo = str(_PF_ROOT)
                _caps = _json.load(open(os.path.join(_repo, "config", "agent-capabilities.json"),
                                        encoding="utf-8")).get("agents", {})
                role_layers += [str(x) for x in (_caps.get(agent_id, {}) or {}).get("knowledge", [])]
            except Exception:
                pass
            try:
                from core import knowledge_registry as _kr
                role_layers += _kr.resolve_layers(agent_id)
            except Exception:
                pass
            for l in role_layers:
                if l not in layers:
                    layers.append(l)
            loaded = set(result.guidelines_loaded or [])
            try:
                result.role_layers = sorted(set(role_layers))
                result.role_missing = sorted({l for l in role_layers
                                              if not any(l in str(g) for g in loaded)})
            except Exception:
                pass
        except Exception:
            pass
        result.layers_detected = layers
        
        # 2. Load guidelines for detected layers
        guidelines = self._load_guidelines_for_layers(layers)
        result.guidelines_loaded = list(guidelines.keys())
        
        # 3. Check artifacts against guidelines
        for artifact_path in artifact_paths:
            if not os.path.exists(artifact_path):
                continue
            
            try:
                with open(artifact_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check against each relevant guideline
                for guideline_file, checks in guidelines.items():
                    for check in checks:
                        result.total_checks += 1
                        violation = self._check_pattern(
                            content, artifact_path, guideline_file, check
                        )
                        if violation:
                            result.violations.append(violation)
                        else:
                            result.passed_checks += 1
            except Exception as e:
                print(f"[KnowledgeCompliance] Error reading {artifact_path}: {e}")
        
        return result
    
    def _detect_layers_from_artifacts(self, artifact_paths: List[str]) -> List[str]:
        """Detect which layers were built based on artifact content."""
        detected_layers = set()
        
        for artifact_path in artifact_paths:
            if not os.path.exists(artifact_path):
                continue
            
            try:
                with open(artifact_path, 'r', encoding='utf-8') as f:
                    content = f.read().lower()
                
                for layer, patterns in LAYER_PATTERNS.items():
                    for pattern in patterns:
                        if re.search(pattern, content, re.IGNORECASE):
                            detected_layers.add(layer)
                            break
            except Exception:
                pass
        
        return sorted(list(detected_layers))
    
    def _load_guidelines_for_layers(self, layers: List[str]) -> Dict[str, List[Dict]]:
        """Load guideline checks for detected layers."""
        guidelines = {}
        
        for layer in layers:
            guideline_files = LAYER_GUIDELINE_MAP.get(layer, [])
            for guideline_file in guideline_files:
                if guideline_file in guidelines:
                    continue
                
                # Load checks for this guideline
                checks = GUIDELINE_CHECKS.get(guideline_file, [])
                if checks:
                    guidelines[guideline_file] = checks
        
        return guidelines
    
    def _check_pattern(
        self, 
        content: str, 
        file_path: str, 
        guideline_file: str, 
        check: Dict
    ) -> Optional[GuidelineViolation]:
        """Check that the guideline's expected pattern is present in the content.

        Positive check: if the pattern is absent, record a violation. Severity is
        advisory by default (low) and medium for security checks, so these do
        not trigger retry loops unless explicitly escalated.
        """
        pattern = check.get("pattern", "")
        check_desc = check.get("check", "")
        check_id = check.get("id", "")
        if not pattern:
            return None
        try:
            found = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
        except re.error:
            return None
        if found:
            return None
        severity = check.get("severity") or ("medium" if check_id.startswith("sec-") else "low")
        return GuidelineViolation(
            violation_id=check_id,
            guideline_file=guideline_file,
            guideline_section=check_desc,
            severity=severity,
            description=f"Expected pattern not found: {check_desc}",
            file_path=file_path,
            suggestion=f"Add content satisfying: {check_desc}",
        )


class GuidelineContentLoader:
    """Load actual guideline content from docs/guidelines/."""
    
    def __init__(self, guidelines_dir: str = "docs/guidelines"):
        self.guidelines_dir = Path(guidelines_dir)
    
    def load_guideline(self, guideline_path: str) -> Optional[str]:
        """Load actual guideline content.

        Accepts both repo-relative paths (e.g. ``docs/guidelines/api/rest.md``)
        and paths relative to the guidelines dir (e.g. ``api/rest.md``).
        """
        candidates = [Path(guideline_path)]
        # If path is already prefixed with the guidelines dir, strip it and also
        # try relative to the configured guidelines dir (avoids double prefix).
        prefix = self.guidelines_dir.as_posix().rstrip("/") + "/"
        normalized = Path(guideline_path).as_posix()
        if normalized.startswith(prefix):
            candidates.append(self.guidelines_dir / normalized[len(prefix):])
        candidates.append(self.guidelines_dir / guideline_path)

        for candidate in candidates:
            if candidate.exists():
                try:
                    with open(candidate, 'r', encoding='utf-8') as f:
                        return f.read()
                except Exception:
                    return None
        return None
    
    def load_guidelines_for_layers(self, layers: List[str], max_tokens: int = 5000) -> str:
        """Load and combine guideline content for multiple layers."""
        combined = []
        total_tokens = 0
        
        for layer in layers:
            guideline_files = list(LAYER_GUIDELINE_MAP.get(layer, []) or [])
            if not guideline_files:
                # Dynamic layers: any docs/guidelines/<layer>/*.md is a valid source (drop files
                # in a dir, or register a layer via core/knowledge_registry) — no static map needed.
                try:
                    import glob as _g
                    base = self.guidelines_dir
                    guideline_files = [os.path.relpath(p, str(base)).replace("\\", "/")
                                       for p in sorted(_g.glob(str(base / layer / "*.md")))
                                       if os.path.isfile(p)]
                except Exception:
                    guideline_files = []
            for guideline_file in guideline_files:
                content = self.load_guideline(guideline_file)
                if content:
                    # Truncate to fit token budget
                    tokens = len(content) // 4
                    if total_tokens + tokens > max_tokens:
                        remaining = (max_tokens - total_tokens) * 4
                        content = content[:remaining] + "\n...[truncated]"
                        combined.append(f"\n\n## {guideline_file}\n{content}")
                        return "\n".join(combined)
                    
                    combined.append(f"\n\n## {guideline_file}\n{content}")
                    total_tokens += tokens
        
        return "\n".join(combined) if combined else ""
    
    def get_guideline_summary(self, layers: List[str]) -> Dict[str, str]:
        """Get summary of guidelines for each layer."""
        summaries = {}
        
        for layer in layers:
            guideline_files = LAYER_GUIDELINE_MAP.get(layer, [])
            layer_guidelines = []
            
            for guideline_file in guideline_files:
                content = self.load_guideline(guideline_file)
                if content:
                    # Get first 500 chars as summary
                    summary = content[:500] + "..." if len(content) > 500 else content
                    layer_guidelines.append({
                        "file": guideline_file,
                        "summary": summary
                    })
            
            if layer_guidelines:
                summaries[layer] = layer_guidelines
        
        return summaries

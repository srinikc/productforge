"""
Test matrix (QA-owned).

Loads config/test-matrix.json — the canonical mapping of
requirement type x layer -> category -> framework / path / runner — and turns it
into: (a) the implement/QA prompt directive (what tests must exist), (b) a
per-category execution plan for validate, and (c) coverage expectations.

This is deliberately data-driven: adding a stack or test type is a config edit.
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
from typing import Any, Dict, List, Optional

_REPO = str(_PF_ROOT)
_MATRIX_PATH = os.path.join(_REPO, "config", "test-matrix.json")


def load(path: Optional[str] = None) -> Dict[str, Any]:
    p = path or _MATRIX_PATH
    try:
        with open(p, "r", encoding="utf-8") as f:
            m = json.load(f) or {}
    except Exception:
        m = {}
    # Merge registered test kits (test-framework/kits/<type>/kit.json) into categories.
    kits = load_kits()
    if kits:
        cats = m.setdefault("categories", {})
        for name, spec in kits.items():
            c = spec.get("category") or name
            cats.setdefault(c, {k: v for k, v in spec.items() if k != "category"})
    return m


def load_kits() -> Dict[str, Any]:
    """Registered test kits (extend the catalogue without editing core config)."""
    out: Dict[str, Any] = {}
    root = os.path.join(_REPO, "test-framework", "kits")
    if not os.path.isdir(root):
        return out
    for name in os.listdir(root):
        f = os.path.join(root, name, "kit.json")
        if os.path.exists(f):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    out[name] = json.load(fh) or {}
            except Exception:
                pass
    return out


def register_kit(name: str, spec: Dict[str, Any]) -> str:
    """Register a new test kit (QA/agent can research an area then register it)."""
    d = os.path.join(_REPO, "test-framework", "kits", name)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "kit.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2, ensure_ascii=False)
    return path


def product_kind(tech_stack: Optional[Dict]) -> str:
    """Infer product kind (web/desktop/mobile/api/cli) from the agreed tech stack."""
    chosen = (tech_stack or {}).get("chosen") or {}
    kind = str(chosen.get("kind") or "").lower()
    langs = [str(x).lower() for x in (chosen.get("languages") or [])]
    fw = [str(x).lower() for x in (chosen.get("frameworks") or [])]
    platforms = [str(x).lower() for x in (chosen.get("platforms") or [])]
    blob = " ".join([kind] + langs + fw + platforms)
    if "electron" in blob or "tauri" in blob or "desktop" in blob:
        return "desktop"
    if "ios" in blob or "android" in blob or "react native" in blob or "flutter" in blob or "mobile" in blob:
        return "mobile"
    if "react" in blob or "vue" in blob or "angular" in blob or "svelte" in blob or "next" in blob or "web" in blob:
        return "web"
    if "cli" in blob or "command-line" in blob:
        return "cli"
    if "api" in blob or "fastapi" in blob or "express" in blob or "django" in blob or "flask" in blob:
        return "api"
    return "default"


def categories_for_kind(kind: str, matrix: Optional[Dict] = None) -> List[str]:
    m = matrix or load()
    kinds = m.get("product_kinds") or {}
    entry = kinds.get(kind) or kinds.get("default") or {}
    cats = list(entry.get("categories") or [])
    cats += list(entry.get("platforms") or [])
    return cats


_SPEC_FILES = ("docs/requirements.md", "docs/design.md", "docs/architecture.md",
               "docs/product-plan.md", "docs/product-design-spec.md", "docs/ux-ia.md")


def spec_ids(project_dir: str) -> Dict[str, List[str]]:
    """FR/NFR ids declared in the project's spec artifacts (normalized)."""
    import re
    text = ""
    for rel in _SPEC_FILES:
        p = os.path.join(project_dir, rel)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    text += f.read() + "\n"
            except Exception:
                pass

    def _norm(ids):
        out = set()
        for i in ids:
            i = i.upper().replace("_", "-")
            i = re.sub(r"^(NFR|FR)(\d)", r"\1-\2", i)
            out.add(i)
        return sorted(out)

    return {
        "fr": _norm(re.findall(r"\bFR[-_]?\d+\b", text, re.I)),
        "nfr": _norm(re.findall(r"\bNFR[-_]?\d+\b", text, re.I)),
    }


def _meta(category: str, matrix: Optional[Dict] = None) -> Dict[str, Any]:
    m = matrix or load()
    return (m.get("categories") or {}).get(category, {})


def directive(features: Optional[List[Dict]] = None,
              nfr_ids: Optional[List[str]] = None,
              tech_stack: Optional[Dict] = None) -> str:
    """The full test catalogue the QA/implement agents must produce and fill."""
    m = load()
    kind = product_kind(tech_stack)
    cats = categories_for_kind(kind, m)
    if not cats:
        return ""
    by_req: Dict[str, List[str]] = {}
    lines = ["", "## TEST CATALOGUE (QA-owned — write REAL tests for EVERY requirement)"]
    for c in cats:
        meta = _meta(c, m)
        req = str(meta.get("requirement") or "functional")
        path = meta.get("path") or f"tests/{c}"
        fw = meta.get("framework") or "any"
        by_req.setdefault(req, []).append(
            f"  - `{c}` -> {path}/ ({fw}); name: {meta.get('naming','')}")
    for req in ("functional", "non_functional", "operational"):
        if by_req.get(req):
            lines.append(f"### {req.replace('_',' ').title()} tests")
            lines.extend(by_req[req])
    feats = [str(f.get("id")) for f in (features or []) if f.get("id")]
    if feats:
        lines.append("- Functional ids to cover: " + ", ".join(feats[:80]))
    if nfr_ids:
        lines.append("- Non-functional ids to cover: " + ", ".join([str(x) for x in nfr_ids[:40]]))
    lines += [
        "- Rules:",
        "  - No empty `pass`/`skip`; every test asserts observable behavior.",
        "  - Every test references its requirement id in the name/comment "
        "(`test_fr_1_...`, `# NFR-2`).",
        "  - UI/E2E/visual tests use Playwright; BDD uses Gherkin `features/*.feature` "
        "+ `steps/*.steps.ts`; DB/API/logic tests use the stack's native runner.",
        "  - Group tests into suites (smoke/sanity/feature/nfr/packaging) and register "
        "them so validate can run them by cycle.",
        "- Product kind: " + kind,
    ]
    return "\n".join(lines)


def _adapter_cmd(project_dir: str, tech_stack: Optional[Dict], category: str) -> List[str]:
    try:
        from core.test_adapters import select_adapter
        ad = select_adapter(project_dir, tech_stack)
        return ad.command(project_dir, category)
    except Exception:
        return []


def plan(project_dir: str, categories: List[str],
         tech_stack: Optional[Dict] = None) -> List[Dict[str, Any]]:
    """Per-category execution plan for validate (what to run, with which runner)."""
    m = load()
    plan_items: List[Dict[str, Any]] = []
    for c in categories:
        meta = _meta(c, m)
        runner = meta.get("runner", "adapter")
        path = os.path.join(project_dir, meta.get("path", f"tests/{c}"))
        cmd: List[str] = []
        pre: List[str] = []
        if runner == "adapter":
            cmd = _adapter_cmd(project_dir, tech_stack, c)
        elif runner == "playwright":
            cmd = ["npx", "playwright", "test"]
        elif runner == "playwright_bdd":
            pre = ["npx", "bddgen"]
            cmd = ["npx", "playwright", "test"]
        elif runner == "nfr":
            cmd = ["nfr_runner", c]
        elif runner == "framework":
            cmd = ["framework", c]
        plan_items.append({
            "category": c,
            "layer": meta.get("layer", ""),
            "requirement": meta.get("requirement", "functional"),
            "runner": runner,
            "cmd": cmd,
            "pre": pre,
            "path": path,
            "exists": os.path.isdir(path),
        })
    return plan_items


def has_category_tests(project_dir: str, category: str) -> bool:
    """True if tests exist for a category either in tests/<category>/ or by name."""
    meta = _meta(category)
    rel = meta.get("path") or f"tests/{category}"
    p = os.path.join(project_dir, *rel.split("/"))
    if os.path.isdir(p):
        for _dp, _dn, fs in os.walk(p):
            if any(f.startswith("test") or ".test." in f or ".spec." in f for f in fs):
                return True
    tdir = os.path.join(project_dir, "tests")
    if os.path.isdir(tdir):
        for _dp, _dn, fs in os.walk(tdir):
            for f in fs:
                if f.endswith((".py", ".ts", ".js")):
                    if (f"test_{category}" in f) or (f"_{category}." in f) or (f".{category}." in f):
                        return True
    return False


def missing_categories(project_dir: str, categories: List[str],
                       tech_stack: Optional[Dict] = None) -> List[str]:
    """Categories with no corresponding tests (coverage gap signal)."""
    return [c for c in categories if not has_category_tests(project_dir, c)]


def generate_bdd(project_dir: str, features: Optional[List[Dict]] = None,
                 nfr_ids: Optional[List[str]] = None,
                 output_dir: Optional[str] = None) -> Dict[str, Any]:
    """Scaffold Playwright-BDD Gherkin `features/` + `steps/`, tagged with FR/NFR ids."""
    import re

    def _safe(s: Any) -> str:
        return re.sub(r"[^0-9A-Za-z_]", "_", str(s or "feature")) or "feature"

    root = output_dir or os.path.join(project_dir, "features")
    steps = os.path.join(project_dir, "steps")
    os.makedirs(root, exist_ok=True)
    os.makedirs(steps, exist_ok=True)
    written: List[str] = []
    for f in (features or []):
        fid = str(f.get("id") or "F-1")
        safe = _safe(fid)
        name = f.get("name") or fid
        tag = fid.replace("_", "-")
        feat_path = os.path.join(root, f"{safe}.feature")
        with open(feat_path, "w", encoding="utf-8") as fh:
            fh.write(
                f"@{tag} @functional\nFeature: {name}\n"
                f"  As a user I want {name} so that it works\n\n"
                f"  Scenario: {name} happy path\n"
                f"    Given the user is on {name}\n"
                f"    When they use {name}\n"
                f"    Then they see the expected result\n")
        written.append(feat_path)
        step_path = os.path.join(steps, f"{safe}.steps.ts")
        if not os.path.exists(step_path):
            with open(step_path, "w", encoding="utf-8") as fh:
                fh.write(
                    "import { createBdd } from 'playwright-bdd';\n"
                    "const { Given, When, Then } = createBdd();\n\n"
                    f"// TODO: implement steps for {name} (tag {tag})\n"
                    f"Given('the user is on {name}', async ({{ page }}) => {{ /* TODO */ }});\n"
                    f"When('they use {name}', async ({{ page }}) => {{ /* TODO */ }});\n"
                    f"Then('they see the expected result', async ({{ page }}) => {{ /* TODO */ }});\n")
            written.append(step_path)
    return {"features_dir": root, "steps_dir": steps, "written": written}

"""Wired-audit: is every core module actually invoked on the runtime path?

Classifies each core/*.py module by WHO references it:
  RUNTIME   -> referenced by the orchestrator/executor/compliance runtime files
  ASSISTED  -> referenced by other runtime core modules (reachable, not a direct entry)
  TOOLING   -> referenced only by scripts/ tests/ templates/ (CLI/CI/tooling)
  UNWIRED   -> no importers (dead) unless allowlisted

Run: python scripts/dev/wired_audit.py
Exit code 1 if any UNWIRED (not allowlisted). Wire it into CI.
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

import os
import sys

sys.path.insert(0, os.getcwd())

import os as _os

_READ_CACHE = {}
_MAX_READ = 2_000_000  # skip huge files


def _read(path: str) -> str:
    """Shared read cache across audits (perf: each file read once per run)."""
    if path in _READ_CACHE:
        return _READ_CACHE[path]
    try:
        if _os.path.getsize(path) > _MAX_READ:
            _READ_CACHE[path] = ""
            return ""
        data = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:
        data = ""
    _READ_CACHE[path] = data
    return data


RUNTIME_ENTRY = [
    "core/pipeline_executor.py", "core/orchestrator", "core/test_framework_integration.py",
    "core/qa_report.py", "core/qa_manifest.py", "core/build_manager.py", "core/vcs.py",
]
TOOL_DIRS = ("scripts/", "tests/", "templates/", "test-framework/dashboard")

# Modules that are legitimately not runtime-wired (tooling/legacy/optional libs).
ALLOWLIST = {
    "agent_migrator", "service_catalog", "business_skills_selector", "code_analyzer",
    "build_utility", "code_executor", "docker_compose_generator", "websocket_manager",
    "memory_api", "marketing", "intake_api", "main", "agent_card_loader",
}

# Naming: "factory" is never stored/surfaced — it is "Product Forge".
# These tokens are legitimate (stdlib/3rd-party or explicit legacy read-compat shims).
NAMING_ROOTS = ("core", "scripts", "dashboard")
NAMING_ALLOW = ("default_factory", "artifactory", "factory_state", "factory_improvement",
                "factory_improvements", "FACTORY_IMPROVEMENT", "factory_supervisor",
                "factory_constitution", "send-to-factory")


def naming_audit():
    import re
    violations = []
    for root in NAMING_ROOTS:
        for dp, _dn, fn in os.walk(root):
            if "__pycache__" in dp:
                continue
            for f in fn:
                if not f.endswith((".py", ".json", ".md", ".html", ".js", ".yaml", ".yml")):
                    continue
                p = os.path.join(dp, f).replace("\\", "/")
                if p.endswith("scripts/dev/wired_audit.py"):
                    continue  # this linter mentions the token by design
                try:
                    lines = _read(p).splitlines()
                except Exception:
                    continue
                for i, line in enumerate(lines, 1):
                    if re.search(r"factory", line, re.I):
                        low = line.lower()
                        if any(a.lower() in low for a in NAMING_ALLOW):
                            continue
                        violations.append(f"{p}:{i}")
    if violations:
        print(f"\nNAMING: {len(violations)} 'factory' violation(s) — use 'Product Forge'")
        for v in violations[:20]:
            print("   ", v)
        return 1
    print("\nnaming: 0 'factory' violations (Product Forge consistent)")
    return 0


STORE_ROOTS = ("core", "scripts", "dashboard", "adapters", "test-framework",
               ".opencode/tools")
STORE_EXTS = ("json", "jsonl", "db", "sqlite", "sqlite3", "yaml", "yml", "csv", "parquet")
# framework / third-party / self files that are not Product Forge stores
STORE_EXTERNAL = {"package.json", "composer.json", "config.yaml", "state.json", "index.json",
                  "queue.json", "metrics.json", "budget.json", "test.json", "_meta.json",
                  "build-manifest.json", "agent-requirements.json", "version.json",
                  "store-registry.json", "tsconfig.json", "manifest.json",
                  "build-manifest-tenant.json", "build-manifest-operator.json"}
STORE_ALLOW = ("dashboard/**", "node_modules/**", "**/*.example.*", "**/fixtures/**",
               "**/samples/**", "**/templates/**", "**/kits/**",
               "dist/build-manifest-*.json", "build-manifest-*.json")


def store_audit():
    """Contract (fatal): every data-file literal must be declared in config/store-registry.json.

    Scans code across all source roots for data-file literals (more extensions, path-aware),
    and fails on anything not registered or allow-listed. New ad-hoc stores cannot slip in.
    """
    import json as _json
    import re as _re
    import fnmatch
    reg_path = "config/store-registry.json"
    try:
        data = _json.load(open(reg_path, encoding="utf-8"))
        reg = data.get("stores", {})
        allow = list(STORE_ALLOW) + list(data.get("allow", []) or [])
    except Exception as e:
        print(f"\nSTORE-REGISTRY: could not read {reg_path}: {e}")
        return 0
    known = set(reg.keys())
    # every registered store must declare a valid visibility (SSOT is opt-in, per concern)
    valid_vis = {"shared", "scope-local", "module-local"}
    bad_vis = [n for n, m in reg.items() if (m or {}).get("visibility") not in valid_vis]
    if bad_vis:
        print(f"\nSTORE-CONTRACT: {len(bad_vis)} store(s) missing/invalid `visibility` "
              f"(shared|scope-local|module-local): {', '.join(bad_vis[:10])}")
        return 1
    ext_re = "|".join(STORE_EXTS)
    pattern = _re.compile(r'["\']([A-Za-z0-9_\-\./]+\.(?:%s))["\']' % ext_re, _re.I)

    def allowed(path: str, base: str) -> bool:
        if base in known or path in known or base in STORE_EXTERNAL:
            return True
        return any(fnmatch.fnmatch(path, g) or fnmatch.fnmatch(base, g) for g in allow)

    unregistered = {}
    for root in STORE_ROOTS:
        if not os.path.isdir(root):
            continue
        for dp, _dn, fn in os.walk(root):
            if "__pycache__" in dp or "node_modules" in dp:
                continue
            for f in fn:
                if not f.endswith(".py"):
                    continue
                p = os.path.join(dp, f).replace("\\", "/")
                if p.endswith("scripts/dev/wired_audit.py"):
                    continue
                try:
                    text = _read(p)
                except Exception:
                    continue
                for lit in set(pattern.findall(text)):
                    base = lit.split("/")[-1]
                    if allowed(lit, base):
                        continue
                    unregistered.setdefault(base, set()).add(p)

    if unregistered:
        print(f"\nSTORE-CONTRACT: {len(unregistered)} data file(s) NOT registered/allowed")
        for name, mods in sorted(unregistered.items())[:40]:
            print(f"   {name:34s} <- {', '.join(sorted(mods)[:2])}")
        print("   register (owner+kind+scope) in config/store-registry.json, or add an `allow` glob")
        print("   -> see docs/ADDING-TO-PRODUCT-FORGE.md")
        return 1
    print("\nstore-registry: all data files registered")
    return 0


DIFF_ROOTS = ("core", "scripts", "dashboard", "config", "adapters",
              "test-framework/core", "test-framework/dashboard", "data", ".opencode")
DIFF_IGNORE = ("node_modules", "__pycache__", ".git", ".backups", ".pipeline",
               "test-framework/results", "products")
MANIFEST = "config/file-manifest.json"


def _collect_manifest_files():
    out = set()
    for root in DIFF_ROOTS:
        if not os.path.isdir(root):
            continue
        for dp, _dn, fn in os.walk(root):
            if any(x in dp for x in DIFF_IGNORE):
                continue
            for f in fn:
                out.add(os.path.join(dp, f).replace("\\", "/"))
    return out


def diff_audit(snapshot: bool = False):
    """Detect NEW files vs the snapshot manifest (works without git).

    Any new *data* file (json/jsonl/db/yaml/csv) that is not a registered store or allowed
    glob -> fail. Run with `--snapshot` to (re)record the baseline after a reviewed change.
    """
    import json as _json
    import re as _re
    current = _collect_manifest_files()
    if snapshot or not os.path.exists(MANIFEST):
        try:
            import json as _j
            os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
            open(MANIFEST, "w", encoding="utf-8").write(_j.dumps(sorted(current), indent=2))
            print(f"\ndiff-audit: baseline {'updated' if snapshot else 'created'} ({len(current)} files)")
            return 0
        except Exception as e:
            print(f"\ndiff-audit: could not write manifest: {e}")
            return 0
    try:
        base = set(_json.load(open(MANIFEST, encoding="utf-8")))
    except Exception:
        return 0
    try:
        data = _json.load(open("config/store-registry.json", encoding="utf-8"))
        known = set(data.get("stores", {}).keys())
        allow = list(STORE_ALLOW) + list(data.get("allow", []) or [])
    except Exception:
        known, allow = set(), list(STORE_ALLOW)
    import fnmatch
    ext_re = _re.compile(r"\.(?:%s)$" % "|".join(STORE_EXTS), _re.I)
    new_files = sorted(current - base)
    offenders = []
    for p in new_files:
        if p == MANIFEST:
            continue
        if not ext_re.search(p):
            continue
        base_name = p.split("/")[-1]
        if base_name in known or base_name in STORE_EXTERNAL:
            continue
        if any(fnmatch.fnmatch(p, g) or fnmatch.fnmatch(base_name, g) for g in allow):
            continue
        offenders.append(p)
    if offenders:
        print(f"\nDIFF-CONTRACT: {len(offenders)} NEW unregistered data file(s)")
        for p in offenders[:25]:
            print(f"   {p}")
        print("   register them, add an `allow` glob, or run `wired_audit.py --snapshot` after review")
        return 1
    print(f"\ndiff-audit: {len(new_files)} new file(s), all registered/allowed")
    return 0


DESTRUCTIVE_PATTERNS = ("rmtree", "Remove-Item", "os.remove", "os.unlink", "shutil.move")
DESTRUCTIVE_ROOTS = ("core", "scripts", "dashboard", "test-framework", "tests", ".opencode")
# shared state that must never be recursively deleted by scripts/tests
SHARED_STATE = ("data", "products/backlog", "products\\backlog",
                ".conversations", "products/ledger", "products\\ledger",
                "products/inbox", "products\\inbox", "products/.locks")


def destructive_audit():
    """Fail if a script/test recursively deletes shared state.

    Tests must use their own uniquely-named scratch paths (e.g. products/_test_<name>/);
    deleting product-forge/, backlog/, .conversations/, ledger/ or inbox/ is never OK.
    """
    violations = []
    for root in DESTRUCTIVE_ROOTS:
        if not os.path.isdir(root):
            continue
        for dp, _dn, fn in os.walk(root):
            if "__pycache__" in dp or "node_modules" in dp:
                continue
            for f in fn:
                if not f.endswith(".py"):
                    continue
                p = os.path.join(dp, f).replace("\\", "/")
                if p.endswith("scripts/dev/wired_audit.py"):
                    continue
                try:
                    lines = _read(p).splitlines()
                except Exception:
                    continue
                for i, line in enumerate(lines):
                    if not any(v in line for v in DESTRUCTIVE_PATTERNS):
                        continue
                    window = " ".join(lines[i:i + 3])
                    if any(s in window for s in SHARED_STATE):
                        violations.append(f"{p}:{i+1}")
    if violations:
        print(f"\nDESTRUCTIVE-CONTRACT: {len(violations)} place(s) recursively delete shared state")
        for v in violations[:20]:
            print("   ", v)
        print("   tests must use their own scratch path (products/_test_<name>/) -- never shared state dirs")
        return 1
    print("\ndestructive-audit: no shared-state deletions in scripts/tests")
    return 0


def _iter_py(roots):
    for r in roots:
        if os.path.isfile(r) and r.endswith(".py"):
            yield r
            continue
        for dp, _dn, fn in os.walk(r):
            for f in fn:
                if f.endswith(".py"):
                    yield os.path.join(dp, f).replace("\\", "/")


def reciprocity_audit():
    """Advisory (NON-FATAL): backend<->dashboard reciprocity REVIEW rule.

    Surfaces ``core.backlog.reciprocity_warnings()``: backend items missing a recorded
    ``dashboard_impact`` decision, dashboard items claiming a backend capability with no
    reciprocal link, and ``needs_dashboard=true`` items without a paired dashboard item.
    Warnings only -- always returns 0 and never fails the build.
    """
    try:
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
        from core import backlog as _bl
        warns = _bl.reciprocity_warnings()
    except Exception as e:
        print(f"\nreciprocity: SKIPPED (advisory) - {e}")
        return 0
    if not warns:
        print("\nreciprocity: 0 warnings (backend<->dashboard REVIEW rule)")
        return 0
    kinds = {}
    for w in warns:
        kinds[w.get("kind", "?")] = kinds.get(w.get("kind", "?"), 0) + 1
    summary = ", ".join(f"{k}={v}" for k, v in sorted(kinds.items()))
    print(f"\nreciprocity: {len(warns)} advisory WARNING(s) [non-fatal] ({summary})")
    for w in warns[:10]:
        print(f"   {w.get('kind')}: {w.get('ref')} - {w.get('detail')}")
    if len(warns) > 10:
        print(f"   ... and {len(warns) - 10} more "
              f"(run: python -c \"from core import backlog; backlog.print_reciprocity_warnings()\")")
    return 0


def backlog_duplicate_audit():
    """Advisory (NON-FATAL): near-duplicate OPEN backlog item pairs.

    Surfaces ``core.backlog.duplicate_pairs()`` so backlog bloat - the compounding cost
    of adding items without a dedup check - stays visible. Warnings only: always returns 0
    and never fails the build (consistent with ``reciprocity_audit``).
    """
    try:
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
        from core import backlog as _bl
        pairs = _bl.duplicate_pairs(threshold=0.6)
    except Exception as e:
        print(f"\nbacklog-duplicates: SKIPPED (advisory) - {e}")
        return 0
    if not pairs:
        print("\nbacklog-duplicates: 0 near-duplicate OPEN pairs (dedup-before-add)")
        return 0
    print(f"\nbacklog-duplicates: {len(pairs)} advisory near-duplicate OPEN pair(s) [non-fatal]")
    for p in pairs[:10]:
        print(f"   {p['score']:.2f}  {p['a']}  <->  {p['b']}")
        print(f"        {p['a_title']!r}  /  {p['b_title']!r}")
    if len(pairs) > 10:
        print(f"   ... and {len(pairs) - 10} more (run: python -m core.backlog --duplicates)")
    return 0


def tier_model_audit():
    """Advisory (NON-FATAL): kctier/model-tier drift vs the model registry.

    Delegates to ``scripts/dev/check_tier_models.py``. Reports drift but always returns 0.
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import check_tier_models as _ctm
        return _ctm.main()
    except Exception as e:
        print(f"\ntier-models: SKIPPED (advisory) - {e}")
        return 0


COST_META_STALE_DAYS = 90


def cost_registry_audit():
    """Advisory (NON-FATAL): warn when the model cost registry is stale.

    Reads ``cost_fetched_at`` (with ``cost_source``) from products/.pipeline/model_registry.json
    and warns when it is older than ``COST_META_STALE_DAYS``. Never fatal.
    """
    import json as _json
    from datetime import datetime as _dt
    path = os.path.join("products", ".pipeline", "model_registry.json")
    try:
        data = _json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"\ncost-registry: SKIPPED (advisory) - {e}")
        return 0
    src = data.get("cost_source", "")
    fetched = data.get("cost_fetched_at", "")
    if not fetched:
        print("\ncost-registry: advisory - no `cost_fetched_at` metadata (add source+fetched_at)")
        return 0
    try:
        age = (_dt.now() - _dt.fromisoformat(str(fetched))).days
    except Exception as e:
        print(f"\ncost-registry: SKIPPED (advisory) - bad cost_fetched_at: {e}")
        return 0
    if age > COST_META_STALE_DAYS:
        print(f"\ncost-registry: STALE (advisory) - cost data is {age}d old "
              f"(> {COST_META_STALE_DAYS}d; source={src!r}, fetched_at={fetched})")
    else:
        print(f"\ncost-registry: fresh ({age}d old; source={src!r}, fetched_at={fetched})")
    return 0



def legacy_guard_audit():
    """Frozen legacy files (config/legacy-frozen.json) must not change or be deleted.

    Fatal: a modified/deleted frozen file means process drift (e.g. adding endpoints to the
    legacy dashboard/server.py instead of the dashboard backlog layer).
    """
    import hashlib
    import json
    _root = str(_PF_ROOT)
    cfg_path = os.path.join(_root, "config", "legacy-frozen.json")
    try:
        cfg = json.load(open(cfg_path, encoding="utf-8-sig"))
    except Exception:
        return 0
    files = cfg.get("files") or {}
    bad = []
    for rel, meta in files.items():
        p = os.path.join(_root, rel)
        if not os.path.exists(p):
            bad.append(f"{rel}: DELETED")
            continue
        try:
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        except Exception:
            bad.append(f"{rel}: UNREADABLE"); continue
        if h != meta.get("sha256"):
            bad.append(f"{rel}: CHANGED")
    if bad:
        print("\nlegacy-frozen: FAIL - frozen legacy file(s) modified or deleted:")
        for b in bad:
            print("   -", b)
        print("   Do NOT edit/delete frozen legacy files; put APIs in the dashboard backlog layer.")
        return 1
    print(f"\nlegacy-frozen: OK ({len(files)} file(s) intact)")
    return 0


def agent_knowledge_audit():
    """Advisory (NON-FATAL): every agent card must declare knowledge that resolves to live guidelines.

    Reads the SSOT (config/agent-capabilities.json 'knowledge' + the card's knowledge_layers), applies
    the loader's alias map, and flags any agent whose layers resolve to NO docs/guidelines/<layer>/*.md.
    """
    import glob as _glob
    import json as _json
    _ALIAS = {"tech": ["api", "backend", "architecture"], "finance": ["unit-economics", "revenue-models"],
              "analytics": ["metrics"], "content": ["ui-ux"], "business": ["business", "business-models"],
              "legal": ["compliance-legal"], "design": ["ui-ux", "rendering"], "domain": ["domain"],
              "business_logic": ["business", "business-models"]}
    _HARD = {"ideation": ["business_logic"], "design": ["api", "frontend", "backend"],
             "architect": ["api", "database", "backend", "architecture"],
             "implement": ["api", "database", "frontend", "backend", "caching", "packaging"],
             "code-review": ["api", "database", "frontend", "backend", "security"],
             "validate": ["testing"], "security": ["security"], "document": ["packaging"]}

    def _live(layer):
        d = os.path.join("docs", "guidelines", layer)
        return os.path.isdir(d) and bool(_glob.glob(os.path.join(d, "*.md")))

    try:
        caps = (_json.load(open("config/agent-capabilities.json", encoding="utf-8")).get("agents") or {})
        missing = []
        for p in _glob.glob("agents/*.agent.json"):
            a = os.path.basename(p)[:-len(".agent.json")]
            try:
                c = _json.load(open(p, encoding="utf-8"))
            except Exception:
                c = {}
            layers = [str(x) for x in (caps.get(a, {}) or {}).get("knowledge", [])]
            layers += [str(x) for x in (c.get("knowledge_layers") or [])]
            if not layers:
                layers = list(_HARD.get(a, []))
            resolved = []
            for l in layers:
                resolved += _ALIAS.get(l, [l])
            if not any(_live(l) for l in resolved):
                missing.append(a)
        if missing:
            print(f"\nagent-knowledge: {len(missing)} agent(s) without live knowledge "
                  f"(declare knowledge in config/agent-capabilities.json): {missing[:10]}")
        else:
            print("\nagent-knowledge: all agents declare knowledge that resolves to live guidelines")
    except Exception as e:
        print(f"\nagent-knowledge: SKIPPED (advisory) - {e}")
    return 0


_PATHS_ALLOW = "core/paths.py"


def paths_audit():
    """Fatal: the repo root is computed ONLY in core/paths.py (BI-0204).

    Flags nested ``dirname`` chains and ``__file__``-based parent chains that re-derive
    the root outside ``core/paths.py``. A ``sys.path.insert`` bootstrap seed is allowed
    -- that seeds the interpreter, it is not domain path logic.
    """
    import re
    dirname_re = re.compile(r"os\.path\.dirname\(\s*os\.path\.dirname\(")
    parent_re = re.compile(r"Path\(\s*__file__\s*\)(?:\.resolve\(\))?\.parent\.parent")
    import json as _json
    frozen = set()
    try:
        frozen = set(_json.load(open("config/legacy-frozen.json", encoding="utf-8")).get("files", {}))
    except Exception:
        pass
    violations = []
    for f in _iter_py(["core", "dashboard", "scripts"]):
        rel = f.replace("\\", "/")
        if rel.endswith(_PATHS_ALLOW) or rel in frozen:
            continue
        for i, line in enumerate(_read(f).splitlines(), 1):
            if "sys.path.insert" in line:
                continue  # interpreter bootstrap seed
            if dirname_re.search(line) or parent_re.search(line):
                violations.append(f"{f}:{i}: {line.strip()}")
    if violations:
        print(f"\nPATHS-CONTRACT: {len(violations)} root computation(s) outside core/paths.py")
        for v in violations[:20]:
            print("   ", v)
        if len(violations) > 20:
            print(f"   ... and {len(violations) - 20} more")
        print("   -> import ROOT from core.paths (see core/paths.py); never re-derive it")
        return 1
    print("\npaths: single-source root (core/paths.py only)")
    return 0


def main():
    all_files = list(_iter_py(["core", "scripts", "tests",
                               "test-framework/core", "test-framework/dashboard",
                               "dashboard", "templates"]))
    runtime_files = set(_iter_py(RUNTIME_ENTRY))
    core_mods = [f for f in all_files if f.startswith("core/") and f.endswith(".py")]
    rows = []
    unwired = []
    for mod in core_mods:
        name = os.path.basename(mod)[:-3]
        importers = []
        for f in all_files:
            if f == mod:
                continue
            try:
                t = open(f, encoding="utf-8", errors="ignore").read()
            except Exception:
                continue
            if (("core." + name) in t) or ("core.orchestrator." + name in t) or (name + ".py" in t) \
                    or ("from core import " + name in t):
                importers.append(f)
        is_runtime = any(f in runtime_files or f.startswith("core/orchestrator") for f in importers)
        tooling_only = bool(importers) and all(f.startswith(TOOL_DIRS) for f in importers)
        if not importers:
            status = "UNWIRED"
            if name not in ALLOWLIST:
                unwired.append(name)
        elif is_runtime:
            status = "RUNTIME"
        elif tooling_only:
            status = "TOOLING"
        else:
            status = "ASSISTED"
        rows.append((name, status, importers[:3]))

    for name, status, imp in sorted(rows, key=lambda r: r[1]):
        print(f"{status:9s} {name:30s} {('<- '+', '.join(imp)) if imp else ''}")

    print(f"\nmodules: {len(rows)} | unwired(not allowlisted): {len(unwired)}")
    rc = 0
    if unwired:
        print("UNWIRED:", ", ".join(sorted(unwired)))
        rc = 1
    rc |= naming_audit()
    rc |= store_audit()
    rc |= diff_audit()
    rc |= destructive_audit()
    rc |= invocation_audit()
    rc |= reciprocity_audit()
    rc |= backlog_duplicate_audit()
    rc |= tier_model_audit()
    rc |= cost_registry_audit()
    rc |= agent_knowledge_audit()
    rc |= paths_audit()
    rc |= legacy_guard_audit()
    return rc


def invocation_audit():
    """Reachability check: no core module may be unreachable unless allowlisted.

    Catches the "imported but never invoked" class that the substring scan above
    reports as RUNTIME (e.g. an unused ``# noqa: F401`` import).
    """
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import invocation_audit as _ia
        return _ia.main()
    except Exception as e:
        print(f"invocation-audit: ERROR {e}")
        return 1


if __name__ == "__main__":
    snapshot = "--snapshot" in sys.argv
    if snapshot:
        raise SystemExit(diff_audit(snapshot=True))
    raise SystemExit(main())

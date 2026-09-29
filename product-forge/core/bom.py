"""Product BOM / footprint at packaging (BI-0217).

Single writer of ``products/<project>/artifacts/9 - Package/BOM.json``: the shipped bill of
materials (declared dependencies + licenses) and footprint (file count/sizes/checksums). Read-only
consumers: ``core/product_page.bom()`` + the dashboard. See ``docs/BOM-DESIGN.md``.

Never fatal: ``build()`` returns a dict; ``write()`` is best-effort.
"""
try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, "core", "paths.py")):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import hashlib
import json
import os
from datetime import datetime
from typing import Dict, List

SCHEMA = "product-forge/bom@1"
PKG_REL = os.path.join("artifacts", "9 - Package")
MAX_FILES = 500
MAX_BYTES_PER_FILE = 20_000_000
_SKIP_DIRS = {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "node_modules",
              ".venv", "venv", ".idea", ".vscode"}


def path(project_dir: str) -> str:
    return os.path.join(project_dir, PKG_REL, "BOM.json")


def _read(path: str, default: str = "") -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return default


def _python_deps(project_dir: str) -> List[str]:
    out: List[str] = []
    req = os.path.join(project_dir, "requirements.txt")
    if os.path.exists(req):
        for ln in _read(req).splitlines():
            s = ln.strip()
            if s and not s.startswith(("#", "-", "git+", "http")):
                out.append(s)
    pytoml = os.path.join(project_dir, "pyproject.toml")
    if os.path.exists(pytoml):
        try:
            import tomllib  # py>=3.11
            data = tomllib.loads(_read(pytoml)) or {}
            for d in ((data.get("project") or {}).get("dependencies") or []):
                out.append(str(d))
        except Exception:
            pass
    return sorted(set(out))


def _node_deps(project_dir: str) -> List[str]:
    pkg = os.path.join(project_dir, "package.json")
    try:
        data = json.loads(_read(pkg)) or {}
    except Exception:
        return []
    out = []
    for key in ("dependencies", "devDependencies"):
        for name, ver in (data.get(key) or {}).items():
            out.append(f"{name}@{ver}")
    return sorted(set(out))


def _licenses(project_dir: str) -> List[str]:
    out = set()
    pkg = os.path.join(project_dir, "package.json")
    try:
        data = json.loads(_read(pkg)) or {}
        if data.get("license"):
            out.add(str(data["license"]))
    except Exception:
        pass
    pytoml = os.path.join(project_dir, "pyproject.toml")
    if os.path.exists(pytoml):
        try:
            import tomllib
            data = tomllib.loads(_read(pytoml)) or {}
            lic = (data.get("project") or {}).get("license")
            if isinstance(lic, dict) and lic.get("text"):
                out.add(str(lic["text"]))
            elif isinstance(lic, str) and lic:
                out.add(lic)
        except Exception:
            pass
    return sorted(out)


def _footprint(source_dir: str) -> Dict:
    files, checksums, oversized = [], {}, []
    total = 0
    if os.path.isdir(source_dir):
        for root, dirs, names in os.walk(source_dir):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for n in sorted(names):
                p = os.path.join(root, n)
                rel = os.path.relpath(p, source_dir)
                try:
                    size = os.path.getsize(p)
                except Exception:
                    continue
                files.append(rel)
                total += size
                if len(files) > MAX_FILES:
                    continue
                if size <= MAX_BYTES_PER_FILE:
                    try:
                        h = hashlib.sha256()
                        with open(p, "rb") as f:
                            for chunk in iter(lambda: f.read(65536), b""):
                                h.update(chunk)
                        checksums[rel] = "sha256:" + h.hexdigest()
                    except Exception:
                        pass
                else:
                    oversized.append(rel)
    return {"file_count": len(files), "total_bytes": total,
            "checksums": checksums, "oversized": sorted(oversized)}


def _source_dir(project_dir: str) -> str:
    pkg = os.path.join(project_dir, PKG_REL)
    return pkg if os.path.isdir(pkg) else project_dir


def build(project_dir: str) -> Dict:
    """Deterministic footprint dict for the packaged product (no side effects)."""
    src = _source_dir(project_dir)
    return {
        "schema": SCHEMA,
        "project": os.path.basename(os.path.normpath(project_dir)),
        "generated_at": datetime.now().isoformat(),
        "source_dir": os.path.relpath(src, project_dir),
        "dependencies": {"python": _python_deps(project_dir), "node": _node_deps(project_dir)},
        "licenses": _licenses(project_dir),
        "footprint": _footprint(src),
        "limits": {"max_files": MAX_FILES, "max_bytes_per_file": MAX_BYTES_PER_FILE},
    }


def write(project_dir: str) -> str:
    """Build and atomically write the BOM. Returns the path ("" on failure)."""
    p = path(project_dir)
    try:
        data = build(project_dir)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, p)
        return p
    except Exception:
        return ""


def load(project_dir: str) -> Dict:
    try:
        with open(path(project_dir), "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


if __name__ == "__main__":
    import sys
    print(json.dumps(build(sys.argv[1] if len(sys.argv) > 1 else "."), indent=2, ensure_ascii=False))

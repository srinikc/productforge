"""Adopt a project built OUTSIDE the pipeline — scan it, then manage it E2E under Product Forge.

Two modes:
  * copy=True (default): copy the external project INTO products/<name>/ and add pipeline files.
  * copy=False: leave it in place; create products/<name>/ with a `link` to the source + the
    pipeline management files (scale-friendly: no duplication).

Scan (no LLM) reads the codebase for flows/structure/paths/interfaces/APIs/tech stack + docs
(goals/vision) and writes docs/adopted-project.md. Idempotent; never deletes the source.

CLI: python -m core.adopt_project scan <path> | adopt <name> <path> [--reference]
"""
import json
import os
import re
import shutil
from datetime import datetime
from typing import Dict, List

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS = os.path.join(REPO, "products")

_EXT_LANG = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
             ".jsx": "JavaScript", ".go": "Go", ".rs": "Rust", ".java": "Java",
             ".rb": "Ruby", ".php": "PHP", ".cs": "C#", ".kt": "Kotlin", ".swift": "Swift",
             ".cpp": "C++", ".c": "C", ".sql": "SQL", ".html": "HTML", ".css": "CSS"}
_SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next",
         "target", ".idea", ".vscode"}


def scan(src_path: str, max_files: int = 4000) -> Dict:
    """Lightweight scan: languages, structure, entry points, docs."""
    out = {"path": os.path.abspath(src_path), "exists": os.path.isdir(src_path),
           "languages": {}, "top_dirs": [], "entry_points": [], "apis": [], "docs": [],
           "file_count": 0, "readme": ""}
    if not out["exists"]:
        return out
    from collections import Counter
    langs = Counter()
    for dp, dn, fs in os.walk(src_path):
        dn[:] = [d for d in dn if d not in _SKIP]
        rel = os.path.relpath(dp, src_path)
        if rel.count(os.sep) == 0 and rel != ".":
            out["top_dirs"].append(rel)
        for fn in fs:
            out["file_count"] += 1
            if out["file_count"] > max_files:
                break
            ext = os.path.splitext(fn)[1].lower()
            if ext in _EXT_LANG:
                langs[_EXT_LANG[ext]] += 1
            if fn in ("main.py", "app.py", "server.py", "manage.py", "index.js", "index.ts",
                      "main.go", "main.rs", "Program.cs", "docker-compose.yml", "Dockerfile",
                      "package.json", "pyproject.toml", "requirements.txt", "go.mod"):
                out["entry_points"].append(os.path.join(rel, fn).replace("\\", "/"))
            if fn.lower().startswith("readme"):
                try:
                    out["readme"] = open(os.path.join(dp, fn), encoding="utf-8",
                                         errors="ignore").read()[:3000]
                except Exception:
                    pass
    out["languages"] = dict(langs.most_common())
    out["top_dirs"] = sorted(set(out["top_dirs"]))[:25]
    return out


def _render_scan_md(name: str, sc: Dict) -> str:
    L = [f"# Adopted project — {name}", "",
         f"> Source: `{sc['path']}` · files: {sc['file_count']} · scanned "
         f"{datetime.now().isoformat(timespec='seconds')}", "",
         "## Languages", ""]
    for k, v in (sc.get("languages") or {}).items():
        L.append(f"- {k}: {v}")
    L += ["", "## Top-level structure", ""]
    for d in sc.get("top_dirs") or []:
        L.append(f"- `{d}/`")
    L += ["", "## Entry points / interfaces", ""]
    for e in sc.get("entry_points") or []:
        L.append(f"- `{e}`")
    if sc.get("readme"):
        L += ["", "## Goals / vision (from README)", "", sc["readme"]]
    return "\n".join(L) + "\n"


def adopt(name: str, src_path: str, copy: bool = True, goal: str = "") -> Dict:
    """Adopt an external project under products/<name>/ (copy or reference)."""
    sc = scan(src_path)
    if not sc["exists"]:
        return {"error": f"source not found: {src_path}"}
    pdir = os.path.join(PRODUCTS, name)
    os.makedirs(pdir, exist_ok=True)
    if copy:
        for item in os.listdir(src_path):
            if item in _SKIP:
                continue
            s, d = os.path.join(src_path, item), os.path.join(pdir, item)
            try:
                if os.path.isdir(s):
                    if not os.path.isdir(d):
                        shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)
            except Exception:
                pass
    # pipeline management files
    pj = os.path.join(pdir, "project.json")
    try:
        data = json.load(open(pj, encoding="utf-8")) if os.path.exists(pj) else {}
    except Exception:
        data = {}
    data.update({"project": name, "adopted_from": os.path.abspath(src_path),
                 "adoption_mode": "copy" if copy else "reference",
                 "idea": goal or data.get("idea") or f"Adopted project: {name}"})
    if not copy:
        data["source_path"] = os.path.abspath(src_path)
    json.dump(data, open(pj, "w", encoding="utf-8", newline="\n"), indent=2, ensure_ascii=False)
    os.makedirs(os.path.join(pdir, "docs"), exist_ok=True)
    open(os.path.join(pdir, "docs", "adopted-project.md"), "w",
         encoding="utf-8", newline="\n").write(_render_scan_md(name, sc))
    return {"project": name, "mode": "copy" if copy else "reference", "source": sc["path"],
            "files_scanned": sc["file_count"], "languages": sc["languages"],
            "scan_doc": "docs/adopted-project.md"}


def _main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Adopt an external project")
    sub = ap.add_subparsers(dest="cmd")
    s = sub.add_parser("scan"); s.add_argument("path")
    a = sub.add_parser("adopt"); a.add_argument("name"); a.add_argument("path")
    a.add_argument("--reference", action="store_true", help="leave in place (no copy)")
    a.add_argument("--goal", default="")
    x = ap.parse_args(argv)
    if x.cmd == "scan":
        print(json.dumps(scan(x.path), indent=2, ensure_ascii=False)[:3000])
    elif x.cmd == "adopt":
        print(json.dumps(adopt(x.name, x.path, copy=not x.reference, goal=x.goal),
                         indent=2, ensure_ascii=False))
    else:
        print("usage: scan <path> | adopt <name> <path> [--reference]")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())

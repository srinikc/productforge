"""
Build manager (devops-owned).

Produces a versioned, numbered build for a project and records it:
  products/<project>/build-info.json          (latest)
  products/<project>/builds/<build_id>.json   (history)
  products/<project>/docs/releases/<build_id>.md
  products/<project>/CHANGELOG.md

Scheme:
  version      = SemVer MAJOR.MINOR.PATCH
  build_number = monotonic int (starts 1, +1 per build)
  build_id     = <version>+build.<n>   (+ git sha when available)

Bump (auto): any breaking change -> major; any feature -> minor; fixes only -> patch;
no significant change -> version unchanged (build number still increments).
"""
import hashlib
import json
import os
import subprocess
from datetime import datetime
from typing import Any, Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read_json(path: str) -> Dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _write_json(path: str, data: Dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _git_sha(project_dir: str) -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=project_dir,
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return (r.stdout or "").strip()
    except Exception:
        pass
    return ""


def latest_build(project_dir: str) -> Optional[Dict]:
    return _read_json(os.path.join(project_dir, "build-info.json")) or None


def _parse_semver(v: str) -> List[int]:
    try:
        parts = (v or "0.0.0").split("+")[0].split(".")
        return [int(parts[0]), int(parts[1]), int(parts[2])]
    except Exception:
        return [0, 0, 0]


def decide_bump(changes: Optional[List[Dict]], current: str) -> str:
    """'major' | 'minor' | 'patch' | 'none' based on the change-set."""
    if not changes:
        return "none"
    kinds = {str(c.get("type", "")).lower() for c in changes if isinstance(c, dict)}
    if "breaking" in kinds:
        return "major"
    if "feat" in kinds or "feature" in kinds:
        return "minor"
    return "patch"


def _bump_version(version: str, bump: str) -> str:
    major, minor, patch = _parse_semver(version)
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return version or "0.1.0"


def create_build(project_dir: str, project: str, trigger: str = "manual",
                 changes: Optional[List[Dict]] = None,
                 bump: Optional[str] = None,
                 version: Optional[str] = None,
                 changes_summary: Optional[str] = None) -> Dict:
    """Create the next build (version + build number) and record it."""
    prev = latest_build(project_dir) or {}
    prev_version = version or prev.get("version") or "0.1.0"
    prev_number = int(prev.get("build_number") or 0)
    build_number = prev_number + 1

    if version:
        new_version = version
    else:
        new_version = _bump_version(prev_version, bump or decide_bump(changes, prev_version))
    build_id = f"{new_version}+build.{build_number}"

    artifacts = _publish_artifacts(project_dir, build_id)
    record = {
        "project": project,
        "version": new_version,
        "build_number": build_number,
        "build_id": build_id,
        "commit": _git_sha(project_dir),
        "trigger": trigger,
        "changes": changes or [],
        "changes_summary": changes_summary or "",
        "artifacts": artifacts,
        "status": "built",
        "created_at": datetime.now().isoformat(),
    }
    record["release_notes"] = _write_release_notes(project_dir, record)

    _write_json(os.path.join(project_dir, "build-info.json"), record)
    _write_json(os.path.join(project_dir, "builds", f"{build_id}.json"), record)
    _append_changelog(project_dir, record)
    print(f"[Build] {project} {build_id} ({trigger})")
    return record


def _publish_artifacts(project_dir: str, build_id: str) -> List[Dict]:
    out: List[Dict] = []
    dist = os.path.join(project_dir, "dist")
    if not os.path.isdir(dist):
        return out
    try:
        from core.artifact_registry import get_registry
        reg = get_registry(project_dir)
        for name in os.listdir(dist):
            src = os.path.join(dist, name)
            if os.path.isfile(src):
                rec = reg.publish(src, build_id)
                try:
                    from core.signing import sign_file
                    sig = sign_file(src, project_dir)   # env key OR HIL-provided key
                    if sig.get("ok"):
                        rec["signature"] = os.path.basename(sig.get("sig_path", ""))
                        rec["signed_by"] = sig.get("source")
                except Exception:
                    pass
                out.append(rec)
    except Exception as e:
        print(f"[Build] artifact publish/sign skipped: {e}")
    return out


def _write_release_notes(project_dir: str, record: Dict) -> str:
    rel_dir = os.path.join(project_dir, "docs", "releases")
    os.makedirs(rel_dir, exist_ok=True)
    path = os.path.join(rel_dir, f"{record['build_id']}.md")
    lines = [f"# {record['project']} v{record['version']} (build {record['build_number']})",
             f"", f"- build id: `{record['build_id']}`",
             f"- trigger: {record['trigger']}", f"- commit: {record.get('commit') or 'n/a'}",
             f"- date: {record['created_at']}", ""]
    if record.get("changes_summary"):
        lines += ["## Summary", record["changes_summary"], ""]
    groups: Dict[str, List[str]] = {}
    for c in record.get("changes") or []:
        groups.setdefault(str(c.get("type", "change")).lower(), []).append(str(c.get("text", "")))
    titled = {"feat": "Added", "feature": "Added", "fix": "Fixed",
              "breaking": "Changed (breaking)", "perf": "Performance", "docs": "Docs"}
    for kind, items in groups.items():
        lines.append(f"## {titled.get(kind, kind.title())}")
        lines += [f"- {i}" for i in items if i]
        lines.append("")
    if record.get("artifacts"):
        lines.append("## Artifacts")
        lines += [f"- {a.get('name')} (sha256 {a.get('sha256','')[:12]})" for a in record["artifacts"]]
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return os.path.relpath(path, project_dir)


def _append_changelog(project_dir: str, record: Dict):
    path = os.path.join(project_dir, "CHANGELOG.md")
    header = "# Changelog\n\n"
    entry = [f"## v{record['version']} (build {record['build_number']}) — {record['created_at'][:10]}"]
    for c in record.get("changes") or []:
        entry.append(f"- [{c.get('type','change')}] {c.get('text','')}")
    if not (record.get("changes")):
        entry.append(f"- build {record['build_number']} ({record['trigger']})")
    entry.append("")
    existing = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()
    if not existing:
        existing = header
    with open(path, "w", encoding="utf-8") as f:
        f.write(existing + "\n".join(entry) + "\n")


def build_summary(project_dir: str) -> Dict:
    b = latest_build(project_dir) or {}
    return {"build_id": b.get("build_id", ""), "version": b.get("version", ""),
            "build_number": b.get("build_number", 0), "status": b.get("status", "none")}

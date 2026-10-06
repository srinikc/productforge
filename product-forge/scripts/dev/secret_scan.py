"""Blocking secret scan for pre-check/CI (BI-0205).

Flags likely hard-coded secrets in tracked files (provider keys, private-key blocks). References
to env vars / placeholders are fine. Exit nonzero when a high-signal pattern is found.
"""
import os
import re
import subprocess
import sys

_PATTERNS = [
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("openrouter_key", re.compile(r"\bsk-or-[A-Za-z0-9-]{20,}\b")),
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("private_key_block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
]
_SKIP_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip", ".gz", ".whl",
             ".woff", ".woff2", ".ico", ".lock", ".drawio"}
_ALLOW = ("REDACTED", "EXAMPLE", "YOUR_", "PLACEHOLDER", "os.getenv", "<", "***", "xxxx")


def scan_text(text: str):
    out = []
    for name, rx in _PATTERNS:
        for m in rx.finditer(text or ""):
            s = m.group(0)
            if any(a in s for a in _ALLOW):
                continue
            out.append((name, s[:6] + "..."))
    return out


def _repo_root() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True)
        return r.stdout.strip() or os.getcwd()
    except Exception:
        return os.getcwd()


def _git(root: str, *args) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _changed_files(root: str) -> tuple[list[str], bool]:
    """Files changed vs the integration branch (merge-base) plus the working tree.

    Per-merge scope: the diff a PR actually introduces. Returns ``(files, resolved)`` where ``resolved``
    is False when no integration ref could be found (e.g. a shallow CI clone) - the caller then falls
    back to the full tree so secrets are never silently skipped. On `develop` after a merge this is empty
    (already scanned on the branch).
    """
    base = ""
    refs = ["origin/develop", "develop"]
    env = os.environ.get("GITHUB_BASE_REF", "").strip()
    if env:
        refs.append(f"origin/{env}")
    for ref in refs:
        base = _git(root, "merge-base", ref, "HEAD")
        if base:
            break
    files: set[str] = set()
    if base:
        files.update(x.strip() for x in _git(root, "diff", "--name-only", base, "HEAD").splitlines())
    files.update(x.strip() for x in _git(root, "diff", "--name-only", "HEAD").splitlines())
    return sorted(f for f in files if f), bool(base)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    scan_all = "--all" in argv
    root = _repo_root()
    fallback = False
    if scan_all:
        files = _git(root, "ls-files").splitlines()
        scope = f"full tree ({len(files)} tracked)"
    else:
        files, resolved = _changed_files(root)
        if not resolved:
            fallback = True  # no integration ref (shallow clone) -> never skip secrets
            files = _git(root, "ls-files").splitlines()
            scope = f"full tree, base unresolved ({len(files)} tracked)"
        else:
            scope = f"changed vs develop ({len(files)})"
    hits = 0
    for f in files:
        if os.path.splitext(f)[1].lower() in _SKIP_EXT:
            continue
        try:
            with open(os.path.join(root, f), encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except Exception:
            continue
        for name, preview in scan_text(text):
            print(f"  SECRET? {f}: {name} ({preview})")
            hits += 1
    print(f"\nsecret-scan: {hits} potential secret(s) in {scope} file(s)"
          + ("" if (scan_all or fallback) else " (use --all for the full-tree sweep)"))
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())

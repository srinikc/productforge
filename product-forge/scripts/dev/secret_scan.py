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


def main(argv=None) -> int:
    root = _repo_root()
    try:
        files = subprocess.run(["git", "ls-files"], cwd=root,
                               capture_output=True, text=True).stdout.splitlines()
    except Exception:
        files = []
    hits = 0
    for f in files:
        if os.path.splitext(f)[1].lower() in _SKIP_EXT:
            continue
        try:
            with open(os.path.join(root, f), "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except Exception:
            continue
        for name, preview in scan_text(text):
            print(f"  SECRET? {f}: {name} ({preview})")
            hits += 1
    print(f"\nsecret-scan: {hits} potential secret(s) in {len(files)} tracked file(s)")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())

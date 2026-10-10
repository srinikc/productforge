"""Python-version compatibility guard (RCCA for the develop CI break).

CI runs Python 3.11; local dev may run 3.12+. PEP 701 (3.12) relaxed the rule that an
f-string REPLACEMENT FIELD (inside ``{...}``) may not contain a backslash. Code that relies
on that relaxation parses locally but is a **SyntaxError on 3.11** - which is exactly how
``core/presentation_generator.py`` broke the ``structure`` CI job (import of ``core/__init__``).

This guard flags a backslash that lies INSIDE an f-string replacement field (at any nesting,
including a nested string/f-string literal inside the field). A backslash in the f-string's
own literal text (outside ``{...}``) is legal on 3.11 and is NOT flagged.

Usage:
    python scripts/dev/pycompat_check.py                # scan core/ scripts/ dashboard/ api/
    python scripts/dev/pycompat_check.py path1 path2    # scan specific files (pre-commit)

Exit 0 = clean, 1 = incompatible construct found (fatal gate).
"""
import io
import os
import sys
import token
import tokenize

ROOTS = ("core", "scripts", "dashboard", "api")


def _has_fstring_tokens() -> bool:
    """FSTRING_START/MIDDLE/END tokens exist on 3.12+ (PEP 701)."""
    return hasattr(token, "FSTRING_START")


def scan_source(src: str) -> list[tuple[int, str]]:
    """Return [(lineno, token_text)] for backslashes inside f-string replacement fields."""
    hits: list[tuple[int, str]] = []
    fstring_depth = 0
    brace_depth = 0
    try:
        toks = tokenize.generate_tokens(io.StringIO(src).readline)
    except Exception:
        return hits
    try:
        for tok in toks:
            nm = token.tok_name.get(tok.type, "")
            s = tok.string
            if nm == "FSTRING_START":
                fstring_depth += 1
            elif nm == "FSTRING_END":
                fstring_depth = max(0, fstring_depth - 1)
            elif fstring_depth > 0 and tok.type == token.OP and s == "{":
                brace_depth += 1
            elif fstring_depth > 0 and tok.type == token.OP and s == "}":
                brace_depth = max(0, brace_depth - 1)
            elif brace_depth > 0 and "\\" in s:
                hits.append((tok.start[0], s))
    except (tokenize.TokenError, IndentationError):
        return hits
    return hits


def scan_file(path: str) -> list[tuple[int, str]]:
    try:
        with open(path, encoding="utf-8") as f:
            return scan_source(f.read())
    except Exception:
        return []


def _iter_py(roots=ROOTS):
    for root in roots:
        if os.path.isfile(root) and root.endswith(".py"):
            yield root
            continue
        for base, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", "node_modules", ".git")]
            for fn in files:
                if fn.endswith(".py"):
                    yield os.path.join(base, fn)


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    if not _has_fstring_tokens():
        print("\npycompat: SKIPPED (interpreter predates PEP 701 f-string tokens; "
              "f-string backslash is already illegal here)")
        return 0
    files = argv or list(_iter_py())
    bad: list[tuple[str, int, str]] = []
    for p in files:
        if not p.endswith(".py") or not os.path.isfile(p):
            continue
        for lineno, txt in scan_file(p):
            bad.append((p, lineno, txt))
    if bad:
        print(f"\npycompat: FAIL - {len(bad)} f-string backslash-in-field construct(s) "
              "(SyntaxError on Python 3.11, the CI target):")
        for p, lineno, txt in bad[:20]:
            print(f"   - {p}:{lineno}: {txt!r}")
        if len(bad) > 20:
            print(f"   ... and {len(bad) - 20} more")
        print("   Fix: move the backslash out of the {...} expression (e.g. build the string "
              "in a local variable, or use chr(10)).")
        return 1
    print(f"\npycompat: OK ({len(files)} file(s); no f-string backslash inside a replacement field)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

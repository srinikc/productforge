"""BI-PF-1340 gate: a change that modifies SHIPPED/SENSITIVE logic must add or update a test.

"No test, no merge": if this branch changes shipped Python (``core/``, ``api/``, ``adapters/``) but adds or
updates no test under ``test-framework/tests/`` (any depth), fail. Exempt a genuinely non-testable change with
``PF_ALLOW_NO_TEST=1`` (record the reason in the item). Tooling/docs/config-only changes are exempt (no shipped
Python touched). See config/language-rule.json for the shipped/sensitive roots.
"""
import os
import subprocess
import sys

_SHIPPED = ("core/", "api/", "adapters/")
_LEGACY_EXEMPT = ("dashboard/",)   # legacy, frozen - not shipped/customer-visible runtime
_TEST_MARK = "test-framework/tests/"


def _git(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    return r.stdout or ""


def _changed():
    files = set()
    base = _git("merge-base", "develop", "HEAD").strip()
    if base:
        files |= {l.strip() for l in _git("diff", "--name-only", base, "HEAD").splitlines() if l.strip()}
    files |= {l.strip() for l in _git("diff", "--name-only", "HEAD").splitlines() if l.strip()}
    files |= {l.strip() for l in _git("ls-files", "--others", "--exclude-standard").splitlines() if l.strip()}
    return files


def _is_shipped(path: str) -> bool:
    p = "/" + path.replace("\\", "/").lstrip("/")
    p = p[len("/product-forge"):] if p.startswith("/product-forge/") else p
    p = p.lstrip("/")
    if p.startswith(_LEGACY_EXEMPT):
        return False
    return any(p.startswith(s) for s in _SHIPPED) and p.endswith(".py")


def _is_test(path: str) -> bool:
    p = path.replace("\\", "/")
    p = p[len("product-forge/"):] if p.startswith("product-forge/") else p
    return _TEST_MARK in ("/" + p) or p.startswith(_TEST_MARK)


def main() -> int:
    if str(os.environ.get("PF_ALLOW_NO_TEST", "")).strip().lower() in ("1", "true", "yes"):
        print("changed-tests: exempt (PF_ALLOW_NO_TEST set) - record the reason on the item")
        return 0
    changed = _changed()
    shipped = sorted(c for c in changed if _is_shipped(c))
    tests = sorted(c for c in changed if _is_test(c) and c.replace("\\", "/").endswith(".py"))
    if shipped and not tests:
        print("changed-tests: FAIL - shipped/sensitive code changed with NO added/updated test:")
        for s in shipped[:10]:
            print(f"    {s}")
        print("  Add/update a test under test-framework/tests/, or set PF_ALLOW_NO_TEST=1 with a recorded reason.")
        return 1
    print(f"changed-tests: OK (shipped_changed={len(shipped)}, tests_changed={len(tests)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

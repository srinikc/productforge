"""Sync the checked-in global commands (``.opencode/command_global/*.md``) into the installed location
(``~/.config/opencode/command/``) **byte-for-byte**. Idempotent + cross-platform.

  python scripts/dev/sync_global_commands.py           # sync (write); auto-called by install.py
  python scripts/dev/sync_global_commands.py --check    # verify only; exit 1 on drift (skips if not installed -> CI-safe)
  python scripts/dev/sync_global_commands.py --dest DIR # override the install dir
"""
import argparse
import os
import shutil
import sys

try:
    from core.paths import ROOT as _ROOT
except ImportError:
    _ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

SRC = os.path.join(str(_ROOT), ".opencode", "command_global")
DEST = os.path.join(os.path.expanduser("~"), ".config", "opencode", "command")


def _files():
    if not os.path.isdir(SRC):
        return []
    return sorted(f for f in os.listdir(SRC) if f.endswith(".md"))


def _bytes(path: str):
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify only; exit 1 on drift")
    ap.add_argument("--dest", default=DEST)
    a = ap.parse_args(argv)
    files = _files()
    if not files:
        print("global-commands: no .opencode/command_global/*.md to sync")
        return 0
    drift, synced, skipped = [], [], []
    for f in files:
        sb = _bytes(os.path.join(SRC, f))
        db = _bytes(os.path.join(a.dest, f))
        if a.check:
            if db is None:
                skipped.append(f)
            elif db != sb:
                drift.append(f)
        else:
            try:
                os.makedirs(a.dest, exist_ok=True)
                shutil.copyfile(os.path.join(SRC, f), os.path.join(a.dest, f))
                synced.append(f)
            except Exception as e:  # noqa: BLE001
                print(f"global-commands: FAIL writing {os.path.join(a.dest, f)}: {type(e).__name__}")
                return 1
    if a.check:
        if drift:
            print(f"global-commands: FAIL (drift in installed copies) -> {', '.join(drift)} "
                  f"(re-run without --check to sync into {a.dest})")
            return 1
        print(f"global-commands: OK (installed copies match source; not installed: {skipped})")
        return 0
    print(f"global-commands: synced {len(synced)} -> {a.dest} ({', '.join(synced)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

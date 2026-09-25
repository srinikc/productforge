"""
Signing (GPG) — supports BOTH key sources:
  1. `env`  : GPG_PRIVATE_KEY / GPG_KEY_ID  (org secret)
  2. `hil`  : project.json -> "signing": { key_id | key_file, passphrase_env }
  3. `keyring`: an existing secret key in the local keyring

Provides tag-signing args for git and detached-armor signatures for artifacts.
All guarded: if gpg/key is unavailable, callers fall back to unsigned and record it.
"""
import json
import os
import shutil
import subprocess
from typing import Dict, List, Optional


def _gpg() -> Optional[str]:
    return shutil.which("gpg") or shutil.which("gpg2")


def _cfg(project_dir: str) -> Dict:
    try:
        with open(os.path.join(project_dir, "project.json"), "r", encoding="utf-8") as f:
            return (json.load(f) or {}).get("signing") or {}
    except Exception:
        return {}


def _import_material(material: str) -> bool:
    g = _gpg()
    if not g or not material:
        return False
    try:
        r = subprocess.run([g, "--batch", "--import"], input=material,
                           capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def _keyring_ids() -> List[str]:
    g = _gpg()
    if not g:
        return []
    try:
        r = subprocess.run([g, "--list-secret-keys", "--with-colons"],
                           capture_output=True, text=True, timeout=30)
        return [l.split(":")[4] for l in r.stdout.splitlines() if l.startswith("sec")]
    except Exception:
        return []


def resolve(project_dir: str = "") -> Dict:
    """Return {source, key_id} for the signing key to use (or {source:'none'})."""
    if not _gpg():
        return {"source": "none", "reason": "gpg not installed"}
    c = _cfg(project_dir)
    # HIL-provided
    if c.get("key_file") and os.path.exists(c["key_file"]):
        try:
            with open(c["key_file"], "r", encoding="utf-8") as f:
                _import_material(f.read())
        except Exception:
            pass
    if c.get("key_id"):
        return {"source": "hil", "key_id": c["key_id"]}
    if c.get("key_file"):
        ids = _keyring_ids()
        return {"source": "hil", "key_id": ids[0] if ids else ""}
    # org secret
    env_key = os.environ.get("GPG_PRIVATE_KEY")
    if env_key:
        _import_material(env_key)
        return {"source": "env", "key_id": os.environ.get("GPG_KEY_ID", "")}
    ids = _keyring_ids()
    if ids:
        return {"source": "keyring", "key_id": ids[0]}
    return {"source": "none", "reason": "no key available"}


def tag_args(project_dir: str = "") -> List[str]:
    """Extra git-tag args for signing (['-u', keyid]) or [] to stay unsigned."""
    k = resolve(project_dir)
    if k.get("source") == "none":
        return []
    return ["-u", k["key_id"]] if k.get("key_id") else []


def sign_file(path: str, project_dir: str = "") -> Dict:
    """Detached-armor signature for an artifact -> <path>.asc."""
    g = _gpg()
    if not g or not os.path.exists(path):
        return {"ok": False, "reason": "gpg or file missing"}
    k = resolve(project_dir)
    if k.get("source") == "none":
        return {"ok": False, "reason": k.get("reason", "no key")}
    out = path + ".asc"
    cmd = [g, "--batch", "--yes", "--armor", "--detach-sign", "-o", out]
    if k.get("key_id"):
        cmd += ["-u", k["key_id"]]
    cmd.append(path)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return {"ok": r.returncode == 0, "sig_path": out if r.returncode == 0 else "",
                "source": k.get("source"), "error": (r.stderr or "")[-200:] if r.returncode else ""}
    except Exception as e:
        return {"ok": False, "reason": str(e)}

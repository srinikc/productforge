"""
Artifact registry (industry-standard build artifact storage).

Content-addressed, immutable, checksummed. Local backend by default under
  products/<project>/.artifacts/<build_id>/
with a pluggable interface for external backends (OCI/Docker registry, S3/GCS/
Azure Blob, Artifactory/Nexus) selected via env PIPELINE_ARTIFACT_BACKEND.

Backends only need to implement `publish(src_path, build_id) -> record`.
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

import hashlib
import json
import os
import shutil
from typing import Dict

_REPO = str(_PF_ROOT)


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class LocalRegistry:
    name = "local"

    def __init__(self, root: str):
        self.root = root
        os.makedirs(root, exist_ok=True)

    def publish(self, src_path: str, build_id: str) -> Dict:
        dest_dir = os.path.join(self.root, build_id)
        os.makedirs(dest_dir, exist_ok=True)
        name = os.path.basename(src_path)
        dest = os.path.join(dest_dir, name)
        shutil.copy2(src_path, dest)
        digest = sha256(dest)
        return {"name": name, "backend": self.name, "build_id": build_id,
                "path": os.path.relpath(dest, self.root), "sha256": digest,
                "size": os.path.getsize(dest)}

    def list(self, build_id: str):
        d = os.path.join(self.root, build_id)
        return sorted(os.listdir(d)) if os.path.isdir(d) else []


class CommandRegistry:
    """External artifact backend via configured commands (real, not a stub).

    Backends: s3 | gcs | azure | oci | http (Artifactory/Nexus) | any (custom cmd).
    Config (project.json -> "artifact_registry" or env PIPELINE_ARTIFACT_CONFIG JSON):
      { "backend": "s3", "bucket": "my-bucket", "prefix": "artifacts",
        "registry": "ghcr.io/org/repo", "base_url": "https://artifactory/...",
        "user": "...", "password_env": "ARTIFACTORY_PASSWORD",
        "command": ["my-uploader", "{file}", "{uri}"] }
    """
    def __init__(self, backend: str, config: Dict):
        self.name = backend
        self.config = config or {}

    def _uri(self, build_id: str, name: str) -> str:
        c = self.config
        b = self.name
        if b == "s3":
            return f"s3://{c.get('bucket','bucket')}/{c.get('prefix','artifacts')}/{build_id}/{name}"
        if b == "gcs":
            return f"gs://{c.get('bucket','bucket')}/{c.get('prefix','artifacts')}/{build_id}/{name}"
        if b == "azure":
            return f"{c.get('container','artifacts')}/{build_id}/{name}"
        if b == "oci":
            return f"{c.get('registry','localhost:5000')}/{c.get('repo','app')}:{build_id}"
        if b == "http":
            return f"{c.get('base_url','https://artifacts.local')}/{c.get('prefix','artifacts')}/{build_id}/{name}"
        return f"{c.get('prefix','artifacts')}/{build_id}/{name}"

    def _cmd(self, src: str, uri: str) -> list:
        b = self.name
        c = self.config
        if b == "s3":
            return ["aws", "s3", "cp", src, uri]
        if b == "gcs":
            return ["gsutil", "cp", src, uri]
        if b == "azure":
            return ["az", "storage", "blob", "upload", "--file", src,
                    "--container-name", str(c.get("container", "artifacts")), "--name", uri]
        if b == "oci":
            if shutil.which("oras"):
                return ["oras", "push", uri, f"{src}:application/octet-stream"]
            return ["docker", "push", uri]
        if b == "http":
            cmd = ["curl", "-fsS", "-T", src, uri]
            if c.get("user"):
                cmd = ["curl", "-fsS", "-u", f"{c['user']}:{os.environ.get(c.get('password_env',''), '')}",
                       "-T", src, uri]
            return cmd
        if c.get("command"):
            return [str(x).replace("{file}", src).replace("{uri}", uri) for x in c["command"]]
        return []

    def publish(self, src_path: str, build_id: str) -> Dict:
        import subprocess
        name = os.path.basename(src_path)
        digest = sha256(src_path)
        uri = self._uri(build_id, name)
        cmd = self._cmd(src_path, uri)
        rec = {"name": name, "backend": self.name, "build_id": build_id,
               "sha256": digest, "size": os.path.getsize(src_path), "uri": uri}
        if not cmd:
            rec.update({"status": "not_configured", "ok": False})
            return rec
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=int(self.config.get("timeout", 600)))
            rec.update({"status": "published" if r.returncode == 0 else "failed",
                        "ok": r.returncode == 0,
                        "error": (r.stderr or "")[-300:] if r.returncode else ""})
        except FileNotFoundError:
            rec.update({"status": "tool_missing", "ok": False, "error": f"{cmd[0]} not installed"})
        except Exception as e:
            rec.update({"status": "error", "ok": False, "error": str(e)[:300]})
        return rec

    def list(self, build_id: str):
        return []


def _load_cfg(project_dir: str) -> Dict:
    try:
        p = os.path.join(project_dir, "project.json")
        if os.path.exists(p):
            with open(p, "r", encoding="utf-8") as f:
                return (json.load(f) or {}).get("artifact_registry") or {}
    except Exception:
        pass
    return {}


def get_registry(project_dir: str):
    cfg = _load_cfg(project_dir)
    backend = str(cfg.get("backend") or os.environ.get("PIPELINE_ARTIFACT_BACKEND", "local")).lower()
    if backend and backend != "local":
        return CommandRegistry(backend, cfg)
    return LocalRegistry(os.path.join(project_dir, ".artifacts"))

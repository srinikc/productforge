"""
NFR / security / packaging runner (4.3-4.6).

Runs real tools when they exist in the environment, and skips cleanly when they
don't (so runs stay green on minimal machines). All commands are allow-listed.

Categories:
  security     -> bandit / pip-audit / npm audit
  accessibility-> package.json test:a11y script (if present)
  performance  -> package.json test:perf / test:load script (if present)
  packaging    -> npm build/pack, python -m build, docker build (Dockerfile)
"""
import json
import os
import shutil
import subprocess
from typing import Dict, List, Optional


def _which(exe: str) -> bool:
    return shutil.which(exe) is not None


def _run(cmd: List[str], cwd: str, timeout: int = 600) -> Dict:
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        tail = ((r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else ""))[-4000:]
        return {"cmd": " ".join(cmd), "ok": r.returncode == 0, "tail": tail}
    except subprocess.TimeoutExpired:
        return {"cmd": " ".join(cmd), "ok": False, "tail": "timeout"}
    except FileNotFoundError:
        return {"cmd": " ".join(cmd), "ok": False, "tail": "executable not found"}
    except Exception as e:
        return {"cmd": " ".join(cmd), "ok": False, "tail": str(e)}


def _scripts(project_dir: str) -> Dict:
    pkg = os.path.join(project_dir, "package.json")
    if os.path.exists(pkg):
        try:
            with open(pkg, "r", encoding="utf-8") as f:
                return (json.load(f) or {}).get("scripts", {}) or {}
        except Exception:
            pass
    return {}


def run_security(project_dir: str) -> List[Dict]:
    out = []
    if os.path.exists(os.path.join(project_dir, "package.json")):
        runner = "npm" if _which("npm") else ("pnpm" if _which("pnpm") else None)
        if runner:
            out.append(_run([runner, "audit", "--audit-level=high"], project_dir))
    if _which("bandit"):
        out.append(_run(["bandit", "-q", "-r", "."], project_dir, timeout=300))
    if _which("pip-audit"):
        out.append(_run(["pip-audit"], project_dir, timeout=300))
    out += run_cve(project_dir)
    out += run_zap(project_dir)
    out += run_tls(project_dir)
    out += run_dos(project_dir)
    return out


def run_cve(project_dir: str) -> List[Dict]:
    """CVE / dependency-vulnerability scan via available scanner (6.2)."""
    out = []
    if _which("trivy"):
        out.append(_run(["trivy", "fs", "--quiet", "--severity", "HIGH,CRITICAL", "."],
                        project_dir, timeout=600))
    elif _which("snyk"):
        out.append(_run(["snyk", "test", "--severity-threshold=high"], project_dir, timeout=600))
    return out


def run_bom(project_dir: str) -> List[Dict]:
    """Software Bill of Materials (7.3): prefer syft, else emit a minimal SBOM."""
    out: List[Dict] = []
    if _which("syft"):
        out.append(_run(["syft", ".", "-o", "json"], project_dir, timeout=300))
        return out
    try:
        import json as _json
        comps = []
        for rel in ("package.json", "requirements.txt"):
            p = os.path.join(project_dir, rel)
            if os.path.exists(p):
                comps.append({"manifest": rel})
        bom = {"bomFormat": "CycloneDX-like", "specVersion": "1.0",
               "components": comps}
        out_dir = os.path.join(project_dir, "docs")
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "BOM.json"), "w", encoding="utf-8") as f:
            _json.dump(bom, f, indent=2)
        out.append({"step": "bom", "cmd": "BOM.json", "ok": True})
    except Exception as e:
        out.append({"step": "bom", "cmd": "BOM.json", "ok": False, "error": str(e)})
    return out


def _target_url(project_dir: str) -> str:
    import json
    try:
        with open(os.path.join(project_dir, "project.json"), "r", encoding="utf-8") as f:
            u = ((json.load(f) or {}).get("deploy") or {}).get("url")
            if u:
                return str(u)
    except Exception:
        pass
    return os.environ.get("BASE_URL", "")


def run_zap(project_dir: str) -> List[Dict]:
    """OWASP ZAP baseline scan (6.3). Needs a running app URL; else not-run."""
    url = _target_url(project_dir)
    if not url:
        return []
    if _which("zap-cli"):
        return [_run(["zap-cli", "quick-scan", "-s", "-r", url], project_dir, timeout=1800)]
    if _which("docker"):
        return [_run(["docker", "run", "--rm", "-t", "ghcr.io/zaproxy/zaproxy:stable",
                      "zap-baseline.py", "-t", url], project_dir, timeout=1800)]
    return []


def run_tls(project_dir: str) -> List[Dict]:
    """TLS/communications security (6.7)."""
    url = _target_url(project_dir)
    if not url:
        return []
    import urllib.parse
    p = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    host = p.hostname or ""
    port = p.port or (443 if p.scheme == "https" else 80)
    if not host:
        return []
    if _which("testssl.sh"):
        return [_run(["testssl.sh", "--quiet", f"{host}:{port}"], project_dir, timeout=600)]
    if _which("openssl"):
        return [_run(["openssl", "s_client", "-connect", f"{host}:{port}",
                      "-servername", host, "-brief"], project_dir, timeout=60)]
    return []


def run_dos(project_dir: str) -> List[Dict]:
    """Rate-limit / load resilience (6.8) — opt-in via PIPELINE_RUN_DOS=1."""
    if os.environ.get("PIPELINE_RUN_DOS", "0") != "1":
        return []
    url = _target_url(project_dir)
    scripts = _scripts(project_dir)
    out = []
    if _which("k6") and url:
        out.append(_run(["k6", "run", "-e", f"BASE_URL={url}", "--vus", "50", "--duration", "30s",
                         "tests/performance/load.js"], project_dir, timeout=600))
    for s in ("test:load", "test:rate-limit", "benchmark"):
        if s in scripts:
            runner = "npm" if _which("npm") else "pnpm"
            out.append(_run([runner, "run", s], project_dir, timeout=600))
            break
    return out


def run_gates(project_dir: str, categories: List[str]) -> List[Dict]:
    """a11y / performance gates via package.json scripts when present."""
    scripts = _scripts(project_dir)
    runner = "npm" if _which("npm") else ("pnpm" if _which("pnpm") else None)
    out = []
    if not runner:
        return out
    if "accessibility" in categories:
        for s in ("test:a11y", "a11y", "test:e2e:a11y"):
            if s in scripts:
                out.append(_run([runner, "run", s], project_dir, timeout=600))
                break
    if "performance" in categories:
        for s in ("test:perf", "perf", "test:load", "benchmark"):
            if s in scripts:
                out.append(_run([runner, "run", s], project_dir, timeout=600))
                break
    return out


def package_contents(project_dir: str) -> List[Dict]:
    """7.2: bundle LICENSE / NOTICE / README / docs into dist/."""
    import shutil
    dist = os.path.join(project_dir, "dist")
    os.makedirs(dist, exist_ok=True)
    lic = ""
    for c in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING"):
        if os.path.exists(os.path.join(project_dir, c)):
            lic = os.path.join(project_dir, c)
            break
    try:
        if lic:
            shutil.copy2(lic, os.path.join(dist, "LICENSE"))
        else:
            with open(os.path.join(dist, "LICENSE"), "w", encoding="utf-8") as f:
                f.write("Proprietary — add your license.\n")
        deps = [m for m in ("requirements.txt", "package.json", "pyproject.toml")
                if os.path.exists(os.path.join(project_dir, m))]
        with open(os.path.join(dist, "NOTICE"), "w", encoding="utf-8") as f:
            f.write("Third-party notices\n" + "\n".join(deps) + "\n")
        for src, dst in (("README.md", "README.md"), ("docs", "docs")):
            sp = os.path.join(project_dir, src)
            if os.path.isdir(sp):
                shutil.copytree(sp, os.path.join(dist, dst), dirs_exist_ok=True)
            elif os.path.exists(sp):
                shutil.copy2(sp, os.path.join(dist, dst))
        return [{"step": "package_contents", "cmd": "dist/{LICENSE,NOTICE,README,docs}", "ok": True}]
    except Exception as e:
        return [{"step": "package_contents", "cmd": "dist", "ok": False, "error": str(e)[:200]}]


def write_footprint(project_dir: str) -> List[Dict]:
    """7.4: resource footprint summary -> docs/footprint.md."""
    dist = os.path.join(project_dir, "dist")
    total = files = 0
    if os.path.isdir(dist):
        for dp, _dn, fs in os.walk(dist):
            for f in fs:
                try:
                    total += os.path.getsize(os.path.join(dp, f))
                    files += 1
                except Exception:
                    pass
    deps = 0
    for m in ("requirements.txt", "package.json"):
        p = os.path.join(project_dir, m)
        if os.path.exists(p):
            try:
                deps += max(1, open(p, encoding="utf-8", errors="ignore").read().count("\n"))
            except Exception:
                pass
    try:
        out = os.path.join(project_dir, "docs")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "footprint.md"), "w", encoding="utf-8") as f:
            f.write(f"# Resource Footprint\n\n- artifacts: {files} file(s), {total/1024:.1f} KiB\n"
                    f"- dependency entries: ~{deps}\n")
        return [{"step": "footprint", "cmd": "docs/footprint.md", "ok": True}]
    except Exception as e:
        return [{"step": "footprint", "cmd": "docs/footprint.md", "ok": False, "error": str(e)[:200]}]


def run_installers(project_dir: str) -> List[Dict]:
    """7.1: platform installers when tooling is present (else not-run)."""
    out: List[Dict] = []
    if _which("dpkg-deb") and os.path.isdir(os.path.join(project_dir, "debian")):
        out.append(_run(["dpkg-deb", "--build", "debian"], project_dir, timeout=600))
    if _which("rpmbuild") and os.path.exists(os.path.join(project_dir, "app.spec")):
        out.append(_run(["rpmbuild", "-bb", "app.spec"], project_dir, timeout=600))
    if _which("candle") and _which("light") and os.path.exists(os.path.join(project_dir, "installer.wxs")):
        out.append(_run(["candle", "installer.wxs"], project_dir, timeout=600))
        out.append(_run(["light", "installer.wixobj"], project_dir, timeout=600))
    if _which("hdiutil") and os.path.exists(os.path.join(project_dir, "macos")):
        out.append(_run(["hdiutil", "create", "dist/app.dmg", "-srcfolder", "macos", "-ov"],
                        project_dir, timeout=600))
    return out


def run_install_verify(project_dir: str) -> List[Dict]:
    """7.5–7.7: install / uninstall / upgrade verification when scripts exist."""
    scripts = _scripts(project_dir)
    runner = "npm" if _which("npm") else ("pnpm" if _which("pnpm") else None)
    out: List[Dict] = []
    if not runner:
        return out
    for group in (("test:install", "install:test"), ("test:uninstall",), ("test:upgrade",)):
        for s in group:
            if s in scripts:
                out.append(_run([runner, "run", s], project_dir, timeout=900))
                break
    return out


def run_packaging(project_dir: str) -> List[Dict]:
    out = []
    scripts = _scripts(project_dir)
    runner = "npm" if _which("npm") else ("pnpm" if _which("pnpm") else None)
    if runner:
        if "build" in scripts:
            out.append(_run([runner, "run", "build"], project_dir))
        if "pack" in scripts:
            out.append(_run([runner, "run", "pack"], project_dir))
    if os.path.exists(os.path.join(project_dir, "pyproject.toml")) and _which("python"):
        out.append(_run(["python", "-m", "build"], project_dir, timeout=600))
    if _which("docker") and any(os.path.exists(os.path.join(project_dir, f))
                                for f in ("Dockerfile", "docker/Dockerfile")):
        out.append(_run(["docker", "build", "-t", "pipeline-artifact", "."],
                        project_dir, timeout=1200))
    out += run_bom(project_dir)
    out += run_installers(project_dir)        # 7.1 multi-format installers (when tooling present)
    out += package_contents(project_dir)      # 7.2 LICENSE/NOTICE/README/docs in package
    out += write_footprint(project_dir)       # 7.4 footprint doc
    out += run_install_verify(project_dir)    # 7.5–7.7 install/uninstall/upgrade
    return out


def run_smoke(project_dir: str) -> List[Dict]:
    """Post-build/deploy smoke suite when one is defined (8.3/8.4, best-effort)."""
    scripts = _scripts(project_dir)
    runner = "npm" if _which("npm") else ("pnpm" if _which("pnpm") else None)
    out = []
    if runner:
        for s in ("test:smoke", "smoke", "test:sanity", "test:health"):
            if s in scripts:
                out.append(_run([runner, "run", s], project_dir, timeout=600))
                break
    return out


def run_for_mode(project_dir: str, mode: str, categories: List[str]) -> List[Dict]:
    if mode == "nfr":
        return run_security(project_dir) + run_gates(project_dir, categories)
    if mode == "packaging":
        return run_packaging(project_dir) + run_smoke(project_dir)
    return []

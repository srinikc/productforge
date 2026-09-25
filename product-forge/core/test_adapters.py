"""
Test adapters (tech-stack agnostic).

A TestAdapter knows how to detect a stack, produce the test command, and (optionally)
how tests are organized. The pipeline selects an adapter from the agreed tech stack
(tech-stack.json) or by detecting repo files, so tests work for ANY stack. Unknown
stacks fall back to a configurable `command` adapter (or research + LLM-generated tests).
"""
import os
from typing import Dict, List, Optional


def _has(d: str, *names: str) -> bool:
    return any(os.path.exists(os.path.join(d, n)) for n in names)


class TestAdapter:
    name = "none"
    languages: List[str] = []

    def detect(self, project_dir: str, tech_stack: Dict) -> bool:
        return False

    def command(self, project_dir: str, category: Optional[str] = None) -> List[str]:
        return []


class PythonAdapter(TestAdapter):
    name = "python"; languages = ["python"]

    def detect(self, project_dir, tech_stack):
        return _has(project_dir, "pyproject.toml", "requirements.txt", "setup.py", "tests", "test")

    def command(self, project_dir, category=None):
        args = ["python", "-m", "pytest", "-q"]
        if category:
            for cand in (os.path.join("tests", category), os.path.join("test", category), category):
                if os.path.isdir(os.path.join(project_dir, cand)):
                    args.append(cand); break
        return args


class NodeAdapter(TestAdapter):
    name = "node"; languages = ["javascript", "typescript", "node"]

    def _scripts(self, project_dir):
        import json
        p = os.path.join(project_dir, "package.json")
        try:
            return (json.load(open(p, encoding="utf-8")) or {}).get("scripts", {}) or {}
        except Exception:
            return {}

    def detect(self, project_dir, tech_stack):
        return os.path.exists(os.path.join(project_dir, "package.json"))

    def command(self, project_dir, category=None):
        if _has(project_dir, "playwright.config.ts", "playwright.config.js", "playwright.config.mjs"):
            return ["npx", "playwright", "test"]
        if "test" in self._scripts(project_dir):
            return ["npm", "test", "--silent"]
        if _has(project_dir, "vitest.config.ts", "vitest.config.js"):
            return ["npx", "vitest", "run"]
        return ["npx", "jest", "--ci"]


class GoAdapter(TestAdapter):
    name = "go"; languages = ["go"]

    def detect(self, project_dir, tech_stack):
        return os.path.exists(os.path.join(project_dir, "go.mod"))

    def command(self, project_dir, category=None):
        return ["go", "test", "./..."]


class RustAdapter(TestAdapter):
    name = "rust"; languages = ["rust"]

    def detect(self, project_dir, tech_stack):
        return os.path.exists(os.path.join(project_dir, "Cargo.toml"))

    def command(self, project_dir, category=None):
        return ["cargo", "test"]


class JavaAdapter(TestAdapter):
    name = "java"; languages = ["java", "kotlin"]

    def detect(self, project_dir, tech_stack):
        return _has(project_dir, "pom.xml", "build.gradle", "build.gradle.kts", "gradlew")

    def command(self, project_dir, category=None):
        if os.path.exists(os.path.join(project_dir, "pom.xml")) and _which("mvn"):
            return ["mvn", "-q", "test"]
        if os.path.exists(os.path.join(project_dir, "gradlew")):
            return [os.path.join(".", "gradlew"), "test"]
        return ["gradle", "test"]


class DotNetAdapter(TestAdapter):
    name = "dotnet"; languages = ["csharp", "fsharp", "dotnet"]

    def detect(self, project_dir, tech_stack):
        return any(f.endswith((".csproj", ".fsproj", ".sln")) for f in _listdir(project_dir))

    def command(self, project_dir, category=None):
        return ["dotnet", "test"]


class PhpAdapter(TestAdapter):
    name = "php"; languages = ["php"]

    def detect(self, project_dir, tech_stack):
        return os.path.exists(os.path.join(project_dir, "composer.json"))

    def command(self, project_dir, category=None):
        return ["vendor/bin/phpunit"]


class RubyAdapter(TestAdapter):
    name = "ruby"; languages = ["ruby"]

    def detect(self, project_dir, tech_stack):
        return os.path.exists(os.path.join(project_dir, "Gemfile"))

    def command(self, project_dir, category=None):
        return ["bundle", "exec", "rspec"]


class FlutterAdapter(TestAdapter):
    name = "flutter"; languages = ["dart", "flutter"]

    def detect(self, project_dir, tech_stack):
        return os.path.exists(os.path.join(project_dir, "pubspec.yaml"))

    def command(self, project_dir, category=None):
        return ["flutter", "test"]


class DesktopAdapter(TestAdapter):
    """Desktop apps: Electron / Tauri via Playwright; native via config command."""
    name = "desktop"; languages = ["electron", "tauri", "desktop"]

    def _is_desktop(self, project_dir):
        if _has(project_dir, "tauri.conf.json", "src-tauri/tauri.conf.json",
                "wdio.conf.js", "wdio.conf.ts", "wdio.conf.mjs"):
            return True
        p = os.path.join(project_dir, "package.json")
        try:
            import json
            deps = {**((json.load(open(p, encoding="utf-8")) or {}).get("dependencies") or {}),
                    **((json.load(open(p, encoding="utf-8")) or {}).get("devDependencies") or {})}
            return any(k in deps for k in ("electron", "@tauri-apps/api", "@tauri-apps/cli",
                                           "@wdio/cli", "webdriverio"))
        except Exception:
            return False

    def detect(self, project_dir, tech_stack):
        return self._is_desktop(project_dir)

    def command(self, project_dir, category=None):
        if _has(project_dir, "wdio.conf.js", "wdio.conf.ts", "wdio.conf.mjs"):
            rel = next(n for n in ("wdio.conf.ts", "wdio.conf.js", "wdio.conf.mjs")
                       if os.path.exists(os.path.join(project_dir, n)))
            return ["npx", "wdio", "run", rel]
        if _has(project_dir, "playwright.config.ts", "playwright.config.js",
                "playwright.config.mjs"):
            return ["npx", "playwright", "test"]
        scripts = {}
        try:
            import json
            scripts = (json.load(open(os.path.join(project_dir, "package.json"), encoding="utf-8")) or {}).get("scripts", {})
        except Exception:
            pass
        if "test:e2e" in scripts:
            return ["npm", "run", "test:e2e"]
        if "test" in scripts:
            return ["npm", "test", "--silent"]
        return []


class CommandAdapter(TestAdapter):
    """Universal fallback: explicit `test.command` from project.json (any stack/tool)."""
    name = "command"

    def __init__(self, command_cfg=None):
        if isinstance(command_cfg, str):
            command_cfg = command_cfg.split()
        self._cfg = command_cfg or []

    def detect(self, project_dir, tech_stack):
        return bool(self._cfg)

    def command(self, project_dir, category=None):
        return list(self._cfg)


def _which(exe):
    import shutil
    return shutil.which(exe) is not None


def _listdir(d):
    try:
        return os.listdir(d)
    except Exception:
        return []


_ADAPTERS: List[TestAdapter] = [
    DesktopAdapter(), PythonAdapter(), NodeAdapter(), GoAdapter(), RustAdapter(),
    JavaAdapter(), DotNetAdapter(), PhpAdapter(), RubyAdapter(), FlutterAdapter(),
]


def select_adapter(project_dir: str, tech_stack: Optional[Dict] = None,
                   command_cfg: Optional[List[str]] = None) -> TestAdapter:
    """Pick an adapter by stack hints, then by file detection, then command fallback."""
    chosen = (tech_stack or {}).get("chosen") or {}
    langs = [str(x).lower() for x in (chosen.get("languages") or [])]
    fw = [str(x).lower() for x in (chosen.get("frameworks") or [])]
    for ad in _ADAPTERS:
        if any(l in langs for l in ad.languages) and ad.detect(project_dir, chosen):
            return ad
    for ad in _ADAPTERS:
        if ad.detect(project_dir, chosen):
            return ad
    return CommandAdapter(command_cfg)


def run_tests(project_dir: str, tech_stack: Optional[Dict] = None,
              category: Optional[str] = None, command_cfg: Optional[List[str]] = None,
              timeout: int = 900) -> Dict:
    """Detect stack, run its test command, return {adapter, cmd, ok, tail}."""
    ad = select_adapter(project_dir, tech_stack, command_cfg)
    cmd = ad.command(project_dir, category)
    if not cmd:
        return {"adapter": ad.name, "cmd": [], "ok": None, "tail": "no test command for stack"}
    import subprocess
    try:
        r = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, timeout=timeout)
        tail = ((r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else ""))[-4000:]
        return {"adapter": ad.name, "cmd": " ".join(cmd), "ok": r.returncode == 0, "tail": tail}
    except FileNotFoundError:
        return {"adapter": ad.name, "cmd": " ".join(cmd), "ok": False, "tail": "runner not installed"}
    except subprocess.TimeoutExpired:
        return {"adapter": ad.name, "cmd": " ".join(cmd), "ok": False, "tail": "timeout"}
    except Exception as e:
        return {"adapter": ad.name, "cmd": " ".join(cmd), "ok": False, "tail": str(e)}

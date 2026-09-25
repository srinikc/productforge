"""
Test Framework integration (wires the external test-framework into the pipeline).

Loads the framework's modules by file path (they are stdlib-only, so this avoids
`core` package collisions), registers the project, runs a test cycle, records
results, logs defects, and writes the framework's cycle/report/defect/traceability
artifacts so the test dashboard can consume them.

Everything is guarded — if the framework or tools are unavailable it degrades.
"""
import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).resolve().parent.parent
_TF = _REPO / "test-framework"
_mods: Dict[str, Any] = {}


def _load(name: str, rel: str):
    if name in _mods:
        return _mods[name]
    spec = importlib.util.spec_from_file_location(f"tf_{name}", str(_TF / rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    _mods[name] = mod
    return mod


def available() -> bool:
    return (_TF / "core" / "runner.py").exists()


def _has(d: str, *names: str) -> bool:
    return any(os.path.exists(os.path.join(d, n)) for n in names)


def _tech_stack(project_dir: str) -> Dict:
    import json
    try:
        p = os.path.join(project_dir, "docs", "tech-stack.json")
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8")) or {}
    except Exception:
        pass
    return {}


def _test_command(project_dir: str, products_dir: str = "products") -> str:
    """Stack-agnostic test command via the adapter registry."""
    try:
        from core.test_adapters import select_adapter
        cfg = None
        try:
            import json
            pj = os.path.join(project_dir, "project.json")
            if os.path.exists(pj):
                t = (json.load(open(pj, encoding="utf-8")) or {}).get("test") or {}
                cfg = t.get("command")
                if isinstance(cfg, str):
                    cfg = cfg.split()
        except Exception:
            cfg = None
        ad = select_adapter(project_dir, _tech_stack(project_dir), cfg)
        cmd = ad.command(project_dir)
        if cmd:
            return " ".join(cmd)
    except Exception:
        pass
    return "python -m pytest -q"


def _needs_app(project_dir: str, categories: List[str]) -> bool:
    """UI/e2e/desktop suites need the app running (brought up via a deploy provider)."""
    cats = {str(c).lower() for c in (categories or [])}
    if cats & {"e2e", "visual", "accessibility", "desktop", "ui"}:
        return True
    if _has(project_dir, "playwright.config.ts", "playwright.config.js", "playwright.config.mjs"):
        return True
    try:
        from core.test_adapters import select_adapter
        return select_adapter(project_dir, _tech_stack(project_dir)).name == "desktop"
    except Exception:
        return False


def _ensure_playwright_browsers(project_dir: str) -> Optional[Dict]:
    """Best-effort bootstrap of Playwright browsers so UI tests can actually run."""
    if not _has(project_dir, "playwright.config.ts", "playwright.config.js", "playwright.config.mjs"):
        return None
    import shutil
    import subprocess
    if not (shutil.which("npx") or shutil.which("npx.cmd")):
        return {"ran": False, "reason": "npx not available"}
    try:
        r = subprocess.run(["npx", "playwright", "install"], cwd=project_dir,
                           capture_output=True, text=True, timeout=900)
        tail = ((r.stdout or "") + (r.stderr or ""))[-500:]
        return {"ran": True, "ok": r.returncode == 0, "tail": tail}
    except Exception as e:
        return {"ran": False, "reason": str(e)}


def _mobile_cfg(project_dir: str, platform_name: str) -> Dict:
    """Read mobile app id / artifact path from project.json (mobile.ios|android)."""
    try:
        import json
        pj = os.path.join(project_dir, "project.json")
        if not os.path.exists(pj):
            return {}
        mob = (json.load(open(pj, encoding="utf-8")) or {}).get("mobile") or {}
        key = "ios" if platform_name.lower() == "ios" else "android"
        cfg = mob.get(key) or {}
        if platform_name.lower() == "ios":
            if "app_path" not in cfg and cfg.get("build"):
                cfg["app_path"] = cfg["build"]
        else:
            if "apk_path" not in cfg and cfg.get("build"):
                cfg["apk_path"] = cfg["build"]
        return cfg
    except Exception:
        return {}


def register_project(project: str, products_dir: str = "products",
                     features: Optional[List[Dict]] = None,
                     deployment: Optional[Dict] = None,
                     categories: Optional[List[str]] = None,
                     project_dir: Optional[str] = None) -> str:
    """Add/update this project in test-framework/config/projects.yaml."""
    import yaml
    pdir = project_dir or os.path.join(products_dir, project)
    cmd = _test_command(pdir, products_dir)
    cfg_path = _TF / "config" / "projects.yaml"
    data = {"projects": {}}
    if cfg_path.exists():
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {"projects": {}}
        except Exception:
            data = {"projects": {}}
    data.setdefault("projects", {})
    entry = {
        "name": project,
        "type": "product",
        "domain": "general",
        "path": f"../products/{project}",
        "apps": {"app": {"path": ".", "type": "python", "test_command": cmd}},
        "deployment": deployment or {"method": "local"},
        "test_categories": {c: True for c in (categories or ["unit", "api", "integration", "e2e"])},
        "features": features or [],
    }
    data["projects"][project] = entry
    try:
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    except Exception as e:
        print(f"[TestFramework] could not write projects.yaml: {e}")
    return str(cfg_path)


def _test_type(cat: str):
    try:
        TestType = _load("test_cycle", "core/test_cycle.py").TestType
        return getattr(TestType, str(cat).upper(), list(TestType)[0])
    except Exception:
        return None


def _run_external_mobile(cmd, project_dir: str, platform_name: str) -> Dict:
    """Run an external/cloud mobile runner (Appium/BrowserStack/Firebase/Maestro)."""
    import subprocess
    if isinstance(cmd, str):
        cmd = cmd.split()
    cmd = [str(c).replace("{platform}", platform_name.lower()) for c in cmd]
    try:
        r = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, timeout=1800)
        return {"platform": platform_name, "external": True, "cmd": " ".join(cmd),
                "passed": r.returncode == 0,
                "tail": ((r.stdout or "") + (r.stderr or ""))[-800:]}
    except Exception as e:
        return {"platform": platform_name, "external": True, "passed": None, "error": str(e)}


def _per_category_enabled(project_dir: str) -> bool:
    """Run extra non-adapter categories (playwright/bdd/nfr). Default ON; opt out."""
    env = os.environ.get("PIPELINE_PER_CATEGORY")
    if env == "0":
        return False
    if env == "1":
        return True
    try:
        import json
        pj = os.path.join(project_dir, "project.json")
        if os.path.exists(pj):
            v = ((json.load(open(pj, encoding="utf-8")) or {}).get("test") or {}).get("per_category")
            if v is not None:
                return bool(v)
    except Exception:
        pass
    return True


def _run_plan_item(item: Dict, project_dir: str, tech_stack: Optional[Dict] = None) -> Optional[Dict]:
    """Run one non-adapter category (playwright/bdd/nfr/framework) and return a summary."""
    import subprocess

    def _run(cmd, timeout=900):
        try:
            r = subprocess.run(cmd, cwd=project_dir, capture_output=True, text=True, timeout=timeout)
            tail = ((r.stdout or "") + (("\n[stderr]\n" + r.stderr) if r.stderr else ""))[-1500:]
            return {"ok": r.returncode == 0, "tail": tail}
        except FileNotFoundError:
            return {"ok": None, "tail": "runner not installed"}
        except Exception as e:
            return {"ok": False, "tail": str(e)}

    cat, runner = item["category"], item["runner"]
    try:
        if runner == "playwright_bdd":
            _run(item.get("pre") or [])
            r = _run(item.get("cmd") or ["npx", "playwright", "test"])
        elif runner == "playwright":
            r = _run(item.get("cmd") or ["npx", "playwright", "test"])
        elif runner == "nfr":
            from core import nfr_runner
            if cat == "security":
                steps = nfr_runner.run_security(project_dir)
            elif cat in ("install", "packaging"):
                steps = nfr_runner.run_packaging(project_dir)
            else:
                steps = nfr_runner.run_gates(project_dir, [cat])
            checkable = [s for s in steps if s.get("ok") is not None]
            ok = all(s["ok"] for s in checkable) if checkable else None
            r = {"ok": ok, "tail": str(steps)[:800]}
        else:
            return None
        return {"category": cat, "runner": runner, "ok": r.get("ok"), "tail": r.get("tail", "")}
    except Exception as e:
        return {"category": cat, "runner": runner, "ok": False, "tail": str(e)}


def _extra_plan_items(plan: List[Dict], project_dir: str, mode: str) -> List[Dict]:
    """Non-adapter categories not covered by the primary suite (avoid double-run)."""
    out = []
    for it in plan:
        runner, cat = it["runner"], it["category"]
        if runner in ("playwright", "playwright_bdd"):
            if it.get("exists") or _has(project_dir, "playwright.config.ts",
                                        "playwright.config.js", "playwright.config.mjs"):
                out.append(it)
        elif runner == "nfr":
            if cat in ("smoke", "sanity") or mode in ("nfr", "full") \
                    or os.environ.get("PIPELINE_RUN_NFR", "0") == "1":
                out.append(it)
    return out


def run_cycle(project: str, project_dir: str, stage_id: str,
              mode: Optional[str] = None, features: Optional[List[Dict]] = None,
              products_dir: str = "products") -> Optional[Dict]:
    """Register → run → record → log defects → complete a test cycle."""
    if not available():
        return None
    try:
        from core.test_framework_bridge import categories_for_mode, mode_for_stage
        mode = mode or mode_for_stage(stage_id)
        categories = categories_for_mode(mode)
    except Exception:
        categories = ["unit", "api", "integration", "e2e"]

    try:
        register_project(project, products_dir, features=features,
                         categories=categories, project_dir=project_dir)

        # QA owns suite/cycle definitions for the product.
        try:
            from core.qa_cycles import ensure_suites
            ensure_suites(project, project_dir, _tech_stack(project_dir))
        except Exception as e:
            print(f"[QACycles] {e}")

        # Build gate: tests run against a versioned build (version + build number).
        build: Dict = {}
        try:
            from core.build_manager import latest_build, create_build
            build = latest_build(project_dir) or {}
            if not build and os.environ.get("PIPELINE_AUTO_BUILD", "1") != "0":
                build = create_build(project_dir, project, trigger=f"test-cycle:{stage_id}")
        except Exception as e:
            print(f"[Build] {e}")

        # QA per-category execution plan (what to run, with which runner).
        category_plan: List[Dict] = []
        try:
            from core.test_matrix import plan as matrix_plan
            category_plan = matrix_plan(project_dir, categories, _tech_stack(project_dir))
        except Exception as e:
            print(f"[TestMatrix] {e}")

        runner = _load("runner", "core/runner.py").TestRunner(
            {"base_path": str(_REPO / products_dir), "execution": {"default_timeout": 600}})
        pcfg = {"apps": {"app": {"path": ".", "type": "python",
                                 "test_command": _test_command(project_dir, products_dir)}}}

        # App lifecycle around UI/e2e/desktop tests: bring the app up, run, tear down.
        lifecycle: Dict = {}
        needs_app = _needs_app(project_dir, categories)
        if needs_app:
            try:
                from core.deploy_providers import run_deploy_up
                up = run_deploy_up(project_dir)
                lifecycle["up"] = {k: up.get(k) for k in ("ran", "provider", "passed")}
                cfg = up.get("cfg") or {}
                url = cfg.get("url") or cfg.get("base_url") or cfg.get("health")
                if url:
                    os.environ["BASE_URL"] = str(url)
                    os.environ["DEPLOY_URL"] = str(url)
                    lifecycle["base_url"] = str(url)
            except Exception as e:
                lifecycle["up"] = {"error": str(e)}
            try:
                browsers = _ensure_playwright_browsers(project_dir)
                if browsers:
                    lifecycle["browsers"] = browsers
            except Exception as e:
                lifecycle["browsers"] = {"error": str(e)}
        try:
            res = runner.run_suite(project, mode or "feature", pcfg)
        finally:
            if needs_app:
                try:
                    from core.deploy_providers import run_deploy_down
                    down = run_deploy_down(project_dir)
                    lifecycle["down"] = {k: down.get(k) for k in ("ran", "provider", "passed")}
                except Exception as e:
                    lifecycle["down"] = {"error": str(e)}

        # Record metrics + traceability via the framework reporter.
        try:
            rep = _load("reporter", "core/reporter.py").TestReporter(project)
            rep.record_run(res)
        except Exception as e:
            print(f"[TestFramework] reporter: {e}")

        # Log defects for failures.
        defects = 0
        try:
            dt_mod = _load("defect_tracker", "core/defect_tracker.py")
            dt = dt_mod.DefectTracker(project)
            sev = getattr(dt_mod.Severity, "HIGH", list(dt_mod.Severity)[0])
            for t in getattr(res, "tests", []) or []:
                if getattr(t, "status", "") in ("failed", "error"):
                    dt.log_defect(
                        title=f"{getattr(t,'name',getattr(t,'test_id','test'))} failed",
                        description=(getattr(t, "message", "") or "")[:500],
                        severity=sev,
                        test_id=getattr(t, "test_id", ""),
                        test_name=getattr(t, "name", ""),
                        suite_name=getattr(res, "suite_name", mode or ""),
                        stack_trace=getattr(t, "traceback", None),
                    )
                    defects += 1
        except Exception as e:
            print(f"[TestFramework] defects: {e}")

        # Root-cause analysis (RCCA): prevention feedback for future stages.
        rcca: List[Dict] = []
        try:
            from core.defect_loop import analyze_open
            rcca = analyze_open(project)
        except Exception as e:
            print(f"[TestFramework] rcca: {e}")

        # Loop back-half: close defects whose tests now pass.
        reconciled: Dict = {"verified": 0, "closed": 0}
        try:
            from core.defect_loop import reconcile
            passed_tests = [t for t in (getattr(res, "tests", []) or [])
                            if getattr(t, "status", "") in ("passed", "pass")]
            all_passed = (getattr(res, "failed", 0) == 0 and getattr(res, "total", 0) > 0)
            reconciled = reconcile(project, passed_tests=passed_tests, all_passed=all_passed)
            if reconciled.get("closed"):
                print(f"  [DEFECTS] closed {reconciled['closed']} defect(s) now passing")
        except Exception as e:
            print(f"[TestFramework] reconcile: {e}")

        # AI trend intelligence (evidence-based): clustering/aging/regression.
        insights: Dict = {}
        try:
            from core.qa_intelligence import analyze as analyze_insights
            insights = analyze_insights(project, project_dir)
            if (insights.get("summary") or {}).get("total"):
                print(f"  [INSIGHTS] {insights['summary']['total']} insight(s) "
                      f"(high={insights['summary'].get('high',0)})")
        except Exception as e:
            print(f"[QAIntelligence] {e}")

        # Cycle bookkeeping.
        cycle_id = ""
        mgr = None
        try:
            cyc_mod = _load("test_cycle", "core/test_cycle.py")
            mgr = cyc_mod.TestCycleManager(project_dir)
            cycle = mgr.start_cycle(project, phase=stage_id, stage=stage_id,
                                    build_version=build.get("build_id", ""))
            cycle_id = cycle.cycle_id
            mgr.add_test_run(
                cycle_id, _test_type("unit"), "pytest",
                tests_run=getattr(res, "total", 0),
                tests_passed=getattr(res, "passed", 0),
                tests_failed=getattr(res, "failed", 0),
                tests_skipped=getattr(res, "skipped", 0),
                duration_seconds=getattr(res, "duration", 0),
                status=getattr(res, "status", "completed"),
                details=[f"{c}" for c in categories],
            )
            mgr.complete_cycle(cycle_id, notes=f"stage={stage_id} mode={mode}")
        except Exception as e:
            print(f"[TestFramework] cycle: {e}")

        # App boot/import smoke: catches "app fails to start" (shallow tests miss it).
        boot: Dict = {}
        try:
            from core.app_smoke import boot_check
            boot = boot_check(project_dir)
            if boot.get("ok") is False:
                print(f"  [BOOT] app failed to import: {boot.get('entrypoint')} "
                      f"-> {str(boot.get('error',''))[:160]}")
                try:
                    dt = _load("defect_tracker", "core/defect_tracker.py")
                    tr = dt.DefectTracker(project)
                    sev = getattr(dt.Severity, "HIGH", list(dt.Severity)[0])
                    tr.log_defect(title=f"App boot failed: {boot.get('entrypoint')}",
                                  description=str(boot.get("error", ""))[:500],
                                  severity=sev, test_id="BOOT-1",
                                  test_name="app_boot", suite_name="smoke")
                except Exception:
                    pass
        except Exception as e:
            boot = {"ok": None, "error": str(e)}

        # Extra per-category runs (playwright/bdd/nfr) not covered by the primary suite.
        category_runs: List[Dict] = []
        try:
            if _per_category_enabled(project_dir) and category_plan and boot.get("ok") is not False:
                for item in _extra_plan_items(category_plan, project_dir, mode or ""):
                    r = _run_plan_item(item, project_dir, _tech_stack(project_dir))
                    if not r:
                        continue
                    category_runs.append(r)
                    print(f"  [CATEGORY] {r['category']} ({r['runner']}): ok={r['ok']}")
                    try:
                        if cycle_id and mgr is not None:
                            mgr.add_test_run(cycle_id, _test_type(r["category"]), r["runner"],
                                             tests_run=1 if r["ok"] is not None else 0,
                                             tests_passed=1 if r["ok"] else 0,
                                             tests_failed=0 if r["ok"] else 1,
                                             status="passed" if r["ok"] else "failed",
                                             details=[r["category"]])
                    except Exception:
                        pass
        except Exception as e:
            print(f"[TestFramework] category runs: {e}")

        # Mobile iOS/Android via simulators/emulators, when the product is mobile.
        mobile_results: List[Dict] = []
        try:
            chosen = _tech_stack(project_dir).get("chosen") or {}
            kind = str(chosen.get("kind") or "").lower()
            platforms = [str(p).lower() for p in (chosen.get("platforms") or [])]
            want_mobile = (kind == "mobile" or any("mobile" in str(c) for c in categories)
                           or any(("ios" in p or "android" in p) for p in platforms)
                           or bool(_mobile_cfg(project_dir, "IOS") or _mobile_cfg(project_dir, "ANDROID")))
            if want_mobile:
                from core.mobile_tester import MobileTester, Platform, TestFramework
                mt = MobileTester(project_dir)
                for plat in (Platform.IOS, Platform.ANDROID):
                    try:
                        st = mt.check_platform_availability(plat)
                        is_avail = getattr(st, "available", getattr(st, "booted", False))
                        if not is_avail:
                            print(f"  [MOBILE] {plat.name} simulator/emulator unavailable; skipped")
                            continue
                        # Bring up the simulator/emulator and install/launch the app (if configured).
                        try:
                            if mt.boot_simulator(plat):
                                print(f"  [MOBILE] {plat.name} booted")
                        except Exception as e:
                            print(f"  [MOBILE] boot {plat.name}: {e}")
                        cfg = _mobile_cfg(project_dir, plat.name)
                        app_path = cfg.get("app_path") or cfg.get("apk_path")
                        app_id = cfg.get("bundle_id") or cfg.get("package")
                        try:
                            if app_path:
                                mt.install_app(plat, app_path)
                        except Exception as e:
                            print(f"  [MOBILE] install {plat.name}: {e}")
                        try:
                            if app_id:
                                mt.launch_app(plat, app_id)
                        except Exception as e:
                            print(f"  [MOBILE] launch {plat.name}: {e}")
                        # External runner (device farm / Appium / Maestro) takes precedence.
                        ext = cfg.get("test_command") or cfg.get("farm_command")
                        if ext:
                            mobile_results.append(_run_external_mobile(ext, project_dir, plat.name))
                        else:
                            mr = mt.run_tests(plat, TestFramework.VITEST_MOBILE)
                            mt.save_result(mr, phase=stage_id)
                            mobile_results.append({"platform": plat.name,
                                                   "passed": getattr(mr, "passed", None),
                                                   "error": getattr(mr, "error", "")})
                        print(f"  [MOBILE] {plat.name}: {mobile_results[-1].get('passed')}")
                    except Exception as e:
                        print(f"  [MOBILE] {plat.name}: {e}")
        except Exception as e:
            print(f"[Mobile] {e}")

        return {
            "cycle_id": cycle_id,
            "mode": mode,
            "categories": categories,
            "total": getattr(res, "total", 0),
            "passed": getattr(res, "passed", 0),
            "failed": getattr(res, "failed", 0),
            "skipped": getattr(res, "skipped", 0),
            "defects": defects,
            "rcca": rcca,
            "boot": boot,
            "reconciled": reconciled,
            "insights": insights.get("summary", {}) if insights else {},
            "build": {k: build.get(k) for k in ("build_id", "version", "build_number", "trigger")} if build else {},
            "category_plan": category_plan,
            "category_runs": category_runs,
            "mobile": mobile_results,
            "app_lifecycle": lifecycle,
            "status": ("failed" if boot.get("ok") is False
                       else getattr(res, "status", "unknown")),
        }
    except Exception as e:
        print(f"[TestFramework] run_cycle failed: {e}")
        return None

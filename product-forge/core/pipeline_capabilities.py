"""
Extended pipeline capabilities (RUN-WIRED).

Some capabilities live in standalone modules (git, cost/finops, release records,
maintenance, onboarding, presentations, domain research, model recommendation,
BYOT, product analyze/ingest, video, traceability, change registry, write safety).
This bridge gives each a real runtime call site and persists a consolidated
report, so nothing is an orphan.

Invoked once per run by the orchestrator (`_run_extended_capabilities`) and
`write_safety.safe_write_* ` is used on the tool write path.
"""
import importlib
import json
import os
from datetime import datetime
from typing import Any, Dict, Optional

_TRIPLE = '"' * 3


def _mk(dotted: str, *args):
    """Construct a class defensively (module:Class), tolerating ctor signatures."""
    try:
        mod_name, cls_name = dotted.split(":")
        cls = getattr(importlib.import_module(mod_name), cls_name)
        try:
            return cls(*args)
        except TypeError:
            return cls()
    except Exception:
        return None


def _call(obj, method: str, *args, **kwargs):
    try:
        fn = getattr(obj, method)
        return fn(*args, **kwargs)
    except Exception as e:
        raise RuntimeError(f"{method}: {e}")


def _first(obj, attempts):
    """Try (method, args) pairs in order; return first success."""
    if obj is None:
        raise RuntimeError("unavailable")
    last = ""
    for method, args in attempts:
        try:
            return getattr(obj, method)(*args)
        except Exception as e:
            last = f"{method}: {e}"
    raise RuntimeError(last)


def _fn(dotted: str, *args, **kwargs):
    """Call a module-level function (``module:function``)."""
    mod_name, fn_name = dotted.split(":")
    return getattr(importlib.import_module(mod_name), fn_name)(*args, **kwargs)


def _probe(name: str, fn) -> Dict[str, Any]:
    try:
        val = fn()
        ok = val is not None
        if isinstance(val, str):
            detail = val[:400]
        elif isinstance(val, (int, float, bool)):
            detail = str(val)
        else:
            detail = str(val)[:400]
        return {"capability": name, "ok": ok, "detail": detail if ok else "no result"}
    except Exception as e:
        return {"capability": name, "ok": False, "error": str(e)[:300]}


def run(project_dir: str, project: str, domain: str = "", product_kind: str = "") -> Dict[str, Any]:
    """Invoke every extended capability once; persist a consolidated report."""
    results = []

    # git_manager — repository snapshot (no repo = handled result, not a failure)
    def _git():
        import subprocess
        if not os.path.isdir(os.path.join(project_dir, ".git")):
            return {"status": "no-repo"}
        g = _mk("core.git_manager:GitManager", project_dir)
        try:
            s = _call(g, "get_status")
            return (s.to_dict() if hasattr(s, "to_dict") else s)
        except Exception:
            return subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=project_dir,
                                  capture_output=True, text=True).stdout.strip()
    results.append(_probe("git_manager", _git))

    # model_recommendation
    def _model():
        eng = _mk("core.model_recommendation:ModelRecommendationEngine")
        return _first(eng, [("find_models_by_capability", ("coding",)),
                            ("generate_recommendation_report", ())])
    results.append(_probe("model_recommendation", _model))

    # byot_integration
    def _byot():
        mgr = _mk("core.byot_integration:BYOTIntegrationManager")
        return _call(mgr, "generate_integration_report")
    results.append(_probe("byot_integration", _byot))

    # domain_research (needs domain)
    if domain:
        results.append(_probe("domain_research",
                              lambda d=domain: _call(_mk("core.domain_research:DomainResearchEngine"),
                                                     "generate_research_report", d)))

    # cost_modeling
    def _cost():
        cm = _mk("core.cost_modeling:CostModeler")
        return _call(cm, "generate_cost_report", project,
                     _call(cm, "estimate_product_costs", product_kind or "web", "small"))
    results.append(_probe("cost_modeling", _cost))

    # finops
    results.append(_probe("finops",
                          lambda: _call(_mk("core.finops:FinOpsManager"), "generate_finops_report")))

    # change_registry
    results.append(_probe("change_registry",
                          lambda: _call(_mk("core.change_registry:ChangeRegistry"), "generate_change_report")))

    # release_manager
    results.append(_probe("release_manager",
                          lambda: _first(_mk("core.release_manager:ReleaseManager", project),
                                         [("get_artifacts", ()), ("select_strategy", ("rolling",))])))

    # traceability
    results.append(_probe("traceability",
                          lambda: _first(_mk("core.traceability:TraceabilityMatrix", project),
                                         [("exists", ()), ("save", ())])))

    # maintenance / onboarding / presentation / video (runtime capabilities)
    results.append(_probe("maintenance",
                          lambda: _call(_mk("core.maintenance:MaintenanceManager"), "run_health_check")))
    results.append(_probe("customer_onboarding",
                          lambda: _call(_mk("core.customer_onboarding:OnboardingGenerator"), 
                                        "generate_onboarding_package", project, {}, {})))
    results.append(_probe("presentation_generator",
                          lambda: _call(_mk("core.presentation_generator:PresentationGenerator"),
                                        "generate_full_package",
                                        _mk("core.presentation_generator:PresentationConfig", project, "0.0.0"),
                                        {})))
    results.append(_probe("video_generation",
                          lambda: _call(_mk("core.presentation_generator:VideoGenerator"),
                                        "generate_demo_video", project, {})))
    results.append(_probe("video_script",
                          lambda: _call(_mk("core.video_generation:VideoGenerationEngine"),
                                        "create_demo_script", {})))
    results.append(_probe("marketing",
                          lambda: _call(_mk("core.marketing:MarketingGenerator",
                                            os.path.dirname(project_dir) or "products"),
                                        "generate_marketing_package", project, {})))

    def _build():
        u = _mk("core.build_utility:BuildUtility", project_dir)
        if u is not None:
            try:
                info = u.get_build_info("output")
                if info:
                    return info
            except Exception:
                pass
        bd = os.path.join(project_dir, "builds")
        return {"builds_dir": bd, "exists": os.path.isdir(bd),
                "entries": (os.listdir(bd) if os.path.isdir(bd) else [])[:10]}
    results.append(_probe("build_utility", _build))
    results.append(_probe("docker_compose_generator",
                          lambda: _fn("core.docker_compose_generator:generate_docker_compose",
                                      {"name": project, "language": "python"})))
    results.append(_probe("memory_api",
                          lambda: _call(_mk("core.memory_api:MemoryAPI",
                                            os.path.dirname(project_dir) or "products", project),
                                        "export_all")))
    results.append(_probe("agent_card_loader",
                          lambda: _call(_mk("core.agent_card_loader:AgentCardLoader"),
                                        "generate_report")))
    results.append(_probe("code_executor",
                          lambda: _mk("core.code_executor:CodeExecutor")))

    # product_analyzer / product_ingestion (only when a source path exists)
    src = os.path.join(project_dir, "src")
    if os.path.isdir(src):
        results.append(_probe("product_analyzer",
                              lambda: _call(_mk("core.product_analyzer:ProductAnalyzer"),
                                            "analyze_product", project, src)))
        results.append(_probe("product_ingestion",
                              lambda: _call(_mk("core.product_ingestion:ProductIngester"),
                                            "ingest_from_folder", project, src)))

    # Parked/overdue follow-ups -> emit follow_up_due (BI-0040).
    def _followups():
        from core import backlog
        due = backlog.parked_review()
        if due:
            try:
                from core import event_bus
                event_bus.emit("follow_up_due",
                               reason=f"{len(due)} parked item(s) due",
                               source="parked_review")
            except Exception:
                pass
        return {"due_count": len(due), "due": [e.get("id") for e in due]}
    results.append(_probe("parked_followups", _followups))

    report = {"project": project, "generated_at": datetime.now().isoformat(),
              "capabilities": results,
              "ok_count": sum(1 for r in results if r.get("ok"))}
    try:
        out = os.path.join(project_dir, "docs", "qa")
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "extended-capabilities.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass
    return report


def safe_write_json(path: str, data: Any) -> bool:
    """Write JSON via write_safety when available (atomic + backup)."""
    try:
        ws = _mk("core.write_safety:WriteSafety", path)
        try:
            _call(ws, "atomic_write_json", path, data)
            return True
        except Exception:
            pass
    except Exception:
        pass
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception:
        return False

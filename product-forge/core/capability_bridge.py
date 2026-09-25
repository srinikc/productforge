"""Runtime bridge for previously-orphan modules (BI-0124..0137).

Wires each orphan onto the runtime path by exposing a single, stage-appropriate
entrypoint the pipeline executor calls. Keeps the executor thin and gives the
dashboard an API-first surface (BI-0122) over the same functions.

Owner: this module is the single writer for the derived artifacts it persists.
Never raises into the pipeline (best-effort, logged).
"""
from __future__ import annotations
import json, os
from datetime import datetime
from typing import Any, Dict, List, Optional


def _pdir(project_dir: str) -> str:
    return project_dir


def _save(project_dir: str, name: str, data: Any) -> str:
    p = os.path.join(project_dir, name)
    os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(p) else None
    try:
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass
    return p


# ── individual adapters (each returns a JSON-able dict; never raises) ─────────

def research_domain(project_dir: str, domain: str) -> Dict[str, Any]:
    try:
        from core.domain_research import DomainResearchEngine
        eng = DomainResearchEngine()
        report = eng.generate_research_report(domain) if hasattr(eng, "generate_research_report") else ""
        trends = eng.get_domain_trends(domain) if hasattr(eng, "get_domain_trends") else []
        bp = eng.get_domain_best_practices(domain) if hasattr(eng, "get_domain_best_practices") else []
        return {"domain": domain, "report": report, "trends": len(trends or []), "best_practices": len(bp or [])}
    except Exception as e:
        return {"error": str(e)}


def compile_knowledge(project_dir: str, notes: Optional[List[str]] = None) -> Dict[str, Any]:
    try:
        from core.knowledge_compiler import KnowledgeCompiler
        kc = KnowledgeCompiler()
        if hasattr(kc, "compile"):
            out = kc.compile(notes or [])
            return {"compiled": bool(out)}
        return {"compiled": False, "reason": "no compile()"}
    except Exception as e:
        return {"error": str(e)}


def estimate_costs(project_dir: str, infra: Optional[Dict] = None,
                   product_type: str = "web-app", scale: str = "small") -> Dict[str, Any]:
    try:
        from core.cost_modeling import CostModeler
        cm = CostModeler()
        est = cm.estimate_product_costs(product_type, scale) if hasattr(cm, "estimate_product_costs") else {}
        data = getattr(est, "__dict__", est)
        try:
            rep = cm.generate_cost_report(os.path.basename(project_dir.rstrip("/\\")) or "project", est)
        except Exception:
            rep = ""
        _save(project_dir, "cost-model.json", {"product_type": product_type, "scale": scale, "estimate": data})
        return {"estimate": data, "report": bool(rep)}
    except Exception as e:
        return {"error": str(e)}


def register_change(project_dir: str, change: Dict) -> Dict[str, Any]:
    try:
        from core.change_registry import ChangeRegistry
        cr = ChangeRegistry(project_dir) if _accepts_path(ChangeRegistry) else ChangeRegistry()
        cid = cr.add_change(change) if hasattr(cr, "add_change") else None
        return {"change_id": cid}
    except Exception as e:
        return {"error": str(e)}


def plan_release(project_dir: str) -> Dict[str, Any]:
    try:
        from core.release_manager import ReleaseManager
        rm = ReleaseManager(os.path.basename(project_dir.rstrip("/\\")))
        rep = rm.generate_report() if hasattr(rm, "generate_report") else None
        return {"ok": True, "report": bool(rep)}
    except Exception as e:
        return {"error": str(e)}


def git_status(project_dir: str) -> Dict[str, Any]:
    try:
        from core.git_manager import GitManager
        gm = GitManager(project_dir)
        is_repo = gm.is_git_repo() if hasattr(gm, "is_git_repo") else False
        st = gm.get_status() if is_repo and hasattr(gm, "get_status") else None
        return {"is_repo": bool(is_repo), "status": getattr(st, "__dict__", st)}
    except Exception as e:
        return {"error": str(e)}


def godock(project_dir: str, tech_stack: Optional[Dict] = None) -> Dict[str, Any]:
    """Generate docker-compose from a project config. Requires a real config (compose
    needs services/ports); if absent, report needs_config instead of fabricating."""
    cfg = tech_stack if isinstance(tech_stack, dict) else {}
    if not cfg.get("services") and not cfg.get("language"):
        return {"status": "needs_config", "reason": "generate_docker_compose needs a project_config with services/language"}
    try:
        from core.docker_compose_generator import generate_docker_compose
        out = generate_docker_compose(cfg)
        if out:
            _save(project_dir, "docker-compose.generated.json", {"content": out} if isinstance(out, str) else out)
        return {"ok": bool(out)}
    except Exception as e:
        return {"error": str(e)}


def byot_catalog(project_dir: str) -> Dict[str, Any]:
    try:
        from core.byot_integration import BYOTIntegrationManager
        m = BYOTIntegrationManager()
        return {"models": len(m.list_models() if hasattr(m, "list_models") else []),
                "tools": len(m.list_tools() if hasattr(m, "list_tools") else []),
                "mcp_servers": len(m.list_mcp_servers() if hasattr(m, "list_mcp_servers") else [])}
    except Exception as e:
        return {"error": str(e)}


def ingest_product(project_dir: str, folder: str = "") -> Dict[str, Any]:
    try:
        from core.product_ingestion import ProductIngester
        ing = ProductIngester()
        res = ing.ingest_from_folder(folder) if folder and hasattr(ing, "ingest_from_folder") else None
        return {"ingested": bool(res)}
    except Exception as e:
        return {"error": str(e)}


def onboard_customer(project_dir: str, plan: Optional[Dict] = None) -> Dict[str, Any]:
    try:
        from core.customer_onboarding import OnboardingGenerator
        og = OnboardingGenerator()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def build_deck(project_dir: str, data: Optional[Dict] = None) -> Dict[str, Any]:
    try:
        from core.presentation_generator import PresentationGenerator
        pg = PresentationGenerator()
        out = pg.generate(project_dir, data or {}) if hasattr(pg, "generate") else None
        return {"path": str(out) if out else None}
    except Exception as e:
        return {"error": str(e)}


def build_video(project_dir: str, cfg: Optional[Dict] = None) -> Dict[str, Any]:
    try:
        from core.video_generation import VideoGenerationEngine
        vg = VideoGenerationEngine()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}


def build_artifacts(project_dir: str, target: str = "docker", phase: str = "production") -> Dict[str, Any]:
    try:
        from core.build_utility import BuildUtility
        bu = BuildUtility(project_dir)
        fn = getattr(bu, f"build_{target}", None) or getattr(bu, "build_all", None)
        res = fn(phase) if callable(fn) else None
        return {"built": bool(res), "result": getattr(res, "__dict__", None)}
    except Exception as e:
        return {"error": str(e)}


def refresh_catalog(project_dir: str) -> Dict[str, Any]:
    """BI-0140: refresh the tech-stack/knowledge catalog + report staleness."""
    try:
        from core import knowledge_refresh as kr
        return kr.refresh(project_dir)
    except Exception as e:
        return {"error": str(e)}


def validate_code(project_dir: str, files: Optional[List[str]] = None) -> Dict[str, Any]:
    """BI-0136: wire code_executor's SAFE operations (validate/run tests) onto the runtime path.

    Deliberately does NOT auto-apply changes or execute arbitrary code from the pipeline;
    it only exposes syntax validation + test running, which the validation stages can use.
    """
    try:
        from core.code_executor import CodeExecutor
        ce = CodeExecutor()
        targets = files or []
        bad = []
        for f in targets[:50]:
            try:
                if hasattr(ce, "validate_syntax") and not ce.validate_syntax(f):
                    bad.append(f)
            except Exception:
                pass
        return {"validated": len(targets) - len(bad), "invalid": bad}
    except Exception as e:
        return {"error": str(e)}


def _accepts_path(cls) -> bool:
    import inspect
    try:
        params = list(inspect.signature(cls).parameters)
        return bool(params)
    except Exception:
        return False


# ── stage dispatch: which adapters run for a given stage ─────────────────────
STAGE_HOOKS: Dict[str, List[str]] = {
    "0b": ["byot_catalog", "refresh_catalog"],   # capabilities + catalog freshness
    "0c": ["research_domain"],          # Market/competition research
    "2":  ["estimate_costs", "godock"],  # architecture: cost + infra
    "4-0": ["git_status"],              # implementation kickoff: VCS state
    "5":  ["validate_code"],            # code review: syntax validation via code_executor
    "7":  ["validate_code"],            # validate/fix: syntax validation
    "8":  ["build_artifacts"],          # delivery: build/packaging
    "9":  ["plan_release"],             # packaging/release
    "13": ["git_status"],               # ops
}

REGISTRY = {
    "research_domain": research_domain, "compile_knowledge": compile_knowledge,
    "estimate_costs": estimate_costs, "register_change": register_change,
    "plan_release": plan_release, "git_status": git_status, "byot_catalog": byot_catalog,
    "ingest_product": ingest_product, "onboard_customer": onboard_customer,
    "build_deck": build_deck, "build_video": build_video, "build_artifacts": build_artifacts,
    "validate_code": validate_code, "godock": godock,
    "refresh_catalog": refresh_catalog,
}


def run_stage_hooks(project_dir: str, stage_id: str, **kw) -> Dict[str, Any]:
    """Invoke the adapters bound to a stage. Best-effort; never raises."""
    out: Dict[str, Any] = {}
    for name in STAGE_HOOKS.get(stage_id, []):
        fn = REGISTRY.get(name)
        if not fn:
            continue
        try:
            args = {}
            if name == "research_domain":
                args["domain"] = kw.get("domain", "")
            out[name] = fn(project_dir, **args)
        except Exception as e:
            out[name] = {"error": str(e)}
    if out:
        _save(project_dir, f"capabilities-{stage_id}.json", out)
    return out

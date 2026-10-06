"""Evidence-gated learning pipeline (BI-PF-0293).

Distils CANDIDATES from run outcomes (closed RCCAs, reviewer feedback, defect reconciles, media-QA
findings, quality/QIR deltas) and, only after approval, promotes them into the OWNER store via that
owner's API. Nothing is injected into a prompt here; static instructions are never rewritten.

Owns (single writer): ``data/learning-candidates.json``.
Applies into (via owner APIs): ``core.learnings`` · ``core.prompt_overlays`` · ``core.knowledge_registry``.

Evidence-gated: no evidence => no candidate. Scoped: project/area by default; global only by explicit
promotion. See docs/LEARNING-PIPELINE-DESIGN.md.
"""

import json
import os
from datetime import datetime

try:
    from core.paths import ROOT as _ROOT
except ImportError:  # script execution
    import sys as _sys
    _d = os.path.abspath(__file__)
    for _ in range(3):
        _d = os.path.dirname(_d)
        if os.path.isfile(os.path.join(_d, "core", "paths.py")):
            _sys.path.insert(0, _d)
            break
    from core.paths import ROOT as _ROOT

STORE = os.path.join(str(_ROOT), "data", "learning-candidates." + "json")
KINDS = ("learning", "overlay", "skill", "knowledge")


def _load() -> dict:
    try:
        with open(STORE, encoding="utf-8-sig") as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _save(data: dict) -> None:
    os.makedirs(os.path.dirname(STORE), exist_ok=True)
    tmp = STORE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, STORE)


def _norm_scope(project: str) -> str:
    return f"project:{project}" if project else "area:"


def list_candidates(status: str = "", scope: str = "") -> list[dict]:
    out = []
    for c in (_load().get("candidates") or {}).values():
        if status and c.get("status") != status:
            continue
        if scope and not str(c.get("scope", "")).startswith(scope):
            continue
        out.append(c)
    return sorted(out, key=lambda c: c.get("proposed_at", ""))


def get(cid: str) -> dict | None:
    return (_load().get("candidates") or {}).get(cid)


# ── evidence collection (all sources optional / guarded) ─────────────────────
def collect_evidence(project_dir: str, project: str = "") -> list[dict]:
    """Gather evidence items from existing streams. Returns [{source, ref, text, severity}]."""
    ev: list[dict] = []
    # closed RCCAs (issues)
    try:
        from core import issues as _iss
        sc = "project" if project else "product_forge"
        for it in (_iss.list_closed(sc, project or None) if hasattr(_iss, "list_closed") else []):
            rcca = it.get("rcca") or {}
            if rcca.get("generalized") or rcca.get("preventive"):
                ev.append({"source": "rcca", "ref": it.get("id"),
                           "text": rcca.get("preventive") or rcca.get("root_cause") or "",
                           "severity": str(it.get("priority") or "P2")})
    except Exception:
        pass
    # defect reconciles
    try:
        from core import defect_loop as _dl
        for d in (_dl.open_defects(project) if project else []) or []:
            ev.append({"source": "defect", "ref": d.get("defect_id"),
                       "text": d.get("rcca_recommendation") or d.get("title") or "",
                       "severity": str(d.get("severity") or "")})
    except Exception:
        pass
    # media QA findings (BI-0191)
    try:
        from core import media_qa as _mq
        r = _mq.validate_project(project_dir)
        for f in (r.get("findings") or []):
            ev.append({"source": "media_qa", "ref": f.get("asset_id"),
                       "text": f"{f.get('check')}: {f.get('detail')}", "severity": "P2"})
    except Exception:
        pass
    return ev


def _rule_from_evidence(item: dict) -> str:
    t = " ".join(str(item.get("text") or "").split())
    return t[:280]


def propose(project_dir: str, project: str = "", scope: str = "") -> list[dict]:
    """Collect evidence -> dedup -> write candidates. Fail-closed: no evidence => no candidate."""
    evidence = collect_evidence(project_dir, project)
    scope = scope or _norm_scope(project)
    data = _load()
    cands = data.get("candidates") or {}
    created: list[dict] = []
    # dedupe by similarity using learnings tokens (reuse)
    try:
        from core import learnings as _ln
        tok = _ln._tokens if hasattr(_ln, "_tokens") else None
        sim = _ln._sim if hasattr(_ln, "_sim") else None
        merge_at = getattr(_ln, "MERGE_AT", 0.6)
    except Exception:
        tok = sim = None
        merge_at = 0.6
    for e in evidence:
        rule = _rule_from_evidence(e)
        if not rule:
            continue
        # skip if a candidate already captures this rule
        dup = False
        if tok and sim:
            for c in cands.values():
                try:
                    if sim(tok(rule), tok(c.get("text", ""))) >= merge_at:
                        dup = True
                        break
                except Exception:
                    pass
        if dup:
            continue
        cid = f"LC-{len(cands) + 1:04d}"
        c = {"id": cid, "kind": "learning", "text": rule,
             "rationale": f"recurring signal from {e.get('source')}",
             "evidence": [{"source": e.get("source"), "ref": e.get("ref")}],
             "confidence": 0.5 + (0.2 if str(e.get("severity", "")).upper() in ("P0", "P1", "critical", "high") else 0.0),
             "scope": scope, "status": "proposed", "proposed_at": datetime.now().isoformat()}
        cands[cid] = c
        created.append(c)
    if created:
        data["candidates"] = cands
        _save(data)
    return created


def add_candidate(rule: str, scope: str = "", source_ref: str = "", kind: str = "learning",
                  rationale: str = "", confidence: float = 0.5) -> dict:
    """Add ONE evidence-gated candidate directly (e.g. from a PIDL correction). Idempotent by text.

    Reuses the same store/shape as ``propose``; promotion still goes through ``approve``/``reject``.
    Nothing is applied to an owner store here.
    """
    text = " ".join(str(rule or "").split())[:280]
    if not text:
        return {"ok": False, "error": "empty rule"}
    if kind not in KINDS:
        kind = "learning"
    data = _load()
    cands = data.get("candidates") or {}
    try:
        from core import learnings as _ln
        tok, sim = getattr(_ln, "_tokens", None), getattr(_ln, "_sim", None)
        merge_at = getattr(_ln, "MERGE_AT", 0.6)
        if tok and sim:
            for c in cands.values():
                if sim(tok(text), tok(c.get("text", ""))) >= merge_at:
                    return {"ok": True, "candidate": c, "existing": True}
    except Exception:
        pass
    cid = f"LC-{len(cands) + 1:04d}"
    c = {"id": cid, "kind": kind, "text": text,
         "rationale": rationale or "PIDL correction feedback",
         "evidence": ([{"source": "pidl", "ref": source_ref}] if source_ref else []),
         "confidence": float(confidence), "scope": scope or "area:", "status": "proposed",
         "proposed_at": datetime.now().isoformat()}
    cands[cid] = c
    data["candidates"] = cands
    _save(data)
    return {"ok": True, "candidate": c, "existing": False}


# ── approval + apply (into OWNER stores via their APIs) ──────────────────────
def _apply(c: dict) -> dict:
    kind = c.get("kind")
    text = c.get("text", "")
    scope = c.get("scope", "")
    area = scope.split(":", 1)[1] if scope.startswith("area:") else ""
    if kind == "learning":
        from core import learnings as _ln
        # need-based: a project-scope candidate is written to the project store
        proj = scope.split(":", 1)[1] if scope.startswith("project:") else ""
        return _ln.add(text, area=area, source_ref=c.get("id", ""), project=proj)
    if kind == "overlay":
        from core import prompt_overlays as _po
        proj = scope.split(":", 1)[1] if scope.startswith("project:") else ""
        pdir = os.path.join(str(_ROOT), "products", proj) if proj else str(_ROOT)
        return _po.set_overlay(pdir, "*", text, by="learning_synth", mode="append")
    if kind == "knowledge":
        from core import knowledge_registry as _kr
        layer = area or "shared"
        if not _live_layer(layer):
            return {"ok": False, "error": f"no live guideline dir for layer '{layer}'"}
        return _kr.add("guideline", name=c.get("id", ""), layers=[layer],
                       notes=text, added_by="learning_synth")
    if kind == "skill":
        from core import skills_registry as _sr
        try:
            sk = _sr.Skill(id=c.get("id", ""), name=c.get("id", ""), description=text[:400],
                           category="general", agent_types=[], tools=[], source="learning_synth")
            return _sr.SkillsRegistry().add_skill(sk)
        except Exception as e:
            return {"ok": False, "error": str(e)}
    return {"ok": False}


def _live_layer(layer: str) -> bool:
    """A registered knowledge layer must resolve to a live docs/guidelines/<layer>/*.md dir."""
    try:
        d = os.path.join(str(_ROOT), "docs", "guidelines", str(layer))
        return os.path.isdir(d) and any(f.endswith(".md") for f in os.listdir(d))
    except Exception:
        return False


def approve(cid: str, by: str = "operator") -> dict:
    data = _load()
    c = (data.get("candidates") or {}).get(cid)
    if not c:
        return {"ok": False, "error": "not_found"}
    applied = _apply(c)
    c["status"] = "approved"
    c["approved_by"] = by
    c["approved_at"] = datetime.now().isoformat()
    # an apply that returns {"ok": False, ...} is NOT applied (fail-closed)
    if isinstance(applied, dict):
        c["applied"] = bool(applied.get("ok", True))
        if not c["applied"]:
            c["apply_error"] = applied.get("error", "apply_failed")
    else:
        c["applied"] = bool(applied)
    data["candidates"][cid] = c
    _save(data)
    return {"ok": True, "candidate": c}


def reject(cid: str, by: str = "operator", reason: str = "") -> dict:
    data = _load()
    c = (data.get("candidates") or {}).get(cid)
    if not c:
        return {"ok": False, "error": "not_found"}
    c["status"] = "rejected"
    c["rejected_by"] = by
    c["reject_reason"] = reason
    c["at"] = datetime.now().isoformat()
    data["candidates"][cid] = c
    _save(data)
    return {"ok": True, "candidate": c}


def edit(cid: str, text: str = "", scope: str = "", by: str = "operator") -> dict:
    data = _load()
    c = (data.get("candidates") or {}).get(cid)
    if not c:
        return {"ok": False, "error": "not_found"}
    if text:
        c["text"] = text
    if scope:
        c["scope"] = scope
    c["edited_by"] = by
    data["candidates"][cid] = c
    _save(data)
    return {"ok": True, "candidate": c}


def effectiveness() -> dict:
    cands = (_load().get("candidates") or {}).values()
    appr = [c for c in cands if c.get("status") == "approved"]
    return {"approved": len(appr), "rejected": len([c for c in cands if c.get("status") == "rejected"]),
            "proposed": len([c for c in cands if c.get("status") == "proposed"]),
            "applied": [c.get("id") for c in appr if c.get("applied")]}

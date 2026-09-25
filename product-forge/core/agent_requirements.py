"""
Agent requirements loader (config-driven).

Loads `agent-requirements.json` (config -> repo root)
so the verbose-agent list, continuation budgets, and required output sections are
data, not hardcoded.
"""
import json
import os
from typing import Dict, List, Optional

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CANDIDATES = [
    os.path.join(_REPO, "config", "agent-requirements.json"),
    os.path.join(_REPO, "agent-requirements.json"),
]
_cache: Optional[Dict] = None


def load() -> Dict:
    global _cache
    if _cache is not None:
        return _cache
    for p in _CANDIDATES:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8-sig") as f:
                    _cache = json.load(f) or {}
                return _cache
            except Exception:
                continue
    _cache = {}
    return _cache


def verbose_agents() -> set:
    return set(load().get("verbose_agents") or [])


def is_verbose(agent_id: str) -> bool:
    return agent_id in verbose_agents()


def continuation(agent_id: str) -> Dict:
    c = load().get("continuation") or {}
    v = is_verbose(agent_id)
    return {
        "factor": c.get("verbose_factor", 4.0) if v else c.get("default_factor", 1.5),
        "max_continuations": c.get("verbose_max_continuations", 6) if v
        else c.get("default_max_continuations", 3),
    }


def required_sections(agent_id: str) -> Optional[Dict]:
    return (load().get("required_sections") or {}).get(agent_id)


def generation_strategy(agent_id: str) -> str:
    """Configured strategy: 'sectioned' | 'single' | 'auto' (default)."""
    g = (load().get("generation") or {})
    v = g.get(agent_id)
    return v if isinstance(v, str) else "auto"


def per_feature_agents() -> list:
    """Agents that must be generated ONE CALL PER FEATURE (F-x) when a plan exists.

    Config-driven (`per_feature_agents`); defaults to the two spec agents so the
    per-feature contract holds even before the config key is present.
    """
    v = load().get("per_feature_agents")
    if not isinstance(v, list) or not v:
        return ["design", "product-design-spec"]
    return [str(x) for x in v if str(x).strip()]


def feature_outline(products_dir: str, project: str) -> List[str]:
    """Read products/<p>/product-plan.json and return ["F-1: <name>", ...].

    Empty list when there is no plan (caller must fall back to a single call).
    """
    if not products_dir or not project:
        return []
    path = os.path.join(products_dir, project, "product-plan.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except Exception:
        return []
    out: List[str] = []
    for mod in (data.get("modules") or []):
        if not isinstance(mod, dict):
            continue
        for feat in (mod.get("features") or []):
            if not isinstance(feat, dict):
                continue
            fid = str(feat.get("id") or "").strip()
            if not fid:
                continue
            name = str(feat.get("name") or "").strip()
            out.append(f"{fid}: {name}" if name else fid)
    return out


def decide_strategy(agent_id: str, prior_truncated: bool = False, just_truncated: bool = False,
                    feature_outline: Optional[List[str]] = None) -> str:
    """Dynamic choice: one call when it fits, sectioned when safely possible.

    Safe rules (no assumptions):
      0. per-feature agent + a known feature outline -> sectioned (one call per F-x)
      1. explicit config (sectioned/single) wins
      2. sectioned requires a known outline (required_sections); otherwise single
         (a sectioned run with no outline would loop -> never do that)
      3. otherwise sectioned only when structured+verbose (or >=4 sections)
      4. default single
    """
    if agent_id in per_feature_agents() and feature_outline:
        return "sectioned"
    cfg = generation_strategy(agent_id)
    if cfg == "sectioned":
        return "sectioned"
    if cfg == "single":
        return "single"
    # auto: only sectioned when it provably needs it (faster common path).
    secs = required_sections(agent_id) or {}
    has_outline = bool(secs.get("essential") or secs.get("recommended"))
    if not has_outline:
        return "single"  # cannot section without a known outline
    if just_truncated or prior_truncated:
        return "sectioned"
    return "single"  # try one call first; promoted to sectioned only on truncation


# ── Deterministic per-feature FR/NFR/US id allocation ────────────────────────
# Fixed, generous block sizes so ids can NEVER collide across features, no
# matter what any single per-feature LLM call invents.
ID_BLOCK_SIZES = {"FR": 25, "NFR": 15, "US": 15}


def id_allocation(feature_outline, block_sizes=None):
    """Stable per-feature FR/NFR/US id blocks from the plan order.

    Feature index i (0-based, product-plan order) owns:
      FR  -> [i*FR_BLOCK  + 1 .. (i+1)*FR_BLOCK]
      NFR -> [i*NFR_BLOCK + 1 .. (i+1)*NFR_BLOCK]
      US  -> [i*US_BLOCK  + 1 .. (i+1)*US_BLOCK]

    Ranges are contiguous per feature and globally unique, and the result
    depends ONLY on the outline order -> identical across runs.
    """
    sizes = dict(ID_BLOCK_SIZES)
    if block_sizes:
        for k, v in block_sizes.items():
            try:
                iv = int(v)
                if iv > 0:
                    sizes[str(k)] = iv
            except Exception:
                pass
    alloc = {}
    for i, label in enumerate(feature_outline or []):
        fid = str(label or "").strip()
        if not fid:
            continue
        if ":" in fid:
            fid = fid.split(":", 1)[0].strip()
        entry = {}
        for prefix in ("FR", "NFR", "US"):
            size = sizes.get(prefix, 0)
            start = i * size + 1
            entry[prefix] = (start, start + size - 1)
        alloc[fid] = entry
    return alloc


def format_feature_range(fid, entry):
    """The strict, per-feature id instruction injected into that feature's prompt."""
    if not entry:
        return ""
    parts = []
    for prefix in ("FR", "NFR", "US"):
        rng = entry.get(prefix)
        if rng:
            parts.append(f"{prefix}-{rng[0]}..{prefix}-{rng[1]}")
    if not parts:
        return ""
    return (f"ASSIGNED ID RANGE for {fid} — you own EXACTLY: " + ", ".join(parts) + ". "
            "Use ONLY these ids; allocate them sequentially within your range; "
            "never use an id outside it; never reuse another feature's ids. "
            "Refer to other features' ids only as plain text — never re-define them.")


def format_allocation_table(allocation):
    """The whole allocation, shown to every section call so ranges are respected."""
    if not allocation:
        return ""
    rows = []
    for fid, entry in allocation.items():
        r = format_feature_range(fid, entry)
        if r:
            rows.append("- " + r)
    if not rows:
        return ""
    return ("\n\nGLOBAL ID ALLOCATION (deterministic — do NOT invent ids; each id "
            "belongs to exactly ONE feature):\n" + "\n".join(rows))

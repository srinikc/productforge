"""Canonical, format-independent requirement-id index — ONE query for all consumers.

Why this exists
---------------
Ids (FR/NFR/US + local families) were parsed by several modules with *different*
regexes (nfr_coverage, progress, output_checklist, compliance...), so the same id
could be seen differently depending on the reader, and detection depended on how
the LLM happened to format the text (headings vs tables vs bullets vs bold).

This module is the single source of truth for *detecting* and *normalising* spec
ids, so every consumer uses the SAME query. Extraction is format-independent: it
matches any id token wherever it appears (`FR-1`, `FR1`, `FR_1`, `**FR-1**`,
`| FR-1 |`, `### FR-1`, inline prose).

Id families come from `config/spec-id-families.json` (single reader).

Definitions vs references
-------------------------
* `defined_in_scopes()` — per feature scope (`## F-n` headings when present, else
  the whole document), the ids that appear in that scope. A scope "owns" an id if
  the id's FIRST occurrence in the document is inside that scope.
* `duplicates()` — ids owned by more than one scope (cross-feature collision), and
  (best-effort) ids that appear more than once *as a definition* in one scope.
* `undefined_refs()` — ids used but never seen.

The durable, non-heuristic upgrade is a machine-readable requirements manifest
(id -> feature) emitted by the pipeline; this module is the fallback/primary
query until then.
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

import os
import re
from typing import Dict, List, Optional, Set, Tuple

_REPO_ROOT = str(_PF_ROOT)
_CONFIG = os.path.join(_REPO_ROOT, "config", "spec-id-families.json")

_DEFAULT = {
    "global": ["FR", "NFR", "US"],
    "feature_id": "F",
    "local": ["AC", "BR", "EC", "V", "EH", "E", "API", "VA", "EDS", "OQ"],
    "local_default": True,
    "emits": {},
}


def families(path: Optional[str] = None) -> Dict:
    """Single reader for config/spec-id-families.json (defaults on failure)."""
    import json
    try:
        with open(path or _CONFIG, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        if isinstance(data, dict) and data:
            merged = dict(_DEFAULT)
            merged.update(data)
            return merged
    except Exception:
        pass
    return dict(_DEFAULT)


def global_prefixes(fam: Optional[Dict] = None) -> List[str]:
    return [str(p).upper() for p in ((fam or families()).get("global") or []) if str(p).strip()]


def local_prefixes(fam: Optional[Dict] = None) -> List[str]:
    return [str(p).upper() for p in ((fam or families()).get("local") or []) if str(p).strip()]


def all_prefixes(fam: Optional[Dict] = None) -> List[str]:
    return sorted(set(global_prefixes(fam)) | set(local_prefixes(fam)),
                  key=len, reverse=True)


def emits_for(agent_id: str, fam: Optional[Dict] = None) -> List[str]:
    """Families an agent is ALLOWED to define (its id contract). [] if none declared."""
    f = fam or families()
    em = f.get("emits") or {}
    return [str(x).upper() for x in (em.get(agent_id) or []) if str(x).strip()]


def registered_prefixes(fam: Optional[Dict] = None) -> List[str]:
    """Every prefix that is legitimately registered (global + local + feature + emits)."""
    f = fam or families()
    s = set(global_prefixes(f)) | set(local_prefixes(f))
    fid = str(f.get("feature_id") or "").upper()
    if fid:
        s.add(fid)
    for v in (f.get("emits") or {}).values():
        for x in (v or []):
            if str(x).strip():
                s.add(str(x).upper())
    return sorted(s, key=len, reverse=True)


def undeclared_ids(text: str, prefixes: Optional[List[str]] = None,
                   fam: Optional[Dict] = None) -> List[str]:
    """id-shaped tokens whose family is NOT registered (agents inventing prefixes).

    Scans for ``LETTERS[-_]digits`` at a definition position (line/table/bullet/
    heading start) so prose/paths are not flagged. Returns sorted unique prefixes.
    """
    import re as _re
    reg = set(registered_prefixes(fam))
    ignore = {"KB", "MB", "GB", "TB", "MS", "FPS", "HTTP", "HTTPS", "JSON", "HTML",
              "CSS", "PDF", "CSV", "SQL", "UUID", "ISO", "UTC", "PO", "PR", "ID", "IP",
              "UI", "UX", "QA", "CI", "CD", "SDK", "CLI", "GUI", "API2"}
    pat = _re.compile(r"(?m)^[ \t]{0,4}(?:#{1,6}[ \t]+|[-*+][ \t]+|\d+\.[ \t]+|\|)[ \t]*\**\s*"
                      r"([A-Z]{1,8})[-_](\d{1,4})\b")
    found = set()
    for m in pat.finditer(text or ""):
        p = m.group(1).upper()
        if p in ignore or p in reg:
            continue
        found.add(p)
    return sorted(found)


def _alt(prefixes: List[str]) -> str:
    return "|".join(sorted(set(p for p in prefixes if p), key=len, reverse=True))


def token_re(prefixes: Optional[List[str]] = None) -> re.Pattern:
    """Format-independent id token: PREFIX + optional separator + digits.

    Matches FR-1, FR1, FR_1, fr-01, **FR-1**, | FR-1 |, ### FR-1 — anywhere.
    """
    alt = _alt(prefixes or all_prefixes())
    if not alt:
        return re.compile(r"$^")
    return re.compile(r"\b(" + alt + r")[-_ ]?(\d+)\b", re.IGNORECASE)


def normalize(fam: str, num) -> str:
    """Canonical id form: ``FR-1`` (upper family, no leading zeros)."""
    try:
        n = int(num)
    except Exception:
        n = str(num)
    return f"{str(fam).upper()}-{n}"


def iter_ids(text: str, prefixes: Optional[List[str]] = None):
    """Yield ``(id, prefix, num, start)`` for every id occurrence, in order."""
    for m in token_re(prefixes).finditer(text or ""):
        yield normalize(m.group(1), m.group(2)), m.group(1).upper(), m.group(2), m.start()


def ids(text: str, prefixes: Optional[List[str]] = None) -> Set[str]:
    """Set of normalised ids present anywhere in ``text``."""
    return {i for i, _p, _n, _s in iter_ids(text, prefixes)}


def scopes(text: str, feature_id: str = "F") -> List[Tuple[str, int, int]]:
    """Feature scopes ``[(fid, start, end)]`` split on ``F-n`` headings.

    Falls back to a single ``("__all__", 0, len)`` scope when there are no feature
    headings, so callers always have at least one scope.
    """
    text = text or ""
    head = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]*(" + re.escape(feature_id) + r"-\d+)\b",
                      re.MULTILINE)
    all_heads = [(m.start(), len(m.group(1))) for m in
                 re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+").finditer(text)]
    out: List[Tuple[str, int, int]] = []
    for m in head.finditer(text):
        pos, level, fid = m.start(), len(m.group(1)), m.group(2)
        end = len(text)
        for hpos, hlevel in all_heads:
            if hpos > pos and hlevel <= level:
                end = hpos
                break
        out.append((fid, pos, end))
    if not out:
        out.append(("__all__", 0, len(text)))
    return out


def defined_in_scopes(text: str, prefixes: Optional[List[str]] = None,
                      feature_id: str = "F") -> Dict[str, Set[str]]:
    """``{scope_id: {ids whose FIRST occurrence is in that scope}}``."""
    text = text or ""
    first_pos: Dict[str, int] = {}
    for i, _p, _n, s in iter_ids(text, prefixes):
        if i not in first_pos:
            first_pos[i] = s
    out: Dict[str, Set[str]] = {fid: set() for fid, _s, _e in scopes(text, feature_id)}
    for i, pos in first_pos.items():
        for fid, start, end in scopes(text, feature_id):
            if start <= pos < end:
                out.setdefault(fid, set()).add(i)
                break
    return out


def duplicates(text: str, prefixes: Optional[List[str]] = None,
               feature_id: str = "F") -> List[str]:
    """Ids owned by more than one feature scope (cross-feature collision)."""
    by_scope = defined_in_scopes(text, prefixes, feature_id)
    owner: Dict[str, List[str]] = {}
    for fid, idset in by_scope.items():
        for i in idset:
            owner.setdefault(i, []).append(fid)
    return sorted(i for i, owners in owner.items() if len(owners) > 1)


def undefined_refs(text: str, prefixes: Optional[List[str]] = None) -> List[str]:
    """Ids used but never seen (placeholder for a manifest-backed check)."""
    seen = ids(text, prefixes)
    return sorted(seen - seen)  # every seen id is 'defined' until a manifest exists


def counts(text: str, prefixes: Optional[List[str]] = None) -> Dict[str, int]:
    """Per-family count of distinct ids (handy for reports)."""
    seen: Set[str] = set()
    out: Dict[str, int] = {}
    for i, p, _n, _s in iter_ids(text, prefixes):
        if i in seen:
            continue
        seen.add(i)
        out[p] = out.get(p, 0) + 1
    return out


# ── Running-number renumbering (BI-0144 follow-up: no hard cap, contiguous ids) ──

def renumber_family(text: str, prefix: str, start: int = 1,
                    mapping: Optional[Dict[str, str]] = None):
    """Renumber one id family to a running sequence from ``start``.

    Ids map in order of FIRST APPEARANCE; every occurrence (definition + refs)
    gets the same new number. Single pass, so no double replacement. When
    ``mapping`` is given, old->new pairs are recorded. Returns (text, next_start).
    """
    order: Dict[int, int] = {}

    def _repl(m):
        try:
            key = int(m.group(2))
        except Exception:
            return m.group(0)
        if key not in order:
            order[key] = start + len(order)
        if mapping is not None:
            mapping[normalize(prefix, key)] = normalize(prefix, order[key])
        return f"{prefix}-{order[key]}"

    new = token_re([prefix]).sub(_repl, text or "")
    return new, start + len(order)


def renumber_global(text: str, counters: Optional[Dict[str, int]] = None,
                    mapping: Optional[Dict[str, str]] = None):
    """Renumber the GLOBAL families (FR/NFR/US) to running numbers.

    ``counters`` carries the running start per family across blocks; ``mapping``
    accumulates old->new ids. LOCAL families are never touched. Returns
    (new_text, counters).
    """
    c = {"FR": 1, "NFR": 1, "US": 1}
    if counters:
        c.update({k: int(v) for k, v in counters.items() if k in c})
    for p in ("FR", "NFR", "US"):
        text, c[p] = renumber_family(text, p, c[p], mapping=mapping)
    return text, c


def apply_map(text: str, mapping: Dict[str, str]) -> str:
    """Replace ids in ``text`` using an old->new map (single pass)."""
    if not mapping:
        return text or ""
    prefixes = sorted({k.split("-", 1)[0] for k in mapping}, key=len, reverse=True)

    def _repl(m):
        key = normalize(m.group(1), m.group(2))
        return mapping.get(key, m.group(0))

    return token_re(prefixes).sub(_repl, text or "")

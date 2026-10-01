"""Pagination helper (API-0.1 §9): cursor-based, bounded."""
import base64
from typing import Any, Dict, List, Tuple

_MAX = 500
_DEFAULT = 50


def _enc(offset: int) -> str:
    return base64.urlsafe_b64encode(str(int(offset)).encode()).decode().rstrip("=")


def _dec(cursor: str) -> int:
    try:
        s = str(cursor or "").strip()
        if not s:
            return 0
        s += "=" * (-len(s) % 4)
        return max(int(base64.urlsafe_b64decode(s.encode()).decode()), 0)
    except Exception:
        return 0


def clamp_limit(limit: int) -> int:
    try:
        n = int(limit)
    except Exception:
        n = _DEFAULT
    return max(1, min(n, _MAX))


def paginate(items: List[Any], *, limit: int = _DEFAULT, cursor: str = "") -> Tuple[List[Any], Dict[str, Any]]:
    lim = clamp_limit(limit)
    start = _dec(cursor)
    page = list(items[start:start + lim])
    links: Dict[str, Any] = {}
    if start > 0:
        links["prev"] = {"cursor": _enc(max(start - lim, 0)), "limit": lim}
    if start + lim < len(items):
        links["next"] = {"cursor": _enc(start + lim), "limit": lim}
    links["self"] = {"cursor": cursor or "", "limit": lim, "total": len(items)}
    return page, links

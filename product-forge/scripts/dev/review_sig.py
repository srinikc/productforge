"""Shared stable finding-signature helpers (BI-PF-1449).

ONE implementation of the finding normalisation/digest used by BOTH:
- ``architect_review.py``  -> disposition binding (``sig:<digest>`` keys), and
- ``review_learnings.py``  -> ledger capture detection (``sig:<digest>`` markers).

Keeping them identical is load-bearing: drift silently breaks disposition resolution or mis-flags
findings as uncaptured.
"""
from __future__ import annotations

import hashlib
import re

SIGNATURE_WORDS = 14


def signature(text: str) -> str:
    """Human-readable stable normalisation (first N words) - for display/proposals."""
    s = str(text or "").lower()
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return " ".join(s.split()[:SIGNATURE_WORDS])


def _normalize_full(text: str) -> str:
    """Full-text normalisation (NOT truncated) so distinct findings cannot share a digest prefix."""
    s = str(text or "").lower()
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def digest(text: str) -> str:
    """16-hex (64-bit) content key over the FULL normalised text, used for ``sig:<digest>``."""
    return hashlib.sha256(_normalize_full(text).encode("utf-8")).hexdigest()[:16]

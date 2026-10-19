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
    """Stable normalisation: lowercase, drop code spans/punctuation, collapse whitespace, first N words."""
    s = str(text or "").lower()
    s = re.sub(r"`[^`]*`", " ", s)
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return " ".join(s.split()[:SIGNATURE_WORDS])


def digest(text: str) -> str:
    """10-hex content key used for ``sig:<digest>`` disposition keys and ledger markers."""
    return hashlib.sha1(signature(text).encode("utf-8")).hexdigest()[:10]

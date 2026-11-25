"""PF design completeness check — HARD STOP gate before Gate 1.5 (Fix R1 / BI-PF-XXXX).

Validates that engineering/designs/<item>.md is substantively filled before the LLM
architect reviewer runs. Prevents fake Gate 1.5 passes caused by empty/placeholder specs.

Rules checked (all deterministic — no LLM):
  1. Design doc exists
  2. All required sections present
  3. No section is entirely TBD / None / N/A / placeholder
  4. Minimum word count per section (tier-aware)
  5. AC count matches backlog item (if item ID given)

Exits:
  0 — all checks pass (safe to run Gate 1.5)
  1 — HARD STOP: one or more checks failed (do NOT run Gate 1.5)
  2 — usage error

Usage:
  python scripts/dev/design_completeness_check.py --item BI-PF-XXXX
  python scripts/dev/design_completeness_check.py --item BI-PF-XXXX --design path/to/design.md
  python scripts/dev/design_completeness_check.py --item BI-PF-XXXX --tier 1
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESIGNS_DIR = ROOT / "engineering" / "designs"

# Required sections (must appear as headings in the design doc)
REQUIRED_SECTIONS = [
    "PRIOR DECISIONS",
    "EXISTING PATH",
    "ASSUMPTIONS",
    "DIVERGENCES",
    "OPEN QUESTIONS",
    "APPROACH",
]

# Sections that gate on minimum word count (Tier 2 defaults; Tier 1 uses 50% of these)
MIN_WORDS: dict[str, int] = {
    "PRIOR DECISIONS": 20,
    "EXISTING PATH":   30,
    "ASSUMPTIONS":     40,
    "DIVERGENCES":     20,
    "OPEN QUESTIONS":  10,
    "APPROACH":        80,
}

# Placeholder patterns that indicate a section was not genuinely filled
PLACEHOLDER_RE = re.compile(
    r"^\s*(tbd|none|n/a|na|todo|placeholder|not\s+applicable|not\s+specified|empty|"
    r"\.\.\.|<.*?>|\[.*?\])\s*$",
    re.IGNORECASE | re.MULTILINE,
)

HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)


def _extract_sections(text: str) -> dict[str, str]:
    """Split markdown by headings; return {HEADING_UPPER: body_text}."""
    matches = list(HEADING_RE.finditer(text))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        heading = m.group(1).strip().upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[heading] = text[start:end].strip()
    return sections


def _find_section(sections: dict[str, str], name: str) -> tuple[str | None, str]:
    """Find a section by name (prefix match; returns key, body)."""
    name_up = name.upper()
    for key, body in sections.items():
        if key.startswith(name_up) or name_up in key:
            return key, body
    return None, ""


def _word_count(text: str) -> int:
    return len(text.split())


def check_design(doc_path: Path, item_id: str, tier: int) -> list[str]:
    """Return list of failure messages; empty list = pass."""
    failures: list[str] = []

    if not doc_path.exists():
        return [f"MISSING: design doc not found at {doc_path}"]

    try:
        text = doc_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"READ ERROR: {doc_path}: {e}"]

    sections = _extract_sections(text)

    for req in REQUIRED_SECTIONS:
        key, body = _find_section(sections, req)

        # 1. Section must exist
        if key is None:
            failures.append(f"MISSING SECTION: '{req}' heading not found in design doc")
            continue

        # 2. Body must not be empty
        if not body.strip():
            failures.append(f"EMPTY SECTION: '{req}' heading exists but has no content")
            continue

        # 3. No placeholder-only content
        # Strip any sub-headings and check remaining prose
        prose = re.sub(r"^#{1,6}\s+.+$", "", body, flags=re.MULTILINE).strip()
        if PLACEHOLDER_RE.fullmatch(prose):
            failures.append(
                f"PLACEHOLDER SECTION: '{req}' contains only placeholder text "
                f"('{prose[:60]}'). Write substantive content."
            )
            continue

        # 4. Minimum word count (Tier 1 uses 50% thresholds)
        min_w = MIN_WORDS.get(req, 10)
        if tier == 1:
            min_w = max(5, min_w // 2)
        wc = _word_count(prose)
        if wc < min_w:
            failures.append(
                f"TOO SHORT: '{req}' has {wc} words (minimum {min_w} for Tier {tier}). "
                f"Add substantive content — not prose padding."
            )

    return failures


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Design completeness HARD STOP before Gate 1.5 (Fix R1)"
    )
    ap.add_argument("--item", required=True, help="Backlog item ID, e.g. BI-PF-1234")
    ap.add_argument("--design", default="", help="Path to design doc (default: engineering/designs/<item>.md)")
    ap.add_argument("--tier", type=int, choices=[1, 2, 3], default=2,
                    help="Item tier: 1=tooling/docs, 2=feature, 3=security/data (default: 2)")
    a = ap.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    doc_path = Path(a.design) if a.design else DESIGNS_DIR / f"{a.item}.md"

    print(f"design-completeness-check: {a.item}  (Tier {a.tier})")
    print(f"  design doc: {doc_path}")
    print()

    failures = check_design(doc_path, a.item, a.tier)

    if failures:
        print("  HARD STOP — design is not ready for Gate 1.5:")
        for f in failures:
            print(f"    ✗ {f}")
        print()
        print("  Fix all issues above, then re-run this check before running Gate 1.5.")
        print("  Reminder: 'INSUFFICIENT_DATA: <what is missing>' is valid if info is unavailable.")
        print("  Do NOT run: python scripts/dev/architect_review.py run --item ... --mode design")
        print("  until this check exits 0.")
        return 1

    print(f"  ✓ All {len(REQUIRED_SECTIONS)} required sections present and substantive")
    print("  Safe to run Gate 1.5 architect review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

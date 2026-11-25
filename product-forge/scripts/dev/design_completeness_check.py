"""Fail a design that omits required engineering dimensions or sections (BI-PF-1614/1615)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "scripts" / "dev")):
    if str(p) not in sys.path:
        sys.path.insert(0, p)
from core import backlog  # noqa: E402
import design_contract_check as dcc  # noqa: E402

CFG = ROOT / "config" / "design-completeness.json"
DESIGNS_DIR = ROOT / "engineering" / "designs"

REQUIRED_SECTIONS = [
    "PRIOR DECISIONS",
    "EXISTING PATH",
    "ASSUMPTIONS",
    "DIVERGENCES",
    "OPEN QUESTIONS",
    "APPROACH",
]

MIN_WORDS: dict[str, int] = {
    "PRIOR DECISIONS": 20,
    "EXISTING PATH":   30,
    "ASSUMPTIONS":     40,
    "DIVERGENCES":     20,
    "OPEN QUESTIONS":  10,
    "APPROACH":        80,
}

PLACEHOLDER_RE = re.compile(
    r"^\s*(tbd|none|n/a|na|todo|placeholder|not\s+applicable|not\s+specified|empty|"
    r"\.\.\.|<.*?>|\[.*?\])\s*$",
    re.IGNORECASE | re.MULTILINE,
)

HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)


def _missing(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


def check_design_doc(doc_path: Path, item_id: str, tier: int = 2) -> list[str]:
    failures: list[str] = []
    if not doc_path.exists():
        return [f"MISSING: design doc not found at {doc_path}"]
    try:
        text = doc_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return [f"READ ERROR: {doc_path}: {e}"]

    matches = list(HEADING_RE.finditer(text))
    sections: dict[str, str] = {}
    for i, m in enumerate(matches):
        heading = m.group(1).strip().upper()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[heading] = text[start:end].strip()

    for req in REQUIRED_SECTIONS:
        found_key = next((k for k in sections if req in k or k.startswith(req)), None)
        if not found_key:
            failures.append(f"MISSING SECTION: '{req}' heading not found in design doc")
            continue
        body = sections[found_key]
        if not body.strip():
            failures.append(f"EMPTY SECTION: '{req}' heading exists but has no content")
            continue
        prose = re.sub(r"^#{1,6}\s+.+$", "", body, flags=re.MULTILINE).strip()
        if PLACEHOLDER_RE.fullmatch(prose):
            failures.append(f"PLACEHOLDER SECTION: '{req}' contains only placeholder text ('{prose[:60]}')")
            continue
        min_w = MIN_WORDS.get(req, 10)
        if tier == 1:
            min_w = max(5, min_w // 2)
        wc = len(prose.split())
        if wc < min_w:
            failures.append(f"TOO SHORT: '{req}' has {wc} words (minimum {min_w} for Tier {tier})")

    return failures


def problems(item_id: str, item: dict | None = None) -> list[str]:
    if item is None:
        item = backlog.get_epic("product_forge", None, item_id)
    if not item:
        return [f"item not found: {item_id}"]
    bad = []
    if CFG.exists() and dcc.enforced(item, dcc._cfg()):
        cfg = json.loads(CFG.read_text(encoding="utf-8-sig"))
        pack = item.get("design_pack") or {}
        for dim in cfg.get("required_dimensions") or []:
            value = pack.get(dim, item.get(dim))
            if _missing(value) and dim not in (cfg.get("allow_empty") or []):
                bad.append(f"missing design dimension: {dim}")
        tokens = [str(x).lower() for x in (cfg.get("placeholder_tokens") or [])]
        for src_name, src in (("design_pack", pack), ("item", item)):
            for key in ("risks",):
                if key in src:
                    for s in dcc._iter_strings(src[key]):
                        if any(t in s.lower() for t in tokens):
                            bad.append(f"placeholder in {src_name}.{key}")

    doc_path = DESIGNS_DIR / f"{item_id}.md"
    if doc_path.exists():
        bad.extend(check_design_doc(doc_path, item_id))
    return sorted(set(bad))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Design completeness check (BI-PF-1614/1615)")
    ap.add_argument("--item", required=True)
    ap.add_argument("--design", default="")
    ap.add_argument("--tier", type=int, choices=[1, 2, 3], default=2)
    a = ap.parse_args(argv)

    if a.design:
        doc_path = Path(a.design)
        fails = check_design_doc(doc_path, a.item, a.tier)
        if fails:
            print(f"design-completeness: FAIL ({len(fails)})")
            for f in fails:
                print(f"  - {f}")
            return 1
        print("design-completeness: OK")
        return 0

    bad = problems(a.item)
    if bad:
        print(f"design-completeness: FAIL ({len(bad)})")
        for p in bad:
            print(f"  - {p}")
        return 1
    print("design-completeness: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] if len(sys.argv) > 1 else None))

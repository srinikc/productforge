"""
NFR coverage (4.3).

Extracts NFR ids (NFR-1, NFR-2, ...) from the requirement/design/architecture
docs and checks whether the project's tests reference them, producing a simple
coverage report (total / covered / missing / percent).
"""
import os
import re
from typing import Dict, List

from core import id_index


def _read_files(root: str, rels: List[str]) -> str:
    out = ""
    for r in rels:
        p = os.path.join(root, r)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    out += f.read() + "\n"
            except Exception:
                pass
    return out


def _norm(ids) -> List[str]:
    out = set()
    for i in ids:
        i = i.upper().replace("_", "-")
        i = re.sub(r"^(NFR|FR)(\d)", r"\1-\2", i)
        out.add(i)
    return sorted(out)


def _ids_of_family(text: str, prefix: str) -> List[str]:
    """Distinct ids of one family via the canonical index (format-independent)."""
    return sorted({i for i, p, _n, _s in id_index.iter_ids(text, [prefix])})


def compute_nfr_coverage(project_dir: str) -> Dict:
    spec = _read_files(project_dir, ["docs/requirements.md", "docs/design.md",
                                     "docs/architecture.md", "docs/product-plan.md"])
    nfr_ids = _ids_of_family(spec, "NFR")
    fr_ids = _ids_of_family(spec, "FR")

    test_text = ""
    for base in ("tests", "test"):
        d = os.path.join(project_dir, base)
        if os.path.isdir(d):
            for dp, _dn, fs in os.walk(d):
                for fn in fs:
                    try:
                        with open(os.path.join(dp, fn), "r", encoding="utf-8", errors="ignore") as f:
                            test_text += f.read() + "\n"
                    except Exception:
                        pass

    def _covered(ids):
        def _pat(i: str) -> str:
            m = re.match(r"^(NFR|FR)-(\d+)$", i)
            if m:
                return r"(?<![A-Za-z0-9])" + m.group(1) + r"[-_]?" + m.group(2) + r"(?!\d)"
            return r"(?<![A-Za-z0-9])" + re.escape(i) + r"(?![A-Za-z0-9])"
        cov = [i for i in ids if re.search(_pat(i), test_text, re.IGNORECASE)]
        return cov, [i for i in ids if i not in cov]

    nfr_cov, nfr_missing = _covered(nfr_ids)
    fr_cov, fr_missing = _covered(fr_ids)
    total = len(nfr_ids)
    return {
        "total": total,
        "covered": len(nfr_cov),
        "missing": nfr_missing,
        "percent": (len(nfr_cov) / total * 100) if total else 0.0,
        # Functional-requirement traceability (3.5)
        "fr_total": len(fr_ids),
        "fr_covered": len(fr_cov),
        "fr_missing": fr_missing,
    }

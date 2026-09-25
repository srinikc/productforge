"""
Architecture diagram generator (5.5).

Emits `docs/architecture.mermaid` and `docs/architecture.drawio` from
`docs/architecture.md` (components + integration points). Deterministic; wired
after the architect stage.
"""
import os
import re
from typing import Dict, List, Tuple

_BULLET = re.compile(r"^\s*[-*]\s+\*{0,2}([A-Za-z0-9][\w ./+-]{1,50})\*{0,2}", re.M)


def _section(text: str, *names: str) -> str:
    for n in names:
        m = re.search(rf"^#+\s*{re.escape(n)}.*$", text, re.I | re.M)
        if not m:
            continue
        start = m.end()
        nxt = re.search(r"^#+\s", text[start:], re.M)
        return text[start: start + (nxt.start() if nxt else len(text))]
    return ""


def _components(text: str) -> List[str]:
    sec = _section(text, "Components", "Component")
    items = [m.group(1).strip() for m in _BULLET.finditer(sec)] if sec else []
    seen, out = set(), []
    for i in items:
        k = i.lower()
        if k not in seen:
            seen.add(k)
            out.append(i)
    return out[:20]


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower() or "node"


def generate(project_dir: str) -> Dict[str, str]:
    arch = os.path.join(project_dir, "docs", "architecture.md")
    try:
        text = open(arch, encoding="utf-8", errors="ignore").read()
    except Exception:
        return {}
    comps = _components(text) or ["Client", "API", "Database"]
    ids = [_slug(c) for c in comps]

    # Mermaid (linear flow; typical client -> api -> db)
    lines = ["flowchart TD"]
    for c, i in zip(comps, ids):
        lines.append(f'  {i}["{c}"]')
    for a, b in zip(ids, ids[1:]):
        lines.append(f"  {a} --> {b}")
    mermaid = "\n".join(lines) + "\n"

    # draw.io (mxGraphModel with one box per component)
    cells = []
    for n, (c, i) in enumerate(zip(comps, ids)):
        cells.append(
            f'<mxCell id="{i}" value="{c}" style="rounded=1;whiteSpace=wrap;html=1;" vertex="1" parent="1">'
            f'<mxGeometry x="80" y="{60 + n * 90}" width="220" height="50" as="geometry"/></mxCell>')
    edges = []
    for n, (a, b) in enumerate(zip(ids, ids[1:])):
        edges.append(f'<mxCell id="e{n}" style="endArrow=block;html=1;" edge="1" parent="1" '
                     f'source="{a}" target="{b}"><mxGeometry relative="1" as="geometry"/></mxCell>')
    drawio = ('<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" page="1" pageWidth="850" '
              'pageHeight="1100"><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
              + "".join(cells) + "".join(edges) + "</root></mxGraphModel>")

    out = {}
    try:
        os.makedirs(os.path.join(project_dir, "docs"), exist_ok=True)
        mp = os.path.join(project_dir, "docs", "architecture.mermaid")
        dp = os.path.join(project_dir, "docs", "architecture.drawio")
        open(mp, "w", encoding="utf-8").write(mermaid)
        open(dp, "w", encoding="utf-8").write(drawio)
        out = {"mermaid": os.path.relpath(mp, project_dir), "drawio": os.path.relpath(dp, project_dir),
               "components": comps}
        print(f"  [Diagram] architecture.mermaid + architecture.drawio ({len(comps)} components)")
    except Exception as e:
        print(f"[Diagram] {e}")
    return out

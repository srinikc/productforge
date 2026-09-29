"""BI-PF-0252: agent-card tools/permission/model consistency audit."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts" / "dev"))

import agent_card_audit as aca  # noqa: E402

_CONFLICT = """---
description: x
mode: subagent
model: "opencode-go/mimo-v2.5"
agent_id: x
permission:
  edit: deny
---

## 0. METADATA
- **Tools**: list_dir, read_file, write_file
"""

_CLEAN = """---
description: y
mode: subagent
model: opencode-go/mimo-v2.5
agent_id: y
permission:
  edit: allow
---

## 0. METADATA
- **Tools**: list_dir, read_file, write_file
"""


def test_flags_write_tool_with_edit_denied_and_quoted_model():
    d = tempfile.mkdtemp()
    try:
        open(os.path.join(d, "bad.md"), "w", encoding="utf-8").write(_CONFLICT)
        open(os.path.join(d, "ok.md"), "w", encoding="utf-8").write(_CLEAN)
        res = dict(aca.findings(d))
        assert "bad.md" in res
        assert any("edit=deny" in i for i in res["bad.md"])
        assert any("quoted" in i for i in res["bad.md"])
        assert "ok.md" not in res
    finally:
        import shutil
        shutil.rmtree(d, ignore_errors=True)

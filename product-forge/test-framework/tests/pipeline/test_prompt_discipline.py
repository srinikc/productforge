"""F0/EOS: the global engineering-discipline guard must reach EVERY agent prompt."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.orchestrator.prompt_builder import discipline_guard  # noqa: E402


def test_discipline_guard_is_nonempty_and_binding():
    t = discipline_guard("design")
    assert t and "ENGINEERING DISCIPLINE" in t


def test_discipline_guard_covers_key_rules():
    t = discipline_guard("implement")
    low = t.lower()
    # no placeholders rule
    assert "todo" in low and "placeholder" in low
    # 360 impact analysis rule
    assert "360" in t and "dependency" in low
    # order: think/design/plan/360 then produce (role-agnostic, not code-only)
    assert "design" in low and "plan" in low and ("produce" in low or "implement" in low)
    # no placeholders rule (any artifact, not only code)
    assert "placeholder" in low and "todo" in low
    # fail-closed evidence rule
    assert "blocked" in low or "unverified" in low

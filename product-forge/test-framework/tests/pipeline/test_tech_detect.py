"""Regression for BI-0078: tech detection must not match common English words."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.tech_stack import detect_tech_from_text  # noqa: E402


def test_prose_go_does_not_select_go():
    assert "go" not in detect_tech_from_text("go through the feature and iterate")


def test_explicit_go_language_matches():
    assert "go" in detect_tech_from_text("Backend written in Go language using REST")


def test_golang_matches():
    assert "golang" in detect_tech_from_text("implemented in golang")


def test_python_and_nextjs_still_match():
    got = detect_tech_from_text("Frontend in Next.js with a Python FastAPI backend")
    assert "python" in got and ("nextjs" in got or "next.js" in got)


def test_react_requires_context():
    assert "react" not in detect_tech_from_text("do not react to this")
    assert "react" in detect_tech_from_text("build the UI using React")

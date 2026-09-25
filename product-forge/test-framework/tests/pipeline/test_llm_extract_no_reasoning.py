"""
Regression for BI-0075: LLM response extraction must NOT fall back to the model's
`reasoning` field (chain-of-thought) as artifact content.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.orchestrator.llm_client import LLMClient  # noqa: E402


def _client():
    c = LLMClient.__new__(LLMClient)  # bypass __init__
    return c


def test_content_preferred():
    c = _client()
    r = {"choices": [{"message": {"content": "Real answer", "reasoning": "thinking..."}}]}
    assert c._extract_response_content(r, "openrouter") == "Real answer"


def test_reasoning_NOT_used_when_content_empty():
    c = _client()
    r = {"choices": [{"message": {"content": "", "reasoning": "We need answer discovery doc..."}}]}
    assert c._extract_response_content(r, "openrouter") == ""


def test_reasoning_NOT_used_when_content_missing():
    c = _client()
    r = {"choices": [{"message": {"reasoning": "chain of thought only"}}]}
    assert c._extract_response_content(r, "openrouter") == ""


def test_structured_content_blocks_joined():
    c = _client()
    r = {"choices": [{"message": {"content": [{"text": "a"}, {"text": "b"}]}}]}
    assert c._extract_response_content(r, "anthropic") == "ab"

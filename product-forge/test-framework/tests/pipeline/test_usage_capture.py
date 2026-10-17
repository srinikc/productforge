"""BI-PF-1423: per-task usage capture - field mapping + delta math."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.dev import usage_capture as u  # noqa: E402


def test_usage_of_maps_opencode_fields():
    s = {"cost": "0.5", "tokens_input": "10", "tokens_output": "20", "tokens_reasoning": "3",
         "tokens_cache_read": "100", "tokens_cache_write": "7"}
    assert u.usage_of(s) == {"input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 3,
                             "cache_read": 100, "cache_write": 7, "cost_usd": 0.5}


def test_delta_subtracts_baseline():
    base = {"input_tokens": 10, "output_tokens": 20, "reasoning_tokens": 0,
            "cache_read": 100, "cache_write": 7, "cost_usd": 0.5}
    cur = {"input_tokens": 15, "output_tokens": 25, "reasoning_tokens": 1,
           "cache_read": 120, "cache_write": 9, "cost_usd": 0.75}
    d = u.delta(base, cur)
    assert d["input_tokens"] == 5 and d["output_tokens"] == 5 and d["cache_read"] == 20
    assert round(d["cost_usd"], 2) == 0.25

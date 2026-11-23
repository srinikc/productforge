import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_architect_review_uses_mimo():
    cfg = json.loads((ROOT / "config" / "architect-review.json").read_text(encoding="utf-8"))
    assert cfg["model"] == "mimo-v2.6-flash"
    assert cfg["provider"] == "opencode-go"
    assert cfg["base_url"].rstrip("/").endswith("/zen/go/v1")
    assert cfg["api_key_env"] == "OPENCODE_ZEN_API_KEY"

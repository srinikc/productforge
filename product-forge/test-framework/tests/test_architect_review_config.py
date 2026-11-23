import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _config():
    return json.loads((ROOT / "config" / "architect-review.json").read_text(encoding="utf-8"))


def test_architect_review_uses_mimo():
    cfg = _config()
    assert cfg["model"] == "mimo-v2.6-flash"
    assert cfg["provider"] == "opencode-go"
    assert cfg["base_url"] == "https://opencode.ai/zen/go/v1"
    assert cfg["api_key_env"] == "OPENCODE_ZEN_API_KEY"


def test_architect_review_has_no_secret_material():
    for key, value in _config().items():
        if not isinstance(value, str):
            continue
        assert "BEGIN PRIVATE KEY" not in value
        assert not value.startswith(("sk-", "sk_proj-"))
        assert key not in {"api_key", "api_key_value", "token", "password"}

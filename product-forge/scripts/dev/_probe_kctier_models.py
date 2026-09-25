"""Probe the three kctier models on opencode-go/zen."""
import json
import os
import urllib.error
import urllib.request

URL = "https://opencode.ai/zen/go/v1/chat/completions"
MODELS = ["mimo-v2.5", "deepseek-v4-flash", "deepseek-v4.1-flash"]

key = os.getenv("OPENCODE_ZEN_API_KEY", "")
print("OPENCODE_ZEN_API_KEY present:", bool(key))

for model in MODELS:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word OK"}],
        "max_tokens": 16,
    }).encode("utf-8")
    req = urllib.request.Request(
        URL, data=body, method="POST",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8", "replace")
            print(f"[{model}] HTTP {resp.status} :: {text[:300]}")
    except urllib.error.HTTPError as e:
        text = e.read().decode("utf-8", "replace")
        print(f"[{model}] HTTP {e.code} :: {text[:300]}")
    except Exception as e:
        print(f"[{model}] ERROR {type(e).__name__}: {e}")

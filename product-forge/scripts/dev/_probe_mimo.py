#!/usr/bin/env python3
"""Probe candidate 'mimo' model ids against the Zen (go + non-go) and OpenRouter
chat-completions endpoints to discover which id/provider actually returns HTTP 200.

Read-only network probe. Writes results to scripts/dev/_probe_mimo_results.json.
"""
import json
import os
import random
import urllib.error
import urllib.request

CANDIDATES = [
    "mimo-v2.5",
    "mimo-v2.5-free",
    "mimo-v2.5-pro",
    "opencode/mimo-v2.5-free",
]

UA = "product-forge-pipeline/1.0"
SESSION = "probe-%06d" % random.randint(0, 999999)

ZEN_KEY = os.environ.get("OPENCODE_ZEN_API_KEY", "")
OR_KEY = os.environ.get("OPENROUTER_API_KEY", "")

PROVIDERS = [
    {
        "name": "zen-go",
        "url": "https://opencode.ai/zen/go/v1/chat/completions",
        "headers": {
            "Authorization": "Bearer %s" % ZEN_KEY,
            "Content-Type": "application/json",
            "User-Agent": UA,
            "x-opencode-session": SESSION,
        },
    },
    {
        "name": "zen",
        "url": "https://opencode.ai/zen/v1/chat/completions",
        "headers": {
            "Authorization": "Bearer %s" % ZEN_KEY,
            "Content-Type": "application/json",
            "User-Agent": UA,
            "x-opencode-session": SESSION,
        },
    },
    {
        "name": "openrouter",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "headers": {
            "Authorization": "Bearer %s" % OR_KEY,
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
    },
]


def probe(provider, model_id):
    body = json.dumps(
        {
            "model": model_id,
            "messages": [{"role": "user", "content": "Reply with the single word OK"}],
            "max_tokens": 16,
        }
    ).encode("utf-8")

    headers = dict(provider["headers"])

    req = urllib.request.Request(provider["url"], data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            status = resp.getcode()
            raw = resp.read().decode("utf-8", "replace")
            return status, raw, None
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        return e.code, raw, None
    except Exception as e:  # noqa: BLE001
        return None, "", "%s: %s" % (type(e).__name__, e)


def short(text, limit=220):
    text = (text or "").replace("\n", " ").replace("\r", " ").strip()
    return text[:limit]


def main():
    if not ZEN_KEY:
        print("WARN: OPENCODE_ZEN_API_KEY not set")
    if not OR_KEY:
        print("WARN: OPENROUTER_API_KEY not set")

    results = []
    print("%-22s %-12s %-6s %s" % ("MODEL", "PROVIDER", "STATUS", "BODY"))
    print("-" * 100)
    for model_id in CANDIDATES:
        for provider in PROVIDERS:
            status, raw, err = probe(provider, model_id)
            results.append(
                {
                    "model": model_id,
                    "provider": provider["name"],
                    "status": status,
                    "body": short(raw),
                    "error": err,
                }
            )
            shown = status if status is not None else "ERR"
            print("%-22s %-12s %-6s %s" % (model_id, provider["name"], shown, err or short(raw)))

    ok = [r for r in results if r["status"] == 200]
    print("\nHTTP 200 hits: %d" % len(ok))
    for r in ok:
        print("  %s via %s" % (r["model"], r["provider"]))


if __name__ == "__main__":
    main()

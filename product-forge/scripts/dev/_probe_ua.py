"""Probe the Zen endpoint with different User-Agent header sets.

Hypothesis: Cloudflare returns 403 error code 1010 to bare HTTP clients
because the request has no/bad User-Agent. This script tries four header
sets (A-D) across two models and prints the HTTP status + short body.
"""
import json
import os
import sys
import urllib.error
import urllib.request

ENDPOINT = "https://opencode.ai/zen/go/v1/chat/completions"
CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def header_sets(api_key):
    base = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    return [
        ("A", dict(base)),
        ("B", {**base, "User-Agent": "opencode/1.0"}),
        ("C", {**base, "User-Agent": CHROME_UA}),
        ("D", {
            **base,
            "User-Agent": "opencode/1.0",
            "Accept": "application/json",
            "Origin": "https://opencode.ai",
            "Referer": "https://opencode.ai/",
        }),
        ("E", {
            **base,
            "User-Agent": "product-forge-pipeline/1.0",
            "x-opencode-session": "probe-session-1",
        }),
        ("F", {
            **base,
            "User-Agent": "opencode/1.0",
            "x-opencode-session": "probe-session-1",
        }),
    ]


def probe(model, label, headers):
    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word OK"}],
        "max_tokens": 16,
    }).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            status = resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        status = e.code
    except Exception as e:  # noqa: BLE001
        body = f"{type(e).__name__}: {e}"
        status = -1
    snippet = body.replace("\n", " ")[:200]
    print(f"  [{model}] {label}: HTTP {status} | {snippet}")
    return status


def main():
    api_key = os.getenv("OPENCODE_ZEN_API_KEY", "")
    if not api_key:
        print("ERROR: OPENCODE_ZEN_API_KEY not set")
        return 2
    print(f"Endpoint: {ENDPOINT}")
    results = {}
    for model in ("mimo-v2.5", "deepseek-v4.1-flash"):
        print(f"Model: {model}")
        for label, headers in header_sets(api_key):
            results[(model, label)] = probe(model, label, headers)
    print("\nSummary:")
    for (model, label), status in results.items():
        print(f"  {model:22s} {label}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Provider Fallback Policy (BI-PF-0247)

## The rule
- **OpenCode Zen "free" models** (`.../zen/v1/chat/completions`, provider `opencode-zen`, `*-free`)
  are **not usable from the API** — they return **403 FreeTierError**.
- The **working paid path** is **opencode-go** (`.../zen/go/v1/chat/completions`), used by the
  `kctier`, `actual`, and `actual-balanced` profiles.

## Defaults (config, not code)
- `llm_client.FALLBACK_PROVIDER` = `PIPELINE_FALLBACK_PROVIDER` (default **`opencode-go`**).
- `llm_client.FALLBACK_ENDPOINT` = `PIPELINE_FALLBACK_ENDPOINT`
  (default `https://opencode.ai/zen/go/v1/chat/completions`).
- Active profile: `config/model-tier.json` → `active_tier` (currently **`actual`**).
- Working tier for E2E: **`kctier`** (`opencode-go`, `deepseek-v4.1-flash`).

## If you must run the free path
`free-trial` / `free-trial-fast` are documented as **zero-cost validation only** and their default
endpoint is the unusable Zen free path; treat them as best-effort. Prefer `kctier` for any run that
must complete.

## Enforcement (advisory)
`scripts/dev/provider_fallback_audit.py` (also a step in `scripts/dev/wired_audit.py`) flags any
profile whose `api_endpoint` routes to the unusable free Zen path. Non-fatal.

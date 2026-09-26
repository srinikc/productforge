# Product Forge — provider credentials & budget (standard)

Owner: `core/credentials.py` (BI-0207). Config: `config/provider-keys.json`.
This is the ONE place that defines **where provider API keys come from**. Tiers and
capability packs resolve keys automatically; no code changes when you switch provider.

## 1. Where keys live

| Priority | Location | Notes |
|---|---|---|
| 1 | **Process environment** | `OPENROUTER_API_KEY=...` exported in the shell (wins) |
| 2 | **`product-forge/.env`** | canonical; ROOT-anchored; gitignored |
| 3 | **`product-forge/.env.local`** | local override; gitignored |

- The loader is **ROOT-anchored** (via `core/paths.py`), so it works no matter which
  directory you run from. It never overrides an already-set process env var.
- **Never commit secrets.** `.env` / `.env.local` are gitignored; commit only
  `.env.example` (names, no values).
- Values are **never logged**; the CLI prints only `key_set: true/false`.

## 2. Provider -> env var (from `config/provider-keys.json`)

| Provider | Kind | Env var | Used for |
|---|---|---|---|
| `opencode-go` / `opencode-zen` | direct | `OPENCODE_ZEN_API_KEY` | llm |
| `openrouter` | aggregator | `OPENROUTER_API_KEY` | llm |
| `gemini` | direct | `GEMINI_API_KEY` | llm, image, vision |
| `openai` | direct | `OPENAI_API_KEY` | llm, image, tts, stt |
| `anthropic` | direct | `ANTHROPIC_API_KEY` | llm |
| `fal` | aggregator | `FAL_KEY` | image, video, 3d, music |
| `replicate` | aggregator | `REPLICATE_API_TOKEN` | image, video, 3d, music |
| `kie` | aggregator | `KIE_API_KEY` | image, video |
| `elevenlabs` | direct | `ELEVENLABS_API_KEY` | tts |
| `deepgram` | direct | `DEEPGRAM_API_KEY` | stt |

The file stores **env var NAMES only**, plus `kind` (direct | aggregator) and
`required_for` (the model kinds it can serve). Add a provider = one JSON entry.

## 3. How the engine uses it

1. A **tier** (`config/model-tier.json`) names a provider for each agent/stage.
2. `llm_client` calls `credentials.key_for(provider)` -> resolves the env var.
3. Missing key -> a clear, early failure (never a silent wrong-provider call).
4. Media adapters (later) use the same `key_for()` for `fal`/`replicate`/`elevenlabs`/...

Check readiness any time:
```
python -m core.credentials --status            # which providers are keyed (redacted)
python -m core.credentials --missing llm,tts   # what is missing for those kinds
```

## 4. Budget caps (per-run / per-provider)

`config/provider-keys.json` -> `budget`:
```json
{ "per_run_cap_usd": 0, "per_provider_cap_usd": 0 }
```
`0` = uncapped. Set `> 0` for a hard stop; adapters/executor call
`credentials.check_budget(provider, spent, run_spent)` -> `(ok, reason)`.

## 5. Day-one setup (standard)

1. Create **`product-forge/.env`** with the provider key you intend to use, e.g.
   `OPENROUTER_API_KEY=...` (for the `openrouter`/`free-trial-fast` tiers) or
   `OPENCODE_ZEN_API_KEY=...` (for the default `opencode-go` tier).
2. Run `python -m core.credentials --status` -> confirm `key_set: true`.
3. Pick a tier that matches the keyed provider (e.g. `--tier free-trial-fast`).
4. Do NOT commit `.env`; keep `.env.example` current.

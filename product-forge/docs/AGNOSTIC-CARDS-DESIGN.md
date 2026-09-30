# Framework-Agnostic Agent Cards — Design (BI-0201)

## Goal
Remove the runtime dependency on `.opencode/agent/*.md` so the pipeline is truly framework-agnostic: all card
readers resolve from **Product Forge's own neutral sources** (`agents/*.agent.json` canonical, optional
neutral `cards/` dir), with `.opencode/agent/*.md` demoted to an explicit **legacy fallback** (never a
default). One resolver, one truth; the pipeline runs identically with or without `.opencode`.

## 360° — verified current state
| Module | Coupling | On runtime path? | Fix |
|---|---|---|---|
| `core/agent_spec.py` | already agnostic (`load_specs` → `agents/*.agent.json`; `from_opencode_card`, `source`) | yes (canonical) | extend with resolver |
| `core/agent_card_loader.py` | default `agent_dir=".opencode/agent"` | via capabilities probe | neutral default + resolver |
| `core/agent_rules.py` | `parse_agent_md`/`list_all_agents` read `.opencode/agent/*.md` | via `agent_migrator` | resolve neutral first |
| `core/schema_validator.py` | `validate_agent_md`/all-agents read `.opencode/agent/*.md` | **yes** (`pipeline_executor:1517`) | resolve neutral first |
| `core/review_ledger.py` | writes `.opencode/agent/*.md` | no (dev shim) | legacy/neutral |
| `core/agent_migrator.py` | reads/writes `.opencode/agent/*.md` | no (migration tool) | legacy tool |
| `core/paths.py` | `OPENCODE_DIR` constant | config | keep (legacy pointer) |
| `core/diagram_render.py` | bundled drawio under `.opencode/tools` | optional | **BI-0202** |

**Blast radius:** resolver in `agent_spec.py`; switch defaults in `agent_card_loader`/`agent_rules`/
`schema_validator`. No new store. `.opencode` files remain on disk (legacy), just not read by default.

## Design decisions (modular, 1 truth per concern)
- **Neutral resolver (single owner = `core/agent_spec.py`):**
  - `cards_dir() -> str`: returns the neutral cards dir. Resolution order:
    1. `agents/` (canonical `*.agent.json`, already the SSOT) — **preferred**.
    2. neutral `cards/` dir (optional markdown/JSON cards from a host framework).
    3. `.opencode/agent/` — **legacy fallback only**, and only when explicitly allowed
       (`ALLOW_OPENCODE_LEGACY=1`), else skipped. Default = agnostic.
  - `resolve_card_path(agent_id) -> Optional[str]`: absolute path to the neutral card for an agent id
    (`.agent.json` first, then `.md`), else legacy. Used by every reader.
  - `source_kind(path) -> "spec"|"cards"|"legacy"`.
- **Readers delegate, never duplicate:** `agent_card_loader`, `agent_rules.parse_agent_md`/
  `list_all_agents`, `schema_validator.validate_agent_md` all call `agent_spec.resolve_card_path` /
  `list_agent_ids`. JSON specs are converted to the card shape via the existing `AgentSpec` fields
  (no parallel parser); `.md` is still parsed only when a legacy/neutral **markdown** card is actually
  resolved.
- **Framework-agnostic:** zero default reads of `.opencode`; a host framework can drop `cards/` and it works.
  `agents/*.agent.json` is the single canonical source; `AgentSpec.source` records provenance (spec/cards/legacy).
- **Fail-closed, no regression:** if a neutral card is missing and legacy is not allowed, readers return
  "not found"/empty (not a silent `.opencode` read); all 65+ agents still load from `agents/`.
- **API-first:** `GET /api/v1/agents` (list ids + source kind), `GET /api/v1/agents/{id}/card` (resolved card
  + source). Introspection surfaces exactly which source won.
- **Scalable:** one directory scan, cached; no per-read globbing of `.opencode`.

## Plan (branch `feature/bi-0201-agnostic-cards`)
1. `docs/AGNOSTIC-CARDS-DESIGN.md` (this file).
2. `core/agent_spec.py` — add `cards_dir()`, `resolve_card_path()`, `list_agent_ids()`, `source_kind()`,
   `card_for(agent_id)` (JSON spec → card dict; `.md` → parsed sections), all neutral-first.
3. `core/agent_card_loader.py` — default dir = neutral (`cards_dir()`); keep `.opencode` only via legacy flag.
4. `core/agent_rules.py` — `parse_agent_md`/`list_all_agents` resolve via `agent_spec` (neutral first).
5. `core/schema_validator.py` — `validate_agent_md` + all-agents scan resolve neutral first.
6. `dashboard/api/app.py` — `/api/v1/agents`, `/api/v1/agents/{id}/card`.
7. Tests `test_agnostic_cards.py` — resolver prefers `agents/`; no default `.opencode` read; a neutral
   `cards/` dir is honored; legacy only with the flag; `agent_card_loader`/`agent_rules`/`schema_validator`
   load all agents without `.opencode`; source kind reported.
8. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
9. Merge; close `BI-0201` through the loop (and note `BI-0202` still owns the drawio binary move).

## Acceptance
- No runtime module **defaults to** reading `.opencode/agent` (grep shows no default read); legacy only with
  `ALLOW_OPENCODE_LEGACY=1`.
- All agents still load and the pipeline runs identically (smoke + full test suite).
- A neutral `cards/` dir is honored; source provenance is reported (`spec`/`cards`/`legacy`).
- `precheck` PASS; API-first introspection; no parallel card parser (one resolver).

## Out of scope (tracked separately)
`BI-0202` (move bundled drawio out of `.opencode/tools`), deleting the legacy `.md` files (archive later),
model-tier naming (`opencode-go` provider names are provider names, not framework coupling).

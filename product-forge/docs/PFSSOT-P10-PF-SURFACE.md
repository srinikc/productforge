# PFSSOT-P10 — `/pf` Command Surface (worker/scheduler API + CLI)

**Item:** BI-PF-0372 (epic BI-PF-0360) · `scripts/pf.py` + `.opencode/command/pf.md` (no new store)

One umbrella command surface over the canonical owners — a **thin client** (doc §26–28). It contains no
orchestration logic; it calls the same core/API the rest of PF uses. The standalone `PF>` TUI is a later
client of the same API.

## Verbs

| verb | maps to |
|---|---|
| `pf product …` | `scripts/pipeline.py` (product generation; the old `/pipeline`) |
| `pf backlog list\|show\|groom\|approve` | `core.backlog` / `core.grooming` |
| `pf work` | `core.work_pull.pull` |
| `pf scheduler status\|eligible\|next\|plan` | `core.scheduler` |
| `pf worker register\|list\|status\|unregister` | `core.worker_registry` |
| `pf adapters` | `core.worker_adapters` |
| `pf dispatch status\|tick` | `core.dispatcher` |
| `pf dogfood` / `pf validate` / `pf release` / `pf package` / `pf audit` / `pf status` | the matching owners |

## Clients

- **`scripts/pf.py`** — the CLI (deterministic verbs return JSON).
- **`.opencode/command/pf.md`** — OpenCode slash command `/pf <verb>`; thin adapter → `scripts/pf.py`.
- **`/pipeline`** — kept as a **deprecated alias** for `/pf product`.
- **API** — the same operations are exposed under `/api/v1/engineering/*`; added
  `GET /engineering/schedule/status` (roll-up).

## 360° check

- Thin clients only (no state, no logic); reuse `pipeline.py`/core/API. No new store.
- Worker verbs honour `WORKER_INTEGRATION_ENABLED` (P8A).
- Agents/product path untouched.

## Verification

```
python scripts/dev/pf_surface_check.py     # OK (/pf verbs + thin adapter + /pipeline alias + API routes)
python scripts/pf.py status                # JSON
python scripts/dev/precheck.py             # fast tier PASS
```

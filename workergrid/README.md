# WorkerGrid

A **producer-agnostic execution plane** for assigning work to workers. **Separate from Product Forge (PF).**
WorkerGrid reads *work* from a producer's API and writes execution status back; it does **not** create backlog,
groom, or generate products.

See `product-forge/docs/WORKERGRID-DESIGN.md` and `ADR-0002` (`product-forge/docs/ARCHITECTURE-DECISIONS.md`).

## Layout
| Path | Purpose |
|---|---|
| `wg.py` | CLI (the `/wg` surface) |
| `client.py` | Producer API client (HTTP only; no producer code imported) |
| `_cfg.py` | Config + paths |
| `config.json` | `pf_api_url`, `token_env`, `default_runtime`, `lease_seconds`, … |
| `instructions.md` | **Shared worker instructions** — edited by `/wg instruct` |
| `state/` | Local coordination state (`workers.json`, `leases.json`) |

## Usage (opencode)
```
/wg register --runtime opencode --caps python,code
/wg list
/wg work --worker WRK-…
/wg schedule eligible
/wg dispatch
/wg instruct                     # show the shared instructions
/wg instruct <text>              # append to instructions.md
/wg config                       # show resolved config + paths
```
CLI equivalent: `python workergrid/wg.py <verb>`.

## Where things are updated (edit here)
- **Instructions / worker charter:** `workergrid/instructions.md` (`/wg instruct`).
- **Config:** `workergrid/config.json`.
- **State:** `workergrid/state/*.json`.

## Producer contract
WorkerGrid consumes the producer's API (Product Forge by default):
- `GET /api/v1/engineering/schedule/next|eligible` (work / eligibility)
- `POST /api/v1/backlog/items/{id}/status` (write-back)

Stage 2 (later): extract coordination into a standalone service (Go) with a shared store + git sync.

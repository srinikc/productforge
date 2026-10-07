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
| `config.json` | `pf_api_url`, `token_env`, `default_runtime`, `lease_seconds`, `service_host`, `service_port`, … |
| `instructions.md` | **Shared worker instructions** — edited by `/wg instruct` |
| `cmd/wg-coordinator/`, `internal/` | **Go coordinator service** (Stage 3a) — `config`, `store`, `httpapi`, `producer` |
| `bin/` | Build output (`wg-coordinator`, gitignored) |
| `state/` | Local coordination state (`workergrid.db` SQLite, `workers.json`, `leases.json`) |

## Usage (opencode)
```
/wg serve                                 # run the coordinator service (Go binary)
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
Build the coordinator: `cd workergrid && go build -o bin/ ./cmd/wg-coordinator`
(`wg serve` fails closed with this hint if `bin/wg-coordinator` is missing).

## Where things are updated (edit here)
- **Instructions / worker charter:** `workergrid/instructions.md` (`/wg instruct`).
- **Config:** `workergrid/config.json` (env overrides: `WORKERGRID_HOME`, `WORKERGRID_STATE_DIR`,
  `WORKERGRID_PF_API_URL`, `WORKERGRID_TOKEN`, `WORKERGRID_LEASE_SECONDS`).
- **State:** `workergrid/state/*` (gitignored).

## Producer contract
WorkerGrid consumes the producer's API (Product Forge by default):
- `GET /api/v1/engineering/schedule/next|eligible` (work / eligibility)
- `POST /api/v1/backlog/items/{id}/status` (write-back)

Stage 3a (done): the coordinator is a **single static Go binary** — behavior pinned by the cross-impl
contract suite (`product-forge/test-framework/tests/pipeline/test_workergrid_service_contract.py`,
gate `scripts/dev/wg_go_check.py`). Still to come: worker agents, PostgreSQL for multi-node (design §6).

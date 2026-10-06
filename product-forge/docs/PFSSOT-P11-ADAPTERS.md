# PFSSOT-P11 — Additional Runtime Adapters

**Item:** BI-PF-0373 (epic BI-PF-0360) · `core/worker_adapters.py` + `core/worker.py` (no new store)

Phase 11 (doc §17) completes the runtime-adapter set so **no runtime requires scheduler redesign**. The
scheduler talks to the worker abstraction; adding a runtime is data (`runtime` on the registry), never a
scheduler change.

## Adapter set

| runtime | adapter | kind |
|---|---|---|
| `opencode` | `OpenCodeAdapter` | optional CLI client (first adapter) |
| `claude-code` | `ClaudeCodeAdapter` | optional CLI client (**new**) |
| `remote` | `RemoteWorkerAdapter` | pull-based remote session (**new**) |
| `command` | `CommandAdapter` | local/test runtime (runs a command in the worktree) |
| `native` | `NativeAdapter` | PF-native path (declared; agents stay native) |

All CLI adapters run through the shared `_run_provider()` helper (one place; adapters stay thin
translators). `ClaudeCodeProvider` was added to the existing provider registry (`core/worker.py`).

## Optional by construction

- `opencode` / `claude-code` — `available()` is `shutil.which(...)`; `start()` **degrades to BLOCKED** when
  the CLI is absent. Neither is a PF dependency.
- `remote` — endpoint/pull-based: `start()` records the assignment and returns `dispatched`; the remote
  worker pulls work via `/api/v1/engineering/work` (`core.work_pull`). No local process, no scheduler change.

## 360° check

- Scheduler, worker registry, `config/engineering-workers.json` unchanged (runtime is data; the config stays
  capacity/capability only — runtimes are never named as an architecture dependency).
- Core imports no adapter (worker layer remains optional/removable; `WORKER_INTEGRATION_ENABLED`).
- API `/engineering/adapters` and `pf adapters` list the new runtimes automatically.

## Verification

```
python scripts/dev/adapters_check.py   # contract verbs + opencode-first + remote dispatch + claude degrade
python scripts/dev/worker_check.py     # provider registry (incl. claude-code) + isolated run
python scripts/pf.py adapters          # lists opencode/claude-code/remote/command/native
```

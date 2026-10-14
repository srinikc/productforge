# Merge / Drift / Conflict — GitHub Backlog Handling

**Scope:** Product Forge's *own* backlog + issues + the multi-session GitHub workflow (`srinikc/productforge`, integration branch `develop`).
**Related:** ADR-0006 (Enterprise Data Plane), EPIC `BI-PF-1292` (EDP), EPIC `BI-PF-0360` (Backlog SSOT + scheduler + workers), `docs/WORKER-SCHEDULER-OPERATIONS.md`, IS-PF-0036 (one working tree per session), `docs/BRANCHING-GIT-WORKFLOW.md`.

> This document records the **problem**, the **root cause**, the **stopgaps in place**, and the **plan + execution order** that eliminates the class. It is the authority for *why* the EDP/backlog work is sequenced the way it is.

---

## 1. Problem observed

Across sessions we repeatedly hit:

- **Merge conflicts** on shared backlog files: `data/backlog/open.json`, `closed.json`, `items/<epic>.json`, `counters.json`, `config/id-blocks.json`.
- **"Stale / dirty / drift"** — a session edits the backlog, another session's tree goes stale; derived docs (`BACKLOG-SUMMARY.md`, `documentation-index.html`) go out of date and race `develop`.
- **Cross-session interference** — one session edits items/epics owned by another (e.g. another session edited `BI-PF-1326–1332` briefs + epic `children[]`).
- **Red `develop`** — a merged PR leaves the integration branch broken (unregistered data files, `ROOT` re-derivation, test pollution), blocking *every* PR until fixed.
- **Moving target** — `develop` advances between push and CI, so a PR merge can reintroduce the same class of conflict.

Net effect: backlog handling → conflicts → someone patches → something else drifts. It compounds.

---

## 2. Root cause

The backlog and issues are **simultaneously**:

1. the **single source of truth**,
2. a **git-tracked artifact**, and
3. **edited concurrently by many sessions** (multiple clones/worktrees).

Every write therefore touches **shared files that git must merge**, and `develop` moves underneath. Leases prevent *double-claim*, but **nothing** prevents *file contention*. This is structural, not a tooling bug — it can only be removed by **externalizing state** and **stopping git from carrying live state**.

---

## 3. Stopgaps in place (reduce, don't eliminate)

| Stopgap | What it does | Limit |
|---|---|---|
| `pf-derived` merge driver (`.gitattributes`) | Regenerates `open/closed.json` from `items/`; max-merges `counters`/`id-blocks` | `items/<epic>.json` briefs are still content; item files can conflict |
| Derived-docs non-blocking (`docs-fresh` WARN; `--strict` in full sweep) | Removes the derived-doc race from per-change gates | Doesn't stop item/index conflicts |
| `backlog-context` / `backlog-epic` **baseline-aware** | Fatal only for NEW drift; grandfathered pre-existing | Existing drift persists; new drift still possible |
| `backlog-context` **always-run** + `changed-tests` + `prepush` tests | Catch backlog/test gaps earlier | Still gitting live state |
| `BI-PF-0374` bookkeeping precheck tier | Cheap minimal tier for derived/bookkeeping changes | Doesn't remove contention |
| One working tree per session (IS-PF-0036) | Avoids same-folder git races | Requires discipline; not enforced |

**Conclusion:** these make the current model *survivable*, not *stable*. The fix is the one-time externalization below.

---

## 4. Target model (the one-time fix)

- **One canonical repo + `git worktree` per session**; **all backlog writes go through the single running API** (never hand-edit another tree).
- **Backlog + issues live in the PostgreSQL system of record** (EDP). JSON files become **read-only projections** rebuilt from the DB.
- **Git carries code + reviewed config only — never live operational state.**
- **Transactionally-allocated IDs** (no local `id-blocks` minting → no collisions).
- **One job/lease truth** (reuse WorkerGrid store, ADR-0003).

After this, "which clone has which files" disappears; conflicts/drift/stale stop by construction.

---

## 5. Plan & execution order

Phases are **gates**, not calendar. We are currently in **Wave 0**; the **Wave 1 core** is what stops the conflicts and is pulled forward.

### Wave 0 — Baseline & orchestration quick-wins (largely DONE)
- ✅ `BI-PF-1325` WG-O1 — `PF_API_TOKEN` canonical.
- ✅ `BI-PF-1293` EDP-01 — storage/data ADR + baseline pin.
- ✅ `BI-PF-1294` EDP-02 — store classification + completeness gate + data-flow inventory.
- ✅ `BI-PF-1295` EDP-03 — de-commit runtime SQLite DBs.
- ✅ `BI-PF-1299` EDP-07 — provider-neutral storage **interfaces + conformance (Go)**.
- Remaining quick-wins: `BI-PF-1327` WG-O3 (canonical repo + worktree + **API-only writes**), `BI-PF-1326` WG-O2 (start wrapper + fetch), `BI-PF-1328` WG-O4 (merge-driver coverage), `BI-PF-1329` WG-O5 (claim-specific).

### Wave 1 — Conflict-stopping core (PULL FORWARD — next priority)
1. **`BI-PF-1300` EDP-08** — versioned migration framework + DB roles + schema-ownership (prereq).
2. **`BI-PF-1309` EDP-17** — canonical Postgres schema (tenants, projects, **backlog, issues**, runs/stages, artifacts metadata, jobs, outbox, audit, usage/quotas).
3. **`BI-PF-1310` EDP-18 + G1** — migration/import tooling (parity, rollback, cutover) + **git decoupling**: backlog/issues move to the DB; JSON becomes projections; **git stops carrying live state**.
4. **G3** — transactional central ID authority.
5. **`BI-PF-1327` WG-O3** — canonical repo + worktrees + **API-only backlog writes**.

**Exit gate:** creating/updating an item is a DB transaction; parallel sessions produce **no** git conflicts on operational state; IDs never collide.

### Wave 2 — Durable jobs / outbox / audit / eventing
- `BI-PF-1311` EDP-19 (JobStore/OutboxStore + leases; one job truth), `BI-PF-1312` EDP-20 (AuditStore), `BI-PF-1265` eventing SSOT.

### Wave 3 — Remaining data-plane features
- Object store/artifacts (`BI-PF-1305/1306/1307/1308`), memory (`BI-PF-1313`).

### Wave 4 — Family: perf/backup/recovery, security, tenancy, residency
- `BI-PF-1314` EDP-22, `BI-PF-1315` EDP-23, `BI-PF-1296` EDP-04, `BI-PF-1301` EDP-09, `BI-PF-1302` EDP-10, `BI-PF-1297` EDP-05, `BI-PF-1303/1304` EDP-11/12.

### Wave 5 — Scale / isolation (evidence-gated)
- `BI-PF-1317` EDP-24.

---

## 6. Coordination rules (until Wave 1 lands)

1. **One working tree per session** (IS-PF-0036): never two sessions in one folder; use a clone or `git worktree`.
2. **Do not edit another session's items/epics.** Changes to backlog state go through the API (or your own clone); never hand-edit a foreign tree.
3. **Stay close to `develop`:** `python scripts/dev/sync_develop.py` at task start (merge, never rebase); the pre-commit/pre-push hooks run it.
4. **Bookkeeping/derived changes stay their own commit** (branch guard); prefer the bookkeeping precheck tier.
5. **A code change that mutates the backlog** is checked by the always-run `backlog-context/-ids/-epic` invariants (baseline-aware).
6. **Red `develop` is a P0:** raise issue → RCCA → fix → guard; do not admin-merge around it.

---

## 7. Success criteria

- A PR that adds/updates a backlog item merges with **no conflict** on `open/closed/counters/id-blocks/items`.
- A session can work in parallel with others with **no stale/dirty tree** and **no cross-session content conflict**.
- IDs are **unique** across sessions by construction.
- `develop` stays green; a red is caught by the **scheduled full sweep**, not by every PR.

---

## 8. References

- ADR-0006 — Enterprise Data Plane (`docs/ARCHITECTURE-DECISIONS.md`).
- EDP roadmap — `docs/Product_Forge_Enterprise_Performance_Security_DB_Storage_Roadmap.md` (§15 work breakdown).
- `docs/WORKER-SCHEDULER-OPERATIONS.md`, `docs/BRANCHING-GIT-WORKFLOW.md`.

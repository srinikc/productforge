# Neutral Vendored Tools — Design (BI-0202)

## Goal
`core/diagram_render.py` locates the bundled draw.io CLI at `.opencode/tools/drawio/draw.io.exe` (~485 MB),
coupling the product to the `.opencode` tree for a **generic** tool. Move bundled tools to a **neutral vendor
location** so nothing depends on `.opencode`; keep the binary **out of normal git** (fetch-on-demand / LFS)
and document the dependency. Fail with a clear error when absent. Framework-agnostic, scalable, API-first.

## 360° — verified current state
| Concern | Now | Target | Owner |
|---|---|---|---|
| drawio CLI resolution | `diagram_render._drawio_cli`: env `PIPELINE_DRAWIO_CLI` → `.opencode/tools/drawio/draw.io.exe` → PATH | env → **neutral vendor** → PATH | reuse + repoint |
| Bundled binary | ~485 MB under `.opencode/tools/drawio/` | neutral `vendor/drawio/` (gitignored; fetch) | move |
| Vendor dir contract | none | documented (`docs/VENDORED-TOOLS.md`) + a `vendor/` resolver | new |
| Audit allowlist | `wired_audit.py:107` allowlists `.opencode/tools` | keep (legacy read-compat) + add `vendor/` | extend |

**Blast radius:** `core/diagram_render.py` (path chain), a small neutral resolver (`core/vendor.py` or a
helper in `paths.py`), a vendor README, `.gitignore`, a fetch helper. No behavior change when the CLI is
found via env/PATH. **The 485 MB binary itself is not committed** (deletion/move of the actual artifact is an
ops step; this change repoints resolution + documents the neutral location).

## Design decisions (modular, 1 truth per concern)
- **Neutral vendor contract (`core/vendor.py`, single owner):**
  - `vendor_dir() -> <root>/vendor` (neutral, outside `.opencode`).
  - `resolve_tool(name, subpaths, env_var) -> Optional[path]`: order = env var → `vendor/<name>/<subpath>` →
    PATH (`which`). So a tool resolves with **zero `.opencode` dependency**.
  - `missing_hint(name, env_var)`: a clear, actionable error string ("place the CLI at vendor/<name>/… or set
    <env_var> or install on PATH").
- **Repoint `diagram_render`:** `_BUNDLED_DRAWIO` becomes `vendor/drawio/draw.io.exe` **via `vendor.resolve_tool`**;
  keep `.opencode/tools/drawio` as a **legacy fallback only** (non-default) so existing setups don't break —
  consistent with the BI-0201 agnostic pattern. Update the docstring to name the neutral path.
- **Vendor dir is not committed:** add `vendor/` (except `vendor/README.md`) to `.gitignore`; document the
  fetch/placement in `docs/VENDORED-TOOLS.md`. Optional `scripts/dev/fetch_vendor.py` helper prints/executes
  the download command (no secrets, idempotent, verifies size).
- **Reuse, never fork:** `paths.py` stays the root SSOT; `vendor` is a neutral location under it. One resolver.
- **Fail-closed/clarity:** if no renderer is available, the existing soft-skip stays, but the error names the
  neutral location + alternatives (no silent `.opencode` assumption).
- **API-first:** `GET /api/v1/vendor/tools` (which vendored tools are resolvable + their paths/source:
  env|vendor|path), so operators can see tool availability without guessing.

## Plan (branch `feature/bi-0202-vendor-tools`)
1. `docs/VENDORED-TOOLS.md` (this design + placement/fetch).
2. `core/vendor.py` — `vendor_dir`, `resolve_tool`, `missing_hint`, `list_tools`.
3. Register the `vendor/` location (no new data store; document in `store-registry` concerns? no — it is a
   filesystem location, not a state store; note in the design).
4. `.gitignore` — ignore `vendor/` binaries, keep `vendor/README.md`.
5. `core/diagram_render.py` — resolve via `vendor.resolve_tool`; neutral path; legacy `.opencode` fallback
   only; clearer error.
6. `dashboard/api/app.py` — `GET /api/v1/vendor/tools`.
7. `scripts/dev/fetch_vendor.py` — idempotent helper to place/download a vendored tool.
8. Tests `test_vendor.py` — resolution order (env → vendor → path); neutral path used; legacy fallback only
   when allowed; missing ⇒ clear hint; `diagram_render._drawio_cli` honors env + vendor + never *defaults* to
   `.opencode`; API shape.
9. Gates: compileall, wired_audit, workflow_matrix, pipeline tests, precheck.
10. Merge; close `BI-0202` through the loop.

## Acceptance
- `diagram_render` resolves drawio via env / neutral `vendor/` / PATH with **no `.opencode` default**; a
  missing tool yields a clear, neutral-location error.
- The vendor location + fetch are documented; the large binary is not committed.
- `precheck` PASS; API exposes vendor tool resolution; zero regression when the CLI is on PATH/env.

## Out of scope (tracked separately)
Actually downloading the 485 MB binary in CI, LFS migration (an ops decision), migrating the other
`.opencode/tools/*.py` helper scripts (dev-only, not runtime).

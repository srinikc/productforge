# vendor/ — neutral vendored tools

Large / third-party CLI binaries used by Product Forge live here, **outside** the `.opencode` tree, so the
product has no dependency on `.opencode` (BI-0202). Binaries are **not committed** (see `.gitignore`); they
are fetched/placed on demand.

## draw.io desktop CLI (used by `core/diagram_render.py`)

Expect it at:

```
vendor/drawio/draw.io.exe
```

Resolution order (first match wins), owned by `core/vendor.py`:

1. env `PIPELINE_DRAWIO_CLI` (explicit path)
2. `vendor/drawio/draw.io.exe` (this neutral location)
3. `drawio` / `draw.io` / `drawio.exe` on `PATH`
4. legacy `.opencode/tools/drawio/draw.io.exe` — **only** when `ALLOW_OPENCODE_TOOLS_LEGACY=1`

If none is found, diagram rendering soft-skips with a clear hint; nothing defaults to `.opencode`.

Placement helper: `python scripts/dev/fetch_vendor.py drawio` prints the neutral target and how to obtain
the CLI (headless draw.io desktop). See `docs/VENDORED-TOOLS.md`.

# Product BOM / Footprint — Design (BI-0217)

## Goal
At the **packaging** stage (stage `9`), emit `products/<project>/artifacts/9 - Package/BOM.json`:
the product's footprint (dependencies, declared licenses, file count/sizes, checksums). It is the
single source for the shipped bill-of-materials and is already surfaced read-only by
`core/product_page.bom()` and the dashboard (`/api/v1/products/<p>/…`).

## Ownership (one writer)
- **Writer:** `core/bom.py` — the only module that writes `BOM.json`.
- **Consumers (read):** `core/product_page.bom()`, dashboard product page.
- **Store registry:** `BOM.json` (kind=`derived`, scope=`project`, visibility=`shared`).

## Schema (`schema: product-forge/bom@1`)
```
{
  "schema": "product-forge/bom@1",
  "project": "<name>",
  "generated_at": "<iso>",
  "source_dir": "artifacts/9 - Package | <project_root>",
  "dependencies": { "python": ["pkg==1.0", ...], "node": ["pkg@1.0", ...] },
  "licenses": ["MIT", "Apache-2.0", ...],          # declared in manifests only
  "footprint": {
    "file_count": <int>,
    "total_bytes": <int>,
    "checksums": { "<relpath>": "sha256:<hex>" }    # bounded (max_files)
  },
  "limits": { "max_files": 500, "max_bytes_per_file": 20000000 }
}
```

## Inputs / decisions
- **Source dir:** packaged output `artifacts/9 - Package/` if it exists, else the project root.
- **Dependencies:** best-effort manifest parse — `requirements.txt`, `pyproject.toml` (PEP 621
  `dependencies`), `package.json` (`dependencies`/`devDependencies`). No network, no license
  inference beyond what manifests declare.
- **Checksums:** SHA-256 per file, **bounded** (`max_files=500`); files larger than
  `max_bytes_per_file` record size only (no hash). Deterministic, sorted.
- **Never fatal:** `build()` returns a dict; `write()` best-effort (mirrors the other
  artifacts); a failure is logged, never raised into the pipeline.

## Wiring
- `core/orchestrator/stage_runner.py`: after stage `9`, `from core import bom; bom.write(self.project_dir)`
  (guarded).
- `scripts/pipeline.py`: `bom <project>` subcommand → `bom.write(...)` + summary.
- `config/store-registry.json`: register `BOM.json`.

## Verification
- Unit test: build() over a temp project with a `package.json` + a file → dependencies, footprint,
  checksums present; write() creates the file at the expected path.
- Gates: `compileall`, `wired_audit` (module wired + store registered), `workflow_matrix`, pipeline
  tests, `precheck`.

## Out of scope (tracked separately)
- Transitive dependency resolution, license-compliance verdicts, SBOM formats (CycloneDX/SPDX),
  signatures/attestation. This is a **footprint manifest**, not a signed SBOM.

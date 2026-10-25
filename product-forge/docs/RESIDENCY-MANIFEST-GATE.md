# Residency manifest and build/deploy gate (EDP-12)

Every generated product declares where its data lives. The declaration is the **residency section** of
`packaging-manifest.json`; `config/residency-manifest.json` is the IN template, and
`products/<project>/residency-manifest.json` overrides it. **`home_region` is required** (no silent US default);
missing/unknown home fails closed.

## Manifest (schema_version 1.0)

```json
{
  "schema_version": "1.0",
  "data_classes": ["product_metadata", "generated_source", "build_evidence"],
  "home_region": "IN",
  "allowed_regions": ["IN"],
  "backup": {"regions": ["IN"], "encrypted": true, "frequency": "daily"},
  "kms": {"provider": "local", "region": "IN", "rotation_days": 90},
  "egress": {"allowed_regions": [], "subprocessors": []},
  "retention": {"days": 365, "legal_hold": false}
}
```

`backup.frequency` is one of `hourly|daily|weekly|monthly`. `retention.legal_hold=true` keeps data but exempts the
policy maximum; `days` must still be > 0.

## Authority and bounds

- `config/residency-profiles/<home>-v1.json` (counsel-owned; `in-v1`, `us-v1`) is authoritative.
- `allowed_regions` must be a subset of the profile's allowed regions; `home_region` must be in both.
- `backup.regions`, `kms.region` and `egress.allowed_regions` must be within the profile's allowed regions.
- The **Go validator** (`go/residencymanifest`, CLI `cmd/pfresidency`) is the build/deploy authority.
  `core.packaging.validate` is the fast pre-build shape/home check with the same invariants; the conformance
  fixtures fail if the two disagree.

## Gate

`python scripts/dev/residency_gate.py [--scope ...] [--project ...] [--mode warn|block] [--report]`

- `gate_mode` in `config/residency-policy.json` defaults to **warn** for the first release; flip to **block** after
  products are warn-clean. The policy carries `gate_mode_ticket`/`gate_mode_expires`; a flip is a recorded decision.
- Unknown/missing home, unreadable profile/policy and validator/toolchain failures **always block**, even in warn.
- `--report` is non-fatal and prints the JSON report.
- Each run writes `engineering/residency-gate.json` (last run) and a bounded `engineering/residency-gate.jsonl`
  (5 MB rotation, 3 files). The report carries `report_version: 1`.

## Error codes (frozen)

`RESIDENCY_UNKNOWN_HOME`, `RESIDENCY_HOME_NOT_ALLOWED`, `RESIDENCY_BACKUP_REGION`, `RESIDENCY_KMS_REGION`,
`RESIDENCY_EGRESS_REGION`, `RESIDENCY_RETENTION`, `RESIDENCY_MISSING_GROUP:<group>`, `RESIDENCY_UNKNOWN_FREQUENCY`,
`RESIDENCY_BACKUP_UNENCRYPTED`, `RESIDENCY_KMS_ROTATION`, `RESIDENCY_INVALID_FIELD:<field>`, `RESIDENCY_SCHEMA_VERSION`, `RESIDENCY_PROFILE_UNREADABLE`,
`RESIDENCY_VALIDATOR_UNAVAILABLE`, `RESIDENCY_MANIFEST_UNREADABLE`, `RESIDENCY_MANIFEST_INVALID`.
Adding/removing a code is a versioned contract change.

## Ownership / rollback

- `config/residency-profiles/**`: counsel (EDP-05), single owner.
- `config/residency-manifest.json` + `packaging-manifest.json`: `core/packaging.py` (single writer).
- `config/residency-policy.json`: `go/backupdrill/region.go` (region cells) + the `gate_mode` rollout lever; changes
  are a recorded decision.
- Rollback: set `gate_mode=warn` (policy violations only) or revert. Existing manifests are regenerated; rebuild any
  cached `packaging-manifest.json`.

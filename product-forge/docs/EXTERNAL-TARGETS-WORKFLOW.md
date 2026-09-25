# External Targets & Deployment — E2E Workflow (for review)

> How Product Forge handles deployment targets, vendor labs, and artifact
> registries **without owning infrastructure**: the user/vendor provides the
> target + credentials; the pipeline selects an adapter, runs setup automation
> (scripts we provide), deploys, verifies, tests, and reports — all gated by QA
> Go/No-Go and HIL.

---

## 0. Targets are DYNAMIC (recommended), not a flat list
"Target" has **two layers**:
1. **Delivery surface** (where the end customer loads it): `web | mobile | desktop | cli | api | library`.
2. **Deployment substrate** (where we deploy): `local | docker | kubernetes | helm | terraform | ansible | remote-linux/windows | <cloud> | <vendor>`.

`core/target_advisor.py` derives a **ranked shortlist** (recommended first, default) from:
product idea, tech stack (`tech-stack.json`), architect `infra.json`, product/marketing
signals, and explicit end-customer constraints (`project.json → deploy.target`).

Precedence: **explicit > recommendation > default**; HIL confirms; the full 19-target
catalog stays available ("show all"). Emits `docs/targets.md` + `docs/targets.json`
at the architect stage. The pipeline then **asks HIL** (default `local` when
non-interactive), records the choice, and the deploy stage consumes it.

---

## 1. Concepts
- **Provider** — how we deploy: `docker | local | command | kubernetes | helm | terraform | ansible | <cloud>` (`core/deploy_providers.py`).
- **Vendor** — who owns the hardware/cloud/lab: vmware/dell/hp/cisco/netapp/s3/aws/azure/gcp/postgres/oracle (`core/vendor_adapters.py`).
- **Registry** — where artifacts live: local | s3 | gcs | azure | oci | http(Artifactory/Nexus) (`core/artifact_registry.py`).
- **Verification policy** — `internal` (we run it) | `external` (needs a lab/vendor) | `not_run` (`core/verification_policy.py`).

**Principle:** we never fabricate verification. Target + credentials are **user-provided**; we provide adapters + setup automation + gates.

---

## 2. What the user provides vs what we provide
| Item | User / Vendor | Product Forge |
|---|---|---|
| Git repo, CI platform | ✅ | templates + scripts |
| Deploy target (k8s cluster, cloud, vSphere, device) | ✅ | adapter + setup script |
| Credentials/secrets (keys, tokens, kubeconfig) | ✅ (via env / secret refs) | secret refs only (never stored in repo) |
| Vendor lab handle (vCenter/iDRAC/OneFS/…) | ✅ | `vendor_adapters` (command-driven) |
| Artifact registry | ✅ (or local) | backend adapter + `md5/sha256 + GPG` |
| Setup automation per target | — | **scripts catalog (below)** |
| Deploy/verify/test/report/fix loop | — | pipeline (gated by QA Go/No-Go + HIL) |

---

## 3. How the user declares a target
```jsonc
// project.json
{
  "deploy": {
    "target": "kubernetes",           // provider (docker|local|kubernetes|helm|terraform|ansible|aws|gcp|azure|...)
    "staging":    { "url": "https://stg.example", "namespace": "app-stg" },
    "production": { "url": "https://app.example", "namespace": "app-prod" },
    "require_staging": true,
    "approval_required": true
  },
  "artifact_registry": { "backend": "oci", "registry": "ghcr.io/org" },   // or local (default)
  "signing": { "key_id": "ABCD1234" }                                     // or org secret (GPG_PRIVATE_KEY)
}

// docs/infra.json (architect emits; user confirms)
{
  "compute": "kubernetes", "storage": "s3", "members": ["postgres"],
  "vendors": [
    { "name": "vmware", "lab_handle": "vcenter.lab.example",
      "commands": { "apply": [["govc","import.ova","..."]], "verify": [["govc","vm.info","..."]] } }
  ]
}
```

---

## 4. E2E flow (target provided → deployed → tested → fixed)
```
[3a Spec Review] → ... → [10a QA Go/No-Go]
                                   │ GO (or HIL override)
                                   ▼
   select provider/vendor  ──►  SETUP (if needed)  ──►  APPLY  ──►  VERIFY (health/smoke)
   (deploy_providers)          (scripts catalog)       (adapter)     (internal or external)
                                   │                                   │
                                   ▼                                   ▼
                         credentials from env/ref                 run tests (functional/e2e/NFR)
                                                                       │
                                                          results → test framework → defects
                                                                       │
                                                          fail → fix agent → rebuild → redeploy (loop)
                                   │
                    staging first (always) ──► HIL approve ──► production (canary/blue-green)
                                                                       │
                                                          post-deploy smoke → monitor → rollback on fail
```

---

## 5. Setup automation catalog (what we provide)
Scripts are **generated/selected when the user picks a target** (kept out of the repo runtime; run by the pipeline or by the user):

| Target | Setup script (we provide) | Purpose |
|---|---|---|
| `local`/`docker` | `scripts/setup/docker_local.*` | compose up/down, health |
| `kubernetes` | `scripts/setup/kind_k8s.*` | create a local kind cluster (if none) |
| `helm` | `scripts/setup/helm_bootstrap.*` | repos/namespaces |
| `terraform` | `scripts/setup/terraform_backend.*` | init/state/plan (cloud creds) |
| `ansible` | `scripts/setup/ansible_inventory.*` | inventory/ssh from config |
| `oci` registry | `scripts/setup/oci_registry_local.*` | run a local registry (docker) |
| `s3` registry | `scripts/setup/minio_local.*` | local S3 (MinIO) for artifact publish |
| vendor | `scripts/setup/vendor_lab_check.*` | validate CLI + lab handle reachability |

Each script is **guarded**: if the target/tooling/creds are missing → it reports `not_run` and the pipeline asks HIL for the target/credentials (never fabricates).

---

## 6. HIL touchpoints
1. **Choose target** (if not declared) — plain-language options (local docker / existing k8s / cloud / vendor lab).
2. **Provide credentials** — env vars or secret refs (we never store them).
3. **Vendor lab handle** — for hardware/vendor verification (`external`).
4. **Approve production** — `develop → main` + prod deploy require HIL.
5. **Override** — QA NO-GO override (`qa.override_gonogo`) and PR merge override (`qa.override_merge`).

---

## 7. Verification policy per target
| Target | Verification |
|---|---|
| docker/local/kind | `internal` (we run health + smoke + tests) |
| cloud (aws/gcp/azure) | `internal` if creds provided, else `external` |
| vendor (vmware/dell/hp/cisco/netapp) | `external` (lab handle required) |
| registry publish | `internal` (checksums + signature) |

Surfaced in `qa-manifest.json → verification_policy` and the Go/No-Go matrix row **"Verification coverage"**.

---

## 8. Review questions
1. **Scripts catalog**: ship the above starter scripts now (local docker/kind, local OCI registry, MinIO/S3)? (recommended)
2. **Target prompt**: if `project.json` has no `deploy.target`, should the pipeline **prompt HIL** with the catalog, or default to `local`?
3. **Cloud creds**: standard env names we should expect (e.g. `AWS_*`, `AZURE_*`, `GOOGLE_*`, `KUBECONFIG`)?
4. **Default registry**: keep `local` (files under `products/<p>/.artifacts/`) unless the user sets one? (recommended)
5. **Vendors**: which labs do you actually have (so we add their exact CLI/handles)?

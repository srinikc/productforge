# Entitlements · Licensing · Editions · Packaging — end-to-end map

**Who this is for:** operators, engineers, and reviewers who need to understand how Product Forge's
*paid features* work: what a customer is allowed to use, how that is enforced, and how the different
build/distribution variants relate. Every term is expanded on first use.

**Companion diagram:** [`docs/diagrams/licensing-entitlements-editions.drawio`](diagrams/licensing-entitlements-editions.drawio).

**Status:** descriptive of what exists **today**, with one **OPEN decision** flagged in
[§7 Feature groups](#7-feature-groups-open--needs-operator-review).

---

## 0. Glossary (plain language)

| Term | Meaning |
|---|---|
| **Feature group (G1–G10)** | A *bundle of capabilities* used as the unit of entitlement. e.g. `G6` = "Collaboration & Tenancy". |
| **Tier** | A *license level* you buy: `trial`, `starter`, `pro`, `enterprise`. A tier unlocks a set of feature groups + limits. |
| **Entitlement** | What a tier is *allowed*: its feature groups + seat/parallel limits. Decision helper: `licensing.entitlements(tier)`. |
| **License key** | A signed token that encodes a tenant's **tier**. Issued by the vendor; verified by the product. |
| **Edition** | A *build/distribution variant* you install: `community`, `saas`, `enterprise`, `on-prem`, `oem`. Each maps to a default tier + deploy target + distribution kind. |
| **Packaging manifest** | A file describing an edition: metadata, its **entitlement requirement**, SBOM (Software Bill of Materials), deployment target, and provenance. |
| **SBOM / LBOM** | Software / License Bill of Materials — the inventory of components and their licenses. |
| **Tenant** | An isolated customer account (org) inside a PF install. |
| **Seat** | A named user slot a tier allows. |
| **HMAC** | *Symmetric* signature: the same secret signs **and** verifies (the old scheme; the secret had to ship). |
| **Ed25519** | *Asymmetric* signature: a **private key signs**, a **public key verifies** (the new scheme; the private key never ships). |
| **Entitlement-at-boundary** | Checking permission **at the moment an action runs** and refusing if not allowed (fail-closed). |
| **Fail-closed** | If anything is unknown/unavailable → **deny**. |
| **REL-0** | The release gate; **licensing/pricing/entitlement decisions are human-governed**. |
| **FEATURE_PR** | The pre-merge validation profile the delivery lane runs. |
| **A2 / A3 / A4** | EPIC-A work packages: licensing (`A2`), compiled packaging (`A3`), edition delivery manifest (`A4`). |

---

## 1. The two axes (do not conflate)

- **Tier** = *what you're allowed* (license level). Owned by `config/licensing-tiers.json`.
- **Edition** = *what you install* (build/distribution variant). Owned by `core/packaging.py` (`EDITIONS`).

An **edition** declares a **default tier**; a **license key** grants a **tier** to a **tenant**; the tier
resolves to **entitlements** (feature groups + limits), which are **enforced** at boundaries.

---

## 2. Feature groups (G1–G10) — titles only today

| Group | Title | Group | Title |
|---|---|---|---|
| **G1** | Core Orchestration & Portfolio | **G6** | Collaboration & Tenancy |
| **G2** | Discovery & Design | **G7** | Intelligence (chat/learning/model-rec/BYOT) |
| **G3** | Quality & Compliance | **G8** | Content & Media |
| **G4** | Build/Deploy/Ops | **G9** | Platform Ops & Licensing (operator-only) |
| **G5** | Intake & Work Management | **G10** | Extensibility & API |

> ⚠️ These are **only titles**. There is **no per-feature → group mapping** in the repo, and this
> mapping was **not operator-reviewed**. See [§7](#7-feature-groups-open--needs-operator-review).

---

## 3. Tiers → feature groups + limits (`config/licensing-tiers.json`)

| Tier | Feature groups unlocked | Seats | Parallel projects |
|---|---|---|---|
| **trial** | G1, G2, G5 | 3 | 1 |
| **starter** | G1, G2, G3, G5, G10 | 10 | 3 |
| **pro** | G1, G2, G3, G4, G5, G6, G10 | 50 | 10 |
| **enterprise** | all (G1–G10) | unlimited | unlimited |

*(`0` = unlimited, bounded by the global capacity governor.)*

---

## 4. Editions → default tier / target / distribution (`core/packaging.py`)

| Edition | Default tier | Deploy target | Distribution |
|---|---|---|---|
| **community** | trial | local | open-source |
| **saas** | pro | docker | hosted |
| **enterprise** | enterprise | kubernetes | commercial |
| **on-prem** | enterprise | docker | commercial |
| **oem** | enterprise | command | white-label |

---

## 5. Feature group → tiers → editions (derived)

| Group(s) | Included by tiers | Editions (via default tier) |
|---|---|---|
| G1, G2, G5 | trial, starter, pro, enterprise | all |
| G3, G10 | starter, pro, enterprise | saas, enterprise, on-prem, oem |
| G4, G6 | pro, enterprise | saas, enterprise, on-prem, oem |
| G7, G8, G9 | enterprise only | enterprise, on-prem, oem |

---

## 6. How a license key works

- **Token shape:** `PF-<base64(payload)>.<base64(signature)>` where `payload` includes `tenant`, `tier`, `seats`, `exp`.
- **Before (legacy):** signature was **HMAC** (symmetric) with a secret stored in the product
  (`data/licensing/.signing-key`) → forgeable if the product is inspected.
- **After A2:** signature is **Ed25519** (asymmetric). The **vendor private key signs**; the **product
  verifies with a public key** (`data/licensing/license-public-key` or env `PF_LICENSE_PUBLIC_KEY`).
  The **private key never ships** (env `PF_LICENSE_PRIVATE_KEY`, signing environment only).
  Implemented in the Go core (`go/pfcore/license.go`: ops `license.keygen` / `license.issue` /
  `license.verify`), called from `core/licensing.py` through `core/go_host.py`.
- **Consequence:** legacy HMAC keys **stop verifying** and must be re-issued (pre-release; acceptable).

---

## 7. Feature groups — OPEN / needs operator review

**Problem:** the groups and the tier→group membership are **implicit** (titles only). Entitlements are
**contractual**, so they must be explicit and operator-approved. **Tracked as item `BI-PF-1264`.**

**Questions for the operator:**
1. What concrete capabilities/APIs/screens belong to **each** group (G1–G10)?
2. Is the **tier → group** membership correct (which tier unlocks which group)?
3. Are the **limits** (seats, parallel projects) right per tier?
4. Which group gates the **worker/orchestration** subsystem (used by A2 enforcement)?

---

## 8. Flows (end-to-end)

### 8.1 Internal / operator
1. Run with `INSTANCE_ROLE=operator` (platform-admin).
2. Provision a tenant + issue a license: `POST /api/v1/tenants/{tenant}/license` → `licensing.issue_key`
   (signs with the **vendor private key**) → stored in `data/licensing/licenses.json`.
3. Billing/checkout: `POST /api/v1/tenants/{tenant}/checkout` → `core/billing.py::checkout` → provisions the tenant.
4. Inspect entitlements: `GET /api/v1/tenants/{tenant}/entitlements`.

### 8.2 Customer (tenant)
1. Their install runs `INSTANCE_ROLE=tenant` (the default).
2. They receive a **license key**.
3. On use, `licensing.verify_key(key)` → the Go core verifies with the **public key** → the **tier**.
4. Actions are gated by **entitlement-at-boundary** (`require_entitlement` / `enforce_for_instance`); a
   forged/edited key or an unentitled action is **refused (fail-closed)**.
5. Seats/members: `core/tenancy.py` (`invite`, `seats`) enforce the tier's seat count.

### 8.3 OEM (white-label / embedded)
1. Built as the **`oem` edition** (white-label, enterprise tier, `command` target).
2. The OEM signs licenses with **its own private key** and ships **its public key** to its customers — the
   same asymmetric flow as 8.2, with the OEM's keypair.
3. Uses the same Enterprise/SaaS/OEM API (`api/routers/enterprise.py`).

---

## 9. Build · packaging · CI-CD (who / when / how / purpose)

| Stage | Trigger | Who / how | Purpose | Path |
|---|---|---|---|---|
| Implement change | item claimed | **worker** in a worktree | produce a validated change | `core/worker`, `workergrid/` |
| Local gates | before completing | worker runs **precheck** (compile, wired-audit, language-rule, store-check, pipeline tests) | mechanical quality | `scripts/dev/precheck.py` |
| Merge | item completed (after operator **Gate 2**) | **delivery lane**: push → **FEATURE_PR** validation → merge to `develop` | controlled, validated merge | `core/delivery.py`, `core/validation_engine.py` |
| CI | **push** to main/develop + **every PR** | GitHub Actions `structure` workflow | enforce structure/naming/registry + full precheck | `.github/workflows/structure.yml` |
| Go build | invocation / tests | `go build` (on demand) | compile the native Go core | `core/go_host.py`, `go/pfcore` |
| Packaging (today) | operator/API | `core/packaging.py::build()` + `POST /packaging/build` | produce/validate the **edition manifest** (entitlement, SBOM, target) | `core/packaging.py`, `api/routers/packaging.py` |
| Release | release time | `core/release.py::gate()` + `POST /release/gate` (operator); **REL-0** human-governed | go/no-go + evidence | `core/release.py`, `api/routers/release.py` |
| **Compiled packaging (A3, future)** | per edition build | Nuitka (Python) + `go build` (Go) + signing + SBOM/LBOM + no-raw-`.py` gate | turn the manifest into a real distributable | A3 work package |

---

## 10. API surface (today)

| Concern | API | Path |
|---|---|---|
| Licensing/tenancy | tenants, license issue/get, entitlements, members, seats, checkout | `api/routers/enterprise.py` |
| Packaging | editions, manifest, validate, **build** | `api/routers/packaging.py` |
| Release | readiness, gate, evidence | `api/routers/release.py` |
| Validation/gates/workers/pipeline | respective routers | `api/routers/*.py` |
| Go core (A2 licensing ops) | internal **wire contract** (JSON), not HTTP | `core/go_host.py` → `go/pfcore` |

**Gap:** there is **no API for the compiled build/package step** yet (A3).

---

## 11. Canonical owners
- Tiers/groups/limits: `config/licensing-tiers.json` · `core/licensing.py`
- Editions: `core/packaging.py`
- Tenancy/seats: `core/tenancy.py` · Billing: `core/billing.py`
- Release gate: `core/release.py`
- Go crypto (A2): `go/pfcore/license.go`

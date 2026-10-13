# Entitlements · Licensing · Editions · Packaging — end-to-end map

**Who this is for:** operators, engineers, and reviewers who need to understand how Product Forge's *paid
features* work: what a customer is allowed to use, how that is enforced, and how the build/distribution variants
relate. Every term is expanded on first use.

**Companion diagram:** [`docs/diagrams/licensing-entitlements-editions.drawio`](diagrams/licensing-entitlements-editions.drawio).

**Model version:** `entitlement_model_version = 1.0` (BI-PF-1264). Groups/tiers/names are **versioned**; a rename
or a change to a group/tier is a **new version** (never a silent edit).

---

## 0. Glossary (plain language)

| Term | Meaning |
|---|---|
| **Feature group** | A *bundle of capability* used as the unit of entitlement (e.g., `build-products`). |
| **Tier** | A *license level* you buy: `trial`, `starter`, `pro`, `enterprise`. |
| **Entitlement** | What a tier is *allowed*: its feature groups + limits. |
| **License key** | A signed token encoding a tenant's **tier**. |
| **Edition** | A *build/distribution variant*: `community`, `saas`, `enterprise`, `on-prem`, `oem`. |
| **Tenant** | The customer **org account**; **multi-tenancy** = many orgs in one install, isolated. |
| **Seat** | A named **user** in a tenant. Limits are **per tenant**: seats (users) → projects → parallel runs. |
| **Baseline** | An entitlement in **every** tier (here: `security`). |
| **Internal-only group** | Never granted to a customer tier (worker internals, PF's own work, platform ops). |
| **HMAC** | *Symmetric* signature (same secret signs+verifies) — the old scheme. |
| **Ed25519** | *Asymmetric* signature (private signs, public verifies) — the new scheme (A2). |
| **Fail-closed** | If unknown/unavailable → **deny**. |
| **A2 / A3 / A4** | EPIC-A work packages: licensing / compiled packaging / edition delivery manifest. |

---

## 1. The two axes
- **Tier** = *what you're allowed* (license level) — `config/licensing-tiers.json`.
- **Edition** = *what you install* (build/distribution variant) — `core/packaging.py` (`EDITIONS`).

---

## 2. Feature groups (model v1.0)
**Base — "Create Products" (in every tier):** `build-products`, `ideate-design`, `assure-quality`, `plan-deliver`.

**Add-ons (differentiate tiers):** `extend-integrate`, `team-multi-tenancy`, `choose-ai-models`, `content-media`,
`ai-agents`, `launch-grow`, `advanced-compliance`.

**Baseline (all tiers):** `security`.

**Internal-only (never a customer tier):** `worker-internals`, `pf-internal-work`, `platform-ops-licensing`.

*(Source of truth: `config/licensing-tiers.json` → `feature_groups`.)*

---

## 3. Tiers → groups + limits (per tenant; 0 = unlimited)
| Tier | Groups | Seats | Projects | Parallel runs |
|---|---|---|---|---|
| **trial** | base | 3 | 2 | 1 |
| **starter** | base + `extend-integrate` | 10 | 20 | 3 |
| **pro** | base + `extend-integrate`, `team-multi-tenancy`, `choose-ai-models`, `content-media`, `ai-agents` | 50 | 100 | 10 |
| **enterprise** | base + all add-ons | unlimited | unlimited | unlimited |

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

## 5. How a license key works
Token: `PF-<base64(payload)>.<base64(signature)>` (payload carries `tenant`, `tier`, `seats`, `exp`, and the
**entitlement model version**). Before A2 the signature was **HMAC** (symmetric, key shipped → forgeable); after
A2 it is **Ed25519** — the **vendor private key signs**, the **product verifies with a public key**, and the
private key never ships (Go core `go/pfcore/license.go`, invoked from Python via `core/go_host.py`).

---

## 6. Flows (end-to-end)
### Internal / operator
Run `INSTANCE_ROLE=operator`; provision tenant + issue license (`POST /api/v1/tenants/{tenant}/license`); checkout
(`POST .../checkout`); read entitlements (`GET .../entitlements`).

### Customer (tenant)
Run `INSTANCE_ROLE=tenant`; receive a license key; `licensing.verify_key` verifies it (public key) → **tier**;
actions gated by **entitlement-at-boundary** (refused if unentitled); seats via `core/tenancy.py`.

### OEM (white-label)
Built as the **`oem` edition** (white-label, enterprise tier, `command` target); the OEM signs licenses with **its**
private key and ships **its** public key — same asymmetric flow.

---

## 7. Build · packaging · CI-CD
| Stage | Trigger | Who/how | Purpose |
|---|---|---|---|
| Implement | item claimed | worker in a feature worktree | validated change |
| Gates | before completing | `scripts/dev/precheck.py` | mechanical quality |
| Merge | item done (Gate 2) | PF delivery lane → **FEATURE_PR** validation → `develop` | controlled merge |
| CI | push to main/develop + every PR | GitHub Actions `structure` workflow | structure + full precheck |
| Packaging (today) | operator/API | `core/packaging.py::build()` + `POST /packaging/build` | edition **manifest** (not compiled) |
| Release | release time | `core/release.py::gate()` + `POST /release/gate`; **REL-0** human-governed | go/no-go + evidence |
| **Compiled packaging (A3, future)** | per edition | Nuitka (Python) + `go build` (Go) + signing + SBOM/LBOM + no-raw-`.py` gate | real distributable |

---

## 8. Canonical owners
Tiers/groups: `config/licensing-tiers.json` + `core/licensing.py`. Editions: `core/packaging.py`. Tenancy:
`core/tenancy.py`. Billing: `core/billing.py`. Release: `core/release.py`. Go crypto (A2): `go/pfcore/license.go`.

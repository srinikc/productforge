# Product Forge — Delivery Baseline Specification

**Item:** BI-PF-0387 (Epic A / BI-PF-0390)  
**Governing ADR:** [ADR-0001: Go-first compiled delivery (one source, many editions)](file:///docs/ARCHITECTURE-DECISIONS.md#L44-L87)  
**Status:** Approved & Locked Baseline  
**Authority:** Single Source of Truth for Platform Delivery, Language Rules, and Multi-Edition Compilation  

---

## 1. Executive Summary & Principles

Product Forge delivers commercial editions from a single unified codebase while providing rigorous intellectual property (IP) protection. Customer-shipped editions must never expose raw, human-readable Python source code.

### The Four Delivery Invariants
1. **ONE Source, Many Editions:** All editions (`community`, `enterprise`, `saas`, `on-prem`, `oem`) are built and packaged from a single repository tree. Per-edition code forks are strictly forbidden.
2. **Go-First for New Shipped & Sensitive Logic:** All new core runtime capabilities, worker scheduling, sensitive cryptography, and high-concurrency subsystems land in native Go (`go/pfcore/`, `go/edpsvc/`, `go/capsvc/`).
3. **Compiled Packaging (No Raw `.py` at Customer):** Existing Python modules are shipped compiled (Nuitka C-extensions/binaries). Customer distributions contain zero readable `.py` files.
4. **Strangler Migration by Value:** Legacy Python modules are migrated to native Go over time based on IP-value and performance assessments (governed by `BI-PF-0386`). A complete big-bang rewrite is a non-goal; compiled Python serves as the permanent fallback for low-value remainder code.

---

## 2. Technology & Language Boundaries

| Tier / Subsystem | Language Authority | Build / Packaging Mechanism | Customer Distribution Form |
|---|---|---|---|
| **Core & Sensitive Data Plane** (`go/pfcore`, `go/edpsvc`, `go/capsvc`) | **Go (Native)** | `go build -trimpath -ldflags="-s -w"` | Stripped native static binary |
| **Existing Shipped Logic** (`core/`, `api/`, `adapters/`) | **Python (Compiled)** | Nuitka compiled C-extension (`.so` / `.pyd`) | Native binary shared libraries (0 `.py` files) |
| **Sensitive Logic Seams** (`core/licensing.py`, `core/billing.py`) | **Go Core + Python Shim** | Ed25519 in Go; thin Python shim delegates to Go host | Native Go binary + compiled shim |
| **Developer Tooling & CI** (`scripts/dev/`, `config/`, `docs/`) | **Python / Bash** | Interpreted / developer execution | Never packaged or shipped to customers |
| **Validation & Test Suite** (`test-framework/`, `tests/`) | **Python (`pytest`)** | Automated CI / test execution | Internal only |

---

## 3. Commercial Edition Matrix

Product Forge commercial packaging maps each edition to a declared licensing tier, deployment target, and distribution profile:

| Edition ID | Licensing Tier | Default Deploy Target | Distribution Kind | Packaging Constraint |
|---|---|---|---|---|
| **`community`** | `trial` | `local` | `open-source` | Public distribution; core platform capabilities only. |
| **`enterprise`** | `enterprise` | `kubernetes` | `commercial` | Compiled binaries only; full feature-group entitlement enforcement. |
| **`saas`** | `pro` | `docker` | `hosted` | Server-hosted deployment; runs source under managed infrastructure. |
| **`on-prem`** | `enterprise` | `docker` | `commercial` | Compiled binaries only; strict air-gap and cryptographic license validation. |
| **`oem`** | `enterprise` | `command` | `white-label` | Compiled binary host with custom branding/OEM profile embedding. |

---

## 4. IP Protection & Packaging Guarantees

### 4.1 No-Raw-`.py` Release Gate
In all customer-facing distributions (`enterprise`, `on-prem`, `oem`), the build pipeline (`scripts/pipeline.py` and `core/packaging.py`) executes an automated release gate:
```text
Assert: count(*.py in customer_distribution_archive) == 0
```
Any presence of uncompiled `.py` files immediately aborts the release build with exit code `CUSTOMER_PACKAGE_RAW_PY`.

### 4.2 Asymmetric Licensing at Boundary
Customer installations verify entitlements via Ed25519 digital signatures. The private signing key never ships to customer environments; public verification keys are embedded into the native Go core (`go/pfcore/license.go`). Entitlement checks fail closed (`require_entitlement` / `enforce_for_instance`).

---

## 5. Architectural Verification & Governance

1. **Gate 0 & Precheck Enforcement:** `scripts/dev/language_rule_check.py` and `core/change_policy.py` mechanically audit every changed file. Any attempt to introduce new uncompiled Python into shipped roots fails closed.
2. **Contract Testing:** `test-framework/tests/pipeline/test_delivery_baseline.py` continuously validates edition mappings, sensitive module boundaries, and compiled distribution rules.
3. **Traceability:** Governed by `BI-PF-0387`, `BI-PF-0388`, `BI-PF-0390`, and `docs/ARCHITECTURE-DECISIONS.md`.

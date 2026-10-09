# Security Architecture — CISO View (Product Forge)

CISO-level security posture for **Product Forge** and the **products it generates**. Companion to
`docs/COMPLIANCE-REGISTER.md` (framework→control→evidence) and `docs/REVIEW-MODEL.md` (the review gates).
(BI-PF-1203, EPIC BI-PF-1202.)

## 1. Scope
- **PF itself** — the engineering factory (pipeline, backlog, API, worker plane).
- **Generated products** — every product PF builds inherits the same controls + gates.

## 2. Trust boundaries (data flow)
```
clients (OpenCode / CLI / future UI / MCP / A2A)
  │  authN at the boundary (api/auth.py: API_TOKEN or API_ALLOW_ANON dev-only); role checks (operator/worker)
  ▼
api/  ── the single control plane (API-first)
  │
  ├── core/backlog (single-writer stores; id authority via git-CAS ref)
  ├── core/pipeline_executor → agents (LLM) ── model providers (BYO-key / self-host)
  ├── core/guardrails (output: toxicity/PII/NSFW/prompt-injection/secret; fail-closed)
  └── products/<p>/  (generated product code + data + docs)
workers (WorkerGrid /wg) ── claim only an existing item (no id minting); lease + heartbeat
external deps ── cataloged with license/bundle_allowed (never blindly bundled)
```
Boundaries: **client→API**, **PF→provider**, **PF→worker**, **PF→generated product**, **process→filesystem/network**.

## 3. Control catalog (what enforces what)
| control | mechanism | where |
|---|---|---|
| authN/authZ at the boundary | `API_TOKEN` + roles (operator/worker); fail-closed | `api/auth.py` |
| tenant isolation ("who can see data") | tenant-scoped authz | `core/tenancy.py` |
| secrets never committed | diff-scoped secret scan (+ `--release` full sweep) | `scripts/dev/secret_scan.py` (`gate:secret-scan`) |
| injection / dangerous patterns | static high-risk scan (SQL/eval/exec/shell/pickle/yaml/DELETE) | `scripts/dev/review_static_check.py` (`gate:review-static`) |
| dependency integrity + license | tool catalog + `bundle_allowed` | `scripts/dev/dependency_catalog_check.py` (`gate:dependency-catalog`) |
| vulnerable-code review | LLM production-risk checklist | `code-review` + `docs/REVIEW-FOCUS.md` (`gate:review-focus`) |
| output guardrails | toxicity/PII/NSFW/prompt-injection/secret; allow\|flag\|block\|redact; **fail-closed** | `core/guardrails.py` |
| AI governance | NIST AI RMF + EU AI Act checkpoints | `core/guardrails.py` |
| release security | scans + pen-test; **blocks release** on critical | `security-audit` agent |
| threat modeling (design) | trust boundaries / threat model at the arch gate | `core/spec_review.py` (E7) |
| audit / evidence | run-bound records; append-only ledgers | `core/close_loop.py`, item `decisions[]` |

## 4. Risk register (top)
| # | risk | severity | mitigation | state |
|---|---|---|---|---|
| R1 | false/inflated compliance claims in generated content | **high** | policy-driven claims (`config/compliance-register.json`); no hardcoded certs (BI-PF-1205) | **fixed** |
| R2 | no explicit **DPDP/GDPR** privacy controls (DSR/retention/DPIA/consent) | **high** | privacy-controls item (BI-PF-1204) | open |
| R3 | no SOC 2 / ISO 27001 program | medium | register documents the gap; pursue when needed | open (gap) |
| R4 | LLM misuse / prompt injection | medium | guardrails prompt-injection + review gates | mitigated |
| R5 | supply-chain (dep license/vuln) | medium | tool catalog + dependency-catalog gate | mitigated |
| R6 | tenant data bleed | medium | `core/tenancy.py` isolation | mitigated |
| R7 | secrets leakage | medium | secret-scan (per-merge + release) | mitigated |

## 5. Framework mapping (detail in the register)
OWASP · NIST AI RMF · EU AI Act · **DPDP (India)** · GDPR · SOC2/ISO — see `docs/COMPLIANCE-REGISTER.md`
(status: implemented | partial | gap). Customer-facing security/compliance claims must be **driven by that
register** — never assert a certification not held.

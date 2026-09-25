# Deployment & Infrastructure Architecture

> System-architect view of how Product Forge handles **packaging, deployment, infrastructure,
> vendors, and verification** — what it does, what it deliberately does not, and how to extend it.

## 1. Position & scope
**Product Forge orchestrates and decides; it does not own infrastructure, vendors, or labs.**
It produces plans, configs, code, and deploy/verify actions that run against an environment
the **user (or a vendor lab) provides**.

| In scope (Product Forge) | Out of scope (user / vendor provides) |
|---|---|
| Decide **what** to build, stack, infra, packaging, deploy method | Physical/VM hardware, proprietary appliances |
| Generate IaC/scripts (Terraform/Ansible/K8s/compose/installers) | Running every vendor SDK in our infra |
| **Select + apply** a provider/target to a supplied environment | Hosting vendor labs / licenses |
| **Research** vendor/product details (web + KB + skills) and cache them | Guaranteeing a lab without access |
| **Verify** against a reachable endpoint/host | **Fabricating** results when no environment exists |
| Emit artifacts + runbooks when no environment is available | Buying/setting up Dell/HP/Cisco/VMware estates |

## 2. Principles
1. **Vendor-agnostic** — no vendor is hardcoded; anything is data + adapter.
2. **Data-driven** — stack/infra/deploy come from config files, not prompts.
3. **User-provided environments** — we target what exists; we don't invent it.
4. **No fabricated verification** — if it can't run, mark `not-run`, never fake.
5. **Bounded research** — learn on demand, cache into the knowledge base, ask the user when unknown.
6. **Everything pluggable** — providers/adapters + a universal command fallback.
7. **Secrets are env-var names** — never values in files.

## 3. Domain model
```
Product KIND (cli|library|web-app|api|mobile|service)
        │  decides
        ▼
PACKAGING  ── build artifacts (image, wheel, jar, msi/deb/rpm, apk/ipa, bundle)
        │
REQUIREMENTS + NFRs ── decide ──▶ INFRA NEEDS (compute, storage, network, identity,
        │                                   observability, data, environments)
        ▼
ENVIRONMENT PROFILE (infra.json) ──▶ TARGETS (hosts, endpoints, cloud, cluster, vendors)
        │
        ▼
PROVIDER / ADAPTER ──▶ APPLY ──▶ VERIFY ──▶ DESTROY / KEEP
```

## 4. Agents & orchestration (who does what)
| Phase | Agent(s) | Responsibility | Artifact |
|---|---|---|---|
| 0/0a | ideation, discovery | gather idea, platforms, deployment intent | `docs/product-plan.md`, `project.json` |
| 1 | design | functional + **non-functional** requirements | `docs/requirements.md` |
| 2 | **architect** | decide stack, runtime, deploy method, infra | `docs/tech-stack.json`, `docs/infra.json`* |
| 9 | **package** | build artifacts per kind/stack | `dist/`, images, installers |
| 11 | **production-deploy** | write/apply deploy scripts for the target | deploy scripts + apply |
| — | **executor** (`stage_runner`) | select provider, **apply → verify → teardown**, record | `report.post_deploy` |
| 5/6 | security, validate | security scans, real tests | issues, verification |

\* `infra.json` = proposed contract (see §5); architect currently emits `tech-stack.json`.

## 5. Data contracts (configuration)
### `project.json` — run + deploy intent
```jsonc
{
  "idea": "...", "model_tier": "free-trial", "enable_tools": true,
  "deploy": {
    "target": "docker",              // docker|local|kubernetes|terraform|ansible|paas|installer|command
    "system": "local_machine",       // local_machine|on_prem_server|cloud_vm|managed_service|paas|container_registry
    "host": "", "endpoint": "", "region": "", "registry": "", "namespace": "",
    "domain": "", "port": 8080, "health_path": "/health",
    "credentials_env": ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
    "commands": { "apply": [], "verify": [], "destroy": [] }
  }
}
```
### `docs/tech-stack.json` (architect) — `chosen.{kind,languages,frameworks,database,cache,deploy,runtime}`
### `docs/infra.json` (proposed) — compute / storage / networking / identity / observability / environments / compliance / cost / vendors
### `docs/ports.json` — derived service ports (feeds deploy health-check)
### `AGENTS.md` — per-project rules (purpose, stack, conventions, verification)
### `.env` — credentials (referenced by name only)

## 6. End-to-end workflow
```
idea → research (on demand) → architect decides stack+infra+deploy
   → package builds artifacts → production-deploy applies
   → executor: select provider (deploy.target | auto-detect)
        apply → health-check + smoke → teardown/keep
   → report.post_deploy = {ran, provider, passed, steps}
   → if no environment/creds: artifacts + runbook, verification = "external"/"not-run"
```

## 7. Provider / adapter model
`core/deploy_providers.py` — `DeploymentProvider` with `detect / apply / verify / destroy`.

| Provider | Behaviour |
|---|---|
| `docker` | compose up --build → health-check → smoke → down -v |
| `local` | run smoke suite against the checkout (no containers) |
| `command` | run configured `commands.{apply,verify,destroy}` — **universal fallback** |
| named aliases | `kubernetes, helm, terraform, ansible, chef, puppet, paas, installer, aws, gcp, azure` → all route through `command` until specialized |

**Add your own:** implement the interface, register it in `_REGISTRY`, or just supply `commands` in the deploy profile (no code).

## 8. Research & knowledge (learn on demand)
Architect/design **should not memorize** vendor ecosystems. Instead:
- **researcher/scout** agents + `http_get` tool fetch vendor docs/APIs.
- **skills_registry** (43 skills) provides reusable know-how.
- **knowledge_compiler** caches findings → reusable knowledge base.
- Bounded (caps); if knowledge is missing → **HITL** (ask the user), never guess.

## 9. Verification policy
| Value | When |
|---|---|
| `internal` | environment provided & reachable → we deploy + verify here |
| `external` | user/vendor runs it (lab) → we emit artifacts + checklist; result supplied back |
| `not-run` | no environment/credentials → **explicit**, never fabricated |

## 10. Capability matrix
| Area | Status |
|---|---|
| Docker deploy (apply/verify/teardown) | ✅ |
| Local smoke verification | ✅ |
| Generic command provider (any tool) | ✅ |
| Package build (npm/python/docker) | ✅ (`nfr_runner`) |
| Security scans (npm audit/bandit/pip-audit) | ✅ (when tools present) |
| Secrets scan in gate | ✅ |
| `infra.json` + architect emits it | ⬜ proposed |
| Specialized k8s/helm/terraform/ansible providers | 🟡 via command; specialized ⬜ |
| Installers (.msi/.deb/.rpm/.dmg), mobile (apk/ipa) | ⬜ (via command) |
| Vendor integration (Dell/HP/VMware/Cisco) | ⬜ via adapters + user labs |
| Bounded research step feeding architect | 🟡 pieces exist; not wired as a step |

## 11. Enterprise breadth catalog (reference)
- **Packaging:** OCI image, Helm, wheel/sdist, npm, jar/war, nupkg, Go/Rust binary, gem, msi/exe, deb/rpm/snap/flatpak/AppImage, pkg/dmg, apk/aab, ipa, Lambda zip, ONNX/safetensors, CDN bundle, PDF.
- **Deploy targets:** bare/local, Docker/Compose, K8s/Helm/Nomad/ECS/EKS/GKE/AKS/OpenShift, serverless/PaaS (Vercel/Netlify/Fly/Render/Cloud Run/Lambda/Functions), IaC (Terraform/Pulumi/CloudFormation), config-mgmt (Ansible/Chef/Puppet/Salt), GitOps/CI (Actions/GitLab/Jenkins/ArgoCD/Flux), edge/CDN, DB migrations (Flyway/Alembic/Liquibase), mobile stores.
- **Infra dimensions:** compute (CPU/GPU/autoscale/regions), storage (object/block/file/DB/cache/search/vector/queue), networking (VPC/subnet/DNS/LB/ingress/TLS/mesh/CDN/API-gw/ports), identity/security (IAM/secrets/KMS), observability (OTel/metrics/logs/traces/SLO), environments (dev/stage/prod), data/compliance (residency/retention/backup/DR), cost.

## 12. How to use
- **Default (docker):** add `docker-compose.yml`; run the pipeline; post-deploy runs automatically at Stage 11 after `production-deploy`.
- **Any tool (terraform/ansible/k8s/paas):** set `deploy.target` + `deploy.commands.{apply,verify,destroy}` in `project.json`.
- **No environment:** leave `deploy` unset → verification is `not-run` (artifacts + runbook still produced).
- **Credentials:** put env-var names in `deploy.credentials_env`; values in `.env`.

## 13. Mapping to code
| Concern | Module |
|---|---|
| Provider registry / apply-verify-destroy | `core/deploy_providers.py` |
| (legacy) post-deploy smoke | `core/deploy_smoke.py` |
| Packaging/security/smoke commands | `core/nfr_runner.py` |
| Real test/build verification | `core/verification_runner.py` |
| Stack decision + ports | `core/tech_stack.py`, `docs/ports.json` |
| Trigger after deploy stage | `core/orchestrator/stage_runner.py`, `PipelineExecutor._run_post_deploy` |
| Project rules | `_write_project_agents_md` → `AGENTS.md` |

## 14. Roadmap
1. `infra.json` contract + architect emits it (kind + NFR → infra).
2. Bounded **research step** feeding architect.
3. Specialized providers: `kubernetes/helm`, `terraform`, `ansible`, `installer`.
4. Verification-policy plumbing (`internal/external/not-run`) into report.
5. Vendor **integration adapters** (vSphere/Dell/HP/Cisco/S3/Postgres…) + lab handles.

## 15. Platform Testing (web / desktop / mobile)

Testing is platform-agnostic. The test cycle selects an adapter (`core/test_adapters.py`),
runs the suite through the framework bridge (`core/test_framework_integration.py`), records
metrics/traceability, logs defects, and books a test cycle. For UI suites it also brings the
app **up and down**.

### Adapters
| Stack | Detect | Command |
|---|---|---|
| web (node) | `package.json` (+ `playwright.config.*`) | `npx playwright test` else npm / vitest / jest |
| desktop (Electron/Tauri) | `tauri.conf.json` / electron,tauri deps (+ playwright) | `npx playwright test` |
| desktop (native) | `wdio.conf.*` / `@wdio/cli`, `webdriverio` | `npx wdio run <conf>` |
| mobile (iOS/Android) | `xcrun simctl` / `adb` availability | Stowaway / Vitest-mobile / Maestro, or external |
| python/go/rust/java/dotnet/php/ruby/flutter | repo files | native runner |
| any (fallback) | `project.json` → `test.command` | that command |

Adapter order: **desktop → python → node → go → rust → java → dotnet → php → ruby → flutter → command**.

### App lifecycle (UI / e2e / desktop)
`_needs_app` (categories `e2e|visual|accessibility|desktop|ui`, a Playwright config, or the
desktop adapter) → `run_deploy_up` (apply → verify; sets `BASE_URL`/`DEPLOY_URL`) →
`npx playwright install` bootstrap (best-effort) → run suite → `run_deploy_down` in a
`finally`. Recorded as `result.app_lifecycle = {up, down, base_url, browsers}`.

### Mobile
```json
{
  "mobile": {
    "ios":     {"bundle_id": "com.x", "app_path": "build/App.app",
                "test_command": "maestro test flows/ios.yaml"},
    "android": {"package":   "com.x", "apk_path": "build/app.apk",
                "test_command": "maestro test flows/android.yaml"}
  }
}
```
- If `test_command`/`farm_command` is set it **takes precedence** and runs as an external
  runner (Appium / BrowserStack / Firebase Test Lab / Maestro); `{platform}` is templated.
- Otherwise: boot simulator/emulator → `install_app` → `launch_app` → built-in runner.
- Skips cleanly when neither a simulator nor an external runner is available.

### Desktop
Electron/Tauri through **Playwright**; native (WinAppDriver/WebdriverIO/Appium) through
`wdio.conf.*`.

### Escape hatch
Any stack/tool via `project.json`:
```json
{ "test": { "command": "make check" } }
```

### Files
| Concern | Location |
|---|---|
| Adapter registry | `core/test_adapters.py` |
| Cycle / lifecycle / mobile | `core/test_framework_integration.py` |
| Deploy up/down | `core/deploy_providers.py` (`run_deploy_up`, `run_deploy_down`, `run_deploy`) |
| Mobile simulator/emulator | `core/mobile_tester.py` |
| Framework modules | `test-framework/core/{runner,test_cycle,reporter,defect_tracker,...}.py` |
| Project config schema | `docs/schemas/project.v1.schema.json` (`test`, `deploy`, `mobile`) |

# Product Forge — Pipeline Stages & Agents Reference

> **Generated** from `pipeline-definition.json` + `agents/*.agent.json` (`scripts/gen_pipeline_reference.py`). Do not hand-edit — re-run the generator.

**39 stages** across the phases below. Every stage's canonical artifact is `artifacts/<stage>/<agent>-output.md`; extra formats (.html/.pdf/.xlsx) are derived per `config/artifact-formats.json`. Stage directories use human-readable names (`<id> - <Name>`, e.g. `1 - Design`) per `config/artifact-paths.json`; each holds a `_stage.json` and the tree has an `artifacts/INDEX.md` (3a).

## Phases

| Phase | Stages |
| --- | --- |
| P1 Ideation & Discovery | 0, 0a |
| P2 Business, Market & Monetization | 0b, 0c, 0d, 0e |
| P3 Design | 1, 1a, 1b, 1c, 1d |
| P4 Architecture | 2, 3, 3a |
| P5 Implementation | 4-0, 4a, 4a-vqa, 4b, 4b-vqa, 4c, 4c-vqa, 4d, 4d-vqa, 4e, 4e-vqa, 4f, 4f-vqa |
| P6 Verification | 5, 6, 7 |
| P7 Delivery | 8, 9, 10, 10a, 11, 12 |
| P8 Operate, Grow & Engage | 13, 13a, 13b |

## Stages

| Stage | Disp | Name | Phase | Agent(s) | Role | Artifact(s) | Prev → Next | Opt | Gate |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **0** | S1.1 | Ideation | P1 Ideation & Discovery | `ideation` | Discovery process — explores, challenges, discovers what user actually needs | `artifacts/0/ideation-output.md` `docs/product-plan.md` | — → 0a |  |  |
| **0a** | S1.2 | Discovery | P1 Ideation & Discovery | `discovery` | Run structured discovery to shape the product. | `artifacts/0a/discovery-output.md` `docs/idea-refined.md` `docs/domain-analysis.md` `docs/stakeholder-map.md` `docs/user-personas.md` `discovery-panel.json` `discovery-questions.json` | 0 → 0b |  |  |
| **0b** | S2.1 | Business & Product Definition | P2 Business, Market & Monetization | `product-owner` | Works WITH the ideation and discovery agents to distill the idea into product goals, vision, scope, personas and success metrics | `artifacts/0b/product-owner-output.md` `product-plan.json` | 0a → 0c | yes | AG-business |
| **0c** | S2.2 | Market, Competition & Positioning | P2 Business, Market & Monetization | `researcher` | Conducts thorough research on topics using web search, academic sources, and industry knowledge. | `artifacts/0c/researcher-output.md` `marketing-strategy/positioning.md` | 0b → 0d | yes | AG-market |
| **0d** | S2.3 | Monetization & Unit Economics | P2 Business, Market & Monetization | `pricing-strategist` | Pricing & monetization lead | `artifacts/0d/pricing-strategist-output.md` | 0c → 0e | yes | AG-monetization |
| **0e** | S2.4 | Go-to-Market & Customer Journey | P2 Business, Market & Monetization | `marketing` | Marketing | `artifacts/0e/marketing-output.md` `marketing-strategy/gtm-strategy.md` `marketing-strategy/campaign-plan.md` | 0d → 1 | yes | AG-gtm |
| **1** | S3.1 | Design | P3 Design | `design` | Extracts formal requirements and produces a design doc from the product plan | `artifacts/1/design-output.md` `docs/design.md` `docs/requirements.md` `artifacts/1/features/F-*-functional.md` | 0e → 1a |  | AG-scope-change |
| **1a** | S3.2 | Product Design Spec | P3 Design | `product-design-spec` | Produce a structured product design specification. | `artifacts/1a/product-design-spec-output.md` `design-spec.json` | 1 → 1b |  |  |
| **1b** | S3.3 | Design Review | P3 Design | `design_critic` | Review the design for quality and completeness. | `artifacts/1b/design_critic-output.md` | 1a → 1c |  |  |
| **1c** | S3.4 | UX/IA Review | P3 Design | `ux-ia` | Define UX and information architecture + design tokens. | `artifacts/1c/ux-ia-output.md` | 1b → 1d |  |  |
| **1d** | S3.5 | Research | P3 Design | `researcher` | Conducts thorough research on topics using web search, academic sources, and industry knowledge. | `artifacts/1d/researcher-output.md` | 1c → 2 |  |  |
| **2** | S4.1 | Architect | P4 Architecture | `architect` | Chooses the tech stack and produces the architecture document (ADRs) from the requirements and design. | `artifacts/2/architect-output.md` `docs/architecture.md` | 1d → 3 |  | AG-architecture |
| **3** | S4.2 | Refine Requirements | P4 Architecture | `orchestrator` | Project Coordinator (judgment plane) | `artifacts/3/orchestrator-output.md` | 2 → 3a |  |  |
| **3a** | S4.3 | QA Spec Review | P4 Architecture | `validate` | Senior QA Engineer | `artifacts/3a/validate-output.md` | 3 → 4-0 |  |  |
| **4-0** | S5.0 | Skeleton | P5 Implementation | `implement`, `devops` | Builds the code from the approved design, architecture, and requirements / Devops | `artifacts/4-0/implement-output.md` `artifacts/4-0/devops-output.md` | 3a → 4a |  |  |
| **4a** | S5.1 | Implementation Iteration 1 | P5 Implementation | `implement`, `devops`, `code-review`, `validate` | Builds the code from the approved design, architecture, and requirements / Devops / Code Review agent (Stage 5) / Senior QA Engineer | `artifacts/4a/implement-output.md` `artifacts/4a/devops-output.md` `artifacts/4a/code-review-output.md` `artifacts/4a/validate-output.md` | 4-0 → 4a-vqa |  |  |
| **4a-vqa** | S5.1a | Visual QA (Iteration 1) | P5 Implementation | `visual_qa` | Verify rendered UI against the design spec | `artifacts/4a-vqa/visual_qa-output.md` | 4a → 4b |  |  |
| **4b** | S5.2 | Implementation Iteration 2 | P5 Implementation | `implement`, `devops`, `code-review`, `validate` | Builds the code from the approved design, architecture, and requirements / Devops / Code Review agent (Stage 5) / Senior QA Engineer | `artifacts/4b/implement-output.md` `artifacts/4b/devops-output.md` `artifacts/4b/code-review-output.md` `artifacts/4b/validate-output.md` | 4a-vqa → 4b-vqa |  |  |
| **4b-vqa** | S5.2a | Visual QA (Iteration 2) | P5 Implementation | `visual_qa` | Verify rendered UI against the design spec | `artifacts/4b-vqa/visual_qa-output.md` | 4b → 4c |  |  |
| **4c** | S5.3 | Implementation Iteration 3 | P5 Implementation | `implement`, `devops`, `code-review`, `validate` | Builds the code from the approved design, architecture, and requirements / Devops / Code Review agent (Stage 5) / Senior QA Engineer | `artifacts/4c/implement-output.md` `artifacts/4c/devops-output.md` `artifacts/4c/code-review-output.md` `artifacts/4c/validate-output.md` | 4b-vqa → 4c-vqa |  |  |
| **4c-vqa** | S5.3a | Visual QA (Iteration 3) | P5 Implementation | `visual_qa` | Verify rendered UI against the design spec | `artifacts/4c-vqa/visual_qa-output.md` | 4c → 4d |  |  |
| **4d** | S5.4 | Implementation Iteration 4 | P5 Implementation | `implement`, `devops`, `code-review`, `validate` | Builds the code from the approved design, architecture, and requirements / Devops / Code Review agent (Stage 5) / Senior QA Engineer | `artifacts/4d/implement-output.md` `artifacts/4d/devops-output.md` `artifacts/4d/code-review-output.md` `artifacts/4d/validate-output.md` | 4c-vqa → 4d-vqa |  |  |
| **4d-vqa** | S5.4a | Visual QA (Iteration 4) | P5 Implementation | `visual_qa` | Verify rendered UI against the design spec | `artifacts/4d-vqa/visual_qa-output.md` | 4d → 4e |  |  |
| **4e** | S5.5 | Implementation Iteration 5 | P5 Implementation | `implement`, `devops`, `code-review`, `validate` | Builds the code from the approved design, architecture, and requirements / Devops / Code Review agent (Stage 5) / Senior QA Engineer | `artifacts/4e/implement-output.md` `artifacts/4e/devops-output.md` `artifacts/4e/code-review-output.md` `artifacts/4e/validate-output.md` | 4d-vqa → 4e-vqa |  |  |
| **4e-vqa** | S5.5a | Visual QA (Iteration 5) | P5 Implementation | `visual_qa` | Verify rendered UI against the design spec | `artifacts/4e-vqa/visual_qa-output.md` | 4e → 4f |  |  |
| **4f** | S5.6 | Implementation Iteration 6 | P5 Implementation | `implement`, `devops`, `code-review`, `validate` | Builds the code from the approved design, architecture, and requirements / Devops / Code Review agent (Stage 5) / Senior QA Engineer | `artifacts/4f/implement-output.md` `artifacts/4f/devops-output.md` `artifacts/4f/code-review-output.md` `artifacts/4f/validate-output.md` | 4e-vqa → 4f-vqa |  |  |
| **4f-vqa** | S5.6a | Visual QA (Iteration 6) | P5 Implementation | `visual_qa` | Verify rendered UI against the design spec | `artifacts/4f-vqa/visual_qa-output.md` | 4f → 5 |  |  |
| **5** | S6.1 | Security Scan | P6 Verification | `security` | "Security analysis with threat modeling, OWASP checks, and vulnerability assessment" | `artifacts/5/security-output.md` | 4f-vqa → 6 |  | AG-security-critical |
| **6** | S6.2 | NFR Tests | P6 Verification | `validate` | Senior QA Engineer | `artifacts/6/validate-output.md` | 5 → 7 |  |  |
| **7** | S6.3 | Full Test Suite | P6 Verification | `validate` | Senior QA Engineer | `artifacts/7/validate-output.md` | 6 → 8 |  |  |
| **8** | S7.1 | Document | P7 Delivery | `document` | Generates comprehensive documentation for the completed software product including README, user guides, API documentation, architecture diagrams, and  | `artifacts/8/document-output.md` `docs/* (README / guides / API)` | 7 → 9 |  |  |
| **9** | S7.2 | Package | P7 Delivery | `package` | Builds platform-specific packages, installers, and artifacts for the completed software product including BOM, security audits, licenses, and cross-pl | `artifacts/9/package-output.md` `dist/* (installers / packages)` | 8 → 10 |  |  |
| **10** | S7.3 | Pre-Production | P7 Delivery | `devops`, `orchestrator` | Devops / Project Coordinator (judgment plane) | `artifacts/10/devops-output.md` `artifacts/10/orchestrator-output.md` | 9 → 10a |  | AG-deploy |
| **10a** | S7.4 | QA Go/No-Go | P7 Delivery | `validate` | Senior QA Engineer | `artifacts/10a/validate-output.md` | 10 → 11 |  |  |
| **11** | S7.5 | Deploy | P7 Delivery | `devops`, `production-deploy` | Devops / Deploys to production with canary/blue-green strategy, feature flags, monitoring, rollback capability. | `artifacts/11/devops-output.md` `artifacts/11/production-deploy-output.md` | 10a → 12 |  | AG-deploy |
| **12** | S7.6 | Exit | P7 Delivery | `orchestrator` | Project Coordinator (judgment plane) | `artifacts/12/orchestrator-output.md` | 11 → 13 |  |  |
| **13** | S8.1 | Operate & Observability | P8 Operate, Grow & Engage | `observer` | "Future-looking insights, serendipity analysis, and alternative approach suggestions" | `artifacts/13/observer-output.md` | 12 → 13a | yes | AG-operate |
| **13a** | S8.2 | Customer Success & Support | P8 Operate, Grow & Engage | `customer-success` | Customer success lead | `artifacts/13a/customer-success-output.md` | 13 → 13b | yes |  |
| **13b** | S8.3 | Growth, Engagement & Feedback | P8 Operate, Grow & Engage | `growth` | Growth lead | `artifacts/13b/growth-output.md` | 13a → — | yes |  |

## Agent reference

| Agent | Role | Stages |
| --- | --- | --- |
| `architect` | Chooses the tech stack and produces the architecture document (ADRs) from the requirements and design. | 2 |
| `code-review` | Code Review agent (Stage 5) | 4a, 4b, 4c, 4d, 4e, 4f |
| `customer-success` | Customer success lead | 13a |
| `design` | Extracts formal requirements and produces a design doc from the product plan | 1 |
| `design_critic` | Review the design for quality and completeness. | 1b |
| `devops` | Devops | 4-0, 4a, 4b, 4c, 4d, 4e, 4f, 10, 11 |
| `discovery` | Run structured discovery to shape the product. | 0a |
| `document` | Generates comprehensive documentation for the completed software product including README, user guides, API documentation, architecture diagrams, and  | 8 |
| `growth` | Growth lead | 13b |
| `ideation` | Discovery process — explores, challenges, discovers what user actually needs | 0 |
| `implement` | Builds the code from the approved design, architecture, and requirements | 4-0, 4a, 4b, 4c, 4d, 4e, 4f |
| `marketing` | Marketing | 0e |
| `observer` | "Future-looking insights, serendipity analysis, and alternative approach suggestions" | 13 |
| `orchestrator` | Project Coordinator (judgment plane) | 3, 10, 12 |
| `package` | Builds platform-specific packages, installers, and artifacts for the completed software product including BOM, security audits, licenses, and cross-pl | 9 |
| `pricing-strategist` | Pricing & monetization lead | 0d |
| `product-design-spec` | Produce a structured product design specification. | 1a |
| `product-owner` | Works WITH the ideation and discovery agents to distill the idea into product goals, vision, scope, personas and success metrics | 0b |
| `production-deploy` | Deploys to production with canary/blue-green strategy, feature flags, monitoring, rollback capability. | 11 |
| `researcher` | Conducts thorough research on topics using web search, academic sources, and industry knowledge. | 0c, 1d |
| `security` | "Security analysis with threat modeling, OWASP checks, and vulnerability assessment" | 5 |
| `ux-ia` | Define UX and information architecture + design tokens. | 1c |
| `validate` | Senior QA Engineer | 3a, 4a, 4b, 4c, 4d, 4e, 4f, 6, 7, 10a |
| `visual_qa` | Verify rendered UI against the design spec | 4a-vqa, 4b-vqa, 4c-vqa, 4d-vqa, 4e-vqa, 4f-vqa |

## Notes

- **Optional stages** (`0b`, `0c`, `0d`, `0e`, `13`, `13a`, `13b`) are enabled or disabled per project by `core/pipeline_tailoring.py` (idea-signal based) and recorded in `pipeline-plan.json` (`enabled_optional` / `disabled_optional`).
- **Display sequence vs canonical id:** `pipeline-plan.json.display` maps a runtime `display_seq` (e.g. `S2.1`) to a `canonical_id` (e.g. `S3.1`) because the visible numbering shifts when optional stages are toggled. The canonical id is the stable reference.
- **Capability generators vs stages:** some outputs (`marketing-strategy/*`, `onboarding/*`, `presentations/*`, `videos/*`, `product-plan.json`) are produced by capability modules (`core/marketing.py`, `core/customer_onboarding.py`, `core/presentation_generator.py`, `core/product_plan.py`) run as stage hooks — independent of stages `0b–0e`.
- **Spec ids** (FR/NFR/US + local families) are parsed by the single canonical query `core/id_index.py`; id families live in `config/spec-id-families.json`. Feature ids are a running number across features (no hard cap): F-1 `FR-1..n`, F-2 `n+1..`, via `core/id_index.renumber_global`.
- **Single-run guard:** `core/run_guard.py` stops any live instance before a start/restart/resume/continue and takes the project lock (`products/.locks/`).
- **run_id linkage:** approvals carry `run_id`; `core/run_state.py` records run attempts in `pipeline-runs.json` and reconciles already-approved stages on resume (preserve-first — user data is never cleared).

# Agent prompt comparison — current vs OSS/industry recommendation

> Review only. Per agent: role (primary/subagent), parent, stage/phase it runs in, current card (mode/tools/required sections/flags) vs recommended core-prompt updates (patterns from MetaGPT, ChatDev, CrewAI, AI-tools system prompts). Keep PF artifact/quality/compliance rules; update only CORE role sections. Fixes: BI-0228 (+ capability BI-0221/0222/0223).

## Global recommended updates (apply to ALL agents)
- Role/Goal/Backstory header (CrewAI/MetaGPT) + explicit NOT-do list.
- Information diet: 'read ONLY these inputs' (ChatDev) — reinforce our INPUT sections.
- Output schema: exact headings **or** JSON fields; termination signal.
- Tool contract: allowed tools + when/how; limit to the agent's subset (3–5).
- Capability vector declared: reasoning level, tools, structured, vision, long_context.
- Reasoning is DELEGATED to PF (on/off per role/stage) — state the expected reasoning level.
- Keep PF artifact/quality/compliance rules unchanged; only core role sections updated.

## Per-class recommended updates
- **Product/Design:** role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on.
- **Architecture:** keep decision-JSON-first; role/goal/backstory; trade-offs + ADR ids; reasoning high; structured_output on.
- **Implementation:** coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on.
- **Verification/QA:** independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on.
- **Delivery/Ops:** canary/rollback + guardrails (keep); tool subset; status JSON; reasoning low.
- **Orchestration:** explicit control-flow contract; termination signals; decision JSON; reasoning high.
- **Business/Content:** role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med.

## Primary agents → sub-agents (grouped)

> `default` = in the standard pipeline (`pipeline-definition.json` ideal_flow); `on-demand` = registered but invoked selectively/conditionally.

| primary | stage/phase | #subs | default subs | on-demand subs | primary does (brief) |
|---|---|---|---|---|---|
| **architect** | 2 (P4 Architecture) | 1 | - | legal-privacy | Architect agent. Chooses the tech stack and produces the architecture document (ADRs) from the requirements and design. |
| **code-review** | 4a,4b,4c,4d,4e,4f (P5 Implementation) | 1 | - | static_verifier | Code Review agent (Stage 5). Reviews implemented code for completeness, bugs, security, performance, quality. |
| **customer-success** | 13a (P8 Operate, Grow & Engage) | 1 | - | customer-onboarding | Customer success lead. Owns onboarding, support, customer health, retention and lifecycle. |
| **design** | 1 (P3 Design) | 4 | design_critic, product-design-spec, ux-ia | review | Design agent. Extracts formal requirements and produces a design doc from the product plan. |
| **devops** | 10,11,4-0,4a,4b,4c,4d,4e,4f (P5 Implementation/P7 Delivery) | 5 | package, production-deploy | finops, maintenance, pre-production | devops agent |
| **document** | 8 (P7 Delivery) | 5 | - | content-creator, content-reader, journal-writer, presentation-generator, summary-creator | Documentation agent. Generates comprehensive documentation for the completed software product including README, user guides, API documentation, architecture diagrams, and PDF exports. |
| **growth** | 13b (P8 Operate, Grow & Engage) | 1 | - | community-social | Growth lead. Owns acquisition/activation/retention/referral, funnel, growth loops and experiments. |
| **implement** | 4-0,4a,4b,4c,4d,4e,4f (P5 Implementation) | 4 | - | implement-api, implement-db, implement-logic, implement-ui | Implement agent. Builds the code from the approved design, architecture, and requirements. |
| **implement-ui** | (on-demand) (-) | 1 | visual_qa | - | Implement UI layer. Creates React/Next. |
| **marketing** | 0e (P2 Business, Market & Monetization) | 4 | growth | community-social, customer-onboarding, sales-crm | marketing agent |
| **product-owner** | 0b (P2 Business, Market & Monetization) | 2 | pricing-strategist | product-analytics | Works WITH the ideation and discovery agents to distill the idea into product goals, vision, scope, personas and success metrics. Invoked ONLY in auto mode. |
| **production-deploy** | 11 (P7 Delivery) | 1 | - | post-production | Production Deployment agent. Deploys to production with canary/blue-green strategy, feature flags, monitoring, rollback capability. |
| **researcher** | 0c,1d (P2 Business, Market & Monetization/P3 Design) | 3 | - | insight-extractor, scout, theme-analyzer | Research agent. Conducts thorough research on topics using web search, academic sources, and industry knowledge. |
| **security** | 5 (P6 Verification) | 3 | - | a11y-audit, legal-privacy, security-audit | "Security analysis with threat modeling, OWASP checks, and vulnerability assessment". |
| **validate** | 10a,3a,4a,4b,4c,4d,4e,4f,6,7 (P4 Architecture/P5 Implementation/P6 Verification/P7 Delivery) | 2 | - | performance, quality_gate | Validation agent. Runs tests via test-framework, logs defects, and reports findings. |

### Sub-agent briefs (what each does)
| subagent | parent | default? | stage/phase | does (brief) |
|---|---|---|---|---|
| a11y-audit | security | no | (on-demand) (-) | Accessibility Audit agent. Validates WCAG 2. |
| community-social | marketing | no | (on-demand) (-) | Community & social media lead. Owns community, social channels, engagement and advocacy. |
| content-creator | document | no | (on-demand) (-) | Content creator agent. Creates high-quality content in various formats (articles, posts, scripts, stories). |
| content-reader | document | no | (on-demand) (-) | Content reader agent. Reads and extracts text from various file formats (txt, pdf, epub, docx) for further processing. |
| customer-onboarding | marketing | no | (on-demand) (-) | customer-onboarding agent |
| design_critic | design | yes | 1b (P3 Design) | Review the design for quality and completeness. |
| finops | devops | no | (on-demand) (-) | finops agent |
| growth | marketing | yes | 13b (P8 Operate, Grow & Engage) | Growth lead. Owns acquisition/activation/retention/referral, funnel, growth loops and experiments. |
| implement-api | implement | no | (on-demand) (-) | Implement API layer. Creates REST/GraphQL endpoints, request/response models, middleware, and API configuration. |
| implement-db | implement | no | (on-demand) (-) | Implement DB layer. Creates database schema, migrations, queries, and data access logic. |
| implement-logic | implement | no | (on-demand) (-) | Implement business logic layer. Creates core business rules, algorithms, validations, and domain logic. |
| implement-ui | implement | no | (on-demand) (-) | Implement UI layer. Creates React/Next. |
| insight-extractor | researcher | no | (on-demand) (-) | Insight extractor agent. Extracts key insights, quotes, ideas, and actionable items from content. |
| journal-writer | document | no | (on-demand) (-) | Journal writer agent. Creates reflective journal entries, personal reflections, and learning logs from content summaries. |
| legal-privacy | security | no | (on-demand) (-) | Legal & privacy counsel. Owns ToS, privacy policy, DPA, licensing, IP and compliance posture. |
| maintenance | devops | no | (on-demand) (-) | maintenance agent |
| package | devops | yes | 9 (P7 Delivery) | Packaging agent. Builds platform-specific packages, installers, and artifacts for the completed software product including BOM, security audits, licenses, and cross-platform packaging. |
| performance | validate | no | (on-demand) (-) | Performance Validation agent. Runs load tests, measures latency, throughput, and concurrent user capacity against NFR targets. |
| post-production | production-deploy | no | (on-demand) (-) | Post-Production Monitoring agent. Continuous SLO monitoring, error budget tracking, chaos testing, post-incident reviews. |
| pre-production | devops | no | (on-demand) (-) | Pre-Production Validation agent. Final check before production deployment. |
| presentation-generator | document | no | (on-demand) (-) | presentation-generator agent |
| pricing-strategist | product-owner | yes | 0d (P2 Business, Market & Monetization) | Pricing & monetization lead. Owns revenue model, pricing, packaging, unit economics, cost, profit and forecast. |
| product-analytics | product-owner | no | (on-demand) (-) | Product analytics lead. Owns product metrics, instrumentation, KPIs and experimentation design. |
| product-design-spec | design | yes | 1a (P3 Design) | Produce a structured product design specification. |
| production-deploy | devops | yes | 11 (P7 Delivery) | Production Deployment agent. Deploys to production with canary/blue-green strategy, feature flags, monitoring, rollback capability. |
| quality_gate | validate | no | (on-demand) (-) | Quality Gate agent. Performs release readiness assessment, go/no-go decisions, and quality gate enforcement. |
| review | design | no | (on-demand) (-) | Review agent. Reviews the design and architecture for correctness, completeness, and feasibility before implementation is allowed. |
| sales-crm | marketing | no | (on-demand) (-) | Sales & CRM lead (optional). Owns sales pipeline, CRM process, deal desk and B2B motions. |
| scout | researcher | no | (on-demand) (-) | Scout agent. Explores new territories, discovers opportunities, and identifies emerging trends and technologies. |
| security-audit | security | no | (on-demand) (-) | Security Audit agent. Runs security scans, penetration testing, vulnerability assessment. |
| static_verifier | code-review | no | (on-demand) (-) | "Static verification of contracts, schemas, and structural compliance". |
| summary-creator | document | no | (on-demand) (-) | Summary creator agent. Creates comprehensive summaries, executive briefs, and key takeaways from analyzed content. |
| theme-analyzer | researcher | no | (on-demand) (-) | Theme analyzer agent. Identifies themes, patterns, connections, and underlying structures in content. |
| ux-ia | design | yes | 1c (P3 Design) | Define UX and information architecture + design tokens. |
| visual_qa | implement-ui | yes | 4a-vqa,4b-vqa,4c-vqa,4d-vqa,4e-vqa,4f-vqa (P5 Implementation) | Verify rendered UI against the design spec. |

**Totals:** 61 agent cards · 15 primaries with sub-agents · 35 subagents · 24 agents in the default pipeline.

## Per-phase view - agents per phase (P1-P8)

**P1 Ideation & Discovery**
- Stage 0 (Ideation): `ideation`(root)
- Stage 0a (Discovery): `discovery`(root)

**P2 Business, Market & Monetization**
- Stage 0b (Business & Product Definition): `product-owner`(primary)
- Stage 0c (Market, Competition & Positioning): `researcher`(primary)
- Stage 0d (Monetization & Unit Economics): `pricing-strategist`(sub)
- Stage 0e (Go-to-Market & Customer Journey): `marketing`(primary)

**P3 Design**
- Stage 1 (Design): `design`(primary)
- Stage 1a (Product Design Spec): `product-design-spec`(sub)
- Stage 1b (Design Review): `design_critic`(sub)
- Stage 1c (UX/IA Review): `ux-ia`(sub)
- Stage 1d (Research): `researcher`(primary)

**P4 Architecture**
- Stage 2 (Architect): `architect`(primary)
- Stage 3 (Refine Requirements): `orchestrator`(root)
- Stage 3a (QA Spec Review): `validate`(primary)

**P5 Implementation**
- Stage 4a (Implementation Iteration 1): `implement`(primary), `devops`(primary), `code-review`(primary), `validate`(primary)
- Stage 4b (Implementation Iteration 2): `implement`(primary), `devops`(primary), `code-review`(primary), `validate`(primary)
- Stage 4c (Implementation Iteration 3): `implement`(primary), `devops`(primary), `code-review`(primary), `validate`(primary)
- Stage 4d (Implementation Iteration 4): `implement`(primary), `devops`(primary), `code-review`(primary), `validate`(primary)
- Stage 4e (Implementation Iteration 5): `implement`(primary), `devops`(primary), `code-review`(primary), `validate`(primary)
- Stage 4f (Implementation Iteration 6): `implement`(primary), `devops`(primary), `code-review`(primary), `validate`(primary)
- Stage 4-0 (Skeleton): `implement`(primary), `devops`(primary)
- Stage 4a-vqa (Visual QA (Iteration 1)): `visual_qa`(sub)
- Stage 4b-vqa (Visual QA (Iteration 2)): `visual_qa`(sub)
- Stage 4c-vqa (Visual QA (Iteration 3)): `visual_qa`(sub)
- Stage 4d-vqa (Visual QA (Iteration 4)): `visual_qa`(sub)
- Stage 4e-vqa (Visual QA (Iteration 5)): `visual_qa`(sub)
- Stage 4f-vqa (Visual QA (Iteration 6)): `visual_qa`(sub)

**P6 Verification**
- Stage 5 (Security Scan): `security`(primary)
- Stage 6 (NFR Tests): `validate`(primary)
- Stage 7 (Full Test Suite): `validate`(primary)

**P7 Delivery**
- Stage 8 (Document): `document`(primary)
- Stage 9 (Package): `package`(sub)
- Stage 10 (Pre-Production): `devops`(primary), `orchestrator`(root)
- Stage 11 (Deploy): `devops`(primary), `production-deploy`(primary)
- Stage 12 (Exit): `orchestrator`(root)
- Stage 10a (QA Go/No-Go): `validate`(primary)

**P8 Operate, Grow & Engage**
- Stage 13 (Operate & Observability): `observer`(root)
- Stage 13a (Customer Success & Support): `customer-success`(primary)
- Stage 13b (Growth, Engagement & Feedback): `growth`(primary)

_Role: `root` = standalone (no parent), `primary` = has sub-agents, `sub` = subagent. Agents not listed here (…on-demand) are invoked selectively, not in the default flow._

## Capability needs per agent (proposed — feeds BI-0221/0222/0223)
| agent | role | parent | stage/phase | in_default | needs_tools | proposed reasoning | needs_structured |
|---|---|---|---|---|---|---|---|
| a11y-audit | subagent | security | (on-demand) (-) | no |  | medium |  |
| agent_config | subagent | - | (on-demand) (-) | no |  | low |  |
| analyst | subagent | - | (on-demand) (-) | no |  | low |  |
| architect | subagent | - | 2 (P4 Architecture) | yes |  | high | yes |
| code-review | subagent | - | 4a,4b,4c,4d,4e,4f (P5 Implementation) | yes |  | medium |  |
| community-social | primary | marketing | (on-demand) (-) | no |  | low |  |
| consensus | subagent | - | (on-demand) (-) | no |  | high | yes |
| content-creator | subagent | document | (on-demand) (-) | no |  | low |  |
| content-reader | subagent | document | (on-demand) (-) | no |  | low |  |
| customer-onboarding | subagent | marketing | (on-demand) (-) | no |  | low |  |
| customer-success | primary | - | 13a (P8 Operate, Grow & Engage) | yes |  | low |  |
| design | subagent | - | 1 (P3 Design) | yes |  | medium | yes |
| design_critic | subagent | design | 1b (P3 Design) | yes |  | medium | yes |
| devops | subagent | - | 10,11,4-0,4a,4b,4c,4d,4e,4f (P5 Implementation/P7 Delivery) | yes | yes | low |  |
| discovery | subagent | - | 0a (P1 Ideation & Discovery) | yes |  | medium | yes |
| document | subagent | - | 8 (P7 Delivery) | yes |  | low |  |
| finops | subagent | devops | (on-demand) (-) | no |  | low |  |
| fix | subagent | - | (on-demand) (-) | no | yes | low |  |
| growth | primary | marketing | 13b (P8 Operate, Grow & Engage) | yes |  | low |  |
| guardian | subagent | - | (on-demand) (-) | no |  | high | yes |
| ideation | primary | - | 0 (P1 Ideation & Discovery) | yes |  | medium | yes |
| implement | subagent | - | 4-0,4a,4b,4c,4d,4e,4f (P5 Implementation) | yes | yes | low |  |
| implement-api | subagent | implement | (on-demand) (-) | no |  | low |  |
| implement-db | subagent | implement | (on-demand) (-) | no |  | low |  |
| implement-logic | subagent | implement | (on-demand) (-) | no |  | low |  |
| implement-ui | subagent | implement | (on-demand) (-) | no | yes | low |  |
| inference | subagent | - | (on-demand) (-) | no |  | high | yes |
| ingestion | subagent | - | (on-demand) (-) | no |  | low |  |
| insight-extractor | subagent | researcher | (on-demand) (-) | no |  | low |  |
| iterative_evaluator | subagent | - | (on-demand) (-) | no |  | high | yes |
| journal-writer | subagent | document | (on-demand) (-) | no |  | low |  |
| legal-privacy | primary | security | (on-demand) (-) | no |  | low |  |
| maintenance | subagent | devops | (on-demand) (-) | no |  | medium |  |
| marketing | subagent | - | 0e (P2 Business, Market & Monetization) | yes |  | low |  |
| observer | subagent | - | 13 (P8 Operate, Grow & Engage) | yes |  | high | yes |
| orchestrator | primary | - | 10,12,3 (P4 Architecture/P7 Delivery) | yes |  | high | yes |
| package | subagent | devops | 9 (P7 Delivery) | yes |  | low |  |
| performance | subagent | validate | (on-demand) (-) | no |  | medium |  |
| post-production | subagent | production-deploy | (on-demand) (-) | no |  | low |  |
| pre-production | subagent | devops | (on-demand) (-) | no |  | low |  |
| presentation-generator | subagent | document | (on-demand) (-) | no |  | low |  |
| pricing-strategist | primary | product-owner | 0d (P2 Business, Market & Monetization) | yes |  | low |  |
| product-analytics | primary | product-owner | (on-demand) (-) | no |  | low |  |
| product-analyzer | subagent | - | (on-demand) (-) | no |  | medium | yes |
| product-design-spec | subagent | design | 1a (P3 Design) | yes |  | medium | yes |
| product-owner | primary | - | 0b (P2 Business, Market & Monetization) | yes |  | medium | yes |
| production-deploy | subagent | devops | 11 (P7 Delivery) | yes |  | low |  |
| quality_gate | subagent | validate | (on-demand) (-) | no |  | medium |  |
| researcher | subagent | - | 0c,1d (P2 Business, Market & Monetization/P3 Design) | yes |  | medium | yes |
| review | subagent | design | (on-demand) (-) | no |  | medium | yes |
| sales-crm | primary | marketing | (on-demand) (-) | no |  | low |  |
| scout | subagent | researcher | (on-demand) (-) | no |  | low |  |
| security | subagent | - | 5 (P6 Verification) | yes |  | medium |  |
| security-audit | subagent | security | (on-demand) (-) | no |  | medium |  |
| static_verifier | subagent | code-review | (on-demand) (-) | no |  | medium |  |
| strategist | subagent | - | (on-demand) (-) | no |  | low |  |
| summary-creator | subagent | document | (on-demand) (-) | no |  | low |  |
| theme-analyzer | subagent | researcher | (on-demand) (-) | no |  | low |  |
| ux-ia | subagent | design | 1c (P3 Design) | yes |  | medium | yes |
| validate | subagent | - | 10a,3a,4a,4b,4c,4d,4e,4f,6,7 (P4 Architecture/P5 Implementation/P6 Verification/P7 Delivery) | yes | yes | medium |  |
| visual_qa | subagent | implement-ui | 4a-vqa,4b-vqa,4c-vqa,4d-vqa,4e-vqa,4f-vqa (P5 Implementation) | yes |  | medium |  |

## Per-agent table (current vs recommended)
| agent | role | parent | stage/phase | class | tools | req-sections | flags | recommended updates |
|---|---|---|---|---|---|---|---|---|
| a11y-audit | subagent | security | (on-demand) (-) | Verification/QA | list_dir, read_file, run_command, write_file | - | - | independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on. |
| agent_config | subagent | - | (on-demand) (-) | Implementation | none (markdown) | - | - | coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on. |
| analyst | subagent | - | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| architect | subagent | - | 2 (P4 Architecture) | Architecture | none (markdown) | architecture_style,tech_stack,components,security,adrs | verbose,auto | keep decision-JSON-first; role/goal/backstory; trade-offs + ADR ids; reasoning high; structured_output on. |
| code-review | subagent | - | 4a,4b,4c,4d,4e,4f (P5 Implementation) | Verification/QA | list_dir, read_file, run_command, write_file | - | - | independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on. |
| community-social | primary | marketing | (on-demand) (-) | Business/Content | read_file, write_file, list_dir, http_get | channels,content,engagement,advocacy | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| consensus | subagent | - | (on-demand) (-) | Orchestration | none (markdown) | - | - | explicit control-flow contract; termination signals; decision JSON; reasoning high. |
| content-creator | subagent | document | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| content-reader | subagent | document | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| customer-onboarding | subagent | marketing | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| customer-success | primary | - | 13a (P8 Operate, Grow & Engage) | Business/Content | read_file, write_file, list_dir | onboarding,support_model,health,retention | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| design | subagent | - | 1 (P3 Design) | Product/Design | none (markdown) | per_feature,functional,functional_requirements,non_functional_requirements,user_stories,api_contracts | verbose,pf,sectioned | role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on. |
| design_critic | subagent | design | 1b (P3 Design) | Product/Design | none (markdown) | - | verbose | role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on. |
| devops | subagent | - | 10,11,4-0,4a,4b,4c,4d,4e,4f (P5 Implementation/P7 Delivery) | Implementation | list_dir, read_file, run_command, write_file | - | - | coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on. |
| discovery | subagent | - | 0a (P1 Ideation & Discovery) | Product/Design | none (markdown) | - | verbose | role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on. |
| document | subagent | - | 8 (P7 Delivery) | Business/Content | list_dir, read_file, run_command, write_file | overview,installation,usage,api_reference,user_guide | verbose,auto | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| finops | subagent | devops | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| fix | subagent | - | (on-demand) (-) | Implementation | list_dir, read_file, run_command, write_file | - | - | coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on. |
| growth | primary | marketing | 13b (P8 Operate, Grow & Engage) | Business/Content | read_file, write_file, list_dir, http_get | funnel_model,channels,loops,experiments | verbose | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| guardian | subagent | - | (on-demand) (-) | Orchestration | none (markdown) | - | - | explicit control-flow contract; termination signals; decision JSON; reasoning high. |
| ideation | primary | - | 0 (P1 Ideation & Discovery) | Product/Design | none (markdown) | vision,features,success_criteria | verbose,auto | role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on. |
| implement | subagent | - | 4-0,4a,4b,4c,4d,4e,4f (P5 Implementation) | Implementation | list_dir, read_file, run_command, write_file | - | - | coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on. |
| implement-api | subagent | implement | (on-demand) (-) | Implementation | list_dir, read_file, run_command, write_file | - | - | coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on. |
| implement-db | subagent | implement | (on-demand) (-) | Implementation | list_dir, read_file, run_command, write_file | - | - | coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on. |
| implement-logic | subagent | implement | (on-demand) (-) | Implementation | list_dir, read_file, run_command, write_file | - | - | coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on. |
| implement-ui | subagent | implement | (on-demand) (-) | Implementation | list_dir, read_file, run_command, write_file | - | - | coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on. |
| inference | subagent | - | (on-demand) (-) | Orchestration | list_dir, read_file, write_file | - | - | explicit control-flow contract; termination signals; decision JSON; reasoning high. |
| ingestion | subagent | - | (on-demand) (-) | Implementation | list_dir, read_file, run_command, write_file | - | - | coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on. |
| insight-extractor | subagent | researcher | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| iterative_evaluator | subagent | - | (on-demand) (-) | Orchestration | list_dir, read_file, run_command, write_file | - | - | explicit control-flow contract; termination signals; decision JSON; reasoning high. |
| journal-writer | subagent | document | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| legal-privacy | primary | security | (on-demand) (-) | Business/Content | read_file, write_file, list_dir, http_get | terms,privacy,ip_licensing,compliance | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| maintenance | subagent | devops | (on-demand) (-) | Verification/QA | none (markdown) | - | - | independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on. |
| marketing | subagent | - | 0e (P2 Business, Market & Monetization) | Business/Content | none (markdown) | gtm,funnel,onboarding,lifecycle | verbose | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| observer | subagent | - | 13 (P8 Operate, Grow & Engage) | Orchestration | none (markdown) | monitoring,slo,incidents,health | - | explicit control-flow contract; termination signals; decision JSON; reasoning high. |
| orchestrator | primary | - | 10,12,3 (P4 Architecture/P7 Delivery) | Orchestration | none (markdown) | - | - | explicit control-flow contract; termination signals; decision JSON; reasoning high. |
| package | subagent | devops | 9 (P7 Delivery) | Implementation | list_dir, read_file, run_command, write_file | - | - | coding-agent edit discipline (write-first, minimal diff, no exploration); explicit tool contract + subset; run tests/build then summarize; reasoning low/med; tools on. |
| performance | subagent | validate | (on-demand) (-) | Verification/QA | list_dir, read_file, run_command, write_file | - | - | independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on. |
| post-production | subagent | production-deploy | (on-demand) (-) | Delivery/Ops | list_dir, read_file, run_command, write_file | - | - | canary/rollback + guardrails (keep); tool subset; status JSON; reasoning low. |
| pre-production | subagent | devops | (on-demand) (-) | Delivery/Ops | list_dir, read_file, run_command, write_file | - | - | canary/rollback + guardrails (keep); tool subset; status JSON; reasoning low. |
| presentation-generator | subagent | document | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| pricing-strategist | primary | product-owner | 0d (P2 Business, Market & Monetization) | Business/Content | read_file, write_file, list_dir, http_get | revenue_model,pricing,unit_economics,cost_profit | verbose | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| product-analytics | primary | product-owner | (on-demand) (-) | Business/Content | read_file, write_file, list_dir | metric_tree,events,kpis,experiments | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| product-analyzer | subagent | - | (on-demand) (-) | Product/Design | none (markdown) | - | verbose | role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on. |
| product-design-spec | subagent | design | 1a (P3 Design) | Product/Design | none (markdown) | per_feature,diagrams,api_contracts,test_plan,traceability | verbose,pf,sectioned | role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on. |
| product-owner | primary | - | 0b (P2 Business, Market & Monetization) | Product/Design | read_file, list_dir, write_file | vision,target_customers,jtbd,success_metrics,ai_integration | verbose | role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on. |
| production-deploy | subagent | devops | 11 (P7 Delivery) | Delivery/Ops | list_dir, read_file, run_command, write_file | - | - | canary/rollback + guardrails (keep); tool subset; status JSON; reasoning low. |
| quality_gate | subagent | validate | (on-demand) (-) | Verification/QA | none (markdown) | - | - | independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on. |
| researcher | subagent | - | 0c,1d (P2 Business, Market & Monetization/P3 Design) | Product/Design | none (markdown) | market,competition,positioning | - | role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on. |
| review | subagent | design | (on-demand) (-) | Product/Design | list_dir, read_file, write_file | - | verbose | role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on. |
| sales-crm | primary | marketing | (on-demand) (-) | Business/Content | read_file, write_file, list_dir | pipeline,qualification,crm,deal_desk | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| scout | subagent | researcher | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| security | subagent | - | 5 (P6 Verification) | Verification/QA | list_dir, read_file, run_command, write_file | - | - | independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on. |
| security-audit | subagent | security | (on-demand) (-) | Verification/QA | list_dir, read_file, run_command, write_file | - | - | independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on. |
| static_verifier | subagent | code-review | (on-demand) (-) | Verification/QA | list_dir, read_file, run_command, write_file | - | - | independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on. |
| strategist | subagent | - | (on-demand) (-) | Business/Content | none (markdown) | - | verbose | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| summary-creator | subagent | document | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| theme-analyzer | subagent | researcher | (on-demand) (-) | Business/Content | none (markdown) | - | - | role/goal/backstory; structured fields; grounded (cite/assumptions), never fabricate; reasoning low/med. |
| ux-ia | subagent | design | 1c (P3 Design) | Product/Design | none (markdown) | design_tokens | verbose | role/goal/backstory; structured-fields + deterministic render; strict 'no-invention' + non-goals; reasoning med; structured_output on. |
| validate | subagent | - | 10a,3a,4a,4b,4c,4d,4e,4f,6,7 (P4 Architecture/P5 Implementation/P6 Verification/P7 Delivery) | Verification/QA | list_dir, read_file, run_command, write_file | - | - | independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on. |
| visual_qa | subagent | implement-ui | 4a-vqa,4b-vqa,4c-vqa,4d-vqa,4e-vqa,4f-vqa (P5 Implementation) | Verification/QA | none (markdown) | - | - | independent-reviewer bias (ChatDev); evidence + verdict rules; adversarial 'find problems'; reasoning med/high; tools on. |

## Notes
- `req-sections` = current ESSENTIAL required-section keys (config).
- `role`: primary vs subagent; `parent`: owning primary (`core/agent_hierarchy.py`); `stage/phase`: where it runs (from `pipeline-definition.json`); on-demand agents show `(on-demand)`.
- Many cards still hardcode `model: opencode-go/mimo-v2.5`; at runtime the tier/router overrides — recommend removing the hardcoded model and relying on the capability vector + tier.
- See `pipeline_review_recommendations.md` for the full consolidated analysis and backlog IDs.

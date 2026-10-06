# Product Forge 4.x/5.x --- Unified Platform, Runtime, Licensing, Deployment, White-Label/OEM & Product-Generation Architecture

**Status:** Target architecture and implementation blueprint\
**Purpose:** Primary implementation baseline for Product Forge's next
evolution\
**Scope:** Product Forge platform + Product Forge Build/Factory +
generated software products/apps + agents/swarms + SaaS + Enterprise +
Community + OEM/white-label + on-prem/air-gapped deployments\
**Baseline considered:** Existing Product Forge 4.x
architecture/repository reconciliation, prior audit remediation, modular
Python implementation, current 39-stage/8-phase pipeline, Agent Runtime,
model catalog/router, memory/knowledge/skills, artifacts, QA,
deployment, licensing/billing, telemetry and commercial primitives.\
**Architecture principle:** Controlled evolution; do not restart or
rewrite working functionality merely to adopt this architecture.

> **RECONCILIATION (BI-PF-0392 / A0):** The **CODE-ALIGNED AMENDMENT** (section §3038 onward) is the
> **authority** wherever it conflicts with earlier sections. The **working authority** for the current program
> is the consolidated plan `docs/PF-TARGET-ARCHITECTURE-AND-IP-PLAN.md`; decisions are recorded in
> `docs/ARCHITECTURE-DECISIONS.md` (ADR register). The baseline is frozen in `docs/PF-BASELINE.md`.
> Note: prose stage-counts ("39-stage" here vs "16-stage" in §T) are descriptive, not contractual — the repo
> pipeline is the authority. Scope: this program is about the **PF platform itself**; the generated-product
> runtime and any EAP *executor* are a separate, parked concern.

------------------------------------------------------------------------

## 0. Executive Decision

Product Forge should evolve into a **technology-independent product
engineering and agent runtime platform** rather than remain a
Python-only application.

The target is a **hybrid polyglot platform**:

  --------------------------------------------------------------------------
  Layer                   Primary technology      Role
  ----------------------- ----------------------- --------------------------
  Experience / UI         TypeScript +            Dashboard, visual builder,
                          React/Next.js           admin, OEM branding,
                                                  product/project UX

  Platform Runtime        Go                      API, orchestration,
                                                  execution, workers,
                                                  scheduler, queues, CLI,
                                                  packaging/runtime control

  AI / Intelligence       Python                  LLM integration, agents,
                                                  RAG/CAG/OKF, memory,
                                                  multimodal processing,
                                                  evaluation, AI
                                                  experimentation

  Protected Native Core   Rust, selectively       Security-sensitive
                                                  execution, sandboxing,
                                                  high-value proprietary
                                                  algorithms, selected
                                                  decision/policy components

  Plugin / portable       WASM, later             Sandboxed portable
  execution                                       plugins,
                                                  skills/tools/extensions,
                                                  selected untrusted or
                                                  third-party execution

  Infrastructure          Docker/OCI + Kubernetes Packaging, deployment and
                          where needed            scaling

  Data                    PostgreSQL + object     Authoritative state,
                          storage + cache/event   artifacts,
                          infrastructure + vector memory/knowledge,
                          capability              telemetry and runtime data
  --------------------------------------------------------------------------

**Do not rewrite Product Forge into Go or Rust.**

Instead:

``` text
CURRENT
Python Product Forge
        |
        v
CONTROLLED EVOLUTION
        |
        +-- TypeScript: Experience
        +-- Go: Platform Runtime
        +-- Python: AI/Intelligence
        +-- Rust: Selective Protected Core
        +-- WASM: Optional sandbox/plugin layer
```

The current Python implementation remains valuable and becomes the
initial **AI/Factory implementation substrate** while stable
language-independent contracts are introduced.

------------------------------------------------------------------------

# 1. The Core Strategic Change

Product Forge must become two closely related but independently
deployable concepts:

``` text
                         PRODUCT FORGE
                              |
              +---------------+----------------+
              |                                |
              v                                v
       PRODUCT FACTORY                    PRODUCT RUNTIME
              |                                |
       BUILD / GENERATE                    RUN / OPERATE
              |                                |
       Requirements                       Agents
       Architecture                       Workflows
       Code                                Tools
       Tests                               Memory
       BOM                                 Models
       Packaging                           Security
       Deployment                          Observability
       Licensing                           Runtime policy
```

The **Factory** creates a product/runtime package.

The **Runtime** executes that package.

This BUILD/RUN separation is one of the most important architectural
changes.

------------------------------------------------------------------------

# 2. Product Forge Is Not One Product Anymore

Product Forge should be treated as a platform with several deployable
forms:

``` text
Product Forge Platform
|
+-- Product Forge SaaS
|
+-- Product Forge Enterprise
|      +-- Customer VPC
|      +-- On-prem
|      +-- Air-gapped
|
+-- Product Forge Community
|
+-- Product Forge OEM / White Label
|
+-- Product Forge Embedded Runtime
|
+-- Product Forge Build SDK / CLI
|
+-- Generated Product Runtime
```

A generated product can itself be:

``` text
Software application
Web application
Mobile application
Desktop application
API/service
Data platform
AI application
Agent
Agent swarm
Workflow automation
MCP server
Tool server
Hybrid application
Enterprise automation
```

------------------------------------------------------------------------

# 3. Product Forge Target Plane Architecture

``` text
                                PRODUCT FORGE
                                     |
        +----------------------------+----------------------------+
        |                            |                            |
        v                            v                            v
   FACTORY PLANE                EXECUTION PLANE              COMMERCIAL PLANE
        |                            |                            |
   Intake/compiler              Agent Runtime                 Licensing
   Architecture                 Workflow Runtime              Entitlements
   Tech selection               Tool Gateway                  Billing
   Code generation              Model Gateway                 Metering
   Test generation              Memory Gateway                Plans
   QA/gates                     Security Policy                OEM
   BOM generation               Runtime Policy                 White Label
   Packaging                    Observability                  Usage/COGS
   Deployment planning          Infrastructure Gateway
        |                            |
        +----------------------------+
                     |
                     v
             SHARED PLATFORM PLANE
                     |
       +-------------+-------------+-------------+
       |             |             |             |
       v             v             v             v
   Identity      Security      Data/State    Observability
   Tenancy       Governance    Artifacts      Audit/Evidence
```

------------------------------------------------------------------------

# 4. Four Major Product Forge Planes

## 4.1 Factory Plane

Responsible for producing a deployable product.

``` text
Intake
  |
Requirements Compiler
  |
Product Definition
  |
Architecture Decision Engine
  |
Technology Selection
  |
Agent/Workflow Design
  |
Model/Tool Selection
  |
Code Generation
  |
Test Generation
  |
Security/License Analysis
  |
BOM Generation
  |
Package Compiler
  |
Release Artifact
```

## 4.2 Execution Plane

Responsible for operating generated products.

``` text
EAP / Product Package
        |
Runtime Loader
        |
Policy Validation
        |
Agent Runtime
        |
Workflow Runtime
        |
Model Gateway
        |
Tool Gateway
        |
Memory/Knowledge Gateway
        |
Infrastructure Gateway
        |
Observability
```

## 4.3 Commercial Plane

Responsible for:

-   plans
-   licensing
-   entitlements
-   metering
-   billing
-   COGS
-   usage
-   OEM
-   white label
-   subscriptions
-   feature capabilities
-   deployment rights

## 4.4 Shared Platform Plane

Responsible for:

-   identity
-   tenancy
-   security
-   secrets
-   policy
-   audit
-   persistence
-   artifact registry
-   observability
-   eventing
-   configuration
-   versioning

------------------------------------------------------------------------

# 5. Technology Architecture

## 5.1 TypeScript --- Experience Layer

Use TypeScript for:

-   React/Next.js UI
-   dashboard
-   visual pipeline builder
-   agent builder
-   product builder
-   architecture visualization
-   administration
-   tenant management
-   OEM branding
-   white-label UI
-   customer portal
-   billing/usage UI
-   operational console

Do not make TypeScript/Node the primary protected Product Forge runtime.

------------------------------------------------------------------------

# 6. Go --- Product Forge Platform Runtime

Go becomes the main compiled platform runtime.

Target responsibilities:

``` text
Go Runtime
|
+-- API gateway/application API
+-- orchestration control
+-- execution control
+-- job scheduler
+-- queue workers
+-- runtime lifecycle
+-- EAP loader
+-- package manager
+-- plugin manager
+-- license verification
+-- entitlement enforcement
+-- deployment controller
+-- update controller
+-- runtime telemetry
+-- CLI
+-- service discovery
+-- concurrency-heavy infrastructure
```

Why Go:

-   native binaries
-   fast compilation
-   strong networking
-   concurrency support
-   simple deployment
-   good Kubernetes/container integration
-   cross-platform compilation
-   low operational complexity

Go is designed for systems programming and has explicit support for
concurrent programming; its toolchain produces compiled executables. Use
these properties for the Product Forge platform/runtime rather than for
every AI component.

------------------------------------------------------------------------

# 7. Python --- AI and Factory Intelligence

Continue using Python for:

``` text
AI
|
+-- Agent intelligence
+-- LLM adapters
+-- RAG
+-- CAG
+-- OKF
+-- Agent memory
+-- Knowledge processing
+-- Multimodal processing
+-- Evaluation
+-- experimentation
+-- data processing
+-- model-specific integrations
+-- AI product intelligence
+-- code intelligence
```

Do not remove the existing Python modules just because Go/Rust are
introduced.

Instead create stable service/API boundaries.

Preferred:

``` text
Go Runtime
     |
     | gRPC / HTTP / internal protocol
     v
Python AI Service
     |
     +-- Agent
     +-- LLM
     +-- RAG
     +-- Memory
     +-- Evaluation
```

Avoid deep Go-to-Python internal imports.

------------------------------------------------------------------------

# 8. Rust --- Selective Protected Native Layer

Rust is a systems programming language with compile-time ownership/type
checks that are designed to provide memory safety without a garbage
collector.

Use Rust only where it adds meaningful value.

Candidate Product Forge components:

``` text
Rust
|
+-- secure execution/sandbox components
+-- sensitive policy enforcement
+-- selected decision engine algorithms
+-- high-value proprietary algorithms
+-- native parsers where security is important
+-- performance-sensitive components
+-- cryptographic/security primitives where appropriate
+-- selected runtime isolation components
```

Rust is NOT the default replacement for Python or Go.

The decision rule is:

``` text
Need AI/data/rapid experimentation?
    -> Python

Need platform/networking/orchestration/runtime?
    -> Go

Need memory-safe native/security/performance-sensitive implementation?
    -> Rust
```

Rust's ownership model and type system are specifically useful for
memory safety and concurrency-sensitive native components.

------------------------------------------------------------------------

# 9. WebAssembly --- Optional Future Plugin/Sandbox Layer

WASM should be introduced only after the core runtime is stable.

Potential use:

``` text
Product Forge Runtime
        |
     WASM Host
        |
 +------+------+------+
 |      |      |      |
Tool  Skill  Plugin  Extension
```

Good candidates:

-   third-party plugins
-   customer-developed extensions
-   portable tools
-   sandboxed skill execution
-   deterministic compute
-   selected generated-product components

WASM is a portable binary instruction format with sandboxing and
non-browser embeddings. It is therefore attractive as a future extension
boundary, but it should not become a Phase-1 dependency.

------------------------------------------------------------------------

# 10. Language-Independent Contracts

This is more important than the choice of languages.

Define canonical contracts for:

``` text
ProductSpec
ArchitectureSpec
TechnologyProfile
AgentSpec
AgentTopology
SkillSpec
ToolSpec
ModelSpec
MemoryPolicy
RuntimeProfile
SecurityPolicy
DeploymentProfile
LicenseProfile
EntitlementProfile
EAPManifest
BOM
TestManifest
EvidenceManifest
ReleaseManifest
```

All languages communicate through these contracts.

Preferred implementation:

``` text
JSON Schema / OpenAPI / Protobuf
```

Use:

-   REST/OpenAPI for external APIs
-   gRPC/Protobuf for high-throughput internal service contracts where
    useful
-   event schemas for asynchronous execution
-   MCP for tool/model ecosystem interoperability where appropriate

------------------------------------------------------------------------

# 11. The Executable Product Package --- EAP

The EAP becomes the central artifact between Factory and Runtime.

``` text
Product Definition
       |
       v
EAP Compiler
       |
       v
+--------------------------------+
| Executable Product Package     |
|                                |
| manifest                       |
| agents                         |
| workflows                      |
| skills                         |
| tools                          |
| model policy                   |
| memory policy                  |
| runtime profile                |
| security policy                |
| deployment profile             |
| license profile                |
| entitlement requirements       |
| tests                          |
| BOMs                           |
| provenance                     |
| signatures                     |
| version/compatibility          |
+--------------------------------+
       |
       v
Product Forge Runtime
```

The EAP must be versioned, signed and reproducible.

------------------------------------------------------------------------

# 12. Build Artifact Hierarchy

Do not confuse source code, package, runtime and deployment image.

``` text
SOURCE
  |
  v
Build
  |
  +--> source artifact
  |
  +--> compiled runtime
  |
  +--> generated application
  |
  +--> EAP
  |
  +--> container image
  |
  +--> deployment bundle
  |
  +--> SBOM
  |
  +--> provenance
  |
  +--> signature
```

------------------------------------------------------------------------

# 13. IP Protection Architecture

The architecture should use three IP zones.

## Zone A --- Open/Visible

Potentially:

-   SDK
-   public API contracts
-   plugin interfaces
-   MCP interfaces
-   schemas
-   community adapters
-   CLI portions
-   documentation
-   examples

## Zone B --- Protected Runtime

Prefer compiled/protected components:

-   Go runtime
-   selected Rust components
-   runtime control
-   licensing/entitlement runtime
-   policy enforcement

## Zone C --- Proprietary Intelligence

Prefer service-side execution:

-   advanced planning
-   proprietary optimization
-   advanced decision intelligence
-   commercial heuristics
-   proprietary product intelligence
-   high-value learning/optimization logic

Architecture:

``` text
Customer
   |
   v
Go Product Forge Runtime
   |
   +--> local permitted functionality
   |
   +--> protected runtime components
   |
   +--> proprietary Product Forge services
              |
              v
       proprietary intelligence
```

No design can make software delivered to a customer machine impossible
to reverse engineer. The goal is to minimize delivered source, isolate
the highest-value IP and enforce authorized use.

------------------------------------------------------------------------

# 14. Licensing Architecture

Create a first-class licensing subsystem.

``` text
licensing/
|
+-- license authority
+-- license format
+-- license verification
+-- signing
+-- deployment identity
+-- activation
+-- renewal
+-- offline activation
+-- grace periods
+-- revocation
+-- entitlement mapping
+-- usage rights
```

Cryptographic model:

``` text
Product Forge Licensing Authority
          |
      private key
          |
          v
     Signed License
          |
          v
 Customer Runtime
          |
   public-key verification
```

Private signing keys never ship with Product Forge.

------------------------------------------------------------------------

# 15. Entitlement Architecture

Separate:

``` text
License
```

from:

``` text
Entitlement
```

License answers:

> What legal/product rights exist?

Entitlement answers:

> What capabilities are enabled for this deployment/tenant/user/product?

Example:

``` text
Enterprise License
|
+-- agent_runtime = enabled
+-- swarm = enabled
+-- advanced_memory = enabled
+-- rag = enabled
+-- cag = enabled
+-- okf = enabled
+-- private_models = enabled
+-- on_prem = enabled
+-- airgap = enabled
+-- max_agents = 100
+-- max_concurrent_runs = 20
```

Capability checks should occur at execution boundaries rather than
scattered `if licensed` statements.

------------------------------------------------------------------------

# 16. Capability Registry

Create a central capability registry.

Example:

``` text
PF.UI.DASHBOARD
PF.FACTORY.PRODUCT_GENERATION
PF.FACTORY.CODE_GENERATION
PF.AGENT.RUNTIME
PF.AGENT.SWARM
PF.MEMORY
PF.RAG
PF.CAG
PF.OKF
PF.MCP
PF.MODEL.ROUTING
PF.DECISION_ENGINE
PF.SECURITY
PF.GOVERNANCE
PF.OEM
PF.WHITE_LABEL
PF.ON_PREM
PF.AIR_GAPPED
PF.BYOK
PF.BYOM
PF.ADVANCED_ANALYTICS
PF.COST_OPTIMIZATION
```

This allows the same runtime to support multiple editions without forks.

------------------------------------------------------------------------

# 17. Product Forge Deployment Models

## 17.1 Community

``` text
User
 |
 v
Product Forge Community
 |
 +-- local runtime
 +-- open components
 +-- community plugins
 +-- selected AI capabilities
```

Use an open-source license selected intentionally after legal review.

Do not accidentally expose proprietary modules merely because the
Community edition is open.

------------------------------------------------------------------------

## 17.2 Professional

``` text
User
 |
 v
Product Forge Professional
 |
 +-- protected runtime
 +-- licensing
 +-- advanced capabilities
 +-- cloud model providers
```

------------------------------------------------------------------------

## 17.3 Enterprise SaaS

``` text
Customer
   |
   v
Product Forge SaaS
   |
   +-- Control Plane
   +-- Factory Plane
   +-- Execution Plane
   +-- Commercial Plane
   +-- proprietary intelligence
```

Highest IP protection because proprietary code can remain server-side.

------------------------------------------------------------------------

## 17.4 Enterprise VPC

``` text
Customer AWS/Azure/GCP
        |
        v
Product Forge Enterprise
        |
        +-- Go runtime
        +-- protected services
        +-- customer data
        +-- customer model access
        +-- customer networking
```

------------------------------------------------------------------------

## 17.5 Enterprise On-Prem

``` text
Customer Data Center
        |
        +-- UI
        +-- Go runtime
        +-- Python AI workers where required
        +-- Rust protected components
        +-- database
        +-- object storage
        +-- license service
```

Use compiled/protected artifacts and signed deployment packages.

------------------------------------------------------------------------

## 17.6 Air-Gapped

``` text
No Internet
    |
    +-- Product Forge Runtime
    +-- local registry
    +-- offline license
    +-- offline update package
    +-- local model adapters
    +-- local data
    +-- audit
```

Use offline license certificates, signed update bundles and explicit
entitlement expiration/grace policies.

------------------------------------------------------------------------

## 17.7 OEM / White Label

``` text
OEM Customer
     |
     v
OEM Configuration
     |
     +-- brand
     +-- logo
     +-- domain
     +-- theme
     +-- product name
     +-- terminology
     +-- enabled capabilities
     +-- models
     +-- workflows
     +-- integrations
     |
     v
Product Forge Runtime
```

One core platform can generate many branded products.

------------------------------------------------------------------------

# 18. OEM Build Profile

Add:

``` text
build_profiles/
|
+-- community.yaml
+-- professional.yaml
+-- enterprise.yaml
+-- enterprise_vpc.yaml
+-- enterprise_onprem.yaml
+-- enterprise_airgap.yaml
+-- oem.yaml
+-- embedded.yaml
```

Each profile specifies:

``` text
source inclusion
compiled components
services
features
capabilities
license
entitlements
branding
deployment
update channel
telemetry policy
security profile
model policy
```

------------------------------------------------------------------------

# 19. White-Label Architecture

White-label must not fork source code.

Use:

``` text
WhiteLabelProfile
|
+-- identity
+-- branding
+-- theme
+-- domain
+-- UI
+-- email
+-- documentation
+-- terminology
+-- feature set
+-- default agents
+-- default workflows
```

At build/deployment time:

``` text
Product Forge Base
        +
OEM Profile
        +
License
        +
Entitlements
        +
Deployment Profile
        |
        v
OEM Product
```

------------------------------------------------------------------------

# 20. Commercial Model

Product Forge should support multiple commercial modes:

``` text
License modes
|
+-- free/community
+-- subscription
+-- usage-based
+-- seat-based
+-- agent/run-based
+-- compute-based
+-- enterprise annual
+-- perpetual + maintenance
+-- OEM license
+-- embedded runtime license
+-- hybrid subscription + usage
```

Do not hard-code one billing model into the runtime.

Commercial policy is data/configuration.

------------------------------------------------------------------------

# 21. Generated Product Technology Selection Layer

This is a major new capability.

Product Forge must choose the technology stack for the **product being
built**, independently from Product Forge's own stack.

``` text
User Requirements
       |
       v
Product Analyzer
       |
       v
Architecture Decision Engine
       |
       v
Technology Selection Engine
       |
       +-- frontend
       +-- backend
       +-- database
       +-- AI
       +-- mobile
       +-- infrastructure
       +-- testing
       +-- security
       +-- observability
       +-- deployment
```

------------------------------------------------------------------------

# 22. Technology Profile Model

Example:

``` yaml
technology_profile:
  product_type: ai_saas

  frontend:
    candidates:
      - typescript_react
      - nextjs

  backend:
    candidates:
      - go
      - java
      - dotnet
      - node

  ai:
    candidates:
      - python

  database:
    candidates:
      - postgresql

  cache:
    candidates:
      - valkey

  deployment:
    candidates:
      - docker
      - kubernetes

  selection_constraints:
    performance: high
    security: high
    cloud_native: true
    team_skill: preferred
    time_to_market: high
    cost: controlled
```

The Architecture Decision Engine chooses the final stack.

------------------------------------------------------------------------

# 23. Technology Selection Inputs

The decision engine should consider:

``` text
Product type
Target platform
Performance
Latency
Security
Scalability
Availability
Data residency
AI requirements
Team skill
Existing enterprise ecosystem
Cloud provider
Target OS
Mobile/web/desktop
Licensing
Dependency compatibility
Vendor lock-in
Cost
Time-to-market
Maintainability
Community maturity
Operational complexity
```

No technology should be selected merely because it is fashionable.

------------------------------------------------------------------------

# 24. Example Technology Selection

## AI SaaS

``` text
Frontend: TypeScript/React
Backend: Go
AI: Python
Database: PostgreSQL
Cache: Valkey
Object: S3-compatible
Runtime: Docker
Scale: Kubernetes if needed
```

## Enterprise Java environment

``` text
Frontend: TypeScript
Backend: Java/Spring
AI: Python
Database: PostgreSQL/enterprise DB as required
Deployment: Kubernetes
```

## High-performance engine

``` text
Frontend/API: Go
Core: Rust
Data: PostgreSQL/object storage
```

## Mobile application

``` text
iOS: Swift
Android: Kotlin
Backend: Go
AI: Python
```

## Agent swarm

``` text
Control plane: Go
Agents: Python or Go depending on workload
AI: Python
Tool protocol: MCP/API
Memory: shared service
Runtime: containerized
```

------------------------------------------------------------------------

# 25. Product Factory Build Flow

The complete flow should become:

``` text
1. INTENT
   |
2. DISCOVERY
   |
3. REQUIREMENTS
   |
4. PRODUCT SPEC
   |
5. ARCHITECTURE DECISION
   |
6. TECHNOLOGY SELECTION
   |
7. AGENT/WORKFLOW DESIGN
   |
8. MODEL SELECTION
   |
9. TOOL/MCP SELECTION
   |
10. MEMORY/KNOWLEDGE DESIGN
   |
11. SECURITY DESIGN
   |
12. CODE GENERATION
   |
13. TEST GENERATION
   |
14. BUILD
   |
15. STATIC/SCA/SBOM/LICENSE CHECK
   |
16. SECURITY TEST
   |
17. FUNCTIONAL/NFR TEST
   |
18. EAP COMPILATION
   |
19. BOM COMPILATION
   |
20. LICENSE/ENTITLEMENT COMPILATION
   |
21. SIGNING
   |
22. PACKAGE
   |
23. DEPLOY
   |
24. VERIFY
   |
25. OPERATE
```

------------------------------------------------------------------------

# 26. Generated Product Package

A generated product should have a canonical package:

``` text
generated-product/
|
+-- product-manifest.yaml
+-- architecture.yaml
+-- technology-profile.yaml
+-- agent-manifest/
+-- workflow-manifest/
+-- runtime-profile.yaml
+-- security-policy.yaml
+-- deployment-profile.yaml
+-- license-profile.yaml
+-- entitlement-profile.yaml
+-- tests/
+-- bom/
+-- provenance/
+-- artifacts/
+-- source/
+-- deployment/
+-- docs/
```

The actual generated application source remains
customer-owned/accessible where the commercial model allows it.

Product Forge's own proprietary runtime should remain separately
packaged.

------------------------------------------------------------------------

# 27. Source Ownership Boundary

This must be explicit.

``` text
Product Forge IP
|
+-- Product Forge engine
+-- proprietary runtime
+-- proprietary algorithms
+-- commercial modules
+-- protected services
+-- platform code
```

versus:

``` text
Customer Product IP
|
+-- generated source
+-- customer requirements
+-- customer data
+-- customer configurations
+-- customer-developed plugins
+-- customer agents
+-- customer business logic
```

Contracts/licensing must explicitly define ownership and rights.

------------------------------------------------------------------------

# 28. BOM Architecture

Product Forge should generate multiple BOMs.

``` text
ABOM = Agent BOM
MBOM = Model BOM
RBOM = Runtime BOM
TBOM = Tool BOM
DBOM = Dependency BOM
SBOM = Software BOM
CBOM = Configuration/Capability BOM
LBOM = License BOM
```

Then:

``` text
Product BOM
|
+-- ABOM
+-- MBOM
+-- RBOM
+-- TBOM
+-- DBOM
+-- SBOM
+-- CBOM
+-- LBOM
```

This is especially important for Enterprise/OEM customers.

------------------------------------------------------------------------

# 29. License/Dependency Governance

The Build Factory must inspect:

``` text
Source dependencies
Container images
OS packages
Python packages
Go modules
Rust crates
npm packages
Models
Model weights
Datasets
Prompts/templates
Fonts
Generated assets
Third-party APIs
```

Produce:

``` text
SBOM
NOTICE
License inventory
Model license inventory
Third-party terms
Security findings
Provenance
```

Default dependency policy should favor permissive licenses, but legal
review is required for actual commercial distribution decisions.

------------------------------------------------------------------------

# 30. Security Architecture

Security must be cross-cutting.

``` text
Identity
   |
Tenant isolation
   |
Authorization
   |
Capability authorization
   |
Tool authorization
   |
Model authorization
   |
Runtime sandbox
   |
Artifact signing
   |
Supply-chain verification
   |
Audit
```

Security modules:

``` text
identity
authentication
authorization
RBAC
ABAC
policy engine
secrets
credential broker
sandbox
tool policy
network policy
artifact signing
SBOM
SCA
SAST
DAST
container scanning
dependency scanning
audit
tamper detection
```

------------------------------------------------------------------------

# 31. Runtime Security Boundary

Generated agents must not receive unrestricted host access.

Preferred:

``` text
Agent
 |
 v
Tool Gateway
 |
 v
Policy Engine
 |
 +-- capability
 +-- tenant
 +-- user
 +-- license
 +-- entitlement
 +-- resource
 +-- network
 +-- data classification
 |
 v
Execution
```

------------------------------------------------------------------------

# 32. Agent/SWARM Runtime Architecture

``` text
                 Supervisor
                     |
        +------------+------------+
        |            |            |
   Specialist A  Specialist B  Reviewer
        |            |            |
        +------------+------------+
                     |
                 Shared State
                     |
        +------------+------------+
        |            |            |
      Memory       Artifacts     Events
```

Hard controls:

``` text
max agents
max depth
max recursion
max runtime
max tokens
max cost
max tool calls
max parallelism
permissions
data access
network access
```

Dynamic agents must still be represented in runtime state and evidence.

------------------------------------------------------------------------

# 33. Agent Memory Architecture

Retain the planned memory taxonomy:

``` text
Working / In-context
Semantic
Episodic
Procedural
External / Retrieval
Parametric
Prospective
```

But expose it through a Memory Gateway:

``` text
Agent
 |
 v
Memory Gateway
 |
 +-- working memory
 +-- semantic memory
 +-- episodic memory
 +-- procedural memory
 +-- retrieval memory
 +-- prospective memory
```

RAG/CAG/OKF remain complementary mechanisms rather than one generic
"memory" feature.

------------------------------------------------------------------------

# 34. Model Gateway

All models must be behind a provider-independent gateway.

``` text
Agent
 |
 v
Model Gateway
 |
 +-- capability
 +-- quality
 +-- cost
 +-- latency
 +-- context
 +-- modality
 +-- residency
 +-- availability
 +-- license
 +-- customer policy
 |
 v
Provider Adapter
 |
 +-- OpenAI
 +-- Anthropic
 +-- Google
 +-- DeepSeek
 +-- other providers
 +-- customer model
 +-- local model
```

Do not hard-code model IDs into product logic.

------------------------------------------------------------------------

# 35. Tool Gateway / MCP

All tools should have:

``` text
ToolSpec
|
+-- identity
+-- version
+-- capability
+-- permissions
+-- input schema
+-- output schema
+-- cost
+-- risk
+-- network access
+-- data access
+-- audit policy
```

MCP should be supported as an interoperability mechanism, not treated as
the entire internal architecture.

------------------------------------------------------------------------

# 36. Infrastructure Gateway

Generated products should deploy through a provider-independent
interface.

``` text
Infrastructure Gateway
|
+-- local
+-- Docker
+-- Kubernetes
+-- AWS
+-- Azure
+-- GCP
+-- customer VPC
+-- on-prem
+-- air-gapped
```

The product's deployment profile determines the selected target.

------------------------------------------------------------------------

# 37. Packaging Architecture

Support:

``` text
Community:
  source package / containers

Professional:
  signed package / containers

Enterprise:
  signed OCI images + license

On-prem:
  signed deployment bundle

Air-gap:
  signed offline bundle + offline license

OEM:
  signed OEM-specific package

SaaS:
  server-side deployment
```

The packaging pipeline must never accidentally include:

-   private signing keys
-   source-control credentials
-   provider secrets
-   internal test data
-   development configuration
-   proprietary source that the selected commercial profile does not
    permit shipping.

------------------------------------------------------------------------

# 38. Update Architecture

Create a signed update mechanism.

``` text
Build Factory
     |
     v
Release Artifact
     |
     v
Sign
     |
     v
Artifact Registry
     |
     +-- SaaS deployment
     +-- Enterprise registry
     +-- On-prem update
     +-- Air-gap export
     +-- OEM channel
```

Air-gapped update:

``` text
Vendor
  |
signed update bundle
  |
offline transfer
  |
customer verification
  |
installation
```

------------------------------------------------------------------------

# 39. Product Forge Repository Evolution

Do not create an entirely separate repository immediately.

Target logical structure:

``` text
productforge/
|
+-- factory/
|    +-- intake/
|    +-- requirements/
|    +-- architecture/
|    +-- technology_selection/
|    +-- generation/
|    +-- test_generation/
|    +-- bom/
|    +-- packaging/
|    +-- release/
|
+-- runtime/
|    +-- contracts/
|    +-- eap/
|    +-- execution/
|    +-- policy/
|    +-- scheduler/
|    +-- workers/
|
+-- gateways/
|    +-- model/
|    +-- tool/
|    +-- memory/
|    +-- infrastructure/
|    +-- credential/
|
+-- commercial/
|    +-- licensing/
|    +-- entitlements/
|    +-- metering/
|    +-- billing/
|    +-- plans/
|    +-- oem/
|    +-- white_label/
|
+-- security/
|    +-- identity/
|    +-- authorization/
|    +-- signing/
|    +-- sandbox/
|    +-- supply_chain/
|
+-- python/
|    +-- agents/
|    +-- ai/
|    +-- rag/
|    +-- memory/
|    +-- evaluation/
|
+-- go/
|    +-- runtime/
|    +-- gateway/
|    +-- cli/
|    +-- workers/
|
+-- rust/
|    +-- secure_runtime/
|    +-- protected_core/
|
+-- ui/
|    +-- web/
|    +-- admin/
|    +-- builder/
|
+-- schemas/
+-- configs/
+-- deploy/
+-- tests/
+-- docs/
```

The exact physical repository split can be deferred until build
boundaries are proven.

------------------------------------------------------------------------

# 40. Existing Python Modules --- Migration Rule

Use this disposition rule:

### KEEP

If the existing Python implementation already satisfies the new
contract.

### KEEP + HARDEN

If functionality is correct but security/contract enforcement is weak.

### PROMOTE

If an existing module should become a first-class
gateway/service/contract.

### MODIFY

If responsibilities cross the new BUILD/RUN boundary.

### MOVE LOGICALLY

If the implementation can stay in Python but its public responsibility
belongs behind a language-neutral gateway.

### PORT TO GO

Only where there is a clear runtime/platform benefit.

### PORT TO RUST

Only where there is a clear native/security/performance/IP benefit.

### DEFER

If it is useful but not required for the core runtime.

### REMOVE

Only when superseded and covered by tests.

------------------------------------------------------------------------

# 41. Existing → Target Changes

  Existing area          Action        Target
  ---------------------- ------------- ------------------------------
  pipeline executor      MODIFY        Factory façade
  orchestrator mixins    KEEP/MODIFY   Factory/runtime coordination
  agent spec             PROMOTE       EAP source contract
  agent runtime          MODIFY        Runtime contract
  agent tool loop        MODIFY        Tool Gateway
  model catalog          KEEP/HARDEN   Model Gateway registry
  model router           PROMOTE       Model Gateway
  model gate             KEEP/HARDEN   Model policy gate
  BYOT                   PROMOTE       BYOK/BYOM
  memory                 KEEP/HARDEN   Memory Gateway
  knowledge              KEEP/HARDEN   Knowledge Gateway
  artifact store         MODIFY        Artifact/EAP registry
  licensing              MODIFY        Commercial Plane
  billing                MODIFY        Commercial Plane
  tenancy                KEEP          Shared Platform
  deployment providers   PROMOTE       Infrastructure Gateway
  sizing                 PROMOTE       RBOM compiler
  tech stack module      MODIFY        Technology Selection Engine
  build manager          MODIFY        Build Factory
  release manager        PROMOTE       Package/release system
  dashboard              MODIFY        Platform/OEM operations UI
  signing                PROMOTE       Supply-chain/EAP integrity
  telemetry              PROMOTE       Runtime observability
  QA framework           KEEP/MODIFY   Product/runtime QA
  security               PROMOTE       Cross-plane security

------------------------------------------------------------------------

# 42. New First-Class Modules

Priority P0:

``` text
technology_selection_engine
architecture_decision_engine
eap_manifest
eap_compiler
eap_registry
runtime_profile
runtime_manager
model_gateway
tool_gateway
memory_gateway
credential_broker
runtime_policy
capability_registry
license_manager
entitlement_manager
package_manager
artifact_signer
release_manager
bom_compiler
usage_meter
deployment_profile
security_profile
```

Priority P1:

``` text
infrastructure_gateway
oem_manager
white_label_manager
unit_economics
update_manager
airgap_manager
wasm_plugin_host
product_runtime_catalog
```

------------------------------------------------------------------------

# 43. Phase Plan

The implementation must be staged so that every phase leaves Product
Forge usable.

## Phase 0 --- Architecture/Contract Freeze

Goal:

> Establish boundaries before large implementation changes.

Implement:

-   BUILD/RUN boundary
-   contract package
-   ProductSpec
-   ArchitectureSpec
-   TechnologyProfile
-   AgentSpec
-   RuntimeProfile
-   DeploymentProfile
-   LicenseProfile
-   EntitlementProfile
-   EAP schema
-   BOM schemas
-   Capability registry

Do not migrate languages yet.

Exit gate:

``` text
All major boundaries have stable contracts.
```

------------------------------------------------------------------------

# 44. Phase 1 --- Current Python Foundation + Commercial Skeleton

This is the immediate phase.

Keep existing Python runtime.

Add:

``` text
capability registry
license manager
entitlement manager
deployment profiles
build profiles
OEM profile
white-label profile
EAP schema/compiler skeleton
technology profile schema
BOM schema
package metadata
signing pipeline
```

Create one end-to-end path:

``` text
Requirement
→ ProductSpec
→ TechnologyProfile
→ existing Python generation
→ EAP
→ license
→ entitlement
→ signed package
→ existing runtime
```

Exit gate:

> One generated product can be built, packaged, licensed, signed and
> executed.

------------------------------------------------------------------------

# 45. Phase 2 --- Go Runtime Foundation

Introduce Go without removing Python.

Move first:

``` text
API façade
runtime lifecycle
scheduler
worker management
package loading
EAP validation
license verification
entitlement enforcement
CLI
```

Architecture:

``` text
Go Runtime
    |
    +-- EAP
    +-- Python AI service
    +-- tools
    +-- model gateway
    +-- storage
```

Exit gate:

> A generated EAP can run through the Go runtime while existing Python
> intelligence remains functional.

------------------------------------------------------------------------

# 46. Phase 3 --- Gateway Extraction

Promote:

``` text
Model Gateway
Tool Gateway
Memory Gateway
Infrastructure Gateway
Credential Broker
```

No direct cross-module coupling.

Exit gate:

``` text
Python/Go implementations can be replaced behind contracts.
```

------------------------------------------------------------------------

# 47. Phase 4 --- Product Technology Selection

Build the Technology Selection Engine.

Inputs:

``` text
requirements
NFRs
target platform
team skill
security
cost
deployment
AI
performance
licensing
```

Outputs:

``` text
frontend stack
backend stack
AI stack
database
cache
infra
testing
security
observability
deployment
```

Exit gate:

> Product Forge can justify and generate a technology profile before
> code generation.

------------------------------------------------------------------------

# 48. Phase 5 --- Build Factory

Implement:

``` text
Product Compiler
Architecture Compiler
Technology Compiler
Agent Compiler
Test Compiler
BOM Compiler
Package Compiler
Deployment Compiler
License Compiler
```

Target:

``` text
Requirement
→ architecture
→ technology
→ source
→ tests
→ BOM
→ package
→ signed release
```

------------------------------------------------------------------------

# 49. Phase 6 --- Protected Runtime

Introduce selective Rust.

Candidates:

``` text
secure execution
sandbox
selected proprietary algorithms
selected decision components
high-risk parser
```

Do not move ordinary business logic to Rust.

Exit gate:

> Protected components are replaceable modules, not hard dependencies
> for the entire platform.

------------------------------------------------------------------------

# 50. Phase 7 --- Enterprise Deployment

Implement:

``` text
SaaS
VPC
on-prem
air-gap
```

Add:

-   offline license
-   offline entitlement
-   signed update
-   deployment profiles
-   enterprise identity
-   RBAC/ABAC
-   audit
-   policy
-   customer model integration
-   customer secrets

------------------------------------------------------------------------

# 51. Phase 8 --- OEM / White Label

Implement:

``` text
OEM tenant
OEM build profile
OEM branding
OEM capabilities
OEM license
OEM update channel
OEM deployment profile
```

Generate:

``` text
CustomerBrand Product
```

without source-code forks.

------------------------------------------------------------------------

# 52. Phase 9 --- WASM/Plugin Ecosystem

Only after runtime contracts are stable.

Introduce:

``` text
plugin SDK
WASM host
plugin registry
plugin signing
plugin permissions
plugin capabilities
plugin marketplace
```

This becomes an extension ecosystem rather than core architecture.

------------------------------------------------------------------------

# 53. Phase 10 --- Product/Agent Runtime Marketplace

Eventually:

``` text
Product Forge Marketplace
|
+-- agents
+-- skills
+-- tools
+-- MCP servers
+-- workflows
+-- product templates
+-- technology profiles
+-- deployment profiles
```

Every package has:

``` text
identity
version
license
capabilities
dependencies
security
BOM
provenance
signature
compatibility
```

------------------------------------------------------------------------

# 54. Deployment Matrix

  -------------------------------------------------------------------------------------------------
  Mode           UI          Go         Python          Rust       Proprietary       License
                                                                   services          
  -------------- ----------- ---------- --------------- ---------- ----------------- --------------
  Community      local/web   yes        yes             optional   limited           community

  Professional   web         yes        yes             selected   optional          commercial

  SaaS           hosted      yes        yes             yes        yes               subscription

  Enterprise     hosted      yes        yes             yes        yes               enterprise
  SaaS                                                                               

  Customer VPC   customer    yes        yes             yes        configurable      enterprise

  On-prem        customer    yes        yes             yes        limited/local     enterprise

  Air-gapped     customer    yes        yes             yes        local/protected   offline
                                                                                     license

  OEM            branded     yes        profile-based   selected   configurable      OEM

  Embedded       embedded    yes        optional        selected   optional          OEM/embedded
                 UI/API                                                              
  -------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

# 55. Packaging Matrix

  -------------------------------------------------------------------------------------------------
  Artifact      Community      Professional        Enterprise          OEM             Air-gap
  ------------- -------------- ------------------- ------------------- --------------- ------------
  Source        allowed by     controlled          generally not PF    controlled      controlled
                license                            proprietary source                  

  Go binary     yes            yes                 yes                 yes             yes

  Python AI     yes/selected   protected/package   protected/package   profile-based   package

  Rust          optional       selected            selected            selected        selected
  components                                                                           

  Docker/OCI    yes            yes                 yes                 yes             yes

  EAP           yes            yes                 yes                 yes             yes

  SBOM          yes            yes                 mandatory           mandatory       mandatory

  Signature     recommended    mandatory           mandatory           mandatory       mandatory

  License       community      commercial          enterprise          OEM             offline

  Entitlement   basic          yes                 yes                 yes             offline
  -------------------------------------------------------------------------------------------------

------------------------------------------------------------------------

# 56. Product Forge Licensing vs Generated Product Licensing

These must be separate.

``` text
Product Forge License
        |
        v
Rights to use Product Forge

Generated Product License
        |
        v
Rights to use the generated application
```

A customer can therefore:

``` text
Use Product Forge Enterprise
        |
        +-- generate Product A
        +-- generate Product B
        +-- generate Agent C
```

without those products inheriting the entire Product Forge license
automatically.

Generated-product licensing must be a separate configurable layer.

------------------------------------------------------------------------

# 57. Product Generation Licensing Flow

``` text
Product Request
      |
Technology selection
      |
Dependency selection
      |
License analysis
      |
License compatibility gate
      |
SBOM/LBOM
      |
Customer-selected product license
      |
Package
```

This prevents accidental inclusion of incompatible dependencies.

------------------------------------------------------------------------

# 58. Product Factory Governance Gates

Every generated product should pass:

``` text
G0 Intake
G1 Requirements
G2 Architecture
G3 Technology
G4 Security
G5 Dependency/license
G6 Code quality
G7 Functional tests
G8 NFR
G9 AI/agent evaluation
G10 BOM
G11 Packaging
G12 Signing
G13 Deployment
G14 Runtime verification
G15 Release
```

The exact existing 39-stage/8-phase pipeline can remain as the
implementation workflow; these are higher-level release gates.

------------------------------------------------------------------------

# 59. Architecture Decision Records

Product Forge should record:

``` text
ADR
|
+-- why technology selected
+-- why architecture selected
+-- why model selected
+-- why agent topology selected
+-- why deployment selected
+-- why database selected
+-- why security controls selected
+-- why license selected
```

This becomes part of product provenance.

------------------------------------------------------------------------

# 60. Technology Selection Should Be Explainable

Do not allow:

``` text
LLM says: use Rust.
```

Instead:

``` text
Requirements
   |
Constraints
   |
Candidate technologies
   |
Evidence
   |
Scoring/decision rules
   |
ADR
   |
Selected technology
```

The LLM can propose candidates, but deterministic rules and gates should
validate the decision.

------------------------------------------------------------------------

# 61. Observability

Every run should produce:

``` text
tenant_id
product_id
run_id
eap_id
eap_version
agent_id
agent_version
model_id
model_version
tool_id
tool_version
runtime_version
deployment_id
license_id
entitlement_version
cost
tokens
latency
artifacts
events
approvals
security decisions
```

This creates complete lineage.

------------------------------------------------------------------------

# 62. Database/State Direction

Product Forge's increasing state footprint means the architecture should
evolve toward an authoritative database-backed control plane.

Use:

``` text
PostgreSQL
|
+-- tenants
+-- users
+-- products
+-- projects
+-- runs
+-- tasks
+-- agents
+-- EAP versions
+-- licenses
+-- entitlements
+-- deployments
+-- usage
+-- costs
+-- decisions
+-- approvals
+-- audit
+-- model catalog
+-- tool catalog
+-- capabilities
```

Keep object storage for:

``` text
source bundles
artifacts
documents
logs where appropriate
models/large files where applicable
generated media
release bundles
```

Use cache/event infrastructure for transient execution.

Do not put every artifact into PostgreSQL.

------------------------------------------------------------------------

# 63. Event Architecture

Separate:

``` text
Event Store
```

from:

``` text
Event Transport
```

For example:

``` text
Authoritative state
      |
PostgreSQL
      |
Event/outbox
      |
Queue/event transport
      |
Workers
```

This avoids the existing class of state/event disagreement problems.

------------------------------------------------------------------------

# 64. Repository and Source Protection

Development repository:

``` text
Private source
    |
CI/CD
    |
build profile
    |
commercial filtering
    |
compile/protect
    |
sign
    |
artifact registry
```

Never build customer artifacts by copying the entire development tree.

The build system should explicitly select:

``` text
included source
excluded source
compiled components
services
configuration
branding
license
entitlement
deployment
```

------------------------------------------------------------------------

# 65. Key Principle for Reverse Engineering

Product Forge should NOT attempt to hide everything.

Customers must know:

``` text
API
capabilities
contracts
integration points
deployment requirements
supported behavior
```

Customers do not need to receive:

``` text
proprietary algorithms
internal heuristics
private architecture details
internal source
commercial intelligence
vendor keys
signing keys
internal prompts/strategies
```

Architecture visibility should be intentional, not accidental.

------------------------------------------------------------------------

# 66. What We Should NOT Do

Do not:

1.  Rewrite all Python into Go.
2.  Rewrite all Python into Rust.
3.  Turn everything into microservices immediately.
4.  Ship all Python source to every customer.
5.  Depend on obfuscation as the main IP protection.
6.  Put license checks randomly throughout the code.
7.  Fork the source for every OEM.
8.  Hard-code one commercial model.
9.  Hard-code model IDs.
10. Hard-code one cloud.
11. Make Kubernetes mandatory for every deployment.
12. Make Rust mandatory for every product.
13. Make Product Forge's technology stack equal to every generated
    product's stack.
14. mix BUILD and RUN responsibilities.
15. make SaaS architecture the only deployment model.

------------------------------------------------------------------------

# 67. Implementation Priority --- What to Do First

Given the user's current priority, the recommended immediate order is:

``` text
1. CONTRACTS
   |
2. BUILD/RUN SEPARATION
   |
3. EAP
   |
4. CAPABILITY REGISTRY
   |
5. LICENSE + ENTITLEMENT
   |
6. BUILD PROFILES
   |
7. PACKAGING + SIGNING
   |
8. TECHNOLOGY SELECTION
   |
9. GO RUNTIME
   |
10. GATEWAYS
   |
11. ENTERPRISE DEPLOYMENT
   |
12. OEM/WHITE LABEL
   |
13. RUST PROTECTED CORE
   |
14. WASM PLUGINS
```

This sequence prevents expensive rewrites.

------------------------------------------------------------------------

# 68. Immediate Repository Work

Before implementing large new features:

### Step A

Inventory current modules against:

``` text
Factory
Runtime
Commercial
Security
Gateway
Data
UI
```

### Step B

Mark every module:

``` text
KEEP
KEEP+HARDEN
PROMOTE
MODIFY
MOVE LOGICALLY
PORT TO GO
PORT TO RUST
DEFER
REMOVE
```

### Step C

Create the canonical contracts.

### Step D

Implement one complete vertical slice.

### Step E

Only then begin systematic Go extraction.

------------------------------------------------------------------------

# 69. First Vertical Slice

The first implementation milestone should be:

``` text
User:
"Build an AI customer-support application"
          |
          v
Product Forge
          |
          v
Requirements
          |
          v
Architecture
          |
          v
Technology Profile
          |
          v
React + Go + Python + PostgreSQL
          |
          v
Generated source
          |
          v
Tests
          |
          v
SBOM/LBOM
          |
          v
EAP
          |
          v
License
          |
          v
Entitlement
          |
          v
Signed package
          |
          v
Go Runtime
          |
          v
Running product
```

This one slice should prove the architecture.

------------------------------------------------------------------------

# 70. Final Target State

``` text
                             PRODUCT FORGE
                                  |
        +-------------------------+-------------------------+
        |                         |                         |
        v                         v                         v
   PRODUCT FACTORY          PRODUCT RUNTIME          COMMERCIAL PLATFORM
        |                         |                         |
   Requirements              Go Runtime               Licensing
   Architecture              Python AI                Entitlements
   Tech Selection             Rust Core                Metering
   Code Generation            Model Gateway             Billing
   Test Generation            Tool Gateway              OEM
   BOM                        Memory Gateway            White Label
   Packaging                  Policy                    Plans
   Deployment                 Security
        |                         |
        +-------------------------+
                  |
                  v
             EAP PACKAGE
                  |
        +---------+---------+
        |         |         |
      SaaS     Enterprise   OEM
        |         |         |
      Cloud     VPC/onprem  Branded
                           |
                     Product Runtime
                           |
                     Generated Product
```

------------------------------------------------------------------------

# 71. Final Technology Decision

## Product Forge itself

**Primary:**

-   TypeScript
-   Go
-   Python

**Selective:**

-   Rust

**Later/optional:**

-   WebAssembly

**Infrastructure:**

-   Docker/OCI
-   Kubernetes when scale/HA warrants it
-   PostgreSQL
-   object storage
-   cache/event infrastructure
-   vector/retrieval layer
-   OpenTelemetry
-   CI/CD
-   artifact registry

## Generated products

Product Forge should support a broader technology catalog:

``` text
TypeScript/JavaScript
Python
Go
Rust
Java/Kotlin
C#/.NET
C++
Swift
SQL/data technologies
mobile stacks
```

The Technology Selection Engine decides rather than imposing Product
Forge's own stack.

------------------------------------------------------------------------

# 72. Architecture Principle to Freeze

The following should become a Product Forge architectural rule:

> **Product Forge is a technology-independent product factory and
> execution platform. Its own platform runtime uses TypeScript for
> experience, Go for platform/runtime infrastructure, Python for
> AI/intelligence, and Rust selectively for protected
> native/security/performance components. Generated products are not
> required to use the Product Forge platform stack; their technology
> stack is selected by the Product Forge Technology & Architecture
> Selection Engine from requirements, constraints, evidence, cost,
> security, licensing and deployment needs.**

And:

> **Product Forge source distribution is a build-profile decision.
> Community, SaaS, Enterprise, On-Prem, Air-Gapped and OEM artifacts are
> generated from the same source through controlled packaging,
> compilation, signing, licensing and entitlement pipelines.**

And:

> **No single language, framework, model provider, cloud provider, agent
> framework, deployment platform or commercial model is allowed to
> become an architectural dependency where a stable contract can provide
> replaceability.**

------------------------------------------------------------------------

# 73. Definition of Done for This Architecture

This architecture is considered implemented when Product Forge can:

-   build a software product
-   build an AI product
-   build an agent
-   build an agent swarm
-   select a technology stack automatically
-   explain its architecture decisions
-   generate source and tests
-   produce SBOM/LBOM/ABOM/MBOM/RBOM/TBOM
-   package the product
-   sign the package
-   license the product
-   enforce entitlements
-   deploy SaaS
-   deploy customer VPC
-   deploy on-prem
-   deploy air-gapped
-   generate OEM/white-label builds
-   execute through the Go runtime
-   use Python AI services
-   use selected Rust protected components
-   support customer BYOK/BYOM
-   support different model providers
-   preserve customer/product data boundaries
-   provide complete execution provenance
-   update signed deployments
-   keep Product Forge proprietary IP separate from generated customer
    product IP
-   add/remove runtime modules without redesigning the entire platform.

------------------------------------------------------------------------

# 74. Reference Technology Sources

-   Go language/specification and compilation: https://go.dev/
-   Rust language and ownership/memory-safety model:
    https://www.rust-lang.org/
-   WebAssembly specification and security/portability model:
    https://webassembly.org/

These references should be treated as technology references; Product
Forge's final dependency and licensing decisions require
version-specific compatibility and license review during implementation.

------------------------------------------------------------------------

# 75. Implementation Directive

**This document should supersede the earlier stack-specific assumption
that Product Forge is primarily a Python runtime.**

It does **not** supersede the existing Product Forge 4.x architecture
wholesale.

Instead:

``` text
Existing Product Forge
        |
        v
Reconcile current implementation
        |
        v
Introduce contracts
        |
        v
Separate Factory / Runtime / Commercial
        |
        v
Add EAP + capability + licensing
        |
        v
Add technology selection
        |
        v
Introduce Go runtime
        |
        v
Introduce protected Rust components selectively
        |
        v
Enterprise deployment
        |
        v
OEM / white-label
        |
        v
WASM/plugin ecosystem
```

**No big-bang rewrite.**

The existing Python Product Forge remains the foundation while these
boundaries are introduced and progressively promoted into the target
architecture.


---



# CODE-ALIGNED AMENDMENT — OCTOBER 2026
## This section supersedes conflicting earlier recommendations in this document

**Repository inspected:** `srinikc/productforge`  
**Branch:** `develop`  
**Inspected branch head:** `97fbafe33be1f3364204b6d469493662fa8a48ae`  

This amendment is the implementation authority wherever it differs from earlier sections.

---

## A. What the Current Code Actually Has

The current `develop` branch is still a **Python-centric modular monolith**, not yet the Go/Rust runtime architecture.

Important verified foundations already present:

- `pipeline_executor.py` — large orchestration façade integrating AgentRuntime, DAG, memory, knowledge, skills, model routing, artifacts, budgets, QA, compliance and tech-stack decisions.
- `agent_runtime.py` — Python agent execution/checkpoint/budget foundation.
- `job_manager.py` — SQLite-backed job/queue state with a one-writer model.
- `deploy_providers.py` — Docker, local, Kubernetes, Helm, Terraform, Ansible, vendor/command and cloud targets.
- `tech_stack.py` — technology detection, structured tech-stack parsing, decision creation and persistence.
- `techstack_guidelines.py` — technology-specific coding knowledge/guidelines.
- `model_catalog.py`, `model_registry.py`, `model_gate.py` — model capability, registry and compatibility foundations.
- `artifact_registry.py` — local and external artifact registry backends.
- `bom.py` — dependency/license/footprint BOM foundation.
- `signing.py` — GPG artifact/tag signing foundation.
- `credentials.py` — provider credential references and budget caps.
- `licensing.py` — feature groups, tiers, signed licenses, tenant provisioning and entitlement checks.
- `billing.py` — billing boundary, currently with a placeholder Stripe integration.
- `sizing.py` — technology/deployment-based sizing.
- verification, telemetry and AG-UI foundations are also present.

The core directory does **not** yet contain first-class implementations named EAP, Runtime Profile, Deployment Profile, Model Gateway, Tool Gateway, Memory Gateway, Capability Registry or Runtime Dependency Compiler.

Therefore these should be introduced as **contracts and adapters around existing modules**, not as competing implementations.

---

# B. The Most Important Architectural Decision

## Product Forge customer runtime becomes Go-first and Python-free by default.

The target is:

```text
                  CUSTOMER DEPLOYMENT
                         |
                         v
                  PF Go Runtime
                         |
       +-----------------+-----------------+
       |                 |                 |
       v                 v                 v
   Workflow          Agent Runtime     Policy/Security
       |                 |                 |
       +-----------------+-----------------+
                         |
              +----------+----------+
              |                     |
              v                     v
        Model Gateway          Tool Gateway
              |
              v
       Provider adapters
```

Python remains important but is explicitly classified:

```text
PYTHON
|
+-- Factory/build-time AI
+-- Product Forge SaaS-side intelligence
+-- optional customer AI worker
+-- generated customer product, when selected by its own technology profile
```

It must **not silently become a PF customer-runtime dependency**.

---

# C. The Two Technology Stacks Must Never Be Confused

There are always two independent decisions.

### C1. Product Forge platform stack

```text
UI             TypeScript
Platform       Go
AI/Factory     Python
Native core    Rust, selectively
Plugin         WASM, later
```

### C2. Generated product stack

Determined independently by:

```text
requirements
NFRs
security
deployment
customer ecosystem
cost
skills
licensing
AI needs
performance
maintainability
```

A generated product may therefore be:

```text
TypeScript/Node
Go
Python
Java/Kotlin
.NET
Rust
C++
Swift
or hybrid
```

Product Forge must not force its own stack onto generated products.

---

# D. New Mandatory Feature-Change Gate

Before implementing **any new PF feature/change**, PF must run:

```text
REQUEST
  |
  v
CHANGE CLASSIFIER
  |
  v
CURRENT CODE ANALYSIS
  |
  v
ARCHITECTURE IMPACT
  |
  v
TECHNOLOGY DECISION
  |
  v
CUSTOMER-RUNTIME DECISION
  |
  v
EAP IMPACT
  |
  v
BOM IMPACT
  |
  v
LICENSE/ENTITLEMENT IMPACT
  |
  v
DEPLOYMENT IMPACT
  |
  v
ADR
  |
  v
IMPLEMENTATION
```

This is not optional documentation. It becomes part of the PF development workflow.

---

# E. Change Classification

Every change is assigned one or more classes.

| Class | Meaning | Default implementation |
|---|---|---|
| C0 | Documentation/config | Existing mechanism |
| C1 | Factory-only | Python initially |
| C2 | UI/control-plane | TypeScript eventually; preserve current UI during migration |
| C3 | Runtime/platform | Go |
| C4 | AI/intelligence | Python behind contract initially |
| C5 | Native/security/performance | Rust candidate |
| C6 | Licensing/commercial | Go runtime + Commercial Plane |
| C7 | Packaging/deployment | Go/package/infrastructure plane |
| C8 | Generated-product technology | Technology Selection Engine |

---

# F. Language Selection Rule

For every change:

```text
Does customer runtime need it?
        |
       NO
        |
        +--> Keep existing implementation unless another benefit exists

       YES
        |
        v
Is it platform/runtime/orchestration?
        |
       YES --> Go

       NO
        |
        v
Is it AI/data/LLM/RAG/evaluation?
        |
       YES --> Python service initially

       NO
        |
        v
Is it security/native/performance sensitive?
        |
       YES --> Rust candidate

       NO
        |
        v
Can it remain behind an explicit service contract?
        |
       YES --> Keep current implementation

       NO --> Architecture review required
```

This prevents a pointless Python→Go/Rust rewrite.

---

# G. Existing Module Disposition

| Current code | Immediate action | Target |
|---|---|---|
| `pipeline_executor.py` | KEEP + progressively slim | Factory façade |
| `agent_runtime.py` | KEEP + contract | Runtime implementation/adapter |
| `job_manager.py` | KEEP + abstract | JobManager contract |
| `dag_executor.py` | KEEP | Workflow contract |
| `agent_spec.py` | PROMOTE | Agent/EAP source contract |
| `agent_hierarchy.py` | KEEP + harden | Topology validator |
| `agent_tool_loop.py` | KEEP behind interface | Tool runtime |
| `tool_registry.py` | PROMOTE | Tool Gateway |
| `tool_policy.py` | PROMOTE | Runtime policy |
| `model_catalog.py` | KEEP | Model metadata |
| `model_registry.py` | KEEP + normalize | Model Gateway catalog |
| `model_gate.py` | KEEP + harden | Model compatibility gate |
| `model_router.py` | PROMOTE | Model Gateway |
| `credentials.py` | KEEP + harden | Credential Broker |
| `agent_memory.py` | KEEP | Memory Gateway implementation |
| `artifact_store.py` | KEEP | Artifact service |
| `artifact_registry.py` | PROMOTE | Artifact Registry |
| `bom.py` | PROMOTE | BOM Compiler |
| `signing.py` | PROMOTE | Package Integrity |
| `licensing.py` | MODIFY | License/Entitlement Runtime |
| `billing.py` | KEEP separate | Commercial adapter |
| `deploy_providers.py` | PROMOTE | Infrastructure Gateway |
| `sizing.py` | PROMOTE | Runtime/footprint compiler |
| `tech_stack.py` | PROMOTE | Technology Selection Engine |
| `techstack_guidelines.py` | KEEP | Technology knowledge |
| dashboard | KEEP initially | TypeScript migration later |
| AG-UI/event stream | KEEP | UI/runtime event contract |

**Do not physically reorganize all these files yet.** Establish interfaces first.

---

# H. First New Contracts

Create these before implementing major features:

```text
core/contracts/
    product_spec
    architecture_spec
    technology_profile
    runtime_profile
    deployment_profile
    license_profile
    entitlement_profile
    component_manifest
    eap_manifest
    bom_schema
    evidence_manifest
```

The initial implementations may all be Python.

The contracts are the important part.

---

# I. EAP Becomes the Factory→Runtime Boundary

The repository currently has no first-class EAP implementation.

Add:

```text
core/eap/
    manifest
    validator
    compiler
    registry
    compatibility
```

EAP must contain:

```text
product
runtime
agents
workflows
skills
tools
models
memory
security
deployment
license
entitlements
tests
BOMs
provenance
signatures
compatibility
```

Example:

```yaml
runtime:
  engine: pf-go-runtime
  version: "1.x"
  python_required: false
  rust_required: false

compatibility:
  os: [linux]
  arch: [amd64, arm64]
```

---

# J. Runtime Dependency Compiler

This is a new P0 component.

```text
EAP
+
Deployment Profile
+
License Profile
+
Runtime Profile
+
Target OS/architecture
        |
        v
Runtime Dependency Compiler
        |
        v
Customer Package Plan
```

It decides whether the delivered package contains:

```text
Go runtime
Rust component
Python AI worker
UI
database migration
configuration
license
entitlements
```

This is the mechanism that ensures PF does not accidentally ship Python.

---

# K. Component Manifest

Every PF component eventually declares:

```yaml
component:
  id:
  version:
  language:
  type:
  build_required:
  runtime_required:
  customer_delivered:
  customer_source:
  capabilities:
  dependencies:
  license:
  security_class:
  platforms:
  architectures:
```

Example:

```yaml
component:
  id: pf-python-ai
  language: python
  build_required: true
  runtime_required: false
  customer_delivered: false
```

If an on-prem feature genuinely needs it:

```yaml
runtime_required: true
customer_delivered: true
```

The package compiler uses this metadata.

---

# L. Two Compilers

Product Forge needs two different compilation concepts.

## Product Compiler

```text
Requirements
→ Product architecture
→ Technology Profile
→ source
→ tests
→ product artifacts
```

## Runtime Package Compiler

```text
EAP
→ runtime dependencies
→ deployment profile
→ license/entitlement
→ platform artifacts
→ signed package
```

This separation is fundamental.

---

# M. Updated Product Generation Flow

```text
INTAKE
  |
DISCOVERY
  |
REQUIREMENTS
  |
PRODUCT SPEC
  |
ARCHITECTURE DECISION
  |
TECHNOLOGY SELECTION
  |
GENERATED PRODUCT STACK
  |
PF RUNTIME REQUIREMENTS
  |
AGENT/WORKFLOW DESIGN
  |
MODEL/TOOL/MEMORY DESIGN
  |
SECURITY
  |
CODE GENERATION
  |
TEST GENERATION
  |
LICENSE/DEPENDENCY ANALYSIS
  |
BOM
  |
EAP
  |
RUNTIME DEPENDENCY COMPILATION
  |
PACKAGE
  |
SIGN
  |
DEPLOY
  |
VERIFY
```

---

# N. Updated Implementation Phases

## Phase 0 — Baseline

Before changing code:

- freeze the `develop` baseline
- record branch SHA
- run current tests
- record current failures
- reconcile existing audit remediation
- establish architecture decision register

No feature work is mixed into this phase.

## Phase 1 — Contracts

Implement only:

```text
ProductSpec
TechnologyProfile
RuntimeProfile
DeploymentProfile
LicenseProfile
EntitlementProfile
ComponentManifest
EAP
BOM
Evidence
```

Existing Python implementation must be able to emit these.

## Phase 2 — Change Architecture Engine

Implement:

```text
ChangeClassifier
ArchitectureImpactAnalyzer
TechnologyDecisionEngine
RuntimeDependencyCompiler
ChangeADR
```

Integrate this into the existing backlog/intake → pipeline path.

This is the most important phase before normal feature development.

## Phase 3 — EAP

Implement:

```text
EAP compiler
EAP validator
EAP registry
compatibility
provenance
```

Reuse existing:

```text
agent_spec
tech_stack
artifact_registry
bom
signing
verification
```

## Phase 4 — Minimal Go Runtime

Build only:

```text
load EAP
validate EAP
verify license
resolve entitlement
execute deterministic workflow
emit typed events
persist result
```

No swarm, no Kubernetes, no complex AI.

**Exit gate: an EAP executes without PF Python source files.**

## Phase 5 — Python Runtime Adapter

Connect:

```text
Go Runtime
    |
Runtime Contract
    |
Existing Python AgentRuntime
```

The current implementation becomes an adapter rather than the permanent customer runtime.

## Phase 6 — Go Runtime Extraction

Move:

```text
job management
scheduler
runtime lifecycle
policy
license verification
entitlements
package loading
artifact access
deployment controller
CLI
```

Do not move AI intelligence merely for language purity.

## Phase 7 — Gateways

Introduce:

```text
Model Gateway
Tool Gateway
Memory Gateway
Credential Broker
Infrastructure Gateway
```

Use current implementations behind them first.

## Phase 8 — Enterprise Persistence

Introduce repository interfaces:

```text
SQLite adapter
JSON adapter
PostgreSQL adapter
```

Move enterprise/runtime authoritative state to PostgreSQL only after contracts are stable.

## Phase 9 — Commercial Packaging

Implement:

```text
SaaS
VPC
on-prem
air-gap
```

with:

```text
signed packages
asymmetric licenses
entitlements
SBOM/LBOM
offline activation
signed updates
```

## Phase 10 — OEM/White Label

Configuration-driven profiles.

No source forks.

## Phase 11 — Rust

Only after measured requirements identify components that benefit from Rust:

```text
sandbox
secure plugin execution
selected high-value native algorithms
performance-sensitive components
```

## Phase 12 — WASM

Only after the plugin contract is stable.

## Phase 13 — Service Decomposition

Only when independent scaling/security/deployment requirements justify it.

---

# O. Licensing Correction

The current HMAC implementation is useful as a development mechanism but should not be the final commercial license design.

Target:

```text
PF License Authority
      |
 private signing key
      |
      v
Signed license
      |
      v
Customer Go Runtime
      |
 public-key verification
```

Private signing material never ships.

Air-gapped deployments use signed offline licenses.

---

# P. Runtime Profiles

Create:

```text
pf-runtime-go
pf-runtime-go-ai-worker
pf-runtime-saas
pf-runtime-enterprise-vpc
pf-runtime-onprem
pf-runtime-airgap
```

Default:

```text
pf-runtime-go
```

contains no Product Forge Python.

---

# Q. Deployment Profiles

Create:

```text
community-local
professional-local
saas
enterprise-saas
enterprise-vpc
enterprise-onprem
enterprise-airgap
oem-cloud
oem-onprem
embedded-runtime
```

Each profile defines:

```text
runtime
components
OS/architecture
network
storage
identity
license
entitlements
update channel
telemetry
model policy
AI worker policy
```

---

# R. Architecture Drift Guard

Add a CI check that fails when:

```text
new PF runtime Python dependency
new undeclared service
direct provider coupling
new license dependency without LBOM
capability without entitlement
EAP schema mismatch
component manifest missing
customer-delivered source violation
feature without architecture decision
undocumented technology selection
```

This should become a release-blocking control.

---

# S. The Critical No-Python Release Test

For every commercial profile where Python is forbidden:

```text
assert no .py PF source
assert no Python executable
assert no pip runtime dependency
assert EAP.python_required == false
assert package manifest contains no Python worker
```

For profiles requiring a Python worker:

```text
assert EAP.python_required == true
assert worker is explicitly declared
assert worker version is in BOM
assert worker license is in LBOM
```

---

# T. Existing Pipeline Is Retained

The existing pipeline definition and orchestration remain the Factory implementation.

The new architecture wraps it:

```text
Change Architecture
        |
Technology Selection
        |
Existing 16-stage Factory Pipeline
        |
EAP Compiler
        |
Runtime Package Compiler
```

Do not throw away the existing pipeline.

---

# U. Important Rule for `pipeline_executor.py`

Do not split the ~3,600-line executor into dozens of files as a cosmetic refactor.

First introduce ports/contracts:

```text
FactoryContext
AgentExecutionPort
ModelPort
ArtifactPort
MemoryPort
TechStackPort
VerificationPort
```

Then progressively reduce direct coupling.

---

# V. Important Rule for `job_manager.py`

Create:

```text
JobManagerPort
```

and retain the SQLite implementation.

Later:

```text
SQLiteJobManager
PostgresJobManager
GoJobManager
```

can share the same contract.

---

# W. Important Rule for `tech_stack.py`

Do not replace it.

Extend it from product stack selection into:

```text
Technology Decision Engine
|
+-- product technology
+-- PF runtime technology
+-- deployment technology
+-- AI technology
+-- security technology
+-- test technology
+-- license compatibility
```

This is the existing module's natural evolution.

---

# X. Example: Any Future Feature

For a request such as:

> "Add voice-agent support."

PF first generates:

```text
UI                TypeScript
runtime            Go
voice transport    Go/provider adapter
AI                 provider realtime OR Python worker
EAP                voice capability
license             PF.RUNTIME.VOICE
BOM                 provider/audio dependencies
deployment          SaaS/VPC/on-prem capability
python_required     false for provider-realtime mode
```

Only then does implementation begin.

For:

> "Add a new RAG algorithm."

PF decides:

```text
class: C4
implementation: Python initially
contract: Memory/Retrieval Gateway
customer Python: only if customer-hosted AI execution requires it
EAP: retrieval capability/version
BOM: model/embedding dependency
```

For:

> "Add secure plugin sandbox."

PF decides:

```text
class: C5
candidate: Rust
reason: native isolation/security/performance
EAP: plugin runtime requirement
license: plugin capability
customer Python: false
```

---

# Y. Implementation-Ready Checklist

A feature cannot enter implementation until:

```text
[ ] requirement understood
[ ] current code inspected
[ ] change class assigned
[ ] architecture impact calculated
[ ] existing module identified
[ ] KEEP/MODIFY/PROMOTE/PORT decision made
[ ] implementation language selected
[ ] customer runtime impact known
[ ] Python requirement explicitly decided
[ ] EAP impact known
[ ] BOM impact known
[ ] license impact known
[ ] entitlement known
[ ] deployment impact known
[ ] security impact known
[ ] tests defined
[ ] ADR recorded
```

---

# Z. Final Frozen Architecture Rule

> **Product Forge is a technology-independent Product Factory and execution platform. Its own platform uses TypeScript for experience, Go for the customer/runtime infrastructure, Python for Factory and AI intelligence, and Rust selectively for protected native/security/performance components.**

> **The default commercial PF customer runtime contains no Product Forge Python source. Python is allowed only as Factory/build-time intelligence, SaaS-side intelligence, an explicitly declared customer AI worker, or as part of a separately generated customer product when its own technology profile selects Python.**

> **Existing Python modules are not rewritten merely because Go/Rust are being introduced. They are first placed behind stable contracts and migrated only where runtime, security, performance, IP protection, deployment, or maintainability provides a concrete benefit.**

> **Every new PF feature must pass Change Classification → Current Code Analysis → Architecture Impact → Technology Decision → Runtime Dependency Decision → EAP/BOM/License/Deployment Impact before implementation.**

> **Product Forge's own technology stack and the technology stack selected for a generated product are independent decisions.**

---

# AA. Immediate Implementation Order

The next work should therefore be:

```text
1. Freeze current develop baseline
        |
2. Canonical contracts
        |
3. Change Architecture Engine
        |
4. Technology Selection Engine extension
        |
5. Component Manifest
        |
6. EAP
        |
7. Runtime Dependency Compiler
        |
8. Minimal Go Runtime proof
        |
9. Python Runtime Adapter
        |
10. Model/Tool/Memory/Infrastructure gateways
        |
11. Go runtime extraction
        |
12. Licensing/Entitlements
        |
13. Packaging/BOM/Signing
        |
14. SaaS/VPC/On-prem/Air-gap
        |
15. OEM/White Label
        |
16. Rust protected components
        |
17. WASM/plugins
        |
18. Selective service decomposition
```

**Do not start normal feature implementation before steps 1–8 have a passing vertical slice.**

The critical proof is:

```text
Requirement
  → architecture decision
  → technology decision
  → existing PF factory
  → EAP
  → runtime dependency compiler
  → signed package
  → Go runtime
  → execution
```

with:

```text
PF Python source absent from the customer package.
```

That is the architectural foundation that prevents the current Python implementation from becoming throwaway while simultaneously preventing Product Forge from drifting back into a Python-dependent customer runtime.

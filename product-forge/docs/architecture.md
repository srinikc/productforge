# Architecture — MyWorld MVP

> **Stage 2 — Architecture.** Inputs: `docs/requirements.md`, `docs/design.md`.
> **Last updated:** 2026-08-23

---

## 1. Architecture Style

**Modular Monolith** with a shared backend API, deployed as a single deployable unit per layer.

| Layer | Runtime | Style |
|---|---|---|
| **Web Frontend** | Next.js 14 (App Router) PWA | Server Components + Client Components, single deployable |
| **Mobile Frontend** | React Native (Expo) | Single codebase, iOS + Android builds |
| **Backend API** | FastAPI (Python 3.12+) | Single async service, modular internal packages |
| **Database** | PostgreSQL 16 | Single instance, row-level security (RLS) |
| **Cache / Real-time** | Redis 7 | Caching, session store, pub/sub for WebSocket fan-out |
| **Voice Service** | Vosk (on-device MVP) / Whisper (Phase 2 server-side) | On-device for MVP: offline + zero-budget |
| **Monorepo** | Turborepo + pnpm | Single repo, multiple packages |

### Why Modular Monolith (not Microservices)

- **Zero budget** (Constraints): microservices multiply hosting costs, operational overhead, and CI complexity. A single backend on a free-tier platform (Railway, Render, Fly.io) keeps cost at $0.
- **Team of one**: operational burden of service mesh, inter-service auth, distributed tracing is unjustified.
- **Module-by-module development** (Constraints): each module is an internal Python package (`myworld.todos`, `myworld.calendar`, `myworld.search`), not a separate service. Future extraction to microservices is possible if scale demands it (Phase 3+).
- **Shared database is a feature** at this scale: cross-module search (FR-3) and todo-event linking (FR-4/FR-5) are trivial SQL JOINs; they become complex with separate databases.

### Rejected Architecture Styles

| Style | Rejected because |
|---|---|
| **Microservices** | Violates zero-budget constraint; operational overhead unjustified for team of one; cross-module queries become distributed joins. |
| **Serverless-only (Lambda/Workers)** | WebSocket support for real-time reminders (FR-6) is awkward; cold starts conflict with NFR-1 (<3s load); Google Calendar sync needs long-lived connections. |
| **Full-stack Next.js only (API routes)** | React Native mobile clients need a standalone API; coupling backend to Next.js ties mobile to Next.js release cadence; FastAPI async + typed schemas are superior for a multi-client API. |
| **Event-driven (Kafka/NATS)** | Unjustified complexity for MVP; Redis pub/sub covers the real-time notification need. |

---

## 2. Tech Stack — Detailed Justification

### 2.1 Web Frontend: Next.js 14 (App Router) as PWA

| Aspect | Detail |
|---|---|
| **Version** | Next.js 14.x (App Router, React Server Components) |
| **PWA** | `@ducanh2912/next-pwa` for service worker generation, offline caching |
| **Justification** | NFR-5 explicitly names Next.js. App Router enables RSC for fast initial paint (NFR-1: <3s). Built-in image optimization, code splitting, ISR. PWA support via service worker for offline (NFR-4). |

**Rejected alternatives:**

| Alternative | Rejected because |
|---|---|
| **Remix** | Smaller PWA tooling ecosystem; requirement explicitly says Next.js; less community support for service worker integration. |
| **Astro** | Not suited for a heavily interactive dashboard app; better for content sites. |
| **Vanilla React + Vite** | Loses SSR/SSG benefits, no built-in PWA tooling, more manual setup for routing and optimization. |

### 2.2 Mobile Frontend: React Native (Expo)

| Aspect | Detail |
|---|---|
| **Framework** | React Native via Expo (managed workflow for MVP) |
| **Justification** | NFR-5 explicitly names React Native. Expo simplifies build/deploy for iOS+Android. Shared design tokens and API client with web. Push notifications via Expo Push (free tier). |

**Rejected alternatives:**

| Alternative | Rejected because |
|---|---|
| **Flutter** | Requirement explicitly says React Native; Dart is a separate skill investment; less code sharing with Next.js web. |
| **Capacitor (Ionic)** | Wraps web in native shell; PWA already covers web; adds complexity without benefit for a separate mobile UX. |
| **Kotlin Multiplatform** | Requirement says React Native; steeper learning curve. |

### 2.3 Backend: FastAPI (Python 3.12+)

| Aspect | Detail |
|---|---|
| **Framework** | FastAPI 0.110+ with Uvicorn (ASGI) |
| **Justification** | Async-native (critical for WebSocket FR-6 + Google Calendar I/O). Pydantic v2 for typed schemas (shared via OpenAPI codegen). Auto-generated OpenAPI docs. Mature `google-api-python-client`. Free-tier deployable on Railway/Render. |

**Rejected alternatives:**

| Alternative | Rejected because |
|---|---|
| **Express / NestJS (Node.js)** | Python Google API libraries are more mature; FastAPI auto-generated OpenAPI + Pydantic validation is superior to Express manual approach; NestJS adds boilerplate unjustified for team of one. |
| **Django REST Framework** | Heavier framework; ORM less flexible for RLS; async support is secondary; overkill for MVP API surface. |
| **Go (Fiber/Chi)** | Excellent performance, but smaller Google Calendar SDK ecosystem; steeper ramp-up. |
| **tRPC (Node)** | Tightly coupled to TypeScript frontends; React Native support less mature; no OpenAPI spec for multi-client consumption. |

### 2.4 Database: PostgreSQL 16

| Aspect | Detail |
|---|---|
| **Version** | PostgreSQL 16.x |
| **ORM** | SQLAlchemy 2.0 (async) with Alembic for migrations |
| **Justification** | Native Row-Level Security (RLS) satisfies FR-1 at the database level. Full-text search (`tsvector`) covers FR-3 without adding Elasticsearch (zero budget). JSONB for flexible event metadata. Free tier on Neon/Supabase/Railway. |

**Rejected alternatives:**

| Alternative | Rejected because |
|---|---|
| **MySQL / MariaDB** | No native RLS; weaker full-text search; PostgreSQL JSONB and array types are better for recurrence rules. |
| **SQLite (Turso)** | Limited concurrent write performance; RLS not natively supported; sync worker needs reliable concurrent access. |
| **MongoDB** | Schema-less is a liability for structured data; no RLS; full-text search requires Atlas Search (paid). |
| **Supabase (as platform)** | Auth tied to GoTrue (not Google OAuth with Calendar scope directly); coupling to Supabase ecosystem reduces flexibility. Use only as hosted Postgres provider, not as platform. |

### 2.5 Cache / Real-time: Redis 7

| Aspect | Detail |
|---|---|
| **Version** | Redis 7.x |
| **Use cases** | (1) JWT refresh token store with TTL; (2) Google Calendar sync state/lock; (3) Rate limiting; (4) Pub/sub for WebSocket notification fan-out (FR-6); (5) Search result caching. |
| **Justification** | Sub-millisecond reads for session validation. Pub/sub enables horizontal WebSocket scaling. Free tier on Upstash (10k commands/day) or Railway. |

**Rejected alternatives:**

| Alternative | Rejected because |
|---|---|
| **Memcached** | No pub/sub, no persistence, no data structures needed for sync locks. |
| **In-memory only** | Does not survive restarts; no cross-process sharing for multiple workers. |
| **Valkey** | Compatible fork, but smaller hosting platform support for MVP. Can migrate later if Redis licensing becomes an issue. |

### 2.6 Voice Recognition: Vosk (On-Device, MVP)

| Aspect | Detail |
|---|---|
| **MVP** | Vosk on-device (React Native native module; browser WASM for PWA) |
| **Phase 2** | Whisper server-side (higher accuracy, more languages) |
| **Justification** | Constraints require open-source only. Design OQ-4 defaults to Vosk for MVP (better offline, NFR-4). Zero server cost. Small model (~40MB) downloaded once. |

### 2.7 Monorepo: Turborepo + pnpm

| Aspect | Detail |
|---|---|
| **Tool** | Turborepo (per Constraints) |
| **Package manager** | pnpm (fast, disk-efficient, strict dependency isolation) |
| **Justification** | Requirement explicitly mandates Turborepo. Shared packages across web and mobile. Cached builds speed up CI. |

---

## 3. Architecture Decision Records (ADRs)

### ADR-001: Modular Monolith over Microservices

- **Status:** Accepted
- **Context:** The system serves a single user's personal data across multiple modules (ToDo, Calendar, Search, future: Finance, News, Wellness). Team of one developer, zero budget. Cross-module queries (search, linking) are core features.
- **Decision:** Deploy as a modular monolith — a single FastAPI application with internal module packages. Each module owns its database tables and business logic but shares the same process and database.
- **Consequences:**
  - (+) Single deployment, single CI pipeline, zero inter-service networking.
  - (+) Cross-module queries are simple SQL JOINs.
  - (+) $0 hosting on free-tier platforms.
  - (-) A bug in one module can crash the entire API.
  - (-) Cannot scale individual modules independently (acceptable for personal-use scale).
  - (-) Future extraction to microservices requires refactoring shared database access. Mitigation: modules communicate through internal interfaces, not direct table access across boundaries.
- **Traceability:** Constraints (zero budget, module-by-module), FR-3 (cross-module search).

### ADR-002: PostgreSQL Row-Level Security for Data Isolation

- **Status:** Accepted
- **Context:** FR-1 requires row-level data isolation per user. Multiple users (family members) share the same database. A bug in application-level filtering could leak cross-user data.
- **Decision:** Enable PostgreSQL RLS policies on every user-scoped table (`todos`, `events`, `reminders`). Every query automatically filters by `user_id = current_setting('app.current_user_id')`. The API middleware sets this context variable from the JWT on every request.
- **Consequences:**
  - (+) Isolation enforced at the database level — immune to application-layer bugs.
  - (+) Simplifies application code (no manual `WHERE user_id = ?` on every query).
  - (-) RLS policies add complexity to migrations (each new table needs a policy).
  - (-) Direct database access (admin tools) bypasses RLS unless roles are configured. Mitigation: admin access uses a separate role with explicit grants.
- **Traceability:** FR-1, NFR-2, AC-A2.

### ADR-003: FastAPI over Node.js/Express for Backend

- **Status:** Accepted
- **Context:** The backend must serve a REST API, handle WebSocket connections, integrate with Google Calendar API, and process voice transcripts. Must run on a free tier.
- **Decision:** Use FastAPI (Python) as the backend framework.
- **Consequences:**
  - (+) Native async/await for I/O-bound Google Calendar and WebSocket operations.
  - (+) Pydantic v2 provides automatic request validation, serialization, and OpenAPI schema generation.
  - (+) `google-api-python-client` is the most mature Google API SDK.
  - (+) Python NLP ecosystem (for future voice transcript parsing) is richer than Node.js.
  - (-) Two languages in the stack (TypeScript frontend, Python backend). Mitigation: OpenAPI spec auto-generated by FastAPI, TypeScript types generated via `openapi-typescript` for frontend consumption.
  - (-) Python GIL limits CPU-bound parallelism. Mitigation: MVP workloads are I/O-bound; CPU-intensive voice processing runs on-device (Vosk).
- **Traceability:** FR-4 (voice), FR-5 (Google Calendar), FR-6 (WebSocket), Constraints (zero budget).

### ADR-004: Next.js 14 App Router with PWA Service Worker

- **Status:** Accepted
- **Context:** Web frontend must be a PWA (installable, offline-capable) with fast initial load (<3s on 4G). Must support Bento Grid dashboard, offline todo CRUD, and cached calendar views.
- **Decision:** Use Next.js 14 App Router with React Server Components for initial render, and a service worker (via `@ducanh2912/next-pwa`) for offline caching and background sync.
- **Consequences:**
  - (+) RSC streams HTML progressively, fast first paint (NFR-1).
  - (+) Service worker caches static assets and API responses, offline support (NFR-4).
  - (+) Background sync API queues offline mutations and replays on reconnect (FR-4 offline CRUD).
  - (-) App Router has some rough edges (caching behavior, streaming boundaries). Mitigation: pin to stable 14.x, follow best practices.
  - (-) PWA installability on iOS Safari is limited (no install prompt, limited background). Mitigation: native React Native app covers full mobile experience.
- **Traceability:** NFR-1, NFR-4, NFR-5, FR-2.

### ADR-005: React Native (Expo) for Mobile

- **Status:** Accepted
- **Context:** Requirements demand iOS + Android apps with full feature parity with web. Push notifications must work on locked screens (AC-R3). Voice capture must access device microphone.
- **Decision:** Use React Native via Expo managed workflow.
- **Consequences:**
  - (+) Single codebase for iOS + Android (NFR-5).
  - (+) Expo Push Notifications free tier; unlimited in production with own credentials.
  - (+) Expo OTA updates (EAS Update free tier) for quick fixes without app store review.
  - (+) Shared design tokens and API client types with web (via monorepo packages).
  - (-) Expo managed workflow limits native module customization. Mitigation: Vosk has Expo-compatible native module; if not, eject to bare workflow (acceptable risk).
  - (-) React Native bridge can cause performance issues on complex animations. Mitigation: design uses minimal animation (150-250ms ease-out only); new architecture (Fabric + TurboModules) available in Expo SDK 51+.
- **Traceability:** NFR-5, FR-4 (voice), FR-6 (push notifications), SC-1.

### ADR-006: Vosk On-Device for MVP Voice Recognition

- **Status:** Accepted
- **Context:** Requirements mandate open-source voice recognition (Constraints). Design OQ-4 defaults to Vosk for MVP. Voice must work offline (NFR-4). Zero budget prohibits cloud STT APIs.
- **Decision:** Use Vosk on-device for MVP. The small English model (~40MB) is downloaded once on first use and cached. Voice processing runs entirely on the client (browser WASM for PWA, native module for React Native).
- **Consequences:**
  - (+) Zero server cost for voice processing.
  - (+) Works offline — satisfies NFR-4 for voice-created todos.
  - (+) No audio data leaves the device — privacy benefit.
  - (-) Accuracy lower than Whisper, especially for accents and noisy environments. Mitigation: design E-5 handles unintelligible transcripts gracefully; Whisper upgrade path in Phase 2.
  - (-) Model download (~40MB) on first use. Mitigation: download triggered on first mic tap with progress indicator; cached thereafter.
  - (-) WASM-based Vosk in browser has limited language support. Mitigation: MVP is English-only; Phase 2 adds languages with Whisper.
- **Traceability:** FR-4, NFR-4, Constraints (open-source, zero budget), Design OQ-4.

### ADR-007: Turborepo Monorepo with pnpm

- **Status:** Accepted
- **Context:** Constraints mandate a monorepo with Turborepo. Multiple packages (web, mobile, shared types, shared API client, design tokens) must coexist.
- **Decision:** Use Turborepo with pnpm workspaces.
- **Consequences:**
  - (+) Shared packages (`@myworld/types`, `@myworld/api-client`, `@myworld/design-tokens`) consumed by web and mobile without publishing to npm.
  - (+) Turborepo caches build outputs, fast CI and local rebuilds.
  - (+) pnpm strict dependency isolation prevents phantom dependencies.
  - (-) Monorepo tooling complexity (workspace config, build ordering). Mitigation: Turborepo handles dependency graph automatically.
  - (-) React Native + monorepo requires careful Metro bundler configuration (symlink resolution). Mitigation: Expo monorepo guide provides tested patterns.
- **Traceability:** Constraints (monorepo with Turborepo).

### ADR-008: Redis for Session, Cache, and Real-time Pub/Sub

- **Status:** Accepted
- **Context:** JWT refresh tokens need secure, TTL-based storage. Google Calendar sync needs distributed locking. WebSocket notifications (FR-6) need pub/sub for multi-worker fan-out. Search results benefit from caching (NFR-1: <500ms).
- **Decision:** Use a single Redis instance for four concerns: (1) refresh token store, (2) sync locks, (3) pub/sub channels, (4) search result cache.
- **Consequences:**
  - (+) Single infrastructure dependency for multiple cross-cutting concerns.
  - (+) Redis TTL auto-expires refresh tokens — no cleanup cron needed.
  - (+) Pub/sub enables horizontal scaling of WebSocket workers if needed.
  - (-) Redis is an additional service to manage. Mitigation: Upstash free tier (10k commands/day) sufficient for MVP; managed service means no operational burden.
  - (-) If Redis goes down, refresh tokens are lost (users must re-authenticate) and sync locks release. Mitigation: acceptable for MVP; Phase 2 can add Redis persistence or migrate to managed HA.
- **Traceability:** FR-1 (JWT), FR-3 (search), FR-5 (sync), FR-6 (real-time).

### ADR-009: Google Full-Text Search over Elasticsearch

- **Status:** Accepted
- **Context:** FR-3 requires cross-module universal search with <500ms latency. Zero budget prohibits Elasticsearch/OpenSearch clusters.
- **Decision:** Use PostgreSQL `tsvector` full-text search with `ts_rank` for relevance scoring. Indexes on `todos` and `events` tables. Search API queries both tables in a single round-trip with `UNION ALL`.
- **Consequences:**
  - (+) Zero additional infrastructure — search runs on the same Postgres instance.
  - (+) `tsvector` indexes provide sub-100ms search for personal-data scale (<10k records per user).
  - (+) `ts_rank` provides basic relevance scoring (title matches rank higher than description).
  - (-) PostgreSQL full-text search lacks fuzzy matching and advanced NLP features. Mitigation: acceptable for MVP personal-use scale; Phase 2 can add pg_trgm for trigram similarity if needed.
  - (-) Search across future modules (News, Documents) may exceed Postgres capabilities. Mitigation: search is abstracted behind an internal `SearchService` interface; backend can be swapped to Meilisearch (free tier) in Phase 3+.
- **Traceability:** FR-3, NFR-1 (500ms), Constraints (zero budget), AC-S1.

### ADR-010: Google People API for Birthday Contact Import

- **Status:** Accepted
- **Date:** 2026-08-23
- **Context:** FR-5 explicitly requires "Birthday/anniversary reminders (manual entry + **contact import**)." US-5 acceptance criteria state: "I can add a birthday manually (name + date) or **pull contacts from Google**." The architecture previously had no integration for importing contacts — only Google OAuth2 and Google Calendar API were listed. Review finding H-1 flagged this gap. The Google People API (`people.googleapis.com`) provides access to the authenticated user's Google Contacts, including the `birthdays` and `names` fields, and is the officially supported API for reading contact data.
- **Decision:** Integrate the **Google People API** (Contacts scope) to fetch contacts that have a birthday field populated. On user-initiated import (via `POST /api/calendar/contacts/import`), the backend fetches contacts with birthdays from Google People API, transforms each into a yearly-recurring all-day event, and **upserts** them into the `events` table (keyed on `google_contact_id` to prevent duplicates). A lightweight `contacts` service is added inside the existing `calendar` module — not a separate module — because imported birthdays are calendar events, and the service's sole responsibility is the fetch-transform-upsert pipeline. The OAuth scope `https://www.googleapis.com/auth/contacts.readonly` is requested incrementally (separate consent from Calendar scope) only when the user triggers the import feature.
- **Consequences:**
  - (+) Closes review gap H-1 — FR-5 and US-5 contact import requirement is now fully addressed in the architecture.
  - (+) User-initiated import (not automatic sync) keeps Google People API quota usage minimal and avoids background sync complexity.
  - (+) Upsert via `google_contact_id` ensures re-imports do not create duplicate events; updated birthdays in Google Contacts are reflected on re-import.
  - (+) Read-only scope (`contacts.readonly`) is the minimum permission — no write-back to Google Contacts.
  - (+) Imported birthdays integrate seamlessly with existing reminder system (FR-6) — they are standard `events` rows with `recurrence_rule` set to yearly and `color` set to `emerald` (per design §10.2 color coding for birthdays/anniversaries).
  - (-) Requires incremental OAuth consent — users must grant a second permission beyond Calendar. Mitigation: consent is requested lazily, only when the user taps "Import from Google Contacts"; clear UX copy explains why.
  - (-) Google People API free quota (10k requests/day per project) is generous for personal use but a sync bug could exhaust it. Mitigation: import is user-initiated (not scheduled), and Redis lock prevents concurrent imports; rate limiting at 1 request/minute per user.
  - (-) `google_contact_id` adds a new column to the `events` table. Mitigation: single nullable column, no schema complexity.
- **Traceability:** FR-5 (contact import), US-5 (pull contacts from Google), Review H-1, `input_needed.md` item #6 (People API Enabled).

### ADR-011: iOS App Store Submission Deferred to Phase 2; MVP Distribution via Expo Go, Android APK Sideload, and Web PWA

- **Status:** Accepted
- **Date:** 2026-08-23
- **Context:** NFR-5 requires cross-platform support (Web, iOS, Android) with full feature parity. SC-1 requires the app to run on iOS and Android devices. However, iOS App Store submission requires an Apple Developer account ($99/year), App Review compliance, provisioning profiles, and a macOS build environment — none of which align with the zero-budget MVP constraint. Android distribution via Google Play has similar (though lower-barrier) requirements. The Web PWA is installable on all platforms without any store. Expo Go allows running the React Native app on physical iOS devices during development without App Store submission. Android APKs can be sideloaded directly onto devices without Google Play. This ADR formalizes the MVP distribution strategy that avoids all app store costs and friction while still enabling real-device testing on both platforms.
- **Decision:** Defer iOS App Store and Google Play Store submissions to Phase 2. For MVP distribution:
  1. **iOS:** Testing via Expo Go app (free, no Apple Developer account needed). No TestFlight, no App Store submission in MVP.
  2. **Android:** APK sideload — build a standalone APK via EAS Build and distribute directly (no Google Play account needed). Users enable "Install from unknown sources" to install.
  3. **Web PWA:** Covers all platforms (desktop, iOS Safari, Android Chrome) as the primary distribution channel. Installable on Android Chrome and desktop browsers; accessible (non-installable) on iOS Safari.
- **Consequences:**
  - (+) **Zero distribution cost** — no Apple Developer ($99/year) or Google Play ($25 one-time) fees during MVP. Aligns with zero-budget constraint.
  - (+) **No App Review delays** — iOS App Review can take 24-48 hours per submission and may reject for policy reasons; avoided entirely in MVP.
  - (+) **Faster iteration** — Expo OTA updates (EAS Update free tier) push fixes to Expo Go users instantly without any store review cycle.
  - (+) **Web PWA is the universal fallback** — every platform with a modern browser can access the full app, ensuring no user is blocked regardless of native app availability.
  - (-) **iOS users cannot install a standalone app in MVP** — they must use Expo Go (which shows an Expo splash screen and requires the Expo Go app installed) or the Web PWA (limited background capabilities on iOS Safari). Mitigation: this is acceptable for MVP testing with family members; Phase 2 adds proper App Store distribution.
  - (-) **Android sideload requires manual APK distribution** — users must receive the APK file via a shared link and enable "unknown sources" in settings. Mitigation: provide a direct download link from the web app or a shared drive; document the install steps clearly.
  - (-) **Push notifications on iOS PWA are limited** — iOS Safari does not support Web Push (background push notifications) for PWAs. Mitigation: iOS users testing via Expo Go receive push notifications via Expo Push (native channel); Web PWA push works on Android and desktop. Phase 2 App Store build enables full APNs.
  - (-) **No public discoverability** — app is not in any store, so discovery is limited to direct sharing. Mitigation: acceptable for MVP (personal/family use); Phase 2 targets store presence.
- **Traceability:** NFR-5 (cross-platform), SC-1 (iOS + Android), Constraints (zero budget), OI-6 (Apple Developer account — now deferred).

### ADR-012: Explicit `/api/v1/` Prefix on All Endpoints

- **Status:** Accepted
- **Date:** 2026-08-23
- **Context:** The API contract table (Section 4.3) previously listed all routes under a bare `/api/` prefix with a note that `/api/` aliased to the latest version internally. While functional for MVP, this creates two problems: (1) clients have no explicit version in their URLs, making it impossible to introduce a breaking `/api/v2/` later without ambiguity about which version `/api/` resolves to; (2) generated OpenAPI specs and typed API clients would embed unversioned paths, forcing a coordinated client upgrade on any future breaking change. The requirements document (`docs/requirements.md` §API Endpoints) lists paths as `/api/...` without specifying versioning — this is an architectural decision, not a requirements conflict. WebSocket endpoints face the same concern: `/ws/notifications` should also carry a version segment.
- **Decision:** All REST endpoints use the explicit `/api/v1/` prefix. The WebSocket endpoint uses `/ws/v1/notifications`. No unversioned `/api/` alias is exposed. FastAPI's `APIRouter` is mounted with `prefix="/api/v1"` at the application level. If a breaking v2 is introduced in a future phase, it will be mounted at `/api/v2/` alongside v1, allowing gradual client migration.
- **Consequences:**
  - (+) **Forward-compatible versioning** — introducing breaking API changes in Phase 2+ requires only adding a new router prefix; existing v1 clients are unaffected.
  - (+) **Explicit contracts** — generated OpenAPI specs and typed API clients (`@myworld/api-client`) embed `/api/v1/` in every path, making the version visible in code, logs, and network inspectors.
  - (+) **Consistency** — REST and WebSocket endpoints follow the same versioning convention (`/api/v1/...`, `/ws/v1/...`).
  - (+) **Observability** — API gateway logs and metrics can segment traffic by version prefix, useful when v2 is introduced.
  - (-) Slightly longer URL paths. Mitigation: negligible impact; no human types these URLs (typed API client handles it).
  - (-) Requirements doc lists paths as `/api/...` without `v1`. Mitigation: requirements specify the resource model, not the URL versioning scheme; the architect owns this decision. Traceability note added to requirements mapping below.
- **Traceability:** `docs/requirements.md` §API Endpoints (resource paths); NFR-2 (Security — explicit versioning reduces accidental exposure of deprecated endpoints); SC-7 (future phases land without breaking MVP modules — versioned API supports this).

---

## 4. Component / Interface View

### 4.1 Monorepo Package Structure

```
products/myworld/
   apps/
     web/                  # Next.js 14 PWA (App Router)
     mobile/               # React Native (Expo)
     api/                  # FastAPI backend
   packages/
     types/                # Shared TypeScript types (generated from OpenAPI)
     api-client/           # Typed HTTP/WebSocket client (web + mobile)
     design-tokens/        # Color, spacing, typography tokens (JSON to CSS/RN)
     validators/           # Shared Zod schemas (web) / Pydantic mirror (api)
   turbo.json
   pnpm-workspace.yaml
   package.json

### 4.2 Backend Internal Modules (FastAPI)

```
apps/api/
  myworld/
    core/                 # Auth middleware, DB session, Redis client, config
    auth/                 # Google OAuth2, JWT issuance, refresh, profile mgmt
    todos/                # CRUD, recurrence engine, offline sync queue
    calendar/             # CRUD, Google Calendar sync worker, event linking
      contacts/           # Google People API fetch, birthday transform, upsert (ADR-010)
    search/               # Cross-module full-text search service
    reminders/            # Reminder scheduling, WebSocket push, notification dispatch
    dashboard/            # Aggregated tile data endpoint
  alembic/                # Database migrations
  tests/
  pyproject.toml
  Dockerfile
```

Each module is a self-contained Python package with its own: Router (API endpoints), Models (SQLAlchemy ORM), Schemas (Pydantic request/response), Service layer (business logic), Repository layer (database access).

Modules communicate through **internal interfaces** (Python function calls), not through HTTP. Cross-module data access goes through the owning module's repository, not direct table queries.

### 4.3 Public API Contracts

All endpoints are JSON over HTTPS. Auth via `Authorization: Bearer <JWT>` header.

| Method | Path | Module | Purpose |
|---|---|---|---|
| POST | `/api/v1/auth/google` | auth | OAuth2 login (exchanges code for JWT) |
| GET | `/api/v1/auth/me` | auth | Current user profile |
| POST | `/api/v1/auth/refresh` | auth | Refresh JWT using refresh token |
| POST | `/api/v1/auth/signout` | auth | Invalidate refresh token |
| GET | `/api/v1/todos` | todos | List todos (filter: status, due range, pagination) |
| POST | `/api/v1/todos` | todos | Create todo |
| GET | `/api/v1/todos/:id` | todos | Get single todo |
| PUT | `/api/v1/todos/:id` | todos | Update todo |
| DELETE | `/api/v1/todos/:id` | todos | Delete todo |
| POST | `/api/v1/todos/voice` | todos | Submit voice transcript for parsing |
| POST | `/api/v1/todos/sync` | todos | Batch sync offline mutations |
| GET | `/api/v1/calendar/events` | calendar | List events (filter: date range, source) |
| POST | `/api/v1/calendar/events` | calendar | Create event (optionally syncs to Google) |
| PUT | `/api/v1/calendar/events/:id` | calendar | Update event |
| DELETE | `/api/v1/calendar/events/:id` | calendar | Delete event |
| POST | `/api/v1/calendar/contacts/import` | calendar | Import birthdays from Google Contacts (ADR-010) |
| GET | `/api/v1/calendar/contacts/import/status` | calendar | Last contact import timestamp and result count (ADR-010) |
| POST | `/api/v1/calendar/sync/google` | calendar | Trigger Google Calendar sync |
| GET | `/api/v1/calendar/sync/status` | calendar | Last sync timestamp and status |
| GET | `/api/v1/dashboard` | dashboard | Aggregated data for all Bento tiles |
| GET | `/api/v1/search?q=` | search | Cross-module search (min 2 chars) |
| GET | `/api/v1/reminders` | reminders | List pending reminders |
| POST | `/api/v1/reminders` | reminders | Create reminder |
| WS | `/ws/v1/notifications` | reminders | Real-time notification stream |

**API versioning:** All endpoints use `/api/v1/` prefix for consistency. *(Updated 2026-08-23 — see ADR-012.)*

### 4.4 Data Model (Canonical Schema)

**Table: `users`**
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK, generated |
| email | VARCHAR(255) | UNIQUE, NOT NULL |
| name | VARCHAR(255) | NOT NULL |
| avatar_url | VARCHAR(512) | NULLABLE |
| provider | VARCHAR(50) | DEFAULT 'google' |
| contacts_scope_granted | BOOLEAN | DEFAULT false (ADR-010: user granted contacts.readonly scope) |
| contacts_synced_at | TIMESTAMPTZ | NULLABLE (ADR-010: last successful contact import timestamp) |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | DEFAULT now() |

RLS: ENABLED on all queries.

**Table: `todos`**
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK, generated |
| user_id | UUID | FK -> users.id, NOT NULL |
| title | VARCHAR(500) | NOT NULL |
| description | TEXT | NULLABLE |
| priority | SMALLINT | DEFAULT 0 (0=none, 1=low, 2=medium, 3=high) |
| due_date | TIMESTAMPTZ | NULLABLE |
| recurrence | VARCHAR(50) | NULLABLE (daily/weekly/monthly/yearly/none) |
| status | VARCHAR(20) | DEFAULT 'open' (open/done) |
| linked_event_id | UUID | FK -> events.id, NULLABLE |
| search_vector | tsvector | Generated from title + description |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | DEFAULT now() |

RLS: ENABLED. Indexes: `user_id`, `status`, `due_date`, `search_vector` (GIN).

**Table: `events`**
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK, generated |
| user_id | UUID | FK -> users.id, NOT NULL |
| title | VARCHAR(500) | NOT NULL |
| description | TEXT | NULLABLE |
| start_at | TIMESTAMPTZ | NOT NULL |
| end_at | TIMESTAMPTZ | NOT NULL |
| all_day | BOOLEAN | DEFAULT false |
| color | VARCHAR(20) | DEFAULT 'blue' (from design token palette) |
| source | VARCHAR(20) | NOT NULL (manual/google) |
| google_event_id | VARCHAR(255) | NULLABLE, UNIQUE per user |
| google_contact_id | VARCHAR(255) | NULLABLE, UNIQUE per user (ADR-010: dedup key for imported birthday contacts) |
| recurrence_rule | JSONB | NULLABLE (iCal RRULE format) |
| search_vector | tsvector | Generated from title + description |
| created_at | TIMESTAMPTZ | DEFAULT now() |
| updated_at | TIMESTAMPTZ | DEFAULT now() |

RLS: ENABLED. Indexes: `user_id`, `start_at`, `google_event_id`, `google_contact_id`, `search_vector` (GIN).

**Table: `reminders`**
| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK, generated |
| user_id | UUID | FK -> users.id, NOT NULL |
| todo_id | UUID | FK -> todos.id, NULLABLE |
| event_id | UUID | FK -> events.id, NULLABLE |
| message | TEXT | NOT NULL |
| trigger_at | TIMESTAMPTZ | NOT NULL |
| type | VARCHAR(20) | NOT NULL (push/in-app) |
| sent | BOOLEAN | DEFAULT false |
| created_at | TIMESTAMPTZ | DEFAULT now() |

RLS: ENABLED. Indexes: `user_id`, `trigger_at` (for scheduler polling), `sent`.

**Constraint:** A reminder binds to exactly one of `todo_id` or `event_id` (CHECK constraint ensures exactly one is NOT NULL).

### 4.5 Integration Points

| Integration | Protocol | Direction | Notes |
|---|---|---|---|
| **Google OAuth2** | HTTPS + OAuth2 | Bidirectional | Auth code exchange, token refresh. Scopes: `openid`, `email`, `profile`. |
| **Google Calendar API** | HTTPS REST | Bidirectional | Read/write events. Separate consent from sign-in. Sync worker runs every 15 min. |
| **Google People API** | HTTPS REST | Inbound (read-only) | Fetch contacts with birthday field for import (ADR-010). Scope: `contacts.readonly`. User-initiated, not scheduled. `google-api-python-client` service: `peopleService.people().connections().list()`. |
| **Web Push (VAPID)** | HTTPS | Outbound | PWA push notifications via Web Push API. |
| **Expo Push** | HTTPS | Outbound | Mobile push notifications via Expo Push API. |
| **WebSocket** | WSS | Bidirectional | Real-time notification delivery to connected clients. |
| **Vosk (on-device)** | In-process | Client-side only | No server integration for MVP. Audio processed locally; only parsed text sent to API. |

### 4.6 Deployment Shape

| Component | Hosting | Free Tier | Notes |
|---|---|---|---|
| **Next.js PWA (web)** | Vercel | Hobby plan (unlimited) | Auto-deploy from Git. Edge functions for API proxying. |
| **React Native (mobile)** | EAS Build (Expo) | 30 builds/month | iOS + Android builds. OTA updates via EAS Update free tier. |
| **FastAPI (API + WS)** | Railway or Render | $5 free credit/month (Railway) or 750 hrs (Render) | Single Docker container. Uvicorn ASGI server. WebSocket on same port. |
| **PostgreSQL** | Neon or Supabase | 0.5 GB storage (Neon) or 500 MB (Supabase) | Managed Postgres. Auto-pause on inactivity (Neon). |
| **Redis** | Upstash | 10k commands/day, 256 MB | Serverless Redis. HTTP API option for edge compatibility. |
| **Domain / DNS** | Cloudflare | Free | DNS, SSL, DDoS protection. |

**Total monthly cost: $0** (all services within free tier limits for personal-use scale).

**Scaling trigger:** If Railway/Render free tier is exhausted (CPU/memory), migrate API to Fly.io free tier (3 shared VMs) or add a $5/month plan. This is a Phase 2 concern.

---

## 5. Non-Functional Requirements Mapping

| NFR | Target | Architecture Response | Verification |
|---|---|---|---|
| **NFR-1: Performance** | Initial load < 3s on 4G | Next.js RSC streams HTML progressively; static assets cached by SW; API responses cached in Redis; dashboard endpoint returns pre-aggregated tile data. | Lighthouse CI on every PR; simulated 4G profile. AC-G5, AC-N2. |
| **NFR-1: Tile render** | < 1s per tile | Each tile fetches data in parallel via `Promise.all`; skeleton placeholders render instantly; SWR (stale-while-revalidate) for cached-first rendering. | Lighthouse LCP measurement per tile route. |
| **NFR-1: Search** | < 500ms | PostgreSQL GIN index on `tsvector` columns; single query with `UNION ALL`; Redis cache for repeated queries (5 min TTL). | API latency monitoring; AC-S1. |
| **NFR-2: Security** | OAuth2 + JWT + RLS | Google OAuth2 for auth; JWT with 15-min access token + 7-day refresh token stored in Redis; PostgreSQL RLS on all user tables; HTTPS everywhere (Cloudflare forced). | Penetration test checklist; AC-A1..A4. |
| **NFR-2: Encryption** | Data at rest | PostgreSQL hosted on Neon/Supabase (encrypted at rest by default). Voice transcripts and journal content encrypted at application level (Phase 2). | Provider documentation; AC-N4. |
| **NFR-2: Logs** | No sensitive data | Structured logging with PII redaction middleware; log levels configurable; no JWT tokens, passwords, or PII in log output. | Code review checklist; log audit. |
| **NFR-3: Accessibility** | WCAG 2.1 AA | Design tokens enforce contrast (Section 2.5); keyboard nav via semantic HTML; focus rings; `aria-*` attributes; `prefers-reduced-motion` respected. | Axe-core scan on every PR (0 critical/serious violations); AC-N1. |
| **NFR-4: Offline** | Full CRUD offline (ToDo), read cache (Calendar) | Service worker caches API responses; IndexedDB stores offline mutations; background sync replays queue on reconnect. React Native: AsyncStorage + sync queue. | Manual offline test matrix; AC-T1. |
| **NFR-5: Cross-platform** | Web PWA + iOS + Android, full parity | Next.js PWA for web; React Native (Expo) for iOS+Android; shared API client + design tokens ensure consistent behavior. | Device testing matrix (iPhone SE, Pixel 7, iPad Mini, Chrome desktop); SC-1. |
| **NFR-5: Responsive** | 375px / 768px / 1024px+ | CSS Grid with breakpoints matching design spec Section 9.1; tiles reflow from 1 to 4 columns. | Visual regression testing; AC-G1, AC-G2. |

### Observability Targets

| Concern | Tool | Target |
|---|---|---|
| **Error tracking** | Sentry (free tier: 5k events/month) | All unhandled exceptions captured; alert on critical errors. |
| **API latency** | FastAPI middleware + Prometheus (or Railway metrics) | p95 latency < 200ms for CRUD; < 500ms for search. |
| **Uptime** | UptimeRobot (free: 50 monitors) | 99% uptime target (acceptable for personal-use MVP). |
| **Logging** | Structured JSON logs (platform-native or Loki free tier) | All API requests logged with method, path, status, latency_ms. |

---

## 6. Risks and Open Items

### Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | **Free tier exhaustion** — Railway/Render free credits run out before MVP is complete. | Medium | High | Monitor usage weekly; migrate to Fly.io free tier or Render's always-free plan (spins down after inactivity). |
| R-2 | **Vosk on-device accuracy** — Voice recognition fails frequently for non-native English speakers. | Medium | Medium | Design already handles gracefully (E-5); collect failure data for Whisper Phase 2 prioritization. |
| R-3 | **Google Calendar API quota** — Free quota (1M queries/day) is generous but sync bugs could cause runaway requests. | Low | High | Rate limiting in sync worker; Redis lock prevents concurrent syncs; monitoring alert at 50% quota. |
| R-4 | **PostgreSQL RLS misconfiguration** — A migration forgets to add RLS policy on a new table. | Medium | Critical | Alembic migration template enforces RLS policy creation; CI check scans all tables for RLS enablement. |
| R-5 | **React Native + monorepo Metro issues** — Symlink resolution in Metro bundler causes build failures. | Medium | Medium | Follow Expo monorepo guide exactly; pin Metro config; test builds on CI after dependency changes. |
| R-6 | **iOS PWA limitations** — Users on iOS Safari cannot install PWA with full capabilities; background notifications don't work. | High | Low | ADR-011: MVP iOS testing via Expo Go (native push via Expo Push, not PWA). Web PWA covers iOS as accessible-only (no install, no background push). Document iOS PWA limitations in onboarding. Full native iOS experience deferred to Phase 2 App Store build. |
| R-7 | **Neon/Supabase auto-pause** — Database pauses after inactivity on free tier; first request after pause has 500ms+ cold start. | High | Medium | Acceptable for personal-use MVP; dashboard shows loading skeleton during cold start. Keep-alive ping every 5 min if needed. |
| R-8 | **WebSocket connection drops on mobile** — Backgrounded apps lose WebSocket connection; reminders may be missed. | High | Medium | Push notifications (Web Push + Expo Push) are the primary delivery mechanism; WebSocket is supplementary for in-app real-time updates. |
| R-9 | **Google People API incremental consent friction** — Users may decline the additional `contacts.readonly` scope, blocking birthday import. | Medium | Low | Lazy consent with clear UX explanation; manual birthday entry remains fully functional as fallback (US-5). |

### Open Items (require user input or future decision)

| # | Item | Status | Blocked by | Notes |
|---|---|---|---|---|
| OI-1 | **Design OQ-1: Tile ordering** — Fixed or personalized on first run? | Deferred | User decision | Architecture default: fixed order (Search, ToDo, Calendar, Upcoming). No personalization layer in MVP. |
| OI-2 | **Design OQ-4: Voice model** — Vosk or Whisper for MVP? | Decided: Vosk | -- | ADR-006. Whisper deferred to Phase 2. |
| OI-3 | **Design OQ-7: Multi-profile switching** — Avatar menu switcher or separate sign-out? | Deferred | User decision | Architecture default: sign-out and re-OAuth (simplest for MVP). Avatar menu switcher in Phase 2. |
| OI-4 | **Hosting provider final selection** — Railway vs Render vs Fly.io for API? | Open | Implementation | All three offer viable free tiers. Final choice depends on actual resource usage during development. Recommend Railway for simplicity; migrate if limits hit. |
| OI-5 | **Google Cloud Console project setup** — OAuth client ID + Calendar API + People API credentials need to be created. People API must be enabled in the project (per `input_needed.md` item #6). | Open | Implementation | Prerequisite for auth module. Requires user's Google account. |
| OI-6 | **Apple Developer account** — Required for iOS app distribution via TestFlight/App Store. | Decided: deferred to Phase 2 | -- | ADR-011. MVP uses Expo Go for iOS testing ($0). Apple Developer account ($99/year) deferred until Phase 2 App Store submission. |
| OI-7 | **DPDP compliance** — Deferred to Phase 2 per requirements. | Deferred | Phase 2 | Architecture should not preclude future consent management. Data model has no DPDP-blocking design. |
| OI-8 | **Calendar sync interval** — Design says "architect decides N". | Decided: 15 min | -- | Configurable via environment variable. 15 min balances freshness vs API quota for personal use. |
| OI-9 | **Vosk Expo module availability** — Confirm Vosk has a working Expo-compatible React Native module. | Open | Implementation | If not available, requires ejecting to bare workflow or building a custom native module. Risk R-5 related. |
| OI-10 | **VAPID key generation** — Web Push requires VAPID keypair generation and registration. | Open | Implementation | One-time setup; keys stored as environment variables. |
| OI-11 | **Contact import UX** — Confirm whether contact import is a one-time bulk action, repeatable on-demand, or both. Also: should contacts without birthdays be shown (greyed out) or silently filtered? | Open | User decision | Architecture default: on-demand import (user taps button each time); contacts filtered to those with a birthday field only. Re-import upserts (no duplicates). |
| OI-12 | **Google People API OAuth incremental consent timing** — Should the `contacts.readonly` scope be requested at initial sign-in (bundled with Calendar) or only when user first triggers import? | Decided: lazy | -- | ADR-010: incremental consent requested only when user taps "Import from Google Contacts". Avoids scope creep at sign-in and reduces consent friction. |

---

## Addendum — 2026-08-23

**Security clarification:** Row-Level Security (RLS) for data isolation + field-level encryption for sensitive columns (health, financial data).

> *This clarification extends ADR-002 (RLS for data isolation, already accepted) and NFR-2 Encryption (Section 5). RLS continues to enforce per-user row isolation at the database level. Field-level encryption is added as a defense-in-depth measure for sensitive columns — specifically health and financial data columns introduced by future modules (Wellness, Finance). Implementation approach: application-level encryption/decryption via a symmetric key (e.g., AES-256-GCM) managed through environment variables in MVP, with key rotation deferred to Phase 2. Encrypted columns are stored as `BYTEA` or base64-encoded `TEXT` and are excluded from full-text search indexes (search cannot operate on ciphertext). This does not conflict with any existing ADR; it supplements the encryption-at-rest guarantee (currently delegated to the hosting provider) with column-level protection for high-sensitivity data.*

### ADR-013: Asymmetric Recurrence Model — Simple Enum for Todos, iCal RRULE JSONB for Events

- **Status:** Accepted
- **Date:** 2026-08-23
- **Context:** The system models two distinct recurring entities: **todos** (FR-2) and **events** (FR-5). Their recurrence needs differ fundamentally. Todos are task-oriented — a user marks "Take out trash" as recurring `weekly` or "Pay rent" as `monthly`. The recurrence semantics are simple: a single frequency with no exceptions, no end-date logic, and no interval complexity. Events, by contrast, are calendar-oriented — they must interoperate with Google Calendar (FR-5), which uses iCal RRULE (`RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR;UNTIL=20261231T235959Z`). Events require support for complex patterns: multi-day intervals (`FREQ=DAILY;INTERVAL=3`), specific weekdays (`BYDAY=TU,TH`), month-end rules (`BYMONTHDAY=-1`), exception dates (`EXDATE`), and bounded recurrence (`COUNT=10` or `UNTIL`). Google Calendar sync (ADR-008 integration) mandates RRULE fidelity — a simplified enum would lose information on import and produce incompatible rules on export. Using RRULE for todos would be over-engineering (no user expects `BYDAY` complexity on a todo); using a simple enum for events would break Google Calendar round-tripping. The data model (Section 4.4) already reflects this split: `todos.recurrence` is `VARCHAR(50)` constrained to `daily/weekly/monthly/yearly/none`, and `events.recurrence_rule` is `JSONB` storing the full iCal RRULE object.
- **Decision:**
  1. **Todos** use a **simple enum** for recurrence: `daily | weekly | monthly | yearly | none`. Stored as `VARCHAR(50)` in `todos.recurrence`. The recurrence engine in the `todos` module generates the next `due_date` by applying a fixed offset (1 day / 7 days / 1 month / 1 year) when a recurring todo is marked done. No support for intervals, weekday selection, or end conditions.
  2. **Events** use **iCal RRULE stored as JSONB** in `events.recurrence_rule`. The RRULE object follows RFC 5545 §3.3.10 and is stored as a structured JSON document (e.g., `{"freq": "WEEKLY", "byday": ["MO", "WE", "FR"], "until": "2026-12-31T23:59:59Z"}`). The recurrence engine in the `calendar` module uses a library (e.g., `python-dateutil.rrule`) to expand RRULE into concrete occurrence dates for display and reminder scheduling. Google Calendar sync preserves RRULE bidirectionally — imported Google events retain their original RRULE; exported events send the JSONB RRULE directly to the Google Calendar API `recurrence` field.
  3. The two models are **intentionally asymmetric** — they serve different user mental models and different integration requirements. No shared recurrence abstraction is introduced.
- **Consequences:**
  - (+) **Todos remain simple** — creating a recurring todo is a single dropdown selection (daily/weekly/monthly/yearly). No cognitive overhead for the user; no RRULE library dependency in the todos module.
  - (+) **Events maintain Google Calendar fidelity** — round-trip sync preserves complex recurrence patterns without data loss. A Google event with `FREQ=WEEKLY;BYDAY=TU,TH;COUNT=8` imports and exports identically.
  - (+) **Reminder scheduling works correctly for both** — todo reminders use simple date arithmetic (add N days/months); event reminders use RRULE expansion to find the next occurrence and schedule accordingly.
  - (+) **JSONB storage for RRULE is query-friendly** — PostgreSQL JSONB operators allow filtering events by recurrence properties (e.g., `WHERE recurrence_rule->>'freq' = 'WEEKLY'`) without a separate table.
  - (-) **Two recurrence engines to maintain** — the `todos` module has a simple offset calculator; the `calendar` module depends on `python-dateutil.rrule` (or equivalent). Mitigation: each engine is internal to its module; no shared recurrence interface means no leak of complexity from events into todos.
  - (-) **Todos cannot express "every 2 weeks" or "every weekday"** — these patterns require RRULE. Mitigation: requirements do not demand this for todos; if needed in Phase 2, the `todos.recurrence` column can be migrated to JSONB without breaking the existing enum values (JSONB can store `{"freq": "weekly"}` as a superset).
  - (-) **RRULE expansion for events can be computationally expensive** for unbounded recurrence rules (no `UNTIL` or `COUNT`). Mitigation: expansion is bounded to the queried date range (e.g., current month + 3 months); the calendar API accepts `start` and `end` parameters to limit expansion.
  - (-) **RRULE JSONB validation** — malformed RRULE JSON could be stored without detection. Mitigation: Pydantic schema on the API layer validates RRULE structure before persistence; invalid RRULE is rejected with a 422 response.
- **Traceability:** FR-2 (todo recurrence), FR-5 (Google Calendar sync, event recurrence), US-2 (recurring todos), US-5 (calendar events with recurrence), Section 4.4 data model (`todos.recurrence`, `events.recurrence_rule`).

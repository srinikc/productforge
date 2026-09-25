# Product Plan — Myworld

_Owned by: Ideation stage (Stage 0). Single source of truth for all downstream agents._

---

## Raw Idea (Full User Input)

> I want to have Central Website - Myworld that will have all of my information/links to app/other places at one central place to refer than multiple sites. It should have following ones and should be very highly intuitive, elegant ui/ux which is latest and if needed can search through internet and scrape the sites which are popular in Good UI design/templates etc.:

### Module 1: News
- Customized top 10-20 News from India on:
  - Politics
  - India in general
  - Global Level top news
  - Technology
  - Electronics, IOT
  - AI / AI Agents industry - whats happening/what's new/standards/tools
  - Farming
  - Government Policies
  - Health Tips - Natural validated ones, Body, ayurvedic ones
  - Travel - Places to visit nearby - spots/curative homestays/resorts

### Module 2: Calendar - Events
- Birthdays, Anniversary of family members, friends, relatives - curative from FB or manual entry
- Other Events of festivals / scheduled events from Google Calendar
- Should be able to schedule a calendar - Google from here
- Reminders / notification for upcoming ones

### Module 3: Goals
- Life Goals + Financial Goals → point to Mymoney app Goals

### Module 4: Health
- Tips, Dashboard/Spreadsheet/Planner - Daily/weekly/monthly
- Diet Chart that includes Vitamins, minerals, antioxidants, nutrients, Fiber, Protein and other healthy identifiers needed for body through natural way:
  - Fruits/Vegetables/Seeds/Herbs/Ayurvedic proven supplements/medicine
- Should be manual added/editable
- Search for above things and categorize accordingly for daily/weekly/monthly plans so it is easily taken care than doing separately
- **Food Menu sub-menu:**
  - Breakfast, Lunch, Snacks, Dinner
  - Search through all Indian - North, South Indian dishes listed for different times
  - Help plan for different weeks of the month for each day

### Module 5: Exploratory
- All information gathered is categorized, organized to explore at convenient time
- Will be done through Info Lake/Omni Lake app being built - need link to that

### Module 6: ToDo
- With followup / reminder - Daily/weekly/monthly/Yearly or specific dates
- Can be tied to an event if needed as option
- Also to goals if any aligning
- Voice enabled input
- Voice enabled at other places where needed/possible

### Module 7: Spiritual
- My spiritual journey to explore with goals, tips
- Mantras/Rituals/Vedas/Upanishads/Puranas
- My journey/journal of spirituality that I can add/explore

### Module 8: Documents Explorer
- Organize reading/Navigate to OneDrive, GDrive to have links to those places

### Module 9: Financial
- Networth, Expenses current month, Assets, Investment summary
- Subscription - upcoming/reminder
- EPFO Balance, Insurance lists - renewal dates
- **Financial Dashboard:**
  - Data to be retrieved from mymoney app
  - All Banks Balance, Fixed deposits

### General Requirements
- All sections should be Cards/Tile or beautifully aligned UI/UX component
- This should be my goto place for anything
- Platform independent, scalable, accessible over internet
- Security driven, web app and mobile app - Android/iOS
- Voice enabled input where needed/possible
- Follow all Development life cycle E-E
- Meeting with all stakeholders team to understand requirement/implementation/feasibility
- Design first, API first approach followed with Development
- Quality at every stage
- Provide Detailed AI Prompt that LLM/models should be able to take it up and implement and validate it E-E
- Built module over module/feature over feature working thoroughly before going to next
- Should be able to add other section as needed - customizable
- Can mention section and where does data come/what areas need to be represented in what way

### System Architecture Overview
```
📱 Frontend (Next.js PWA + React Native)
       │ (REST APIs / WebSocket Reminders)
⚙️ Backend Gateway (FastAPI / Node.js)
       ├── 🔐 Security Layer (JWT + Row-Level Encryption)
       ├── 📰 Scraping Workers (Celery + BeautifulSoup / RSS Feeds)
       └── 🗄️ Database Matrix (PostgreSQL for User Data + Redis for Caching)
```

### Design Specification
- Asymmetrical, high-density Bento Grid
- Luxury Dark Mode scheme:
  - Dominant: Deep Charcoal #0B0B0C
  - Accents: Emerald #10B981 (Health/Finance)
  - Deep Blue #3B82F6 (Productivity)
- Every module acts as a standalone micro-app tile

### System Character Prompt
> Senior Full-Stack Architect & UX Engineer — Build "Myworld" Ultimate Personal Portal & Dashboard Hub. Cross-platform (Next.js Web PWA + React Native iOS/Android), secure API design, modular UI engineering. Intuitive, visually stunning, luxury dark-themed personal dashboard based on responsive Bento Grid design.

### Core Architectural Requirements
1. Feature-driven development - each module completely functional before next
2. Next.js 14+ (App Router), Tailwind CSS, TypeScript, FastAPI (Python), PostgreSQL with Prisma/SQLAlchemy, Redis
3. End-to-end encryption for financial, health, and personal journaling data
4. JWT-based OAuth2 security
5. Fully adaptive cross-platform Web PWA and native mobile screens
6. Voice-to-Text via Web Audio API / Native Device microphones

### Module Specifications (from user)
- **Module 1:** Core Grid Matrix - 12-column responsive, frosted-glass, universal search, app shortcuts
- **Module 2:** News Engine - High-density text tile, category filters, background fetch, Redis cron, RSS feeds, top-15 JSON
- **Module 3:** Calendar - Bi-directional, color-coded, Google Calendar API, local inputs, push notifications
- **Module 4:** ToDo - Task matrix Day/Week/Month/Year, cross-linking to Calendar/Goals, floating mic button, transcription
- **Module 5:** Wellness - Tabbed sub-view, nutrition chart, recipe cards, North/South Indian meal matrix
- **Module 6:** Spiritual - Dual-pane, Mantras/Vedas/Upanishads/Puranas, encrypted journal
- **Module 7:** Financial - Balance trackers, mymoney endpoints, insurance/subscription timeline, goal metrics

### Phased Execution
1. Design & Schema First - DB schema or JSON contract
2. API Definition - Structured REST endpoints with TypeScript/Python types
3. Frontend Element - Tailwind CSS with mock data
4. End-to-End Wiring - Connect UI to live backend
5. Quality Validation - Automated integrity verification across screen orientations

---

## Stakeholder Questions & Answers

| # | Agent | Question | User answer |
|---|---|---|---|
| 1 | Design | Module priority and MVP scope? | MVP: Bento Grid + Search + ToDo + Calendar (full E2E, not prototype). Phase 2: Financial. Phase 3: News + Wellness. Phase 4: Spiritual. Phase 5: Documents + Info Lake. |
| 2 | Architect | Deployment target? | PaaS (Vercel + Railway/Render + Supabase/Neon). Zero budget — free tiers only. |
| 3 | Architect | Single user or multi-profile? | Multiple users/profiles with Gmail (Google OAuth2) login. Isolated data per user. |
| 4 | Design | Bento grid density? | Focused grid — fewer tiles per row, larger tap targets, more whitespace (luxury feel). |
| 5 | Design | News data sources and personalization? | Both category-based AND behavior-learning (clicks, dwell time). Both web app and mobile app. |
| 6 | Architect | Google Calendar sync direction? | Bidirectional (read + write back as option). Birthdays/anniversaries from both manual entry and contact import. |
| 7 | Design | Voice input scope? | ALL text-input areas (ToDo, Calendar, Journal, Search, Quick Capture). Free open-source (Whisper/Vosk). |
| 8 | Architect | mymoney app integration? | Existing app with API. Document needed endpoints in input_needed.md. |
| 9 | Review | DPDP Act compliance for MVP? | Skip for MVP. Add reminder to Todo.md and product-plan.md for Phase 2. |
| 10 | Review | Financial data legal concerns? | Safe — read-only display, no financial advice, no regulatory concern. |
| 11 | Code Review | Component library approach? | shadcn/ui + Radix base + custom luxury theme layer. Scrape open-source UI patterns from GitHub/design sites. |
| 12 | Implement | Monorepo structure? | Yes (Turborepo/Nx). Handles scaling. DB included: PostgreSQL + Redis. |
| 13 | Architect | PWA offline scope? | ToDo ✅, Calendar ✅, Spiritual Journal ✅, News ❌, Financial ✅ (cached), Documents ✅ (links), Wellness ✅ (cached). |
| 14 | Validate | Testing strategy? | Standard — unit tests + automated E2E (Playwright web, Detox mobile) + visual regression. |
| 15 | Review | Accessibility target? | WCAG 2.1 AA. Trust AI for UI guidelines. |

---

## Goals & Non-Goals

### Goals
- Single destination for ALL personal information and tools
- Luxury, elegant dark-themed UI that feels premium
- Full E2E working MVP (not a prototype)
- Cross-platform: Web PWA + iOS + Android with feature parity
- Zero budget for MVP using free tiers
- Multi-user support with Google OAuth
- Module-by-module development (each fully functional before next)
- Voice input everywhere using open-source tools
- Offline capability where possible
- Scalable architecture for future growth
- Customizable — add new sections as needed

### Non-Goals (for MVP)
- Financial advice or trading features (display only)
- Full DPDP compliance (deferred to Phase 2)
- Heavy ML/AI for news personalization (simple scoring, not deep learning)
- Real-time collaboration between users
- Desktop native apps (PWA covers desktop)

---

## Users / Audience

- **Primary user:** The builder/creator (personal use)
- **Secondary users:** Family members, friends (multi-profile support)
- **Access:** Gmail login, platform-independent
- **Devices:** Desktop browsers, mobile phones (Android/iOS), tablets

---

## Constraints

| Constraint | Detail |
|---|---|
| Budget | Zero — all free tiers (Vercel, Railway/Render, Supabase/Neon, Upstash) |
| Timeline | Module-by-module, each fully E2E working before next |
| Compliance | DPDP compliance deferred to Phase 2 |
| Data sources | mymoney API (existing), Google Calendar API, open-source news RSS, open-source voice recognition |
| Design | Luxury dark theme with WCAG 2.1 AA accessibility |
| Architecture | Monorepo with Turborepo/Nx |
| Platforms | Web PWA + Android + iOS (full feature parity) |

---

## Success Criteria

- MVP (Bento Grid + Search + ToDo + Calendar) is fully E2E working on web and mobile
- User can log in with Gmail and see personalized dashboard
- ToDo supports voice input and works offline
- Calendar syncs bidirectionally with Google Calendar
- All modules load within 3 seconds on 4G mobile
- Zero hosting costs for MVP
- Each subsequent phase builds on working MVP without breaking existing features
- News module aggregates 10-20 articles per category
- Wellness module provides complete weekly/monthly diet plans
- Financial module displays all data from mymoney API

---

## Decisions Captured (incl. rejected alternatives)

| Decision | Chosen | Rejected | Rationale |
|---|---|---|---|
| Deployment | PaaS (free tiers) | Self-hosted, Cloud (paid) | Zero budget constraint |
| Auth | Google OAuth2 | Custom auth, Social login (other providers) | Gmail login requested, simplest flow |
| User scope | Multi-profile | Single user | Future-proofing, family use |
| Component library | shadcn/ui + Radix + custom | Build from scratch, Material UI | Balance of speed + luxury customization |
| Voice | Open-source (Whisper/Vosk) | Cloud APIs (Google Speech) | Zero budget, privacy |
| DB | PostgreSQL + Redis | MongoDB, Firebase | Relational data fits well, free tiers available |
| Monorepo | Turborepo/Nx | Separate repos | Easier management, shared types |
| News personalization | Category + behavior learning | Category only, Full ML | Balanced approach, no heavy infrastructure |
| Testing | Unit + E2E + visual regression | Basic manual only, Full security scanning | Standard quality bar for MVP |
| Accessibility | WCAG 2.1 AA | A (too basic), AAA (too strict for dark theme) | Good balance of accessibility + design |
| Calendar sync | Bidirectional | Read-only | User needs to create events from Myworld |
| Offline scope | Most modules offline-capable | Online-only | Better mobile experience |

---

## Open Items

- [ ] mymoney API endpoints, parameters, URLs needed (see input_needed.md)
- [ ] DPDP Act compliance for Phase 2 (see todo.md)
- [ ] Specific RSS feeds for news categories to be finalized in design phase
- [ ] Google Calendar API project setup and OAuth scopes
- [ ] Open-source voice recognition library selection (Whisper vs Vosk)
- [ ] Design reference scraping from popular UI/UX sites
- [ ] Contact import API for birthdays/anniversaries (Google People API?)
- [ ] Google People API setup for contact import
- [ ] Design system tokens and theme configuration

---

## Tech Stack (Full Documentation)

### 💰 Budget: $0 (Free Tiers Only)

| Service | Provider | Free Tier Limits |
|---|---|---|
| Frontend Hosting | Vercel | 100GB bandwidth, unlimited deploys |
| Backend Hosting | Railway or Render | 500 hours/month, 512MB RAM |
| Database (Postgres) | Supabase or Neon | 500MB storage, 50K rows |
| Cache (Redis) | Upstash or Redis Cloud | 10K commands/day, 256MB |
| Auth | NextAuth.js / Google OAuth | Free |
| Voice Recognition | Whisper (self-hosted) or Vosk | Free, open-source |
| News RSS | RSS feeds | Free |
| E2E Testing | Playwright + Detox | Free, open-source |

### 🎨 Frontend Stack

**Web (Next.js PWA)**

| Technology | Version | Purpose |
|---|---|---|
| Next.js | 14+ (App Router) | React framework, SSR/SSG, API routes |
| React | 18+ | UI library |
| TypeScript | 5+ | Type safety |
| Tailwind CSS | 3+ | Utility-first styling |
| shadcn/ui | Latest | Accessible component primitives |
| Radix UI | Latest | Headless UI components |
| Zustand | Latest | Lightweight state management |
| React Hook Form | Latest | Form handling |
| Zod | Latest | Schema validation |
| next-pwa | Latest | PWA support for Next.js |
| Framer Motion | Latest | Animations & micro-interactions |
| Lucide React | Latest | Icon library |

**Mobile (React Native)**

| Technology | Version | Purpose |
|---|---|---|
| React Native | 0.73+ | Cross-platform mobile |
| Expo | 50+ | Development platform (optional) |
| React Navigation | 6+ | Navigation |
| React Native Paper | Latest | Material Design components (base) |
| AsyncStorage | Latest | Local storage |
| Expo Speech / Vosk | Latest | On-device voice recognition |

**UI/Design System**

| Technology | Purpose |
|---|---|
| Tailwind CSS | Utility-first styling |
| shadcn/ui | Accessible primitives |
| Radix UI | Headless components |
| Framer Motion | Animations & micro-interactions |
| Lucide React | Icon library |
| Custom Theme | Dark luxury (#0B0B0C, #10B981, #3B82F6) |

### ⚙️ Backend Stack

**API Server**

| Technology | Version | Purpose |
|---|---|---|
| FastAPI | 0.109+ | High-performance Python API framework |
| Python | 3.11+ | Runtime |
| Pydantic | 2+ | Data validation & serialization |
| SQLAlchemy | 2+ | ORM for PostgreSQL |
| Alembic | Latest | Database migrations |
| Uvicorn | Latest | ASGI server |

**Authentication & Security**

| Technology | Purpose |
|---|---|
| Google OAuth2 | Gmail login |
| JWT (python-jose) | Token-based auth |
| passlib + bcrypt | Password hashing (if needed) |
| cryptography | Row-level encryption for sensitive data |

**Background Jobs**

| Technology | Purpose |
|---|---|
| Celery | Task queue for scraping, notifications |
| Redis (Upstash) | Celery broker + result backend |
| BeautifulSoup / feedparser | RSS feed parsing |

**Voice Processing**

| Technology | Purpose |
|---|---|
| Whisper (OpenAI, self-hosted) | Speech-to-text (best accuracy) |
| Vosk | Lightweight offline alternative |
| faster-whisper | Optimized Whisper for speed |

### 🗄️ Database Stack

**PostgreSQL (Supabase / Neon)**

| Feature | Implementation |
|---|---|
| ORM | SQLAlchemy 2+ |
| Migrations | Alembic |
| Row-Level Security | User-scoped data isolation |
| Encryption | Field-level encryption for health/financial data |
| Free Tier | 500MB storage, 50K rows |

**Redis (Upstash / Redis Cloud)**

| Feature | Implementation |
|---|---|
| Caching | News, calendar events, session data |
| Job Queue | Celery broker |
| Rate Limiting | API rate limit counters |
| Free Tier | 10K commands/day, 256MB |

### 🔗 API Design

**API-First Approach**
- OpenAPI 3.0 spec defined before implementation
- RESTful endpoints with consistent naming
- JWT Bearer token authentication
- JSON request/response format
- WebSocket for real-time reminders

**Core API Endpoints (MVP)**

```
POST   /api/auth/google          # Google OAuth login
GET    /api/auth/me              # Current user profile
POST   /api/auth/logout          # Logout

GET    /api/dashboard            # Dashboard tiles data
GET    /api/search               # Universal search

GET    /api/todos                # List todos
POST   /api/todos                # Create todo
PUT    /api/todos/:id            # Update todo
DELETE /api/todos/:id            # Delete todo
POST   /api/todos/voice          # Voice-to-text todo

GET    /api/calendar/events      # List events
POST   /api/calendar/events      # Create event
PUT    /api/calendar/events/:id  # Update event
DELETE /api/calendar/events/:id  # Delete event
POST   /api/calendar/sync/google # Sync with Google Calendar

GET    /api/reminders            # List reminders
POST   /api/reminders            # Create reminder
```

**Future API Endpoints (Phase 2+)**

```
GET    /api/news                  # Aggregated news
GET    /api/news/:category        # Category-specific news

GET    /api/health/diet           # Diet plans
POST   /api/health/diet           # Create/update diet
GET    /api/health/meals          # Food menu

GET    /api/financial/summary     # Financial summary from mymoney
GET    /api/financial/banks       # Bank balances
GET    /api/financial/fds         # Fixed deposits
GET    /api/financial/epfo        # EPFO balance
GET    /api/financial/insurance   # Insurance lists
GET    /api/financial/subscriptions # Subscriptions

GET    /api/spiritual/journal     # Spiritual journal entries
POST   /api/spiritual/journal     # Create journal entry
GET    /api/spiritual/library     # Mantras/Vedas/Upanishads

GET    /api/documents             # Document links
POST   /api/documents             # Add document link
```

### 🧩 Monorepo Structure

```
products/myworld/
├── apps/
│   ├── web/                    # Next.js PWA (Vercel)
│   ├── mobile/                 # React Native (Expo)
│   └── api/                    # FastAPI backend
├── packages/
│   ├── ui/                     # Shared UI components
│   ├── types/                  # Shared TypeScript types
│   ├── config/                 # Shared configs (ESLint, TS)
│   └── utils/                  # Shared utilities
├── pipeline.json               # Pipeline state
├── project-config.json         # Project decisions
├── package.json                # Root package.json
├── docs/                       # Requirements, architecture, docs
├── checkpoints/                # Recovery checkpoints
├── dlq/                        # Dead letter queue
├── selective_runs/             # Selective agent runs
├── reports/                    # Test results, code reviews
├── architecture/               # Architecture diagrams
├── turbo.json                  # Turborepo config
└── docker-compose.yml          # Local dev (Postgres, Redis)

### 🚀 Deployment Architecture

```
┌─────────────────────────────────────────┐
│              CDN (Vercel)                │
│         Next.js PWA (Static)            │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│         Backend (Railway/Render)         │
│           FastAPI + Celery              │
│    ┌──────────┐  ┌──────────────────┐  │
│    │ Auth     │  │ News Workers     │  │
│    │ (JWT)    │  │ (Background)     │  │
│    └──────────┘  └──────────────────┘  │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│       Database (Supabase/Neon)           │
│  ┌────────────┐  ┌──────────────────┐  │
│  │ PostgreSQL │  │ Redis (Upstash)  │  │
│  └────────────┘  └──────────────────┘  │
└─────────────────────────────────────────┘
```

### 🔧 Development Tools

| Tool | Purpose |
|---|---|
| Turborepo | Monorepo build orchestration |
| ESLint | Code linting (JS/TS) |
| Ruff | Code linting (Python) |
| Prettier | Code formatting |
| Husky | Git hooks |
| lint-staged | Pre-commit checks |
| Playwright | Web E2E testing |
| Detox | Mobile E2E testing |
| Vitest | Unit testing (web) |
| Pytest | Unit testing (backend) |
| Alembic | Database migrations |
| Docker Compose | Local development environment |

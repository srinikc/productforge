# Review — MyWorld MVP

**APPROVED**

> **Reviewer:** Architecture Review Agent (independent)
> **Date:** 2026-08-23 (Re-review)
> **Inputs reviewed:** `docs/requirements.md`, `docs/design.md`, `docs/architecture.md`
> **Scope:** Verification that all findings from the initial review (H-1, H-2, M-1 through M-5) have been resolved. Traceability (FR/NFR → Design → Architecture), SOLID / DRY / YAGNI compliance, anti-pattern scan, NFR coverage, and trade-off acknowledgement.

---

## 1. Summary

The three documents now form a **coherent, complete, and internally consistent** MVP plan for a zero-budget personal dashboard. All seven findings from the initial review (2 High, 5 Medium) have been **fully resolved** with well-reasoned additions to the requirements, design, and architecture documents.

The architecture makes sound choices (modular monolith, PostgreSQL RLS, Vosk on-device, Turborepo) that are justified against the constraints. The design is detailed and internally consistent, with strong accessibility and motion specifications. The requirements document is thorough, with a traceability matrix, acceptance criteria, and user stories.

The verdict is **APPROVED** — the document set is ready for implementation.

---

## 2. Verification of Previous Findings

> All seven findings from the initial review have been verified against the updated documents.

### High

#### H-1: Google People API integration — ✅ RESOLVED

- **Resolution:** ADR-010 added to architecture.md (lines 262-277). The Google People API is now a first-class integration.
- **Evidence across documents:**
  - `requirements.md` FR-5 (line 39): Added explicit Google People API scope (`contacts.readonly`) with incremental consent.
  - `architecture.md` ADR-010: Full ADR documenting the decision, consequences, and traceability.
  - `architecture.md` §4.2 (line 345): `contacts/` sub-package added under `calendar/` module.
  - `architecture.md` §4.3 (lines 380-381): Two new endpoints — `POST /api/v1/calendar/contacts/import` and `GET /api/v1/calendar/contacts/import/status`.
  - `architecture.md` §4.4 `users` table (lines 402-403): `contacts_scope_granted` and `contacts_synced_at` columns added.
  - `architecture.md` §4.4 `events` table (line 440): `google_contact_id` column added for dedup.
  - `architecture.md` §4.5 (line 471): Google People API listed as integration point (HTTPS REST, inbound, read-only).
  - `architecture.md` §6 Risks: R-9 added for incremental consent friction.
  - `architecture.md` §6 Open Items: OI-11 (contact import UX) and OI-12 (consent timing) documented.
- **Verdict:** Complete. The fix is thorough, well-documented, and traceable to FR-5 and US-5.

#### H-2: Apple Developer cost vs zero-budget contradiction — ✅ RESOLVED

- **Resolution:** ADR-011 added to architecture.md (lines 279-297). iOS App Store submission deferred to Phase 2. MVP uses Expo Go, Android APK sideload, and Web PWA.
- **Evidence across documents:**
  - `requirements.md` NFR-5 (line 75): Updated to "Web PWA (Next.js) + Android (React Native) for MVP; iOS in Phase 2."
  - `requirements.md` SC-1 (line 228): Updated to "fully E2E working on web PWA and Android" (iOS removed).
  - `requirements.md` Change Log (lines 258-260): Documents all changes.
  - `architecture.md` ADR-011: Full ADR documenting the distribution strategy, consequences, and traceability.
  - `architecture.md` OI-6 (line 545): Updated to "Decided: deferred to Phase 2."
  - `architecture.md` Risk R-6 (line 531): Updated to reference ADR-011 and document iOS PWA limitations.
- **Verdict:** Complete. The contradiction is resolved by deferring iOS distribution, which aligns with the zero-budget constraint.

---

### Medium

#### M-1: 12-column grid not reflected in design — ✅ RESOLVED

- **Resolution:** Design §9.5 added (lines 286-297): "Grid system" section explicitly documents 12/8/4 column scaffold.
- **Evidence:**
  - `design.md` §9.5 (line 290): "Grid update: 12-column layout on desktop (1280px+), 8-column on tablet (1024-1279px), 4-column on phone (0-639px)."
  - `design.md` §9.5 (line 296): Explains why 12/8/4 and not 12/6/4 (clean half-row spans on tablet).
- **Verdict:** Complete. The 12-column base grid is now explicit, and the mapping to tile columns is documented.

#### M-2: "Row-level encryption" vs "Row-Level Security" semantic gap — ✅ RESOLVED

- **Resolution:** Architecture Addendum added (lines 555-559): clarifies RLS for data isolation + field-level encryption for sensitive columns.
- **Evidence:**
  - `architecture.md` Addendum (line 557): "Row-Level Security (RLS) for data isolation + field-level encryption for sensitive columns (health, financial data)."
  - The addendum explains that RLS enforces per-user row isolation, and field-level encryption is added as defense-in-depth for sensitive columns (health, financial data introduced by future modules).
- **Verdict:** Complete. The semantic gap is closed: RLS handles access control, field-level encryption handles data-at-rest protection for sensitive columns.

#### M-3: Festival display not explicitly addressed — ✅ RESOLVED

- **Resolution:** Design §20 added (lines 553-566): "Festival Data Source" section.
- **Evidence:**
  - `design.md` §20 (line 557): Indian public holidays sourced from Google Calendar API (Indian Holidays calendar).
  - `design.md` §20 (line 560): Regional/local festivals are user-entered.
  - `design.md` §20 (line 561): Rendering uses neutral `text-secondary` color (per §10.2).
  - `design.md` §20 (lines 563-566): Edge cases documented (offline, duplicates, sync).
- **Verdict:** Complete. Festival display is now fully specified with data source, UX, and edge cases.

#### M-4: API versioning inconsistency — ✅ RESOLVED

- **Resolution:** ADR-012 added to architecture.md (lines 299-312): explicit `/api/v1/` prefix on all endpoints.
- **Evidence:**
  - `architecture.md` ADR-012: Full ADR documenting the versioning decision.
  - `architecture.md` §4.3 (line 390): "All endpoints use `/api/v1/` prefix for consistency."
  - `architecture.md` §4.3 table (lines 363-388): All endpoints now use `/api/v1/` prefix.
  - `architecture.md` ADR-012 (line 311): Acknowledges requirements use `/api/` without `v1`, explains that requirements specify resources, architecture specifies URL versioning.
- **Verdict:** Complete. The architecture is internally consistent. The requirements/architecture boundary is explicitly documented.

#### M-5: Recurrence model inconsistency — ✅ RESOLVED

- **Resolution:** ADR-013 added to architecture.md (lines 561-579): "Asymmetric Recurrence Model."
- **Evidence:**
  - `architecture.md` ADR-013: Full ADR documenting the intentional asymmetry.
  - Todos use simple enum (`daily/weekly/monthly/yearly/none`) — task-oriented, no complex patterns needed.
  - Events use iCal RRULE JSONB — calendar-oriented, must interoperate with Google Calendar.
  - The ADR explicitly justifies the asymmetry: different user mental models, different integration requirements.
  - Migration path documented: `todos.recurrence` can be migrated to JSONB in Phase 2 if needed.
- **Verdict:** Complete. The asymmetry is now a deliberate, well-justified architectural decision with clear rationale and migration path.

---

## 3. Traceability Checklist (Updated)

> Every requirement must trace to at least one design section and one architecture section. "✅" = fully traced. "⚠️" = gap or inconsistency. "❌" = not addressed.

| Req | Design Coverage | Architecture Coverage | Status |
|---|---|---|---|
| **FR-1** Auth | §8.4, §12.1 | ADR-002, §4.3 auth endpoints, §4.4 `users` | ✅ |
| **FR-2** Bento Grid | §7.2, §8.3, §9, §9.5 | §4.3 `/api/dashboard`, NFR-1 mapping | ✅ |
| **FR-3** Universal Search | §10.3, §7.2 CommandPalette | ADR-009, §4.3 search endpoint, `search` module | ✅ |
| **FR-4** ToDo Engine | §10.1, §12.2, §12.5 | §4.3 todos endpoints, §4.4 `todos` table, ADR-006, ADR-013 | ✅ |
| **FR-5** Calendar / Events | §10.2, §12.3, §20 | §4.3 calendar endpoints, §4.4 `events` table, §4.5 Google Calendar + People API, ADR-010 | ✅ |
| **FR-6** Reminders / Notifications | §10.4, §14 | §4.3 reminders endpoints + WS, §4.5 Web Push + Expo Push | ✅ |
| **NFR-1** Performance | §5 Motion, §12 flows | §5 NFR mapping, Redis cache, RSC streaming | ✅ |
| **NFR-2** Security | §2.5 Contrast | ADR-002 RLS, §5 NFR mapping, Addendum (field-level encryption) | ✅ |
| **NFR-3** Accessibility | §16, §2.5, §9.4 | §5 NFR mapping (axe-core) | ✅ |
| **NFR-4** Offline | §12.5, §10.1/10.2 | ADR-004, §5 NFR mapping (SW + IndexedDB) | ✅ |
| **NFR-5** Cross-Platform | §9.1, §8.2 | ADR-004, ADR-005, ADR-011, §5 NFR mapping | ✅ |
| **SC-1** E2E on all platforms | — | ADR-005, ADR-011 | ✅ |
| **SC-6** Zero hosting costs | — | §4.6 Deployment Shape, ADR-011 | ✅ |

**Orphan requirements:** None — every FR and NFR has full coverage.
**Invented stack:** None — every technology in the architecture traces back to a requirement or constraint. No unjustified additions detected.

---

## 4. Trade-offs Acknowledged

The architecture document excels at documenting trade-offs. The following key decisions are explicitly justified with pros/cons:

| Trade-off | Decision | Acknowledged? |
|---|---|---|
| Modular monolith vs microservices | Monolith (zero budget, team of one) | ✅ ADR-001 |
| PostgreSQL FTS vs Elasticsearch | FTS (zero budget, personal scale) | ✅ ADR-009 |
| Vosk on-device vs Whisper server | Vosk MVP, Whisper Phase 2 | ✅ ADR-006 |
| Expo managed vs bare workflow | Managed for MVP | ✅ ADR-005 |
| Next.js PWA vs native desktop | PWA (covers desktop) | ✅ ADR-004 |
| FastAPI vs Node.js/Go | FastAPI (async, Google SDK maturity) | ✅ ADR-003 |
| Redis single instance vs specialized stores | Single instance (simplicity) | ✅ ADR-008 |
| Dark-only theme vs system preference | Dark-only (luxury design direction) | ✅ Design E-13 |
| iOS App Store vs Expo Go / APK sideload | Defer to Phase 2 (zero budget) | ✅ ADR-011 |
| Google People API incremental consent vs bundled scope | Lazy consent (reduce friction) | ✅ ADR-010 |
| Asymmetric recurrence (enum vs RRULE) | Intentional split (different mental models) | ✅ ADR-013 |
| API versioning (`/api/v1/` explicit) | Explicit versioning (forward-compatible) | ✅ ADR-012 |

No significant trade-offs were silently made. The architecture correctly identifies risks (R-1 through R-9) and open items (OI-1 through OI-12) with mitigations.

---

## 5. Remaining Observations (Low severity, non-blocking)

The following items from the initial review remain as low-severity observations. They do not block implementation and can be addressed during development.

#### L-1: Dark theme not explicitly stated in requirements

- **Status:** Not addressed. Low priority.
- **Note:** Design §1 and E-13 clearly document dark-only. The architecture does not conflict. Implementers will follow the design.

#### L-2: Rate limiting strategy not detailed

- **Status:** Not addressed. Low priority.
- **Note:** Architecture §2.5 mentions Redis for rate limiting. ADR-010 mentions rate limiting for contact import (1 req/min per user). Specific rate limits for other endpoints can be defined during implementation.

#### L-3: Calendar sync interval (15 min) buried in open items

- **Status:** Not addressed. Low priority.
- **Note:** OI-8 documents the 15-minute default. Implementers will see this in the open items table.

---

## 6. Conclusion

All seven findings from the initial review (H-1, H-2, M-1 through M-5) have been **fully resolved** with well-reasoned additions to the requirements, design, and architecture documents. The document set is now **coherent, complete, and internally consistent**.

The core architectural decisions (modular monolith, PostgreSQL + RLS, Vosk on-device, Turborepo) remain correct for the constraints. The design system is detailed and production-ready. The requirements document is thorough, with full traceability.

The verdict is **APPROVED** — the document set is ready for implementation.

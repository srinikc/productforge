# Functional Spec — BI-EVENTS-1539 — Structured outbox metrics and alerting for event authority

- **Version:** 1
- **Status:** approved
- **Owner:** Srinikc
- **Source:** BI-EVENTS-1539
- **Functional SHA:** 542eaf3a5173
- **Linked design:** 

## 1. Outcome
Outbox metrics and alerts expose backlog health.

## 2. Actors
- operator
- on-call

## 3. Scope
- metrics
- alerts

## 4. Non-goals
- transport implementation

## 5. Assumptions and dependencies
- Prometheus-compatible metrics owner exists
- event outbox

## 6. Domain and glossary
eventing

## 7. Functional requirements
### FR-1 — Expose an outbox_rows_current gauge by tenant/status and an EVENT_OUTBOX_BOUND_E
- **priority:** P0
- **source:** BI-EVENTS-1539
- **preconditions:** Event authority is deployed.
- **trigger:** Metrics are scraped or alert evaluated.
- **inputs:** outbox rows; projection result
- **outputs:** metric/alert
- **errors:** missing signal blocks release
- **auth:** metrics read only
- **idempotency:** scrape idempotent
- **data_rules:** tenant/status labels
- **edge_cases:** no rows
- **acceptance:** Given event authority, when metrics are scraped, then outbox rows and bound rejections are visible.
- **verification:** metrics test

### FR-2 — Emit structured outbox prune and projection-failure signals through the existing
- **priority:** P0
- **source:** BI-EVENTS-1539
- **preconditions:** Event authority is deployed.
- **trigger:** Metrics are scraped or alert evaluated.
- **inputs:** outbox rows; projection result
- **outputs:** metric/alert
- **errors:** missing signal blocks release
- **auth:** metrics read only
- **idempotency:** scrape idempotent
- **data_rules:** tenant/status labels
- **edge_cases:** no rows
- **acceptance:** Given event authority, when metrics are scraped, then outbox rows and bound rejections are visible.
- **verification:** metrics test


## 8. Operation matrix
| Mode | Operation | Scope | Actor | Expected result | Error |
|---|---|---|---|---|---|
|  | scrape |  |  |  |  |

## 9. Configuration contract
| Name | Default | Precedence | Valid values | Empty behavior | Invalid behavior | Startup validation |
|---|---|---|---|---|---|---|
| - | - | - | - | - | - |

## 10. Non-functional requirements
- low cardinality

## 11. Data lifecycle
metrics retained per platform

## 12. Compatibility
no breaking change

## 13. Rollback behavior
remove metrics

## 14. Observability
outbox_rows_current and bound counter

## 15. Traceability
| FR | Design | Test | Evidence |
|---|---|---|---|
| FR-1 | docs/IMPLEMENTATION-CONTROLS-DESIGN.md | tests/test_review_material_change.py | tests/test_review_material_change.py |
| FR-2 | docs/IMPLEMENTATION-CONTROLS-DESIGN.md | tests/test_review_material_change.py | tests/test_review_material_change.py |

## 16. Open questions
- No open questions: implementation follows the existing metrics owner.

## 17. Definition of Done
- Delivery Complete requires all five states

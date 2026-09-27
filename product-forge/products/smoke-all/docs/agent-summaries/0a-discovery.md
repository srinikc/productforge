# 0a discovery — brief summary

> status: completed · generated 2026-09-26T23:43:50

# DISCOVERY Output - Stage 0a
## Token Usage
  - **Input Tokens:** 5339
## Output
# Discovery Document — `add`
## 1. Clarified Goal
  - In: one command, two integer operands, integer addition, stdout output, exit status, no dependencies.
## 2. Domain Analysis
  - Exactly two operands. Zero, one, or three-plus operands is an input error.
## 3. Stakeholder Map
## 4. User Personas
### P1 — Shell user (primary)
  - **Context:** Working in a terminal, mid-task, needs the sum of two integers without opening a calculator app or a Python REPL. `[ASSUMPTION]`
### P2 — Scripter / test author (secondary)
  - **Context:** Calls `add` from another script or a test and consumes the result programmatically. `[ASSUMPTION]`
### P3 — Maintainer / reviewer (internal)
  - **Context:** Reads, tests, or modifies the single module. `[ASSUMPTION]`
### Anti-personas (explicitly not served)
  - Calculator/notebook user wanting floats, expressions, history, or a visual UI.
## 5. End-to-End User Journey
### Happy path — `add 2 3`
  - Mixed signs: `add -4 1` → `-3`.
### Failure path — invalid input
## 6. Assumptions
  - `[ASSUMPTION]` "Integers" includes negative values.
## 7. Open Items / Focused Clarifying Questions
## 8. Out of Scope (no approval implied)

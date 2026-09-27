# 1 design — brief summary

> status: completed · generated 2026-09-27T09:41:04

# DESIGN Output - Stage 1
## Token Usage
  - **Input Tokens:** 143744
## Output
## F-1: `add` command entry point
### Requirements
### Behaviour
### Business rules
### Validation
### Edge cases
### Error handling
### Acceptance criteria
### API behaviour
### Data model (informational)
### Test obligations
### Open questions
## F-2: Two positional integer operands
### Requirements
#### Functional Requirements (FR)
#### Non-Functional Requirements (NFR)
#### User Stories (US)
### Behaviour
### Business rules
### Validation
### Edge cases
### Error handling
### Acceptance criteria
### API behaviour
### Priority
## F-3: Integer addition
### Requirements
#### Functional Requirements (FR)
#### Non-Functional Requirements (NFR)
#### User Stories (US)
### Behaviour
### Business rules
  - **BR-1 — Sum definition.** The result is the unique integer `s` such that `s - int1 = int2` under exact arithmetic. There is no modular, bounded, saturating, or floating variant.
### Validation
  - **V-1 (precondition).** Both operands MUST already be valid per the F-2 grammar; F-3 MUST reject-by-not-running if either is not. Addition on unvalidated text is forbidden (`FR-60`).
### Edge cases
  - **EC-1 — Both zero.** `add 0 0` → `0`.
### Error handling
  - **EH-1 — Invalid operand.** F-3 MUST NOT run. The F-1 path applies: one-line diagnostic on stderr naming the offending argument, stdout empty, exit status `2`.
### Acceptance criteria
### API behaviour
  - **API-1 — CLI contract surface.** `add <int1> <int2>`
### Data model
  - **DM-1 — Value model.** An operand and the result are members of the mathematical integers ℤ with unbounded magnitude. The only representations crossing the boundary are (a) argv strings conforming to the F-2 grammar (referred to as plain text, not re-defined here) and (b) the canonical decimal string of `FR-57` on stdout. No other representation is observable.
### Priority
  - **must-have:** `FR-51`–`FR-61`, `FR-63`; `NFR-33`, `NFR-34`, `NFR-36`, `NFR-37`, `NFR-38`, `NFR-39`, `NFR-40`, `NFR-41`, `NFR-44`, `NFR-45`; `US-31`–`US-36`.
### Open Questions
  - **OQ-1 — Digit-length limit.** CPython ≥ 3.11 caps int↔str conversion via `sys.set_int_max_str_digits` (default 4300 digits), which affects both operand parsing (`EC-14`) and result rendering. Should the tool (a) accept the interpreter default and report a clean exit-`2` error beyond it, (b) raise the limit at start-up to support arbitrary lengths at extra CPU cost, or (c) document a deliberate maximum input length? This determines whether `NFR-32`'s 10,000-digit target is achievable as written. Decision belongs to the USER/Architect; F-3 specifies only that the failure mode MUST be clean (`EH-3`).
## F-4: Print result to stdout
### Requirements
#### Functional Requirements (FR)
#### Non-Functional Requirements (NFR)
#### User Stories (US)
### Behaviour (what it must do)
  - sign handling per `BR-2`,
### Business rules
### Validation
### Edge cases
### Error handling
### Acceptance criteria
### API behaviour
### Priority
### Open questions
## F-5: Exit-status contract
### Requirements
#### Functional Requirements (FR)
#### Non-Functional Requirements (NFR)
#### User Stories (US)
### Behaviour
### Business Rules
  - **BR-1 (Normative status table).** The following mapping is total over all possible inputs and is the single source of truth for exit status:
### Validation
  - **V-1** — Before returning any status, the program MUST assert that the chosen value is an element of `{0, 1, 2}`.
### Edge Cases
### Error Handling
### Acceptance Criteria
### API Behaviour
### Priority
  - **must-have:** `FR-101`–`FR-111`, `FR-113`–`FR-122`; all of `NFR-61`, `NFR-63`–`NFR-69`, `NFR-71`, `NFR-74`, `NFR-75`; `US-61`–`US-65`, `US-67`–`US-75`.
## F-6: Input validation and error message
### Requirements
#### Functional Requirements (FR)
#### Non-Functional Requirements (NFR)
#### User Stories (US)
### Behaviour
  - **Fail-fast, first-error-only (FR-126, FR-133):** exactly one failure is ever reported, even when several inputs are wrong.
### Business rules
### Validation
### Edge cases
### Error handling
### Acceptance criteria
### API behaviour
### Test vectors
### Priority
### Open Questions
## F-7: Standard library only
### Requirements
#### Functional Requirements (FR)
#### Non-Functional Requirements (NFR)
#### User Stories (US)
### Behaviour
  - **B-1.** `add` is delivered as one or more Python source files. Running it requires only the `python3` executable already present on the target machine.
### Business rules
### Validation
### Edge cases
### Error handling
### Acceptance criteria
### API behaviour
### Open Questions
## F-8: Correct handling of negative results
### Requirements
#### Functional Requirements (FR)
#### Non-Functional Requirements (NFR)
#### User Stories (US)
### Behaviour
### Business rules
### Validation
### Edge cases
### Error handling
### Acceptance criteria
### API behaviour
### Test cases
### Priority
### Open questions
## F-9: Arbitrary-precision output
### Requirements
#### Functional Requirements (FR)
#### Non-Functional Requirements (NFR)
### Behaviour
  - F-9 consumes the exact sum `S` produced by F-3 and the canonical rendering rules owned by F-4 (base 10, no leading zeros, single trailing `\n`) and F-8 (leading `-` for `S < 0`). It adds no new arithmetic and no new sign rules.
### Business rules
  - **BR-1:** The output value is exactly `S = int1 + int2` as defined by F-3; F-9 changes neither the value nor the arithmetic.
### Validation
  - **V-1:** Emitted stdout MUST match the regular expression `^-?[0-9]+\n$`, with the leading `-` present only when `S < 0`.
### Edge cases
  - **EC-1:** `S == 0` → `0\n` (never `-0\n`, never `+0\n`).
### Error handling
  - **EH-1:** If the interpreter reports its integer-string conversion limit for an otherwise-valid sum, the program MUST NOT surface a partial result and MUST NOT claim success with a truncated line. It either completes the correct rendering or fails through the F-5/F-6 failure channel — never a truncated token under exit status `0`.
### Acceptance criteria
  - **AC-1 (FR-201):** `add 9223372036854775807 1` → stdout `9223372036854775808\n`, exit `0` (correctly exceeds the signed 64-bit maximum).
### API behaviour
  - **API-1:** Program `add` (F-1). On success, stdout carries exactly one decimal token per F-4/F-9; stderr is empty; exit status is `0` (status value owned by F-5).
### Data model (DM)
  - **DM-1:** Value type = mathematical integer (unbounded ℤ), represented in use by the interpreter's arbitrary-precision integer type.
### Tests (T)
  - **T-1:** 64-bit boundaries: `9223372036854775807 + 1`; `-9223372036854775808 + -1`.
### Open questions (OQ)
  - **OQ-1:** Is there an intended *practical* upper bound for results (e.g., guaranteeing 1,000,000-digit output within a stated time), or should the tool be documented as memory-bound only? — Needs USER confirmation; not a reason to reduce scope.
### Priority
## F-10: Usage/help output
### Requirements
#### Functional Requirements (FR)
#### Non-Functional Requirements (NFR)
#### User Stories (US)
### Behaviour
### Business rules
### Validation
### Edge cases
### Error handling
### Acceptance criteria
### API behaviour
### Priority
## F-11: Unit tests for the add function and CLI
### Requirements
#### Functional Requirements (FR)
#### Non-Functional Requirements (NFR)
#### User Stories (US)
### Behaviour
  - The suite MUST verify both layers: the internal `add` function (direct arithmetic) and the CLI process (parsing, validation, rendering, exit status, and stream routing).
### Business Rules
  - BR-1: The suite MUST treat the contracts in F-1 through F-10 as normative. If a test contradicts a stated contract, the test is defective and MUST be corrected, not the contract.
### Validation
  - The suite is validated by running `python -m unittest` from the project root; a zero exit status and an `OK` summary indicate success.
### Edge Cases
  - EC-1: Arity edge cases: 0 operands, 1 operand, 3 operands, and many operands; each MUST produce exit status 2, empty stdout, and non-empty stderr.
### Error Handling
  - Subprocess tests MUST use `subprocess.run(..., timeout=10)`; on `TimeoutExpired`, the test MUST fail with the command and captured output in the message.
### Acceptance Criteria
  - AC-1: Running `python -m unittest` from the project root on a stock CPython 3.8+ interpreter with no third-party packages executes the full suite and exits 0.
### API Behaviour
  - API-1: The internal `add` function MUST be importable without side effects (no stdout/stderr output at import time) and MUST be pure: `add(int1, int2) -> int`.
### Priority
  - Feature priority: **must-have** — the product plan explicitly includes unit tests for the `add` function and CLI, and the tests are the primary automated verification of all contracts in F-1 through F-10.
## Functional Requirements
### F-1: `add` command entry point — FR-1 … FR-8
### F-2: Two positional integer operands — FR-26 … FR-36
### F-3: Integer addition — FR-51 … FR-60
### F-4: Print result to stdout — FR-76 … FR-84
### F-5: Exit-status contract — FR-101 … FR-108
### F-6: Input validation and error message — FR-126 … FR-133
### F-7: Standard library only — FR-151 … FR-157
### F-8: Correct handling of negative results — FR-176 … FR-182
### F-9: Arbitrary-precision output — FR-201 … FR-206
### F-10: Usage/help output — FR-226 … FR-233
### F-11: Unit tests for the add function and CLI — FR-251 … FR-260
## Non-Functional Requirements
### Performance (NFR-1 … NFR-3)
### Scalability & Availability (NFR-4 … NFR-7)
### Security (NFR-8 … NFR-11)
### Data & Residency (NFR-12 … NFR-13)
### Deployment & Environment (NFR-14 … NFR-15)
## User Stories
### F-1: `add` command entry point
  - **AC-1**: The entry point is invocable by that name from a POSIX-style shell.
### F-2: Two positional integer operands
  - **AC-1**: The first argument after the program name is treated as `int1` and the second as `int2`.
### F-3: Integer addition
  - **AC-1**: The emitted value equals `int1 + int2` for every pair of accepted operands.
### F-4: Print result to stdout
  - **AC-1**: The rendering uses ASCII digits `0`–`9` only, with no radix prefix.
### F-5: Exit-status contract
  - **AC-1**: Exit status is `0` iff exactly two operands were supplied, both passed the grammar, and a complete result line was written to stdout.
### F-6: Input validation and error message
  - **AC-1**: The first failing stage aborts the pipeline and later stages do not run.
### F-7: Standard library only
  - **AC-1**: Only Python 3 standard-library modules (or built-ins) are used; no `pip install`, virtual-environment, or vendored third-party file is required.
### F-8: Correct handling of negative results
  - **AC-1**: `add 2 -5` emits `-3\n`.
### F-9: Arbitrary-precision output
  - **AC-1**: The emitted digit count equals the exact digit count of the sum, with no fixed-width cap.
### F-10: Usage/help output
  - **AC-1**: An incorrect invocation causes the usage line to be emitted on stderr.
### F-11: Unit tests for the add function and CLI
  - **AC-1**: The suite is runnable with `python -m unittest` or `python -m unittest discover` on a stock CPython 3.8+ interpreter.
## API Contracts
### Cross-feature process-level surface (referenced by all features)
### F-1: `add` command entry point
### F-2: Two positional integer operands
### F-3: Integer addition
### F-4: Print result to stdout
### F-5: Exit-status contract
### F-6: Input validation and error message
### F-7: Standard library only
### F-8: Correct handling of negative results
### F-9: Arbitrary-precision output
### F-10: Usage/help output
### F-11: Unit tests for the add function and CLI
## 1. Design Direction
## Components
### Component-model overview
### Component inventory
### Composed components
### Feature components (one per product-plan feature)
### Data model
### Test components
### Component interaction
### Open Questions
## Data Models
### Conventions
### DM-1: `Invocation` — the per-process aggregate
  - `len(raw_args) == len(operand_tokens)` — no token is added, dropped, reordered, or rewritten.
### DM-2: `DecimalIntegerGrammar` — the operand language (constant)
  - Deterministic: the accept/reject decision for a given token is identical on every run, machine, and locale.
### DM-3: `ParsedOperand` — one validated token
  - `accepted == (rejected_by == None)` and `not accepted == (value == None)`.
### DM-4: `Sum` — the arithmetic result
  - `value == operands[1].value + operands[2].value`.
### DM-5: `OutputEnvelope` — the stdout record
  - Present iff `Invocation.outcome == SUCCESS`; absent on **every** failure path — this is the zero-stdout-bytes guarantee of `FR-127`.
### DM-6: `DiagnosticMessage` — the stderr record (F-6)
  - At most one `GRAMMAR_ERROR` per run (the pipeline aborts at the first failing stage — `FR-126`); exactly one `ARITY_ERROR` if arity fails.
### DM-7: `ExitStatus` — terminal status (constant enum)
  - Exactly one status per process; set once, at termination, and never revised.
### DM-8: `UsageText` — the usage literal (constant)
  - Byte-identical across runs, hosts, interpreters, time zones, and locales.
### DM-9: `TestCase` — one verification fixture (F-11)
  - Expected values are **literals**, never recomputed via the code under test — a test must not be able to pass by reproducing the bug.
### DM-10: `TestResult` — one executed fixture outcome (F-11)
  - Comparison is **byte-exact** on stdout and exit status; stderr is byte-exact for `ARITY`/`GRAMMAR` fixtures.
### DM-11: `TestSuite` — the aggregate run (F-11)
  - Deterministic and repeatable: two consecutive runs on the same interpreter produce identical `results` statuses.
### Relationships
### Lifetime and mutability
### Traceability
### Cross-cutting data invariants
  - **No floating point anywhere.** No model in this section may be represented with binary or decimal floating-point types at any point in its lifetime (`FR-53`).
### Open questions

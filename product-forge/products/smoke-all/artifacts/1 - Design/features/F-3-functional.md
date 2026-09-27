## F-3: Integer addition
**Feature ID:** F-3
**Depends on:** F-1 (`add` command entry point), F-2 (two positional integer operands) — F-3 consumes operands that have already been accepted by the F-2 grammar; F-3 does not re-define argument handling, arity rules, or the digit grammar.

### Requirements

#### Functional Requirements (FR)

| id | Requirement | Priority |
|---|---|---|
| FR-51 | The program MUST compute `int1 + int2` as the exact mathematical sum for every pair of operands accepted under the F-2 operand grammar. | must-have |
| FR-52 | The computation MUST use arbitrary-precision integer arithmetic; the result MUST NOT overflow, truncate, round, saturate, or wrap at any magnitude or sign. | must-have |
| FR-53 | The parse → add → render path MUST NOT use binary floating-point or decimal floating-point values at any point. | must-have |
| FR-54 | Sign rules: same-sign operands MUST produce a result with that sign and magnitude equal to the sum of the magnitudes; opposite-sign operands MUST produce a result whose magnitude is the difference of the magnitudes and whose sign is the sign of the larger-magnitude operand; if the magnitudes are equal the result MUST be `0`. | must-have |
| FR-55 | `0` MUST be the additive identity: for every accepted `x`, `x + 0 = 0 + x = x` (including `+0` and `-0` as operand spellings). | must-have |
| FR-56 | Negative zero MUST NOT be emitted: whenever the computed sum is zero, the rendered result MUST be exactly `0`. | must-have |
| FR-57 | Canonical rendering: the sum MUST be rendered as an optional single leading `-` (U+002D, only when the value is negative) followed by one or more ASCII decimal digits `0`–`9`, with no leading zeros except the single digit `0`, no `+` prefix, no whitespace, no thousands separator, no underscore, and no exponent notation. | must-have |
| FR-58 | The rendered sum MUST be written to **stdout** followed by exactly one newline (`\n`, U+000A); nothing else (no banner, prompt, label, padding, or `\r`) MAY be written to stdout. | must-have |
| FR-59 | On a successful addition the program MUST write nothing to **stderr** and MUST terminate with exit status `0`. | must-have |
| FR-60 | Addition MUST be attempted only after both operands pass F-2 validation. If either operand is invalid, or if arity is not exactly two, the program MUST NOT compute a sum and MUST take the F-1 error path (one-line stderr diagnostic, empty stdout, exit status `2`). | must-have |
| FR-61 | Addition MUST be a pure function of its two operands: environment variables, locale, config files, clock, filesystem, network, stdin contents, and process state MUST NOT influence the result. | must-have |
| FR-62 | Addition MUST be commutative in effect: for any accepted `a` and `b`, `add a b` and `add b a` MUST produce byte-identical stdout, stderr, and exit status. | should-have |
| FR-63 | The printed result MUST be re-parseable under the F-2 grammar and MUST denote exactly the mathematical sum of the two operands (round-trip equality). | must-have |

#### Non-Functional Requirements (NFR)

| id | Requirement | Priority |
|---|---|---|
| NFR-31 | Performance: for two operands of up to 1,000 decimal digits each, the parse → add → render cycle MUST complete in under 100 ms wall clock on a 2-core 2 GHz reference machine, excluding interpreter start-up. | should-have |
| NFR-32 | Scalability: operands of at least 10,000 decimal digits MUST be handled without algorithmic failure, stack overflow, or non-zero exit; runtime SHOULD scale no worse than linearly in operand length. | should-have |
| NFR-33 | Availability: addition MUST require no network, no daemon, no service, and no auxiliary process; it MUST succeed on a host with no network interface and no writable filesystem. | must-have |
| NFR-34 | Security: the addition path MUST NOT use `eval`, `exec`, `compile`, `ast.literal_eval`, shell interpolation, or any dynamic evaluation of operand text; operands MUST reach integers only through a strict parser. | must-have |
| NFR-35 | Resource bound: peak additional memory for the addition step SHOULD be O(n) in combined operand length; no buffer MAY be allocated whose size is independent of and larger than the input. | should-have |
| NFR-36 | Data residency: the program MUST NOT read, write, persist, cache, log, or transmit operand or result data; values exist only in process memory and on stdout. | must-have |
| NFR-37 | Deployment: the implementation MUST run on CPython 3 using only the standard library — no third-party packages, no virtualenv, no filesystem writes, no installed data files. | must-have |
| NFR-38 | Determinism: identical arguments on the same interpreter version MUST yield byte-identical stdout, empty stderr, and identical exit status on every invocation. | must-have |
| NFR-39 | Locale independence: parsing and rendering MUST NOT depend on `LANG`, `LC_ALL`, `LC_NUMERIC`, or any locale/encoding setting; ASCII digits MUST be emitted regardless of environment. | must-have |
| NFR-40 | Portability: results MUST be identical across POSIX shells on Linux and macOS, and MUST NOT depend on host endianness, word size, or CPU architecture. | must-have |
| NFR-41 | Interpretability: success vs. failure MUST be distinguishable by exit status alone (`0` vs `2`), and no failure path MAY leave a partial or plausible-looking number on stdout. | must-have |
| NFR-42 | Testability: the addition operation MUST be separable from CLI argument handling so it can be exercised directly with integer inputs and compared against an exact reference result. | should-have |
| NFR-43 | Observability: diagnostics for failed addition MUST be a single line on stderr, human-readable and naming the offending input, with no multi-line traceback and no internal paths. | should-have |
| NFR-44 | Encoding safety: the entire stdout payload MUST be ASCII (`0x30`–`0x39`, `0x2D`, `0x0A`), so that pipeline consumers and non-UTF-8 terminals cannot corrupt or block it. | must-have |
| NFR-45 | Concurrency safety: concurrent invocations MUST be independent — no shared temp files, lock files, or mutable global state MAY affect results. | must-have |

#### User Stories (US)

| id | Story | Priority |
|---|---|---|
| US-31 | As a shell user, I want `add 2 3` to print `5` so that I get an exact integer sum without leaving the terminal. | must-have |
| US-32 | As a shell user, I want `add -7 4` to print `-3` so that negative and mixed-sign operands behave like ordinary integer arithmetic. | must-have |
| US-33 | As a script author, I want the sum on stdout and nothing on stderr on success so that `sum=$(add "$a" "$b")` captures the number uncontaminated. | must-have |
| US-34 | As a script author, I want a stable exit status so that I can branch on success (`0`) versus invalid input (`2`) inside `if`, `&&`, and `||` chains. | must-have |
| US-35 | As a user handling large identifiers, I want `add 99999999999999999999 1` to print `100000000000000000000` exactly so that no precision is silently lost. | must-have |
| US-36 | As a user, I want `add 5 -5` and `add -0 0` to print `0` so that signed zeros never leak into output. | must-have |
| US-37 | As a user, I want `add 5 0` and `add 0 5` to print `5` so that zero behaves as the identity element in both positions. | should-have |
| US-38 | As a pipeline author, I want the result to be a plain newline-terminated decimal integer so that downstream tools consume it without cleaning. | should-have |

### Behaviour

1. **Precondition** — The entry point (F-1) has established exactly two operands and each operand has passed F-2 validation. F-3 starts from two validated integer values.
2. **Convert** — Each validated operand's digit string is converted to an exact integer value. No rounding, scaling, or intermediate float representation occurs.
3. **Add** — Compute `int1 + int2` exactly, with unbounded magnitude and correct sign per `BR-2`.
4. **Normalise** — If the sum is zero, normalise it to unsigned zero (`BR-4`, `FR-56`).
5. **Render** — Produce the canonical decimal string per `FR-57`.
6. **Emit** — Write the rendered string plus exactly one `\n` to stdout; write nothing to stderr.
7. **Exit** — Terminate with status `0`.
8. If any step before 6 fails (validation was not reached, an input exceeds a supported limit, or an internal error occurs), no sum is emitted and the error path in `EH-1`–`EH-4` applies.

### Business rules

- **BR-1 — Sum definition.** The result is the unique integer `s` such that `s - int1 = int2` under exact arithmetic. There is no modular, bounded, saturating, or floating variant.
- **BR-2 — Sign resolution (exhaustive).**

| int1 sign | int2 sign | Result |
|---|---|---|
| + | + | positive, magnitude `|int1| + |int2|` |
| − | − | negative, magnitude `|int1| + |int2|` |
| + | − | sign of the larger magnitude; magnitude `abs(|int1| − |int2|)` |
| − | + | sign of the larger magnitude; magnitude `abs(|int1| − |int2|)` |
| equal magnitudes, opposite signs | | `0` |
| either is zero | | the other operand's value |

- **BR-3 — Identity.** `0` (however spelled: `0`, `+0`, `-0`, `000`) contributes nothing to the sum.
- **BR-4 — Zero canonicalisation.** Every computed zero renders as `0`. `-0`, `+0`, `00`, and ` 0` are never valid outputs.
- **BR-5 — No expression parsing.** Operands are values, not expressions. Operators, parentheses, function names, or multiple terms inside a single argument (e.g. `2+3`, `(2)`, `2 3`) are not parsed; such an argument is simply a malformed operand and is rejected by the F-2 grammar (`FR-27`–`FR-32` there). Exactly one addition occurs per invocation; the tool is not an accumulator or REPL.
- **BR-6 — Sign spelling is not arithmetic.** An explicit `+` prefix on an operand has no effect beyond the value; `-` denotes negation of the following digits only.
- **BR-7 — Leading zeros are not arithmetic.** Leading zeros affect neither value nor output; the output never carries leading zeros (`FR-57`).
- **BR-8 — Bound of this feature.** F-3 does not re-validate grammar, does not decide arity, does not format diagnostics beyond the error-handling rules below, and does not define exit codes for arity errors (those belong to F-1).

### Validation

- **V-1 (precondition).** Both operands MUST already be valid per the F-2 grammar; F-3 MUST reject-by-not-running if either is not. Addition on unvalidated text is forbidden (`FR-60`).
- **V-2 (postcondition).** The rendered result MUST match the canonical pattern `^-?(0|[1-9][0-9]*)$` and, when parsed back, MUST equal the exact sum (`FR-63`, `AC-12`).
- **V-3 (no result-side limits).** There is no maximum magnitude, no minimum, and no range check on the sum. Arbitrarily large and negative results are valid.
- **V-4 (no operand-side value checks).** F-3 MUST NOT reject an operand for being "too large", "zero", or "negative" — those are value properties, not errors.
- **V-5 (single newline).** Output validation MUST confirm exactly one terminating `\n` and no other control characters (`NFR-44`, `AC-15`).
- **V-6 (silence on success).** stderr MUST be zero bytes on every successful path (`FR-59`).

### Edge cases

- **EC-1 — Both zero.** `add 0 0` → `0`.
- **EC-2 — Cancellation.** `add 5 -5` → `0`; MUST NOT be `-0`, `+0`, or an empty line.
- **EC-3 — Cancellation with signs reversed.** `add -5 5` → `0`.
- **EC-4 — Carry propagation adding a digit.** `add 999 1` → `1000`.
- **EC-5 — Long carry chain.** `add 999…9 (n nines) 1` → `1` followed by `n` zeros (result has `n+1` digits).
- **EC-6 — Both negative.** `add -3 -4` → `-7`.
- **EC-7 — Negative larger magnitude, mixed signs.** `add -10 3` → `-7`.
- **EC-8 — Positive larger magnitude, mixed signs.** `add 10 -3` → `7` (no leading `+`).
- **EC-9 — Signed zero spellings.** `add -0 -0` → `0`; `add +0 -0` → `0`; `add -000 000` → `0`.
- **EC-10 — Leading zeros with signs.** `add -0007 +0002` → `-5`.
- **EC-11 — Result is a single zero digit after large cancellation.** `add 1000000000000000000000 -1000000000000000000000` → `0` (exactly one digit).
- **EC-12 — Precision boundary.** `add 9007199254740993 1` → `9007199254740994`. This exceeds the IEEE-754 double exact-integer range (2^53); the result MUST be exact, which is the observable proof that no float is involved (`FR-53`).
- **EC-13 — Very large magnitudes.** Operands of thousands of digits MUST produce an exact decimal result, subject to `OQ-1`.
- **EC-14 — Digit-limit guard (CPython ≥ 3.11).** `int()`/`str()` conversion is subject to `sys.set_int_max_str_digits` (default 4300 digits). An operand or a rendered result exceeding that limit will raise `ValueError`/`int` conversion error at the interpreter level. This MUST surface as the clean error path (`EH-3`), never as a raw traceback. Resolution deferred to `OQ-1`.
- **EC-15 — Memory exhaustion.** An operand large enough to exhaust addressable memory may cause the process to be killed by the OS (SIGKILL/OOM). This is outside the graceful-handling contract and MUST be documented as such; the program MUST NOT attempt to pre-allocate based on claimed lengths.
- **EC-16 — Expression-shaped single argument.** `add 2+3 1` → both arguments are malformed; exit `2` (`BR-5`).
- **EC-17 — Non-integer shaped operands passed through.** `add 1.0 2`, `add 0x10 1`, `add 1e3 1` → rejected by F-2 grammar; exit `2`, no stdout.
- **EC-18 — Identical operands.** `add 7 7` → `14`; the two operands are independent and MUST NOT be deduplicated or memoised into a wrong result.
- **EC-19 — Sum equals an operand.** `add 0 42` → `42`; `add 42 0` → `42`; byte-identical to each other (`FR-62`).

### Error handling

- **EH-1 — Invalid operand.** F-3 MUST NOT run. The F-1 path applies: one-line diagnostic on stderr naming the offending argument, stdout empty, exit status `2`.
- **EH-2 — Wrong arity.** F-3 MUST NOT run; the F-1 arity path applies (stderr usage/diagnostic, stdout empty, exit status `2`).
- **EH-3 — Internal conversion/limit failure.** If operand conversion or result rendering raises (e.g. `EC-14`), the program MUST catch it at the top level and emit a single-line stderr diagnostic (e.g. identifying the argument or the limit involved), leave stdout empty, and exit `2`. A Python traceback MUST NOT be printed.
- **EH-4 — Output write failure.** If writing the result fails (broken pipe, `ENOSPC`, `/dev/full`, closed stdout), the program MUST NOT exit `0` and MUST NOT retry silently; it MUST terminate non-zero with a one-line stderr diagnostic. A partially written number MUST NOT be treated as success.
- **EH-5 — No silent failure.** There is no case in which the program exits `0` without having written a complete canonical result to stdout.
- **EH-6 — Encoding/terminal failure.** Because the payload is pure ASCII (`NFR-44`), an unset or exotic `PYTHONIOENCODING`/locale MUST NOT cause a crash or an altered number; the bytes written MUST be identical regardless of the environment's text encoding.
- **EH-7 — Interrupt.** On SIGINT/SIGPIPE the program MAY terminate before writing; it MUST NOT write a partial number followed by the newline in a way that a consumer could mistake for a complete result.

### Acceptance criteria

| id | Criterion |
|---|---|
| AC-1 | `add 2 3` → stdout is exactly the bytes `5\n`; stderr is empty; exit `0`. |
| AC-2 | `add -7 4` → `-3\n`; stderr empty; exit `0`. |
| AC-3 | `add 7 -4` → `3\n`; stderr empty; exit `0`. |
| AC-4 | `add -7 -4` → `-11\n`; stderr empty; exit `0`. |
| AC-5 | `add 5 -5` → `0\n` (not `-0`, not blank); exit `0`. |
| AC-6 | `add 0 0` → `0\n`; exit `0`. |
| AC-7 | `add -0 -0` and `add +0 -000` → `0\n`; exit `0`. |
| AC-8 | `add +00042 -0002` → `40\n`; exit `0`. |
| AC-9 | `add 999 1` → `1000\n`; exit `0`. |
| AC-10 | `add 99999999999999999999 1` → `100000000000000000000\n`; exit `0`. |
| AC-11 | `add 9007199254740993 1` → `9007199254740994\n`; exit `0` (proves no float path). |
| AC-12 | For every accepted pair `(a, b)`, the integer parsed from stdout equals `int(a) + int(b)` as computed by an independent exact-arithmetic reference. |
| AC-13 | `add 2+3 1` → stdout empty; stderr non-empty; exit `2` (no expression evaluation). |
| AC-14 | `add 1.0 2` → stdout empty; stderr non-empty; exit `2`. |
| AC-15 | Byte-exactness verified with `od`/`cmp`: exactly one trailing `\n`, no `\r`, no leading/trailing spaces, no other bytes. |
| AC-16 | 100 consecutive identical invocations produce identical stdout, empty stderr, and exit `0` (`NFR-38`). |
| AC-17 | The rendered result never contains `+`, space, comma, underscore, or a leading zero other than the value `0` itself. |
| AC-18 | `add 7 7` and `add 7 7` again → identical `14\n`; operands are independent (`EC-18`). |
| AC-19 | `add 0 42` and `add 42 0` produce byte-identical stdout (`FR-62`). |
| AC-20 | Running with `LC_ALL=C`, `LC_ALL=de_DE.UTF-8`, and `LC_ALL=tr_TR.UTF-8` yields byte-identical stdout (`NFR-39`). |
| AC-21 | Triggering the interpreter digit-limit path produces a one-line stderr message, empty stdout, exit `2`, and no traceback (`EH-3`). |
| AC-22 | Redirecting stdout to `/dev/full` produces a non-zero exit and a stderr diagnostic (`EH-4`). |

### API behaviour

- **API-1 — CLI contract surface.** `add <int1> <int2>`

| channel | success | invalid operand | wrong arity |
|---|---|---|---|
| stdout | `<canonical-sum>\n` | empty | empty |
| stderr | empty | one line naming the offending argument | one line usage/diagnostic |
| exit status | `0` | `2` | `2` |

- **API-2 — stdout payload.** UTF-8-irrelevant ASCII bytes: optional `-` (`0x2D`), digits `0x30`–`0x39`, one terminating `0x0A`. No BOM, no `\r`, no colour codes, no padding to a fixed width, no locale grouping separators.
- **API-3 — Function-level contract (behavioural, not a mandated signature).** The addition operation behaves as a pure total function `sum = f(int1, int2)` over all integers, returning exactly their mathematical sum and raising nothing for in-range values. Module names, parameter names, and packaging are decided later (Architect/Implement) and are not specified here.
- **API-4 — Newline semantics.** The trailing `\n` is part of the contract. Consumers using `$( )` command substitution strip it by shell behaviour; consumers requiring byte-exact output MUST read stdout raw (e.g. with `od`).
- **API-5 — No other I/O.** The command reads no stdin (piped input to stdin MUST NOT alter the result or the exit status), opens no files, writes no files, and opens no sockets.
- **API-6 — Options.** No flags, no `--` handling, no `--help` arithmetic, no configuration environment variables affect the addition result.

### Data model

- **DM-1 — Value model.** An operand and the result are members of the mathematical integers ℤ with unbounded magnitude. The only representations crossing the boundary are (a) argv strings conforming to the F-2 grammar (referred to as plain text, not re-defined here) and (b) the canonical decimal string of `FR-57` on stdout. No other representation is observable.
- **DM-2 — No stored state.** Nothing about an invocation persists after exit: no cache, no history file, no temp file, no environment mutation (`NFR-36`).

### Priority

- **must-have:** `FR-51`–`FR-61`, `FR-63`; `NFR-33`, `NFR-34`, `NFR-36`, `NFR-37`, `NFR-38`, `NFR-39`, `NFR-40`, `NFR-41`, `NFR-44`, `NFR-45`; `US-31`–`US-36`.
- **should-have:** `FR-62`; `NFR-31`, `NFR-32`, `NFR-35`, `NFR-42`, `NFR-43`; `US-37`, `US-38`.
- **nice-to-have:** none. F-3 is the core value-producing feature of the tool; nothing in it is optional for a correct `add`.

### Open Questions

- **OQ-1 — Digit-length limit.** CPython ≥ 3.11 caps int↔str conversion via `sys.set_int_max_str_digits` (default 4300 digits), which affects both operand parsing (`EC-14`) and result rendering. Should the tool (a) accept the interpreter default and report a clean exit-`2` error beyond it, (b) raise the limit at start-up to support arbitrary lengths at extra CPU cost, or (c) document a deliberate maximum input length? This determines whether `NFR-32`'s 10,000-digit target is achievable as written. Decision belongs to the USER/Architect; F-3 specifies only that the failure mode MUST be clean (`EH-3`).
- **OQ-2 — Exit status for limit-exceeded input.** Should an oversized-but-well-formed operand exit `2` (same as malformed, current spec) or a distinct status? Current spec: `2`, for consistency with F-1.
- **OQ-3 — stdin.** The brief defines two positional operands and no piped input. F-3 therefore specifies that stdin MUST be ignored (`API-5`). Confirm this is intended and that no `add` reading a line from stdin is ever required.
- **OQ-4 — SIGPIPE policy.** Should the tool silently exit on a broken pipe (`add 1 2 | head -n0` style) or exit non-zero with a diagnostic (`EH-4`)? Current spec requires non-zero; the user may prefer POSIX-conventional silent termination.

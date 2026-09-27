## F-9: Arbitrary-precision output

**Feature ID:** F-9
**Depends on:** F-3 (integer addition), F-4 (print result to stdout), F-5 (exit-status contract), F-8 (correct handling of negative results). F-9 does **not** re-define argument handling (F-1), the operand grammar (F-2), the arithmetic itself (F-3), the stdout envelope (F-4), any exit-status value (F-5), diagnostic text (F-6), the dependency envelope (F-7), or the negative-sign encoding (F-8). F-9 owns only the **scale envelope of the emitted number**: the guarantee that the base-10 rendering of the sum `S` is exact and effectively unbounded for arbitrarily large magnitudes, and the invariants that keep that rendering machine-, locale-, and configuration-independent.

### Requirements

#### Functional Requirements (FR)

| ID | Requirement | Priority |
|---|---|---|
| FR-201 | The program MUST render the sum `S` in base 10 for any magnitude that fits in available process memory. The number of emitted digits MUST equal the exact digit count of `S`; there MUST be no fixed-width cap (no 16/19/32/64/128-bit or any other fixed width) applied to the output. | must-have |
| FR-202 | The emitted digit count MUST be exactly `D = 1` when `S == 0`, else `len(str(abs(S)))`, and MUST be independent of the host platform's word size, CPU architecture, or any native C integer width. | must-have |
| FR-203 | The rendering MUST NOT truncate, round, saturate, clamp to a machine maximum, wrap around, or substitute any sentinel (`inf`, `nan`, `overflow`, `…`) for any value. Every accepted operand pair that could produce a large sum MUST produce that sum exactly. | must-have |
| FR-204 | The rendering MUST NOT contain digit grouping, thousands separators, underscores, spaces, decimal points, exponent/scientific notation, radix prefixes, or any character outside ASCII `0`–`9` (U+0030–U+0039), plus at most one leading `-` (U+002D) when `S < 0` as owned by F-8. | must-have |
| FR-205 | The rendering MUST be deterministic: for a fixed `(int1, int2)` accepted under the F-2 grammar, the byte sequence written to stdout MUST be identical on every run, every host, every platform, and every locale. | must-have |
| FR-206 | Round-trip fidelity: parsing the emitted output token under the F-2 operand grammar MUST yield an integer exactly equal to `S`. | must-have |
| FR-207 | The render path MUST NOT convert `S` through a binary floating-point or decimal floating-point value at any point. | must-have |
| FR-208 | The program MUST NOT impose an application-level maximum on operand magnitude or result magnitude. The only bound is the interpreter's available memory; the tool MUST NOT advertise, enforce, or document a finite maximum result size. | must-have |
| FR-209 | The rendering MUST be emitted as a single contiguous token with no interior whitespace or newline, terminated by exactly one `\n` (per F-4). It MUST NOT wrap or insert line breaks at any column width. | must-have |
| FR-210 | The program MUST emit the exact digit count for sums spanning many orders of magnitude greater than any native integer type on the host. | must-have |
| FR-211 | The output path MUST treat small and arbitrarily large sums through the same rendering logic. There MUST be no special-cased fast path that produces a structurally different textual form for values below any threshold. | must-have |
| FR-212 | On CPython 3.11+ (which caps integer→decimal-string conversion at a default of 4300 digits), the program MUST produce the correct decimal rendering for results with more than 4300 digits without surfacing the interpreter's integer-string conversion limit as a user-visible error for otherwise-valid input. The interpreter's default cap is a host artifact, not a contract limit of this tool. | must-have |

#### Non-Functional Requirements (NFR)

| ID | Category | Requirement | Target / Measurement |
|---|---|---|---|
| NFR-121 | Performance | Rendering a sum of `n` decimal digits MUST be linear-time, `O(n)`, in the digit string — no quadratic concatenation loops. | A 1,000,000-digit sum renders in < 2 s on a modern laptop (should-have nuance within this feature; `O(n)` is must-have). Measured by wall-clock timing on a synthetic large sum. |
| NFR-122 | Scalability / availability | The program MUST remain a single ephemeral, stateless process per invocation: no daemon, no server, no persistence. Each invocation is independent; large consecutive sums MUST NOT degrade across invocations. | N repeated invocations of large-sum cases, each exit 0, no cross-run state. |
| NFR-123 | Memory | Peak additional memory for rendering MUST be `O(n)` in output digit count `n`, holding no more than a small constant number of full copies of the digit string. | Memory profiling of a large-sum invocation scales linearly, not quadratically. |
| NFR-124 | Security | The render path MUST NOT `eval`, `exec`, shell-substitute, `format`, or template the sum, the digit string, or any user-controlled value. Output is data and MUST NEVER be interpreted as code or as a format string. | Static inspection of the render path; no user-controlled format string reachable. |
| NFR-125 | Security (resource exhaustion) | The program MUST NOT present a truncated or partial digit token as a successful result. Stdout emitted under a success status MUST be either the complete correct line or empty. | Failure-injection / very-large-input tests assert stdout is complete-on-success and empty-on-failure. |
| NFR-126 | Data / residency | The program MUST store no data at rest, write no files, open no network sockets, and transmit no bytes except the stdout/stderr streams defined by F-1/F-4/F-6. The sum and its rendering MUST be confined to process memory for the duration of the invocation. | Filesystem/network syscall tracing shows no writes/sockets; no temporary files. |
| NFR-127 | Deployment / environment | Arbitrary-precision output MUST behave identically on any CPython ≥ 3.8, on any OS, regardless of `PYTHONINTMAXSTRDIGITS`, `LANG`, `LC_NUMERIC`, `LC_ALL`, or any other environment setting. No environment variable may be *required* to enable correct large-sum output. | Byte-identity of stdout across environment permutations. |
| NFR-128 | Data integrity / portability | The rendered digit string MUST be byte-for-byte identical whether the process runs on a 32-bit or 64-bit host and on big- or little-endian architectures. | Cross-platform comparison of captured stdout bytes (where hosts are available). |

### Behaviour

- F-9 consumes the exact sum `S` produced by F-3 and the canonical rendering rules owned by F-4 (base 10, no leading zeros, single trailing `\n`) and F-8 (leading `-` for `S < 0`). It adds no new arithmetic and no new sign rules.
- For every accepted input, F-9 emits exactly one token: `0` · `[1-9][0-9]*` · `-[1-9][0-9]*`, immediately followed by one `\n`.
- The emitted token's digit count is the exact mathematical digit count of `S`; leading zeros present in the *operands* (F-2) never survive into the output.
- Rendering is a pure, total function of `S`: same `S` → same bytes, independent of operands' textual form, host, locale, terminal, or environment.
- The output path is uniform: values in the machine-int range and values far beyond it pass through the same formatting logic; no threshold-based special case exists.
- The interpreter's own integer-string conversion ceiling (CPython 3.11+ default 4300 digits) is treated as a host constraint to be neutralized, not as an error to be surfaced for valid input.

### Business rules

- **BR-1:** The output value is exactly `S = int1 + int2` as defined by F-3; F-9 changes neither the value nor the arithmetic.
- **BR-2:** Exactly one canonical textual form exists per integer value: optional leading `-` (F-8) followed by the most-significant-first decimal digits, with no leading zeros except that the value zero is the single character `0`.
- **BR-3:** The output stream is a single logical line: `[ - ] digit+` then exactly one `\n`. Nothing precedes and nothing follows it.
- **BR-4:** The output digit count is a pure function of `S`; it MUST NOT depend on the textual length of the operands (operand leading zeros do not survive).
- **BR-5:** "Arbitrary precision" is a contract, not a best-effort: the tool claims no maximum result size; the only bound is available process memory / interpreter capability.
- **BR-6:** Output bytes are data. No locale, encoding, terminal width, or environment variable may influence them.
- **BR-7:** The interpreter's integer→string digit cap is a host artifact outside this tool's contract; for otherwise-valid input it MUST NOT be surfaced to the user as an error.

### Validation

- **V-1:** Emitted stdout MUST match the regular expression `^-?[0-9]+\n$`, with the leading `-` present only when `S < 0`.
- **V-2:** No-leading-zero check: the token MUST match `^0\n$`, `^[1-9][0-9]*\n$`, or `^-[1-9][0-9]*\n$`.
- **V-3:** Round-trip check: re-parsing the emitted token under the F-2 grammar yields a value equal to `S`.
- **V-4:** Digit-count check: the number of digit characters equals `D` per FR-202.
- **V-5:** Determinism check: two runs, and any two platforms, produce identical stdout bytes.
- **V-6:** Large-magnitude check: a sum exceeding the CPython 3.11+ default integer-string conversion cap (> 4300 digits) renders fully and exits 0 with no `ValueError` surfaced.

### Edge cases

- **EC-1:** `S == 0` → `0\n` (never `-0\n`, never `+0\n`).
- **EC-2:** Large-magnitude negative `S` → `-` followed by the full magnitude digits (per F-8), with no overflow marker.
- **EC-3:** Sums whose digit count is just below, exactly at, and just above the interpreter's default integer-string conversion cap (4299 / 4300 / 4301 digits on CPython 3.11+) — all must render exactly.
- **EC-4:** Operands supplied with leading zeros (e.g., `000007 000000`) → canonical output with leading zeros dropped.
- **EC-5:** Both operands zero, or cancellation to zero → `0\n`.
- **EC-6:** Extremely large operands (e.g., 100,000+ digits each) → exact output, bounded only by process memory.
- **EC-7:** Sum whose magnitude equals a power of ten (e.g., `999…9 + 1`) → digit count increases by exactly one; no digit loss or off-by-one at the boundary.
- **EC-8:** Locale configured to group digits differently (`LC_NUMERIC`) → output unchanged, no separators.
- **EC-9:** 32-bit vs 64-bit host → identical digit count and identical bytes.
- **EC-10:** Very large negative sum combined with F-8 sign encoding → single `-`, no double sign, no space between sign and digits.

### Error handling

- **EH-1:** If the interpreter reports its integer-string conversion limit for an otherwise-valid sum, the program MUST NOT surface a partial result and MUST NOT claim success with a truncated line. It either completes the correct rendering or fails through the F-5/F-6 failure channel — never a truncated token under exit status `0`.
- **EH-2:** If memory is exhausted during rendering, stdout MUST be either the complete correct line or empty; a partial digit token MUST NEVER be terminated by `\n` under a success status.
- **EH-3:** Any rendering-time failure MUST report to stderr in the diagnostic style owned by F-6; stdout MUST remain byte-clean on any failure (consistent with the F-6 validation pipeline).
- **EH-4:** `-0` MUST NOT be emitted under any circumstance; zero is always unsigned.
- **EH-5:** No placeholder token (`N/A`, `?`, `-`, `overflow`, `inf`, `nan`, empty line) may ever be emitted in place of a numeric result.

### Acceptance criteria

- **AC-1 (FR-201):** `add 9223372036854775807 1` → stdout `9223372036854775808\n`, exit `0` (correctly exceeds the signed 64-bit maximum).
- **AC-2 (FR-203):** Sums exceeding the 64-bit range render exactly, with no saturation to `9223372036854775807` and no wrap-around to a negative value.
- **AC-3 (FR-202, FR-210):** For a sum with a known digit count `k` (> 1000), stdout contains exactly `k` digit characters, independent of host word size.
- **AC-4 (FR-204, FR-209):** stdout matches `^-?[0-9]+\n$` and contains no `,`, `_`, space, `.`, `e`/`E`, `+`, or wrapping newline.
- **AC-5 (FR-206):** Feeding the emitted output back through the F-2 grammar yields a value equal to `S` (e.g., `add $(add 2 3) 0` → `5\n`).
- **AC-6 (FR-205, NFR-127):** The same invocation under differing `LANG`, `LC_ALL`, and `PYTHONINTMAXSTRDIGITS` values produces byte-identical stdout.
- **AC-7 (FR-212):** On CPython 3.11+, adding two operands whose sum has more than 4300 digits succeeds with exit `0` and the full digits on stdout, with no `ValueError` surfaced to the user.
- **AC-8 (FR-209):** stdout is exactly one line terminated by exactly one `\n`, with no interior whitespace and no column wrapping.
- **AC-9 (FR-211):** A small sum and a very large sum use the same code path and produce structurally identical output forms (only the digit count differs).
- **AC-10 (NFR-123):** Peak memory during a large-sum render scales linearly with digit count; the program does not retain unnecessary duplicate copies of the digit string.
- **AC-11 (FR-201):** `add 999 1` → `1000\n` (not `01000\n`); the digit count increases by exactly one at the power-of-ten boundary.
- **AC-12 (NFR-121):** A 1,000,000-digit sum renders within the NFR-121 time budget, confirming `O(n)` behaviour.

### API behaviour

> The program's API surface is its command-line process contract (owned by F-1/F-4/F-5); F-9 specifies only the *shape and scale* of the successful output.

- **API-1:** Program `add` (F-1). On success, stdout carries exactly one decimal token per F-4/F-9; stderr is empty; exit status is `0` (status value owned by F-5).
- **API-2:** `add <a> <b>` where the sum has `n` digits → stdout carries exactly `n` digit characters, plus an optional leading `-` (F-8), plus one trailing `\n`. No fixed maximum `n`.
- **API-3:** The emitted token is a valid operand under the F-2 grammar (optional `+`/`-`, ASCII digits, no separators), enabling round-trip composition.
- **API-4:** Rendering is pure: no files, no network, no environment writes, no side effects (NFR-126).
- **API-5:** Rendering is idempotent: the same input always yields the same output bytes (NFR-127 / FR-205).
- **API-6:** A consumer may capture the result via `$(add a b)` and receive the value with the trailing newline stripped, without needing to trim whitespace, separators, or notation.

### Data model (DM)

- **DM-1:** Value type = mathematical integer (unbounded ℤ), represented in use by the interpreter's arbitrary-precision integer type.
- **DM-2:** Output representation = canonical decimal string matching `-?\d+` with no leading zeros except the single character `0`.
- **DM-3:** No persisted record, no schema, no storage. The value exists only in-process during a single invocation.

### Tests (T)

- **T-1:** 64-bit boundaries: `9223372036854775807 + 1`; `-9223372036854775808 + -1`.
- **T-2:** Power-of-ten boundary digit-count increase: `999…9 + 1`.
- **T-3:** Cancellation to zero and `0 + 0`.
- **T-4:** Operands with leading zeros.
- **T-5:** Digits just below / at / above the CPython 3.11+ integer-string cap (4299 / 4300 / 4301).
- **T-6:** Very large magnitudes (10⁵–10⁶ digits) for memory and linear-time checks.
- **T-7:** Environment-permutation byte-identity (`LANG`, `LC_ALL`, `PYTHONINTMAXSTRDIGITS`).
- **T-8:** 32-bit vs 64-bit host digit-count parity (where hosts are available).
- **T-9:** Round-trip parse of emitted output under the F-2 grammar.

### Open questions (OQ)

- **OQ-1:** Is there an intended *practical* upper bound for results (e.g., guaranteeing 1,000,000-digit output within a stated time), or should the tool be documented as memory-bound only? — Needs USER confirmation; not a reason to reduce scope.
- **OQ-2:** Should the tool guarantee successful output for *any* magnitude regardless of the interpreter's integer-string conversion limit, or is exceeding the interpreter default (4300 digits on CPython 3.11+) acceptable to reject? — Needs USER confirmation (F-9 assumes the guarantee).
- **OQ-3:** If a user sets `PYTHONINTMAXSTRDIGITS` to a low value, should the tool's output remain identical to the default configuration (i.e., override the user's environment)? — Needs USER confirmation (F-9 assumes identical behaviour).

### Priority

**must-have.** Arbitrary-precision output is the property that makes the tool's result trustworthy for any accepted input; the critical, non-obvious risk is the CPython 3.11+ integer→string conversion cap (FR-212), which would otherwise turn a mathematically valid sum into a user-visible error. All FRs above are must-have; the concrete million-digit performance budget in NFR-121 is the only "should-have" nuance within the feature.

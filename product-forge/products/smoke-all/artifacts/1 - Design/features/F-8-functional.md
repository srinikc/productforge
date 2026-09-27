## F-8: Correct handling of negative results

**Feature ID:** F-8
**Depends on:** F-1 (`add` command entry point), F-2 (two positional integer operands), F-3 (integer addition), F-4 (print result to stdout), F-5 (exit-status contract) — F-8 does **not** re-define argument handling, arity rules, the operand grammar, the arithmetic itself, the rendering envelope, or any exit-status value. F-8 owns only the **signed rendering of a sum strictly less than zero**: how a negative sum is distinguished from zero and from positive sums, how the sign is encoded and positioned, and the invariants that make a negative result unambiguous, round-trippable, and locale-independent.

### Requirements

#### Functional Requirements (FR)

| ID | Requirement | Priority |
|---|---|---|
| FR-176 | The program MUST detect that the computed sum `S` is strictly less than zero and render `S` as a signed value: a single leading `-` (U+002D HYPHEN-MINUS, byte `0x2D`) followed by the base-10 magnitude `\|S\|`. `add 2 -5` MUST emit `-3\n`. | must-have |
| FR-177 | The sign MUST be emitted as ASCII `-` U+002D (byte `0x2D`). U+2212 MINUS SIGN, U+2010/U+2011 hyphens, en dash U+2013, em dash U+2014, the fullwidth minus U+FF0D, or any digit-glyph substitution MUST NOT be used. | must-have |
| FR-178 | The sign MUST appear exactly once, at byte offset 0 of the rendered value, immediately followed by the first significant digit. Duplicate signs, separated signs, and bracketed forms MUST NOT appear: `--3`, `- 3`, `(-3)`, `-3-`, `3-` are all forbidden. | must-have |
| FR-179 | The magnitude portion of a negative result MUST contain no leading zeros: the rendered line MUST match `^-[1-9][0-9]*\n$` for `S < 0`. `add -7 -1` MUST emit `-8\n`, never `-08\n`. | must-have |
| FR-180 | The sign of the rendered result MUST be derived solely from the exact mathematical sum, never from operand order and never from the sign of the first operand. `add -5 2` and `add 2 -5` MUST both emit `-3\n`. | must-have |
| FR-181 | The program MUST NEVER emit `-0`. Whenever the exact sum is zero — including `add -5 5`, `add 5 -5`, `add -0 0`, `add 0 -0`, `add -0 -0` — stdout MUST be exactly `0\n`. Zero carries no sign in this interface. | must-have |
| FR-182 | A rendered negative result MUST itself be a valid operand under the F-2 grammar (`-` followed by one or more ASCII decimal digits, nothing else) so that output can be consumed as input: `add $(add 2 -5) 5` MUST yield `2\n`. | must-have |
| FR-183 | For a negative sum `S`, the rendered magnitude MUST equal the decimal expansion of `\|S\|` exactly, such that re-parsing the emitted line as an integer yields exactly `S` — with no digits dropped, prepended, or fabricated. | must-have |
| FR-184 | Magnitude rendering of a negative result MUST use the same arbitrary-precision, base-10 path as a non-negative result: no truncation, saturation, wrapping, or sign-magnitude width limit (32-bit, 64-bit, or otherwise) may apply. | must-have |
| FR-185 | On a successful negative result the program MUST write exactly one complete line `-<magnitude>\n` to stdout, write zero bytes to stderr, and terminate with exit status `0`. | must-have |
| FR-186 | A negative result MUST NOT be treated as an error condition: it MUST NOT raise, MUST NOT set a non-zero exit status, MUST NOT suppress stdout, and MUST NOT emit any diagnostic. | must-have |
| FR-187 | The sign MUST survive the full parse → add → render → write path as a literal byte: output MUST be ASCII/UTF-8 compatible on stdout whether stdout is a TTY, a regular file, or a pipe, with no BOM and no encoding preamble. | must-have |
| FR-188 | Sign classification MUST be performed by comparing the exact sum against zero and MUST be correct at arbitrary magnitude, including when operands are shaped so that a naive sign-bit or floating-point classification would be wrong by many orders of magnitude. | must-have |

#### Non-Functional Requirements (NFR)

| ID | Target | Measurement | Priority |
|---|---|---|---|
| NFR-106 | **Performance:** the negative-result path adds no measurable overhead versus the non-negative path; `add -9999999999999 1` completes in < 50 ms wall clock on reference hardware. | Timed loop of 1000 invocations, median and p95 wall clock; compare against an equivalent non-negative invocation. | must-have |
| NFR-107 | **Scalability (magnitude):** correct sign and full magnitude for operands of at least 10,000 decimal digits each that yield a negative sum, in < 500 ms per invocation. | Generate maximal-size operands, invoke, byte-compare against a reference big-integer computation. | must-have |
| NFR-108 | **Availability/robustness:** 100% of syntactically valid negative-result invocations exit `0` with a complete line; zero crashes across the full generated operand space (see `T-1`–`T-7`). | Exhaustive small-range sweep plus randomized large-magnitude fuzzing; assert exit status and stdout shape on every case. | must-have |
| NFR-109 | **Security:** the sign is emitted as inert data only — never executed, never interpolated into a shell command, never used to build a filename, path, or option string. A leading `-` in *output* MUST NOT be interpreted by the program as an option. | Code inspection for any exec/eval/shell/path construction involving output; confirm the output byte is written by a literal write to stdout. | must-have |
| NFR-110 | **Data/residency:** no persistence, no temp files, no network, no writes outside process memory plus the stdout/stderr streams. Negative values MUST NOT be cached, logged, or telemetered anywhere. | Filesystem and socket syscall observation (e.g., `strace`) around a negative-result run; assert no file/socket activity. | must-have |
| NFR-111 | **Deployment/environment:** identical byte-for-byte output under `LC_ALL=C`, `LC_ALL=de_DE.UTF-8`, and `LC_ALL=ar_EG.UTF-8` — no locale-specific minus sign, digit shaping, decimal separator, or group separator. | Byte-compare stdout across the three locale settings for the same invocation. | must-have |
| NFR-112 | **Portability:** output is pure ASCII on POSIX and on Windows; the terminating sequence is `\n` (byte `0x0A`) on both, never `\r\n`. | Byte-compare stdout hexdump on both platforms. | must-have |
| NFR-113 | **Determinism:** identical operands always produce byte-identical stdout, stderr, and exit status across repeated runs and across process restarts. | 100 repeated invocations of the same pair; assert identical stdout/stderr bytes and status. | must-have |
| NFR-114 | **Observability:** a successful negative-result run produces an empty stderr stream; no progress, warning, or debug output is emitted on any channel other than the single stdout line. | Assert stderr length is exactly 0 bytes for successful runs, including very large magnitudes. | must-have |

#### User Stories (US)

| ID | Story | Priority |
|---|---|---|
| US-106 | As a shell user, I want `add 2 -5` to print `-3` so that I can express subtraction by negating an operand without a second command. | must-have |
| US-107 | As a script author, I want the output of one `add` call to be accepted as an operand by the next, so that I can chain arithmetic in pipelines and substitutions. | must-have |
| US-108 | As a script author, I want `add -5 5` to print `0` and never `-0`, so that numeric equality comparisons on the output behave correctly. | must-have |
| US-109 | As a data-processing user, I want negative results printed with a plain ASCII `-`, so that standard tools (`grep`, `cut`, `sort -n`, `bc`) parse my output without special-casing. | must-have |
| US-110 | As an operator, I want a failing invocation to never leave a plausible-looking partial negative number on stdout, so that a failed run cannot be mistaken for a valid result. | must-have |

### Behaviour

1. F-1/F-2 accept exactly two operands; F-3 computes the exact arbitrary-precision sum `S = int1 + int2`; F-8 receives `S`.
2. F-8 classifies `S` against zero: `S > 0` → positive/unsigned path (F-4); `S == 0` → emit exactly `0` (FR-181); `S < 0` → negative path defined here.
3. On the negative path, F-8 renders the magnitude `|S|` in base 10 with no leading zeros, prefixes exactly one `-`, appends exactly one `\n`, and writes the resulting line to stdout as the sole stdout content.
4. stderr remains empty and the exit status is `0`.
5. The rendering is produced from the integer value, never from a textual slice or concatenation of the original operand strings, so that cancellation (`add -1000000000000000000000 999999999999999999999` → `-1`) and sign flips are correct.

### Business rules

| ID | Rule |
|---|---|
| BR-1 | Zero is unsigned in this interface. There is exactly one rendering of zero — `0` — and `-0`, `+0`, and ` 0` are all invalid output forms. |
| BR-2 | Sign is a property of the **result**, not of any operand. Operand order is semantically irrelevant to the rendered line. |
| BR-3 | A negative result is a normal, successful outcome: it is never a warning, never an error, and never affects the exit status. |
| BR-4 | The emitted sign is a data character in the output grammar (`-` `[0-9]+`), not a marker, flag, or escape; downstream parsers may treat the output as an integer literal. |
| BR-5 | Every negative result is exactly one line: one sign, at least one digit, one terminator. Nothing precedes, follows, or interleaves. |
| BR-6 | The number line is covered without ambiguity: the mapping from the exact sum `S` to the emitted byte string is injective — distinct sums never produce the same line, and the same sum never produces two different lines. |

### Validation

| ID | Check | Method |
|---|---|---|
| V-1 | The first byte of stdout is `-` **iff** the exact sum is negative, and never otherwise. | Compare stdout prefix against the reference-computed sign. |
| V-2 | The sign byte is exactly `0x2D`. | Hexdump / `od -c` of stdout; assert no multi-byte minus encoding appears. |
| V-3 | No `-0` is ever emitted. | Byte-compare stdout to `b"0\n"` for all zero-sum operand pairs, including `-0`/`0` operand spellings. |
| V-4 | Output shape matches `^-?(0\|[1-9][0-9]*)\n$`. | Regex assertion over stdout of every test case in `T-1`–`T-7`. |
| V-5 | Round-trip: the emitted line, re-parsed by the F-2 grammar, equals the reference sum exactly. | Feed stdout back as an operand to a second invocation; assert the composed result. |
| V-6 | Arbitrary precision holds: a ≥1000-digit negative result matches a reference big-integer computation digit-for-digit. | Differential test against a reference arbitrary-precision computation. |
| V-7 | Locale independence. | Run under `LC_ALL=C`, `de_DE.UTF-8`, `ar_EG.UTF-8`; byte-compare stdout. |
| V-8 | Operand-order independence. | For each pair `(a, b)`, byte-compare `add a b` against `add b a`. |
| V-9 | stderr is empty and exit status is `0` on every negative result. | Capture both streams and the status; assert `stderr == b""` and `status == 0`. |

### Edge cases

| ID | Case | Required outcome |
|---|---|---|
| EC-1 | `add -5 5` reduces to zero. | stdout `0\n`, exit `0`, stderr empty. |
| EC-2 | `add 5 -5` reduces to zero from the other order. | stdout `0\n`, exit `0`, stderr empty. |
| EC-3 | `add -0 0`, `add 0 -0`, `add -0 -0` (operands spelled with a negative zero). | stdout `0\n`; `-0` MUST NOT appear. |
| EC-4 | `add 0 -7` — first operand is zero, result is negative. | stdout `-7\n`; the sign comes from the result, not the leading operand. |
| EC-5 | `add -000123 1` — operand has leading zeros and a sign. | stdout `-122\n`; operand formatting does not leak into output. |
| EC-6 | `add -1000000000000000000000 999999999999999999999` — near-total cancellation beyond 64-bit range. | stdout `-1\n`; no overflow or wrap. |
| EC-7 | `add 2 -5` and `add -5 2`. | Both emit the byte-identical line `-3\n`. |
| EC-8 | `add -1 0` and `add 0 -9223372036854775808` (magnitude at/over signed 64-bit boundary). | stdout `-1\n` and the exact negative value; no clamping. |
| EC-9 | Very long negative result (≥10,000 digits). | Full magnitude written, correct single sign, exactly one terminator. |
| EC-10 | stdout redirected to a file or a pipe. | Output byte-identical to the TTY case; byte `0x2D` present; no BOM; no CRLF. |
| EC-11 | Locale set to a UTF-8 locale (`de_DE.UTF-8`, `ar_EG.UTF-8`). | Output byte-identical to `LC_ALL=C`; no U+2212, no shaped digits, no grouping separators. |
| EC-12 | Operand `-` alone, `--5`, `- 3`, `-3.0`, `-1e5`, `- 000`. | Handled by F-2/F-6: single-line stderr diagnostic, empty stdout, exit `2`. The negative-result rendering path MUST NOT run. |
| EC-13 | `add -2147483648 -1` and other combinations crossing common 32-bit limits. | Exact negative result; no wraparound. |
| EC-14 | Both operands negative with equal magnitudes and opposite signs in a chain. | Result sign is recomputed from the arithmetic each time; never sticky. |

### Error handling

| ID | Condition | Required behaviour |
|---|---|---|
| EH-1 | The sum is negative. | **Not an error.** stdout is the single signed line, stderr empty, exit status `0`. No warning, no code path that raises. |
| EH-2 | An operand that merely *looks* negative (`-`, `--3`, `- 3`, `-3.0`, `-1e5`) is supplied. | Rejected by the F-2 grammar via the F-6 pipeline: exactly one stderr diagnostic line, zero stdout bytes, exit status `2`. No partial negative rendering. |
| EH-3 | Writing the negative result to stdout fails (closed/full descriptor, I/O error). | The process MUST NOT exit `0` (an exit status of `0` is reserved for a run that wrote the complete `-<magnitude>\n` line per F-5); a single-line diagnostic goes to stderr when stderr is writable. |
| EH-4 | The write is interrupted (e.g., broken pipe) mid-line. | No fabricated terminator and no fabricated digits are appended; a truncated prefix MUST NOT be completed into a well-formed line. |
| EH-5 | Any unexpected internal failure on the negative-result path. | No unhandled traceback escapes: a single-line diagnostic to stderr and a non-zero exit status; stdout MUST NOT carry a line that could be mistaken for a valid result. |

### Acceptance criteria

| ID | Given / When / Then |
|---|---|
| AC-1 | **Given** operands `2` and `-5`, **when** the program runs, **then** stdout is exactly the 3 bytes `-3\n`, stderr is empty, and exit status is `0`. |
| AC-2 | **Given** operands `-5` and `2` (order reversed), **when** the program runs, **then** stdout is byte-identical to AC-1. |
| AC-3 | **Given** operands `-5` and `5`, **when** the program runs, **then** stdout is exactly `0\n` — never `-0\n`. |
| AC-4 | **Given** any pair of operands whose exact sum is negative, **when** the program runs, **then** the first stdout byte is `0x2D` and the remainder matches `[0-9]+\n` with no leading zero in the magnitude. |
| AC-5 | **Given** the output `-3\n` from a prior invocation, **when** it is supplied as an operand together with `5`, **then** the composed result is `2\n` (the sign is parseable by the same grammar). |
| AC-6 | **Given** operands `-1000000000000000000000` and `999999999999999999999`, **when** the program runs, **then** stdout is exactly `-1\n` with no overflow. |
| AC-7 | **Given** the same negative-result invocation run under `LC_ALL=C`, `de_DE.UTF-8`, and `ar_EG.UTF-8`, **when** outputs are compared, **then** all three stdout streams are byte-identical and contain only ASCII `0x2D` as the sign. |
| AC-8 | **Given** the operand `-` (bare sign) or `-3.0`, **when** the program runs, **then** stdout is empty, stderr contains exactly one diagnostic line, and exit status is `2` — no negative-result line is produced. |

### API behaviour

The interface is the process itself; there is no library, network, or file API.

| ID | Contract element | Specification |
|---|---|---|
| API-1 | Invocation | `add <int1> <int2>` — two positional operands, no options or flags (as fixed by F-1/F-2). |
| API-2 | Output channel | On a negative sum, stdout carries exactly one line: `0x2D` + ASCII decimal digits of `\|S\|` (no leading zeros) + `0x0A`. Total stdout length = `1 + digits(\|S\|) + 1` bytes. No trailing spaces, no extra blank line. |
| API-3 | Error channel | Empty (0 bytes) on every successful negative-result run. |
| API-4 | Exit status | `0` for a negative result, identical to the positive and zero cases; the sign of the result never selects a different status (status values are owned by F-5). |
| API-5 | Encoding | ASCII / UTF-8-safe, platform-independent: byte `0x2D`, digit bytes `0x30`–`0x39`, terminator `0x0A`. No BOM, no CRLF translation on any platform. |
| API-6 | Idempotence | Repeated invocation with identical operands yields byte-identical stdout, stderr, and exit status. |
| API-7 | Composability | The emitted line is a valid operand for a subsequent invocation (F-2 grammar), enabling `add $(add a b) c`. |
| API-8 | Non-goals | No JSON/YAML output mode, no multi-line output, no locale-formatted numbers, no colour, no sign suppression — none of these are part of the contract for this feature. |

### Test cases

| ID | Input | Expected stdout (bytes) | Status |
|---|---|---|---|
| T-1 | `2 -5` | `-3\n` | 0 |
| T-2 | `-5 2` | `-3\n` | 0 |
| T-3 | `-5 5` | `0\n` | 0 |
| T-4 | `0 -7` | `-7\n` | 0 |
| T-5 | `-000123 1` | `-122\n` | 0 |
| T-6 | `-1000000000000000000000 999999999999999999999` | `-1\n` | 0 |
| T-7 | `-0 0` | `0\n` | 0 |
| T-8 | `- 5` | *(empty)* | 2 |

### Priority

**Overall: must-have.** A command named `add` that cannot represent negative sums is functionally incorrect for the majority of real operand pairs, so this feature is on the critical path.

| Element | Priority | Rationale |
|---|---|---|
| Sign correctness and sign-source rule (FR-176, FR-180, FR-188) | must-have | Core correctness; wrong sign is a silent, high-impact error. |
| ASCII `-` encoding and locale independence (FR-177, NFR-111, NFR-112) | must-have | Output must be machine-consumable by standard tooling in any environment. |
| No `-0` (FR-181, BR-1) | must-have | Prevents downstream equality/comparison bugs. |
| Round-trippability (FR-182, API-7) | must-have | Enables composition, the primary scripted use. |
| Arbitrary-precision magnitude (FR-184, NFR-107) | must-have | Mandated by the project's standard-library, no-limits arithmetic stance. |
| Exact line shape and clean channels (FR-178, FR-179, FR-185, FR-186, NFR-114) | must-have | Makes the output deterministic and parseable. |
| Performance parity (NFR-106) | should-have | No functional impact, but guards against an inefficient sign path. |
| Portability and determinism evidence (NFR-112, NFR-113) | should-have | Verification strength; cheap to satisfy. |
| Security/data-residency inspection (NFR-109, NFR-110) | nice-to-have | Low risk for a local, stateless computation, but should be confirmed by inspection. |

### Open questions

| ID | Question | Owner |
|---|---|---|
| OQ-1 | The brief specifies only "prints the sum". This spec assumes a result of zero is always rendered as `0` and never `-0`; please confirm that no signed-zero representation is expected. | USER |
| OQ-2 | The brief does not mention any option to suppress or alter the sign (e.g., printing an absolute value, `+` prefixes for positive results, or colour). This spec treats sign handling as unconditional and non-configurable; confirm that no such switch is required. | USER |
| OQ-3 | The brief does not state an expected behaviour when stdout cannot be written. This spec assumes a failed write is never a successful run (no exit `0`). Confirm that no alternative (e.g., best-effort partial output with exit `0`) is desired. | USER |

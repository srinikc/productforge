## F-4: Print result to stdout

**Feature ID:** F-4
**Depends on:** F-1 (`add` command entry point), F-2 (two positional integer operands), F-3 (integer addition) — F-4 consumes the already-computed exact sum from F-3 and owns only the *rendering and emission* of that value to stdout. F-4 does **not** re-define argument handling, arity rules, the digit grammar, or arithmetic; those belong to F-1, F-2, and F-3 respectively.
**Scope of this feature:** given a successfully computed sum `S` (arbitrary-precision integer) and an accepted invocation, produce the canonical textual rendering of `S`, emit it on stdout as a single line, keep stderr empty, and signal success via the exit status.

---

### Requirements

#### Functional Requirements (FR)

| ID | Requirement | Priority |
|---|---|---|
| FR-76 | The program MUST write the textual rendering of the computed sum `S` to **stdout** on every successful run (i.e., whenever F-1 arity rules and F-2 operand grammar are satisfied). | must-have |
| FR-77 | `S` MUST be rendered in **base 10** using ASCII digit characters `0`–`9` (U+0030–U+0039) only. No other radix, and no radix prefix (`0x`, `0o`, `0b`), may appear. | must-have |
| FR-78 | The rendered value MUST be followed by **exactly one** line terminator: `\n` (U+000A, byte `0x0A`). Nothing may be written after it. | must-have |
| FR-79 | The rendering MUST NOT contain leading zeros, except that the value zero itself is rendered as the single character `0`. (`0` → `0`; `5` → `5`; `007`-style operands never leak into output.) | must-have |
| FR-80 | A negative sum MUST be prefixed with exactly one `-` (U+002D, byte `0x2D`) placed immediately before the first digit. A positive sum MUST NOT be prefixed with `+`. | must-have |
| FR-81 | The value zero MUST be rendered as `0` — never as `-0`, `+0`, `00`, `0.0`, an empty string, or any whitespace. Zero is a *successful result*, not an absence of output. | must-have |
| FR-82 | The output line MUST contain no padding, no thousands separators (`,`/`_`/space), no exponent or decimal point, no unit, no label, and no prefix such as `=` or `sum:`. The line is the bare number. | must-have |
| FR-83 | stdout MUST be the sole channel for the result. No banner, version string, prompt, progress text, or diagnostic may be written to stdout under any circumstance. | must-have |
| FR-84 | On the success path, **stderr MUST receive zero bytes**. | must-have |
| FR-85 | On the success path, the process MUST terminate with exit status `0`, and it MUST do so only after the result bytes have been flushed to stdout. | must-have |
| FR-86 | The program MUST NOT apply terminal-dependent formatting: no line wrapping, paging, colour, or ANSI escape sequences. Output bytes MUST be identical whether stdout is a TTY, a pipe, a regular file, or `/dev/null`. | must-have |
| FR-87 | The emitted byte sequence MUST be ASCII-only: `0x30`–`0x39` for digits, an optional single leading `0x2D`, and a final `0x0A`. No UTF-8 BOM, no non-breaking spaces, no Unicode minus (U+2212) or en/em dash. | must-have |
| FR-88 | The complete line MUST be emitted as one logical unit (a single write, or writes that are flushed before exit) such that the **last byte** observable on stdout is the `0x0A` terminator. | must-have |
| FR-89 | If writing to stdout fails (e.g., closed pipe / `EPIPE`, disk full on a redirected file), the program MUST NOT surface a language traceback; it MUST write at most one diagnostic line to **stderr** and terminate with a non-zero status. | must-have |
| FR-90 | On any output-write failure the program MUST NOT exit with status `0` (no false success). | must-have |
| FR-91 | stdout MUST be flushed before the process terminates, so the result is never silently lost when stdout is a pipe or a file. | must-have |
| FR-92 | Rendering MUST be exact for sums of **arbitrary magnitude**: a result with thousands of digits MUST be printed in full, with no truncation, rounding, scientific notation, or ellipsis. | must-have |
| FR-93 | Rendering MUST be deterministic and pure: for a given integer value `S`, the produced byte sequence is always the same, independent of locale, environment variables, host, or run order. | must-have |
| FR-94 | No result value may be suppressed. Only argument/arity/parse failures (owned by F-1 and F-2) suppress output; a computed result — including `0` — is always printed. | must-have |
| FR-95 | The rendering MUST be idempotent under shell consumer use: a consumer capturing stdout MUST receive exactly the number plus one newline, with no trailing blank line. | must-have |

#### Non-Functional Requirements (NFR)

| ID | Requirement | Target / Measurement |
|---|---|---|
| NFR-46 | Output performance: rendering + emission of a 1000-digit result MUST add less than 50 ms over the F-1/F-2/F-3 processing time on a modern commodity CPU. | Measured wall-clock delta of render+write step, 100 runs, p95 < 50 ms. |
| NFR-47 | Memory: the output path MUST use memory O(n) in the number of output digits, and MUST NOT buffer the whole pipeline beyond the single result line. | Peak RSS with a 100 000-digit result stays proportional to the digit count; no accumulated buffers. |
| NFR-48 | Availability: output MUST have no external dependency — no network, no filesystem read/write, no service, no daemon. The command works fully offline and in a sandbox with only a read-only filesystem. | Run with network disabled and CWD read-only; stdout contract still holds. |
| NFR-49 | Security: the result MUST be written verbatim as data. It MUST NOT be passed through a format string as a template, evaluated, interpreted, or expanded by a shell, and MUST never be used to construct a command. | Code review + test with an adversarial digit string; no evaluation/format expansion path exists. |
| NFR-50 | Privacy: operands and results MUST NOT be logged, telemetered, or duplicated to stderr on the success path. stderr byte count is exactly 0 on success. | Assert captured stderr length == 0 for a corpus of successful runs. |
| NFR-51 | Data residency/persistence: the process MUST NOT persist operands or results to disk, temp files, caches, history, or environment variables during normal operation. | Filesystem-snapshot diff before/after a run shows no writes outside the redirected stdout sink. |
| NFR-52 | Determinism/portability of output: `LANG`, `LC_ALL`, `LC_NUMERIC`, `PYTHONHASHSEED`, and terminal type MUST NOT change the output bytes. | Same invocation across locales `C`, `en_US.UTF-8`, `de_DE.UTF-8`, `ar_EG.UTF-8` yields byte-identical stdout. |
| NFR-53 | Deployment/environment: Python 3 standard library only; no third-party packages; runs on Linux, macOS, and Windows invoked from a POSIX-style shell; no build step beyond byte-compilation. | Runs green in a clean interpreter with an empty site-packages for third-party imports. |
| NFR-54 | Output-sink robustness: the contract MUST hold when stdout is a TTY, a pipe, a regular file, a FIFO, or `/dev/null`. | Byte-level assertions per sink type. |
| NFR-55 | Reliability: the success path emits exactly one line and exactly one terminator; partial lines are never left terminated mid-number. | `wc -l` == 1 and `wc -c` == len(rendered)+1 on success. |
| NFR-56 | Observability: exit status is the machine-readable outcome signal (`0` success, non-zero failure); stderr carries at most one diagnostic line per failure and is empty on success. | Exit-code and stderr-length assertions across the test matrix. |
| NFR-57 | Composability/usability: stdout MUST be directly consumable by shell substitution and pipelines, e.g. `x=$(add 2 3)` yields `5` with no whitespace stripping required. | Shell-level end-to-end test asserting the captured variable equals the bare number. |
| NFR-58 | Internationalization: output digits are ASCII and MUST NOT be subject to locale digit shaping, grouping, or RTL bidi marks. | Locale matrix comparison (see NFR-52); no U+200E/U+200F/U+0660-U+0669 in output. |
| NFR-59 | Encoding robustness: emission MUST succeed under a restrictive stdout encoding (e.g., `PYTHONIOENCODING=ascii` or `=latin-1`) because the payload is ASCII. | Run with `PYTHONIOENCODING=ascii`; output bytes unchanged, exit status `0`. |
| NFR-60 | Testability: the output contract MUST be verifiable byte-for-byte by capturing stdout/stderr and the exit status of a subprocess. | Test suite asserts raw byte sequences (hex) and exit codes. |

#### User Stories (US)

| ID | Story | Priority |
|---|---|---|
| US-46 | As a command-line user, I want the sum printed on stdout, so that I can read the answer directly in my terminal. | must-have |
| US-47 | As a shell scripter, I want stdout to be exactly the number followed by one newline, so that `x=$(add 2 3)` gives me `5` without extra text. | must-have |
| US-48 | As a shell scripter, I want exit status `0` on a printed result, so that I can branch on `$?` reliably. | must-have |
| US-49 | As a pipeline author, I want stdout to contain nothing but the result, so that `add 2 3 \| wc -c` prints `2`. | must-have |
| US-50 | As a user redirecting output to a file, I want exactly one trailing newline, so the file is a valid POSIX text file and `wc -l` prints `1`. | must-have |
| US-51 | As a user computing negative sums, I want a single leading `-` on negative results, so that sign is unambiguous downstream. | must-have |
| US-52 | As a user computing very large sums, I want the complete exact digits, so that I can copy the value into another tool without losing precision. | must-have |
| US-53 | As a user, I want no banners, labels, or prompts around the number, so that output can be pasted straight into another command. | must-have |
| US-54 | As a user on a system with a non-UTF-8 locale, I want the result to still print correctly, so that the tool is usable everywhere. | should-have |
| US-55 | As a user whose stdout sink fails (broken pipe, full disk), I want a short error message and a non-zero exit rather than a Python traceback, so that the failure is diagnosable in a pipeline. | should-have |
| US-56 | As a maintainer, I want the rendering to be locale-independent and deterministic, so that tests are stable across CI environments. | must-have |
| US-57 | As a user capturing output into a variable, I want no trailing blank line, so that downstream string comparisons are not off by a newline. | should-have |

---

### Behaviour (what it must do)

1. F-4 is entered only after F-1 has validated argument arity and F-2 has validated both operands against the integer grammar, and F-3 has produced the exact sum `S`.
2. F-4 converts `S` into its canonical decimal string `R`:
   - sign handling per `BR-2`,
   - zero handling per `BR-3`,
   - no leading zeros per `BR-4`,
   - no separators or exponents per `BR-5`.
3. F-4 appends exactly one `\n` to `R`, producing the payload `P = R + "\n"` (`BR-6`).
4. F-4 writes `P` to stdout, then flushes stdout so the bytes are observable by the parent process before termination (`BR-9`, `FR-91`).
5. F-4 writes nothing to stderr and returns exit status `0` (`FR-84`, `FR-85`).
6. If any step of the write/flush fails, F-4 follows the error-handling path (`EH-1`–`EH-5`) instead of reporting success.
7. F-4 performs no arithmetic, no re-validation of operands, and no re-parsing of arguments.

**Data model (DM)**

| ID | Item | Description |
|---|---|---|
| DM-1 | `S` | The exact integer sum produced by F-3. Arbitrary precision; may be negative, zero, or positive; unbounded magnitude. Consumed read-only. |
| DM-2 | `R` | Canonical decimal string form of `S`. Matches `/^-?(0\|[1-9][0-9]*)$/`. ASCII only, non-empty, no leading zeros (except `"0"`), no `+`. |
| DM-3 | `P` | The emitted payload: `R` concatenated with exactly one `"\n"`. Byte length `= len(R) + 1`. |
| DM-4 | Exit status | Process outcome signal: `0` = result emitted; non-zero = failure (usage/parse errors owned by F-1/F-2; output-write failure owned by F-4, see `EH-1`). |

---

### Business rules

| ID | Rule |
|---|---|
| BR-1 | **Single-line contract.** The result is exactly one line: `R` followed by one `\n`. There is no preceding blank line, no trailing blank line, and no second line. |
| BR-2 | **Sign rendering.** Sign is emitted only for negative values, as a single leading `-` (U+002D). Positive values carry no sign character. `+` is never emitted, even if the operands carried `+` signs. |
| BR-3 | **Zero is canonical.** Any result with value zero renders as the single character `0`. `-0`, `+0`, `00`, `-00`, and empty output are all forbidden representations of zero. |
| BR-4 | **No leading zeros.** The digit sequence begins with a non-zero digit unless the value is exactly zero, in which case it is the single digit `0`. Input leading zeros accepted by F-2 are normalized away in output. |
| BR-5 | **No decoration.** No grouping separators, decimal point, exponent, unit, currency symbol, label, or prefix (e.g. `=`, `sum:`, `result:`) may be emitted. |
| BR-6 | **Exactly one terminator.** The line terminator is exactly `\n` (U+000A). `\r\n` (CRLF) and a missing terminator are both non-conforming. |
| BR-7 | **stdout is result-only; stderr is diagnostics-only.** The two streams are never mixed. On success stderr is byte-empty; on failure stdout carries no diagnostic. |
| BR-8 | **Exit status reflects emission.** Status `0` is emitted only if the full payload was written and flushed. Any output failure yields a non-zero status. |
| BR-9 | **Flush before exit.** The payload must be flushed before process termination so that a parent reading a pipe or file sees the complete line. |
| BR-10 | **Presentation is value-determined, not environment-determined.** Locale, terminal type, redirection target, and environment variables must not change the bytes produced for a given `S`. |
| BR-11 | **Zero-length rendering is impossible.** A successful run always emits at least two bytes: the shortest case is `0\n`. |
| BR-12 | **No partial-line success.** The program must never exit `0` having emitted part of a line, and must never emit the terminator before the full digit sequence is written (except as a consequence of an unrecoverable failure, which must be non-zero per `BR-8`). |

---

### Validation

| ID | Validation | Failure handling |
|---|---|---|
| V-1 | **Conformance to `DM-2`:** after rendering, `R` must match `/^-?(0\|[1-9][0-9]*)$/`. | Internal invariant violation; must not occur. If it does, treat as an internal error, emit one diagnostic line to stderr, exit non-zero (`EH-5`). |
| V-2 | **Non-empty:** `R` must contain at least one character. | As V-1. |
| V-3 | **ASCII-only:** every byte of `P` must be in `{0x2D} ∪ [0x30..0x39] ∪ {0x0A}`, with `0x2D` permitted only at index 0 and `0x0A` only at the final index. | As V-1. |
| V-4 | **Single terminator:** `P` must end with exactly one `0x0A`, and `0x0A` must not appear anywhere else in `P`. | As V-1. |
| V-5 | **No whitespace other than the terminator:** `R` must contain no spaces, tabs, non-breaking spaces, or Unicode line separators. | As V-1. |
| V-6 | **Round-trip value fidelity:** parsing `R` back as a base-10 integer must yield exactly `S` (no digit loss, no truncation, no sign error). | As V-1; asserted in tests. |
| V-7 | **Byte-length consistency:** observed stdout byte count must equal `len(R) + 1`. | Test assertion failure; indicates a rendering/emission defect. |

---

### Edge cases

| ID | Situation | Required behaviour |
|---|---|---|
| EC-1 | Sum is `0` (e.g. `add 0 0`, `add 5 -5`). | Emit `0\n`; exit `0`; stderr empty. Zero is printed, never suppressed. |
| EC-2 | Operand is `-0` or `+0` and the sum is zero (e.g. `add -0 0`). | Emit `0\n`. Never `-0`, `+0`, or `00`. |
| EC-3 | Both operands carry leading zeros (e.g. `add 007 +00042`). | Emit the normalized value `49\n`; the leading zeros must not survive into output. |
| EC-4 | Result is a single-digit negative (e.g. `add -2 -3`). | Emit exactly three bytes: `2D 35 0A` (`-5\n`). |
| EC-5 | Result crosses a magnitude boundary (e.g. `add 99999999999999999999 1`). | Emit the full multi-digit result `100000000000000000000\n`, no separators, no exponent. |
| EC-6 | Result is negative and large (e.g. `add -99999999999999999999 -1`). | Emit `-100000000000000000000\n` with a single leading `-`. |
| EC-7 | Result has thousands of digits (e.g. operands of 2000 digits each). | Emit every digit in full on one logical line; no truncation, no ellipsis, no wrapping inserted by the program. |
| EC-8 | Result would be positive but an operand had an explicit `+` (e.g. `add +2 +3`). | Emit `5\n` — the `+` is never propagated to output (`BR-2`). |
| EC-9 | stdout is a terminal. | Emit the same bytes as any other sink; no colour, paging, or TTY-specific formatting (`FR-86`). |
| EC-10 | stdout is a pipe whose reader exits early (broken pipe / `EPIPE`). | Do not emit a traceback; emit at most one stderr diagnostic line; exit non-zero (`EH-1`, `FR-89`, `FR-90`). |
| EC-11 | stdout is redirected to a file on a full filesystem (`ENOSPC`). | Same as EC-10: no traceback, one stderr line, non-zero exit. |
| EC-12 | stdout is `/dev/null`. | Write succeeds; exit `0`; stderr empty. Sink semantics are the OS's concern, not the program's. |
| EC-13 | stdout encoding is restricted (`PYTHONIOENCODING=ascii`). | Emission still succeeds byte-identically because the payload is ASCII (`NFR-59`). |
| EC-14 | Locale sets a grouping/decimal convention (`LC_NUMERIC=de_DE.UTF-8`). | Output bytes are unchanged (no `.` or `,` grouping) (`BR-10`, `NFR-52`). |
| EC-15 | Result is exactly one digit, positive (e.g. `add 2 3`). | Emit exactly two bytes: `35 0A` (`5\n`). |
| EC-16 | Consumer uses command substitution (`x=$(add 2 3)`). | `x` equals `5`; no trailing blank line (`US-57`). |

---

### Error handling

| ID | Condition | Required handling |
|---|---|---|
| EH-1 | stdout write fails with `EPIPE` / `BrokenPipeError` (downstream consumer closed the pipe). | Suppress the interpreter traceback. Write at most one single-line diagnostic to stderr. Terminate with a non-zero status (`FR-89`, `FR-90`). Exit status used: `1` (see `OQ-1`). |
| EH-2 | stdout write fails with an I/O error other than a broken pipe (e.g. `ENOSPC`, `EIO`, `EACCES` on the redirect target). | Same as `EH-1`: single stderr diagnostic, non-zero exit, no traceback. |
| EH-3 | stdout flush fails at process shutdown. | The failure MUST NOT be swallowed into a `0` exit status; non-zero exit and (best-effort) one stderr diagnostic. Suppress any traceback emitted by interpreter shutdown. |
| EH-4 | `S` is an internal value that cannot be rendered per `V-1` (invariant violation; should be unreachable). | Emit one diagnostic line to stderr, emit nothing to stdout, exit non-zero. Never emit a malformed line with exit `0`. |
| EH-5 | Any unexpected exception occurs while rendering or emitting. | Suppress the traceback, emit at most one stderr diagnostic line, emit nothing further to stdout, exit non-zero. |
| EH-6 | Arity or operand-grammar failure (owned by F-1/F-2). | F-4 is not entered. stdout receives nothing; the diagnostic and exit status `2` are F-1/F-2's contract and are not re-specified here. |
| EH-7 | A diagnostic is required (any of `EH-1`–`EH-5`). | The diagnostic MUST go to stderr only, MUST be a single line, and MUST NOT contain a language traceback or the operand/result values (per `NFR-50`). |
| EH-8 | Partial output has already been written when a failure is detected. | Do not attempt to "repair" the line; ensure the exit status is non-zero so consumers do not treat the partial line as a successful result (`BR-12`, `FR-90`). |

---

### Acceptance criteria

| ID | Criterion | Verified by |
|---|---|---|
| AC-1 | `add 2 3` writes exactly the bytes `35 0A` (`5\n`) to stdout, writes 0 bytes to stderr, and exits `0`. | Subprocess capture of raw bytes + exit code. |
| AC-2 | `add -2 -3` writes exactly `2D 35 0A` (`-5\n`), stderr empty, exit `0`. | Byte-level assertion. |
| AC-3 | `add 2 -3` writes exactly `2D 31 0A` (`-1\n`), stderr empty, exit `0`. | Byte-level assertion. |
| AC-4 | `add -2 3` writes exactly `31 0A` (`1\n`) — no `+`, no leading zero, stderr empty, exit `0`. | Byte-level assertion. |
| AC-5 | `add 0 0` writes exactly `30 0A` (`0\n`), exit `0`. Zero is printed, not suppressed. | Byte-level assertion. |
| AC-6 | `add -0 0` writes exactly `30 0A` (`0\n`) — never `-0`. | Byte-level assertion. |
| AC-7 | `add 007 +00042` writes exactly `34 39 0A` (`49\n`) — input leading zeros and the `+` sign do not appear in output. | Byte-level assertion. |
| AC-8 | For a sum of arbitrary magnitude (e.g. 1000+ digits), stdout contains the full exact digits with no separators, no exponent, no truncation; byte count equals digit count + sign + 1. | Length + regex + round-trip parse assertions. |
| AC-9 | On every success case, captured stderr length is exactly `0`. | `len(stderr) == 0` across the success corpus. |
| AC-10 | On every success case, stdout ends with exactly one `0x0A`, contains no other `0x0A`, no `0x0D`, and no whitespace bytes other than the terminator. | Byte scan assertion. |
| AC-11 | `add 2 3 \| wc -c` prints `2` and `add 2 3 \| wc -l` prints `1`. | Shell pipeline integration test. |
| AC-12 | `x=$(add 2 3)` results in `x` equal to `5` (no trailing blank line, no surrounding whitespace). | Shell substitution test. |
| AC-13 | Output bytes are byte-identical across `LC_ALL=C`, `LC_ALL=en_US.UTF-8`, `LC_ALL=de_DE.UTF-8`, and `PYTHONIOENCODING=ascii`. | Locale/encoding matrix byte comparison (`NFR-52`, `NFR-59`). |
| AC-14 | Output bytes are byte-identical when stdout is a TTY (pty), a pipe, a regular file, and `/dev/null`. | Sink matrix byte comparison (`NFR-54`). |
| AC-15 | When the stdout pipe is closed before the write (`add 2 3 \| head -c 0`), the process does not print a traceback, emits at most one stderr line, and exits non-zero. | Integration test inspecting stderr for traceback markers and checking exit code ≠ 0. |
| AC-16 | When stdout is redirected to a full filesystem, the process exits non-zero with at most one stderr line and no success indication. | Fault-injection test (small tmpfs). |
| AC-17 | Exit status is `0` if and only if the complete payload was flushed to stdout. | Paired assertion over success and injected-failure cases (`BR-8`). |
| AC-18 | Rendering `S = 0`, `S = 5`, `S = -5`, `S = 10^n`, and `S = -(10^n)` each produces output matching `/^-?(0\|[1-9][0-9]*)\n$/`. | Regex assertion over the boundary corpus. |
| AC-19 | Round-tripping the emitted digits back to an integer yields the original `S` for a randomized corpus of large signed values. | Property test (`V-6`). |
| AC-20 | No file, temp artifact, cache, or log is created or modified by a successful run (outside the redirected stdout sink). | Filesystem-diff assertion (`NFR-51`). |
| AC-21 | On the success path, no non-zero exit and no stdout output containing digits is produced for arity/grammar failures — those cases keep stdout empty (F-1/F-2 contract preserved, not overridden). | Integration test with `add 1`, `add 1 2 3`, `add x 1`. |

---

### API behaviour

The public interface of F-4 is a **process-level contract** (a CLI is the API here; no library, HTTP, or RPC surface is introduced).

| ID | Surface | Contract |
|---|---|---|
| API-1 | **stdin** | Not read. F-4 MUST NOT block on or consume stdin under any circumstance. |
| API-2 | **stdout** | Success: the single line `R\n` (bytes `[0x2D]? [0x30-0x39]+ 0x0A`), flushed before exit. Failure: either nothing, or a partial line preceding a non-zero exit (`EH-8`). Never a diagnostic. |
| API-3 | **stderr** | Success: exactly 0 bytes. Failure: at most one single line, no traceback, no operand/result values leaked (`EH-7`, `NFR-50`). |
| API-4 | **Exit status** | `0` = sum emitted and flushed. `1` = output-write/flush failure owned by F-4. `2` = usage/arity/parse error owned by F-1/F-2. Any other non-zero status indicates an unexpected internal error (`EH-5`). |
| API-5 | **Invocation form** | No options, flags, or environment-variable knobs affect F-4's output. Behaviour is a pure function of the two operands (after F-1/F-2 processing) for a given stdout sink outcome (`BR-10`). |
| API-6 | **Composability guarantee** | The stdout payload is a valid POSIX text line and a valid base-10 integer token; it is safe to feed to `$(...)`, `xargs`, `wc`, `sort -n`, or another `add` invocation without post-processing. |

**Byte-level conformance examples**

| Invocation | Computed sum (`S`, from F-3) | stdout (hex) | stdout (visible) | stderr | Exit |
|---|---|---|---|---|---|
| `add 2 3` | 5 | `35 0A` | `5\n` | (0 bytes) | 0 |
| `add -2 -3` | -5 | `2D 35 0A` | `-5\n` | (0 bytes) | 0 |
| `add 2 -3` | -1 | `2D 31 0A` | `-1\n` | (0 bytes) | 0 |
| `add -2 3` | 1 | `31 0A` | `1\n` | (0 bytes) | 0 |
| `add 0 0` | 0 | `30 0A` | `0\n` | (0 bytes) | 0 |
| `add -0 0` | 0 | `30 0A` | `0\n` | (0 bytes) | 0 |
| `add 007 +00042` | 49 | `34 39 0A` | `49\n` | (0 bytes) | 0 |
| `add 99999999999999999999 1` | 100000000000000000000 | `31` + `30`×20 + `0A` | `100000000000000000000\n` | (0 bytes) | 0 |
| `add -99999999999999999999 -1` | -100000000000000000000 | `2D 31` + `30`×20 + `0A` | `-100000000000000000000\n` | (0 bytes) | 0 |
| `add 2 3` (pipe closed early) | 5 | (payload cannot be delivered) | — | 1 diagnostic line | 1 |
| `add 1 2 3` (arity error, F-1) | n/a — F-4 not entered | (empty) | (empty) | 1 diagnostic line (F-1) | 2 |

**Non-conforming outputs (explicitly forbidden):** `5` with no newline; `5\n\n`; `5\r\n`; ` 5\n`; `5 \n`; `+5\n`; `05\n`; `-0\n`; `0.0\n`; `5e0\n`; `sum: 5\n`; `=5\n`; `\n` alone; empty stdout with exit `0`; ANSI-coloured digits; any stdout diagnostic on a failure.

---

### Priority

**Priority: must-have.**

Rationale: printing the result is the sole observable purpose of the command — `add 2 3` → `5` is the stated vision of the brief. Without F-4 the program computes a value that no user or downstream process can observe. All FRs in this section are `must-have`; the should-have items are limited to the degradation-path and convenience behaviours captured in US-54, US-55, and US-57 (robust failure reporting and shell-substitution ergonomics), which do not alter the success-path contract.

---

### Open questions

| ID | Question | Why it blocks nothing right now |
|---|---|---|
| OQ-1 | F-1/F-2 define exit status `2` for usage/parse errors and `0` for success. This section proposes exit status `1` for an output-write/flush failure (broken pipe, disk full) to keep the categories distinguishable. Confirm `1` is the desired code, or supply the preferred code. | Defaulted to `1` (`API-4`, `EH-1`, `EH-2`); tests assert only "non-zero" for these paths in `AC-15`/`AC-16` so the spec is usable either way. |
| OQ-2 | On a broken-pipe failure (`EC-10`), should the program write a diagnostic line to stderr at all, or exit silently with a non-zero status (the common Unix convention for SIGPIPE-style exits)? | Defaulted to "at most one diagnostic line" (permissive: silent is compatible with "at most one"); confirm if silence is mandatory. |
| OQ-3 | Should an output-write failure attempt to align with shell convention by terminating on `SIGPIPE` rather than catching the error? | Not required by the brief; the brief constrains only the success path. Defaulted to catching and exiting non-zero without a traceback (`FR-89`). |

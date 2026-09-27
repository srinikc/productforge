## F-5: Exit-status contract

**Feature ID:** F-5
**Depends on:** F-1 (`add` command entry point), F-2 (two positional integer operands), F-3 (integer addition), F-4 (print result to stdout) — F-5 consumes the *outcome categories* already produced by F-1, F-2, F-3 and F-4 and owns only the **process exit status** as an externally observable interface. F-5 does **not** re-define arity rules (F-1), the operand grammar (F-2), arithmetic (F-3), or stdout rendering (F-4); it fixes the status value that each of those outcomes must yield, and the invariants that hold between the status and the two byte streams.

### Requirements

#### Functional Requirements (FR)

| ID | Requirement | Priority |
|---|---|---|
| FR-101 | The process MUST terminate with exit status `0` **iff** exactly two operands were supplied, both satisfied the F-2 operand grammar, and the F-4 rendering of the sum was written to stdout as a complete line. | must-have |
| FR-102 | The process MUST terminate with exit status `2` when argument arity is not exactly two operands (zero, one, or three-plus arguments), writing nothing to stdout. | must-have |
| FR-103 | The process MUST terminate with exit status `2` when any supplied operand fails the F-2 operand grammar, writing nothing to stdout. | must-have |
| FR-104 | The process MUST terminate with exit status `1` when an unexpected internal failure or an output (I/O) failure prevents completion, including resource exhaustion and a closed/broken stdout destination. Status `1` MUST NOT be produced by any input-condition error. | must-have |
| FR-105 | The set of exit statuses the process may produce for **any** input is exactly `{0, 1, 2}`. No other status, no negative status, and no termination by signal-as-control-flow may occur on a defined input. | must-have |
| FR-106 | Every outcome MUST map deterministically to exactly one row of the normative status table (`BR-1`). The same argv, environment, and stream destinations MUST always yield the same status. | must-have |
| FR-107 | On exit status `0`, stderr MUST be empty (zero bytes) and stdout MUST contain exactly the F-4 rendering (base-10 digits followed by exactly one `\n`), with nothing else. | must-have |
| FR-108 | On exit status `2`, stdout MUST be empty (zero bytes) and stderr MUST contain at least one non-empty, single-line diagnostic terminated by `\n`. | must-have |
| FR-109 | On exit status `1`, stderr MUST contain at least one non-empty, single-line diagnostic terminated by `\n`, unless stderr itself is unwritable, in which case the status `1` is still returned. | must-have |
| FR-110 | The process MUST NOT emit an unhandled-exception traceback on any outcome reachable from user input. Any caught internal failure is reported as a single-line diagnostic, retaining status `1` (`FR-104`). | must-have |
| FR-111 | Validation precedence MUST be: arity first (F-1), then operand grammar (F-2), then arithmetic and rendering (F-3/F-4). The first failing stage determines the status; later stages MUST NOT run once an earlier stage fails. | must-have |
| FR-112 | When both an arity error and an operand-grammar error are present (e.g., three arguments where the second is also malformed), the status MUST be `2` and the diagnostic MUST describe the arity error. | should-have |
| FR-113 | Exit status MUST be delivered after stdout and stderr contents are flushed, so that observing status `0` implies the sum line was fully written to the stream (subject to `EC-4`). | must-have |
| FR-114 | Exit status `0` MUST NOT be returned if any byte was written to stderr, or if a write of the sum line failed or was truncated. | must-have |
| FR-115 | Exit status MUST be independent of locale, `LANG`/`LC_*`, `TERM`, environment variables, current working directory, TTY-vs-pipe destination, file descriptors 0/1/2 reassignment, umask, and wall-clock time. | must-have |
| FR-116 | Exit status MUST NOT depend on the magnitude, sign, or textual length of the operands or the result, beyond whether they pass the F-2 grammar. | must-have |
| FR-117 | Exit status MUST be observable as-is by the invoking shell (e.g., `add 2 3; echo $?` → `0`; `add 2; echo $?` → `2`) and MUST be in the range `0`–`255`. | must-have |
| FR-118 | Statuses `3`–`125` MUST remain unallocated and MUST NOT be produced. Statuses `126`, `127`, and `128+` MUST NOT be produced (they are reserved to the shell for command-not-executable, command-not-found, and signal termination). | must-have |
| FR-119 | "No arguments" and "empty-string argument(s)" MUST both yield status `2`, with nothing on stdout. | must-have |
| FR-120 | Exit status for a *successful* run MUST be reachable when stdin is closed, absent, or not readable; the process MUST NOT read from stdin in any case. | must-have |
| FR-121 | The status value MUST be set by an explicit, documented path in the program. The program MUST NOT rely on implicit interpreter defaults, implicit fall-through, or the value of the last evaluated expression to produce status `0`. | must-have |
| FR-122 | The exit-status mapping is part of the public interface. Any change to a status value or to which condition yields it is a breaking interface change requiring a spec revision; it MUST NOT be altered silently (`FR-105`, `FR-106`). | must-have |

#### Non-Functional Requirements (NFR)

| ID | Requirement | Priority |
|---|---|---|
| NFR-61 | **Performance** — Total wall-clock time from process start to exit-status availability MUST be ≤ 250 ms for operand strings up to 1,000 digits on a modern desktop CPU; status determination MUST add no measurable latency beyond the F-4 output emission. | must-have |
| NFR-62 | **Performance** — Determining the status MUST be O(1) in the number of operands (fixed at two) and MUST NOT introduce any extra pass over the result beyond what F-4 already performs. | should-have |
| NFR-63 | **Scalability / availability** — The status mapping MUST be total and deterministic: for 100% of invocations, exactly one table row matches. There is no retry, no partial availability, and no stateful degradation. | must-have |
| NFR-64 | **Robustness** — Correct status behaviour MUST hold under fuzzed/random argv (including binary bytes, control characters, very long arguments, and non-UTF-8 byte sequences) with no unhandled exceptions and no status outside `{0, 1, 2}`. | must-have |
| NFR-65 | **Security** — Diagnostics MUST NOT leak interpreter internals, stack frames, absolute filesystem paths, environment dumps, or the raw unescaped argument. Echoed argument text MUST be control-character-escaped and truncated (≤ 64 characters) before being written to stderr. | must-have |
| NFR-66 | **Security** — Arguments MUST be treated as inert data only; no evaluation, no shell invocation, no path resolution, and no file access may be triggered by argument content, and no argument content may influence the status except through F-2 grammar validation. | must-have |
| NFR-67 | **Data handling / residency** — The process MUST persist nothing and read nothing from disk or network; operands and result exist only in process memory, and the only bytes leaving the process are on stdout and stderr. No telemetry, no logs, no temp files. | must-have |
| NFR-68 | **Deployment / environment** — Runs on Linux and macOS with a POSIX-style shell and a Python 3 standard-library runtime only; no environment variables, config files, or companion processes are required to produce the documented statuses. | must-have |
| NFR-69 | **Portability** — Statuses `0` and `2` (and the reserved `1`) MUST be observable identically under `sh`, `dash`, `bash`, and `zsh`, and MUST remain meaningful when the status is truncated to the low 8 bits. | must-have |
| NFR-70 | **Observability** — The pair (exit status, single-line stderr diagnostic) MUST be sufficient to diagnose any failure without additional tooling or debug output. | should-have |
| NFR-71 | **Stream safety** — Behaviour MUST be defined and non-traceback for stdout/stderr redirected to a file, a pipe, `/dev/null`, or closed before invocation. | must-have |
| NFR-72 | **Resource limits** — Peak memory MUST be O(n) in operand/result length; exhausting memory MUST resolve to status `1` with a diagnostic, never to an unhandled exception or a wrong success status. | should-have |
| NFR-73 | **Terminal usability** — Diagnostics MUST be plain ASCII, single-line, and free of ANSI escape sequences, so they render correctly in dumb terminals, log files, and screen readers. | should-have |
| NFR-74 | **Testability** — The status table MUST be fully verifiable by an automated harness that spawns the process and asserts (status, stdout bytes, stderr bytes) triples, with one case per table row plus each edge case. | must-have |
| NFR-75 | **Compatibility** — Status values MUST remain stable across all patch releases of the tool; only a spec revision may change them. | must-have |

#### User Stories (US)

| ID | Story | Priority |
|---|---|---|
| US-61 | As a **shell user**, I want a successful `add 2 3` to exit `0`, so that `add 2 3 && echo ok` behaves as expected. | must-have |
| US-62 | As a **shell user**, I want a failing `add` to exit non-zero, so that `&&`/`set -e` pipelines stop instead of continuing with a bad value. | must-have |
| US-63 | As a **script author**, I want usage and grammar errors to exit `2` and unexpected failures to exit `1`, so that I can distinguish "bad input, fix the caller" from "tool broke, retry/report". | must-have |
| US-64 | As a **CI author**, I want exit statuses to be deterministic for identical inputs, so that build outcomes are reproducible and cacheable. | must-have |
| US-65 | As a **script author**, I want stdout to be empty when the command fails, so that captured output is never polluted by a partial or bogus number. | must-have |
| US-66 | As a **pipeline author**, I want a broken/closed stdout to produce a clean non-zero status rather than a traceback, so that logs stay readable. | should-have |
| US-67 | As a **security-conscious operator**, I want no stack traces or environment details in stderr, so that failures cannot leak internals into shared logs. | must-have |
| US-68 | As a **user**, I want a one-line explanation on stderr whenever the command fails, so that I know what to change without reading docs. | must-have |
| US-69 | As a **shell user**, I want statuses within `0`–`255`, so that `$?` checks and shell conditionals behave predictably. | must-have |
| US-70 | As an **automation author**, I want the status to be independent of locale, cwd, TTY, and environment, so that containerized runs match my laptop. | must-have |
| US-71 | As a **user**, I want status `0` to guarantee the full sum line was actually delivered, so that I can trust the output I just redirected to a file. | must-have |
| US-72 | As a **tester**, I want a documented, normative status table, so that I can write one assertion per row and prove coverage. | must-have |
| US-73 | As a **maintainer**, I want the status mapping to be frozen as a contract, so that refactors cannot silently break downstream scripts. | must-have |
| US-74 | As a **user** who redirects output to `/dev/null`, I want the exit status to be unaffected by where output goes, so that silencing output does not change control flow. | must-have |
| US-75 | As a **user** adding very large integers, I want the exit status to stay `0` regardless of magnitude, so that big numbers are never mistaken for an error. | must-have |

### Behaviour

`add` exposes a four-way observable interface: the argv it receives, the bytes it writes to stdout, the bytes it writes to stderr, and the integer exit status it returns. This feature specifies the last of those and the invariants tying it to the other three.

1. **Evaluate arity (F-1).** Count the operands. If the count is not exactly two, produce the usage diagnostic on stderr, write nothing to stdout, and stop with status `2`.
2. **Validate operands (F-2).** If either operand fails the digit grammar, produce a single-line diagnostic on stderr naming (escaped, truncated) the offending argument, write nothing to stdout, and stop with status `2`.
3. **Compute and render (F-3, F-4).** Compute the exact sum and render it as a base-10 line. Write it to stdout.
4. **Determine status.** If step 3 completed and the write to stdout was not detected as failed, return `0`. If an internal or output failure occurred at any point, return `1` after emitting a single-line diagnostic.

Stages 1–3 are ordered and mutually exclusive: the first failing stage fixes the status, and no stage may run after an earlier stage has failed (`FR-111`).

### Business Rules

- **BR-1 (Normative status table).** The following mapping is total over all possible inputs and is the single source of truth for exit status:

| # | Outcome | Condition | stdout | stderr | Exit |
|---|---|---|---|---|---|
| T0 | Success | Exactly two operands; both pass the F-2 grammar; sum line written completely | `<base-10 sum>\n` | empty | `0` |
| T1 | Usage error | Operand count is 0, 1, or ≥ 3 | empty | usage diagnostic + `\n` | `2` |
| T2 | Operand error | Operand count is 2; ≥ 1 operand fails the F-2 grammar | empty | single-line operand diagnostic + `\n` | `2` |
| T3 | Internal / I/O failure | Resource exhaustion, unwritable stdout detected, or any unexpected internal failure | empty or partially written | single-line diagnostic (best effort) + `\n` | `1` |

- **BR-2 (Precedence).** Arity before grammar before arithmetic before rendering. Rows T1 and T2 both yield `2`; when both conditions are present, T1's diagnostic (arity) is reported.
- **BR-3 (Status is not a severity ladder).** `1` is reserved for "the tool did not work as designed", never for "the user typed something wrong". Input errors are always `2`.
- **BR-4 (Claim of success).** Status `0` is a claim that stdout holds exactly one line: the base-10 rendering of the sum followed by one `\n`, and stderr is empty. This claim MUST hold whenever `0` is returned.
- **BR-5 (Freshness).** No file, lock, cache, or persistent state participates in status determination; the status is a pure function of argv and the writability of the output streams.
- **BR-6 (Frozen contract).** The table in `BR-1` is an interface. Additions require a spec revision; removals or remappings are breaking changes.
- **BR-7 (Reserved space).** `3`–`125` unallocated; `126`, `127`, and `128+` reserved to the shell and never emitted by this program.

### Validation

- **V-1** — Before returning any status, the program MUST assert that the chosen value is an element of `{0, 1, 2}`.
- **V-2** — Exactly one `BR-1` row MUST match the observed outcome; zero or two matching rows is a defect.
- **V-3** — Status `0` MUST be accompanied by empty stderr; a non-empty stderr with status `0` is a defect (`FR-114`).
- **V-4** — Statuses `2` and `1` MUST be accompanied by a non-empty, single-line stderr diagnostic, except the unwritable-stderr case in `FR-109`.
- **V-5** — For statuses `2` and `1`, stdout MUST be empty (status `1` may allow a detected partial write, per `EC-4`).
- **V-6** — stderr diagnostics MUST contain no traceback markers (`Traceback (most recent call last)`, `File "`), no absolute paths, and no newline-separated multi-line bodies.
- **V-7** — Each `BR-1` row MUST be exercised by an automated case asserting the `(status, stdout, stderr)` triple (`NFR-74`).
- **V-8** — The status MUST be identical across re-runs with the same argv under varied `LANG`, `LC_ALL`, cwd, and stdout destinations (`FR-115`).

### Edge Cases

| ID | Case | Required behaviour |
|---|---|---|
| EC-1 | Zero arguments (`add`) | Status `2`, stdout empty, usage diagnostic on stderr (row T1). |
| EC-2 | One argument (`add 5`) | Status `2`, stdout empty, usage diagnostic (row T1). |
| EC-3 | Three or more arguments (`add 1 2 3`) | Status `2`, stdout empty, usage diagnostic; the extra operands are never summed (row T1). |
| EC-4 | stdout closed or connected to a pipe whose reader has exited (broken pipe / `add 2 3 | head -0`) | No traceback. Status `1` with a single-line diagnostic on stderr; no status `0` is reported. |
| EC-5 | stdout redirected to `/dev/null` | Status `0`; redirection destination does not change the status. |
| EC-6 | Empty-string operand (`add "" 3`) | Status `2` (rows T1/T2), stdout empty; the empty argument is named in the diagnostic. |
| EC-7 | Malformed operand that looks numeric (`add 0x10 3`, `add 1.5 2`, `add " 3" 4`, `add 1_000 2`) | Status `2`, stdout empty (delegated to F-2 validation). |
| EC-8 | Both an arity error and a malformed operand (`add 1 x 3`) | Status `2`; diagnostic describes the arity error (`BR-2`). |
| EC-9 | Very large operands (e.g., 100,000 digits) | Status `0` on success; magnitude never alters the status (`FR-116`). If memory is exhausted, status `1` (`NFR-72`). |
| EC-10 | Negative / zero result (`add -5 5` → `0`) | Status `0`; the value of the result never alters the status. |
| EC-11 | stdin closed or absent | Status is unchanged; stdin is never read (`FR-120`). |
| EC-12 | Non-UTF-8 / binary argv bytes | Status `2` (grammar failure) or `0` (if the bytes are valid digits), never a traceback; diagnostic escapes non-printable bytes. |
| EC-13 | stderr closed | Status still reflects the outcome; status `2`/`1` are returned even though the diagnostic cannot be delivered (`FR-109`). |
| EC-14 | Non-ASCII digit look-alikes (e.g., Arabic-Indic digits) | Status `2`; only ASCII `0`–`9` are accepted (delegated to F-2). |

### Error Handling

| ID | Failure | Handling | Status |
|---|---|---|---|
| EH-1 | Wrong arity | Catch at the entry stage; print usage line to stderr; emit no stdout bytes | `2` |
| EH-2 | Operand fails grammar | Catch before arithmetic; print one line naming the escaped, truncated offending argument | `2` |
| EH-3 | Unexpected internal exception during parse/add/render | Catch at the top level; print a generic single-line diagnostic; suppress the traceback | `1` |
| EH-4 | stdout write failure / broken pipe | Detect the failed write; suppress the traceback; print a single-line diagnostic to stderr if possible; never report `0` | `1` |
| EH-5 | Memory/resource exhaustion | Reduce to a single-line diagnostic where possible; otherwise exit `1` silently on stderr but never `0` | `1` |
| EH-6 | stderr unwritable | Do not attempt retry or re-open; return the status that the outcome dictates | `2` or `1` |

### Acceptance Criteria

| ID | Criterion |
|---|---|
| AC-1 | Given `add 2 3`, when run in a POSIX shell, then stdout is exactly `5\n`, stderr is empty, and `$?` is `0`. |
| AC-2 | Given `add -5 5`, then stdout is exactly `0\n`, stderr is empty, and `$?` is `0`. |
| AC-3 | Given `add`, `add 5`, or `add 1 2 3`, then stdout is empty, stderr is non-empty with one line, and `$?` is `2`. |
| AC-4 | Given `add 1 x`, then stdout is empty, stderr names the offending argument as a single line, and `$?` is `2`. |
| AC-5 | Given `add "" 3`, then stdout is empty and `$?` is `2`. |
| AC-6 | Given any invocation, the observed `$?` is always an element of `{0, 1, 2}` (`FR-105`). |
| AC-7 | Given `add 2 3 | head -0` (reader exits early), no traceback appears on stderr and `$?` is `1`, never `0` (`EC-4`, `FR-114`). |
| AC-8 | Given `add 2 3 > /dev/null; echo $?`, the result is `0` (`EC-5`). |
| AC-9 | Given the same argv run 100 times with varied `LANG`, `LC_ALL`, cwd, and stdout destination, the status is identical every time (`FR-115`, `FR-106`). |
| AC-10 | Given 100,000-digit operands, the run exits `0` with a correct sum line (`FR-116`, `EC-9`). |
| AC-11 | Given any failing run, stderr contains no traceback marker, no absolute path, and exactly one line (`V-6`, `NFR-65`). |
| AC-12 | Given `add 1 x 3` (arity **and** grammar error), `$?` is `2` and the diagnostic describes the arity error (`BR-2`, `FR-112`). |
| AC-13 | Given a fuzzed corpus of random/binary argv values, no run produces a status outside `{0, 1, 2}` and no run produces an unhandled traceback (`NFR-64`, `FR-110`). |
| AC-14 | Given status `0`, stdout parses as exactly one base-10 integer line and stderr is zero bytes (`BR-4`, `FR-107`). |

### API Behaviour

The "API" of this feature is the process boundary.

| ID | Contract element | Specification |
|---|---|---|
| API-1 | **Invocation** | `add <int1> <int2>` — two positional operands, no flags, no options, no environment switches. |
| API-2 | **Return value (exit status)** | Integer in `{0, 1, 2}`: `0` = success (T0); `2` = user/input error (T1, T2); `1` = internal or output failure (T3). |
| API-3 | **stdout contract** | Success: exactly `<base-10 sum>` + `\n` (owned by F-4). Error: zero bytes, except the detected partial-write case which forces status `1`. |
| API-4 | **stderr contract** | Empty on success. Exactly one `\n`-terminated diagnostic line on `2` and `1` (best effort when stderr is unwritable). Diagnostics are ASCII, control-character-escaped, and ≤ 64 chars of echoed argument. |
| API-5 | **Idempotency** | `status(argv, stdout_dest, stderr_dest)` is a pure function; no hidden state, no caching, no ordering effects across invocations. |
| API-6 | **Error signalling** | Out-of-band: the status itself is the machine-readable signal; stderr is the human-readable signal. Neither is emitted in the other's channel. |
| API-7 | **Compatibility surface** | The status values and the condition→status mapping are contractual; changes require a spec revision (`BR-6`, `NFR-75`). |
| API-8 | **Unsupported inputs** | Anything other than exactly two grammar-valid operands is an unsupported input and returns `2`; unsupported inputs MUST NOT be partially processed. |

### Priority

**Overall:** must-have. The exit-status contract is the only machine-readable result of the tool and is a prerequisite for shell composability (`&&`, `||`, `set -e`), scripting, and automated verification.

- **must-have:** `FR-101`–`FR-111`, `FR-113`–`FR-122`; all of `NFR-61`, `NFR-63`–`NFR-69`, `NFR-71`, `NFR-74`, `NFR-75`; `US-61`–`US-65`, `US-67`–`US-75`.
- **should-have:** `FR-112`; `NFR-62`, `NFR-70`, `NFR-72`, `NFR-73`; `US-66`.

- **F-5 local ID scope (non-global):** `AC-1`–`AC-14`, `BR-1`–`BR-7`, `V-1`–`V-8`, `EC-1`–`EC-14`, `EH-1`–`EH-6`, `API-1`–`API-8` are scoped to this feature section and may be reused with different meanings in other feature sections.
- **Cross-references:** F-1 (arity and entry point), F-2 (operand grammar), F-3 (integer addition), F-4 (stdout rendering) are referenced as plain text; their IDs are not re-defined here.

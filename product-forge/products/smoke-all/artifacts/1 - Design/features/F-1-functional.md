## F-1: `add` command entry point

**Feature ID:** F-1
**Feature name:** `add` command entry point
**Summary:** The single feature of the product. A stateless, dependency-free Python 3 CLI that accepts exactly two integer operands, prints their sum to stdout, and exits `0`. All failures are diagnosed on stderr with a non-zero exit status.
**Priority (feature-level):** must-have

---

### Requirements

**Functional requirements (FR ids)**

| ID | Requirement | Priority |
|---|---|---|
| FR-1 | The program MUST be invocable as `add <int1> <int2>` from a POSIX-style shell, accepting exactly two positional operands. | must-have |
| FR-2 | The program MUST parse each operand as an integer using a strict, explicitly-defined decimal integer grammar (see Business rules `BR-1`–`BR-4`). | must-have |
| FR-3 | The program MUST compute the exact arithmetic sum `int1 + int2` using arbitrary-precision integer arithmetic. | must-have |
| FR-4 | On success the program MUST write the result as a base-10 integer string followed by exactly one `\n` (U+000A) to **stdout**, and write nothing to stderr. | must-have |
| FR-5 | On success the program MUST terminate with exit status `0`. | must-have |
| FR-6 | If argument arity is not exactly two operands, the program MUST write a usage/diagnostic message to **stderr**, write nothing to stdout, and terminate with exit status `2`. | must-have |
| FR-7 | If any operand fails the integer grammar (`BR-1`), the program MUST write a single-line diagnostic to **stderr** naming the offending argument, write nothing to stdout, and terminate with exit status `2`. | must-have |
| FR-8 | The program MUST print the usage line to stderr on arity error, in the form `usage: add <int1> <int2>`, followed by the result-free newline-terminated diagnostic. | must-have |
| FR-9 | The program MUST support `-h` / `--help`: print the usage line to **stdout** and exit `0`. The help text MUST share the same usage string used by `FR-8`. | should-have |
| FR-10 | The program MUST be a pure function of its argv: no reads or writes to files, stdin, environment variables, network, or global mutable state; the only observable side effect is the stdout/stderr byte stream and the exit status. | must-have |
| FR-11 | The program MUST consume input **only** from argv. It MUST NOT read stdin (even when stdin is a pipe or TTY), MUST NOT accept operands from environment variables, and MUST NOT read a config file. | must-have |
| FR-12 | The program MUST rely on the Python 3 standard library only and MUST NOT declare any third-party runtime dependency. | must-have |
| FR-13 | The program MUST NOT evaluate, compile, or `eval()`/`exec()` any user-supplied text, and MUST NOT invoke a shell. | must-have |
| FR-14 | The output for a given `(int1, int2)` pair MUST be byte-identical across runs, processes, and machines, independent of locale and current working directory. | must-have |
| FR-15 | The program MUST NOT emit any output on stdout when it exits with a non-zero status, so that `$(add 2 3)` never captures partial or diagnostic text. | must-have |

**Non-functional requirements (NFR ids)**

| ID | Requirement | Target / measurement |
|---|---|---|
| NFR-1 | Latency: end-to-end wall time for `add 2 3` on a reference machine, including interpreter start-up. | p50 < 100 ms, p95 < 250 ms; measured with `time` over 100 runs from a warm cache. |
| NFR-2 | Throughput/statelessness: no state is retained between invocations; N concurrent invocations produce identical, independent results. | 100 parallel invocations yield 100 identical correct outputs and 100 zero exit codes. |
| NFR-3 | Operand scalability: correctness is preserved for integers far beyond 64-bit range. | `add` returns the exact sum for operands of ≥ 1,000 decimal digits (subject to `EC-6`). |
| NFR-4 | Determinism/reliability: identical argv always yields identical stdout bytes and exit status. | Byte-for-byte comparison across 1,000 repeated runs. |
| NFR-5 | Security: no file, network, subprocess, or dynamic-code-execution capability is exercised at runtime. | Static review of the single entry-point module; no imports of `os.system`, `subprocess`, `socket`, `eval`, `exec`, or dynamic `import`. |
| NFR-6 | Input-safety: malicious or oversized operands cannot cause code execution, crashes, or unbounded resource use. | Fuzzing with generated non-numeric, control-character, and 1 MB-length argv strings yields exit `2` or `EC-6` behaviour, never a traceback or hang. |
| NFR-7 | Deployment/environment: single-file, zero-configuration executable; runs in any environment with Python 3 available. | Runs from an empty directory with no env vars set other than `PATH`. |
| NFR-8 | Portability: identical behaviour on CPython 3.8+ across Linux, macOS, and Windows (cmd/PowerShell) including exit status and newline handling. | Same acceptance suite passes on all three platforms. |
| NFR-9 | Availability model: a short-lived, single-process, foreground command with no daemon, service, or listening port; there is no uptime target beyond "runs when invoked". | No process outlives the command; no sockets opened. |
| NFR-10 | Data/residency: no user data is persisted, logged, cached, or transmitted; operands and results exist only in process memory for the lifetime of the invocation. | No file or socket writes observed under filesystem/network tracing. |
| NFR-11 | Locale independence: output digits and separators must not change under any `LC_ALL`/`LANG` value. | `LC_ALL=de_DE.UTF-8 add 1000 1` outputs `1001\n` (never `1.001`). |
| NFR-12 | Observability: the only diagnostic channel is stderr; diagnostics are single-line and machine-greppable. | Diagnostics match a stable prefix; no stack traces leak on the error paths defined in `EC-1`–`EC-6`. |
| NFR-13 | Solo robustness: unexpected internal failure must not surface a Python traceback to the user. | Any unhandled internal exception is converted to a stderr diagnostic with exit status `2` (see `EC-7`). |
| NFR-14 | Terminal-safety: output MUST NOT contain ANSI escapes or other control characters other than the single trailing newline. | Output byte inspection. |
| NFR-15 | Maintainability: the entire feature is implementable in a single module of ≤ 100 source lines with no conditional platform branches in the core arithmetic path. | Source line count and review. |

**User stories (US ids)**

| ID | Story |
|---|---|
| US-1 | As a developer at a shell prompt, I want to type `add 2 3` and see `5`, so that I can compute a value without leaving the terminal. |
| US-2 | As a script author, I want the result on stdout with nothing else, so that I can capture it with `$(add 2 3)` or a pipe. |
| US-3 | As a script author, I want a deterministic exit status, so that I can branch on success (`0`) versus input error (`2`) in shell conditionals. |
| US-4 | As a user who mistyped a command, I want a clear one-line error and a usage line, so that I can correct the invocation immediately. |
| US-5 | As a user with large numbers, I want arbitrary-precision results, so that I am not limited by 32-/64-bit overflow. |
| US-6 | As a new user, I want `add --help` to show the usage line, so that I can learn the command without reading source. |
| US-7 | As a security-conscious operator, I want the tool to touch no files, no network, and no shell, so that I can run it safely in constrained environments. |
| US-8 | As an automation author, I want the command to be stateless and side-effect-free, so that parallel invocations never interfere. |
| US-9 | As an international user, I want digits formatted the same regardless of my locale, so that downstream parsers never break. |
| US-10 | As a maintainer, I want a stdlib-only single-file tool, so that there is nothing to install or vendor. |

---

### Behaviour

1. The process is invoked with `argv` of the form `["add", <operand1>, <operand2>]`.
2. `-h` / `--help` appearing anywhere in argv is intercepted first (FR-9): the usage line is written to stdout followed by `\n`, and the process exits `0`.
3. Otherwise the argument count is checked (FR-1, FR-6). Exactly two operands are required; zero, one, or three-or-more operands is an arity error.
4. Each operand is validated against the integer grammar (`BR-1`) in left-to-right order (FR-2). The first offending operand is reported (FR-7).
5. The sum is computed with Python's arbitrary-precision `int` addition (FR-3).
6. The result is rendered as a base-10 string with a leading `-` only when negative, then written to stdout with exactly one trailing newline (FR-4), and the process exits `0` (FR-5).
7. No other output, prompt, spinner, colour, or timing information is produced on any path (FR-10, NFR-14).
8. The process is fully synchronous: it reads argv, computes, writes, and exits. There is no interaction loop, no stdin polling, and no retry (FR-11).

---

### Business rules

| ID | Rule |
|---|---|
| BR-1 | The accepted integer grammar is: `-?[0-9]+` — an optional single ASCII hyphen-minus `U+002D`, followed by one or more ASCII digits `0`–`9` (`U+0030`–`U+0039`). Nothing else is accepted as an operand. |
| BR-2 | A leading `+` is rejected. Numeric separators (`_`, `,`, spaces, thin spaces, apostrophes) are rejected. Leading zeros are accepted and normalised in the result (`007` → parsed as `7`). |
| BR-3 | Only ASCII digits are accepted. Non-ASCII decimal digits (e.g. Arabic-Indic `٣`, fullwidth `３`), superscripts, Roman numerals, and spelled-out numbers are rejected with exit `2`. |
| BR-4 | Floating-point, scientific, hexadecimal (`0x10`), octal (`0o17`), binary (`0b101`), and `inf`/`nan` style literals are rejected with exit `2`. |
| BR-5 | The operation is mathematically exact integer addition. There is no rounding, saturation, wrap-around, modulus, or floating-point path. |
| BR-6 | `-0` is a valid operand and is equal to `0`; the result of any sum equal to zero is rendered as `0`, never `-0` or `+0`. |
| BR-7 | Addition is commutative and associative for the two-operand case; `add a b` and `add b a` produce identical stdout bytes. |
| BR-8 | Exit statuses are fixed: `0` = success, `2` = usage/operand error. No other status is produced on a designed path. |
| BR-9 | Exit status `2` is the only failure status; the tool never returns `1` for input problems, so scripts can distinguish "bad input" from "unexpected internal failure". |
| BR-10 | Operands are consumed positionally by index. There is no flag parsing other than `-h`/`--help`; flags such as `--base`, `--precision`, or `-v` are **not** part of this feature and MUST be treated as invalid operands, not as options. |
| BR-11 | An operand that begins with `-` and consists solely of digits is a negative number, not an option. The only reserved tokens are the exact strings `-h` and `--help`. |
| BR-12 | The command is stateless: no history, no memoisation, no temp files, no environment mutation. |

---

### Validation

Validation occurs in this strict order; the first failing check determines the diagnostic.

| Step | Check | On failure |
|---|---|---|
| V-1 | `-h` or `--help` present in argv | Print usage to stdout, exit `0` (FR-9) |
| V-2 | `len(argv) - 1 == 2` | Arity error `EC-1`/`EC-2`/`EC-3`, exit `2` |
| V-3 | Operand 1 matches `BR-1` | Diagnostic `EC-4`, exit `2` |
| V-4 | Operand 2 matches `BR-1` | Diagnostic `EC-4`, exit `2` |
| V-5 | Both operands parse under `BR-2`–`BR-4` without accepted-but-unintended forms | Diagnostic `EC-4`, exit `2` |
| V-6 | Result is convertible to a decimal string within the interpreter's configured limit | Diagnostic `EC-6`, exit `2` |

Validation MUST be performed before any arithmetic, and no partial result may be written to stdout on a failed validation (FR-15).

---

### Edge cases

| ID | Case | Required behaviour |
|---|---|---|
| EC-1 | No operands: `add` | Usage + diagnostic → stderr, exit `2`. |
| EC-2 | One operand: `add 2` | Usage + diagnostic → stderr, exit `2`. |
| EC-3 | Three or more operands: `add 2 3 4` | Usage + diagnostic → stderr, exit `2`. No implicit folding of extra operands. |
| EC-4 | Non-integer operand: `add 2 x`, `add 2 3.0`, `add 2 1e3`, `add 2 0x10`, `add 2 +3`, `add 2 1,000`, `add 2 1_000`, `add 2 ٣` | Diagnostic naming the offending argument (`"x"`) → stderr, exit `2`. |
| EC-5 | Empty-string operand: `add "" 3` | Treated as invalid (zero digits, fails `BR-1`), exit `2`. |
| EC-6 | Very large operands whose decimal rendering exceeds the interpreter's int→str digit limit (CPython 3.11+ default 4300 digits) | Diagnostic → stderr, exit `2`. This is an explicit, documented operands-scaling limit, **not** a silent truncation. See `OQ-1`. |
| EC-7 | Unexpected internal exception on any code path | Converted to a single-line stderr diagnostic, exit `2`, never a traceback (`NFR-13`). |
| EC-8 | Zero results reached by negative operands: `add -5 5`, `add 0 -0`, `add -0 -0` | stdout `0\n`, exit `0`. |
| EC-9 | Negative results: `add 2 -5` | stdout `-3\n`, exit `0`. |
| EC-10 | Both operands negative: `add -2 -3` | stdout `-5\n`, exit `0`. |
| EC-11 | Leading zeros: `add 007 0003` | stdout `10\n`, exit `0`. |
| EC-12 | Extremely large positive/negative operands within `EC-6` limits | Exact sum, exit `0` (`NFR-3`). |
| EC-13 | Leading/trailing whitespace in an operand: `add " 2" 3`, `add "2 " 3` | Rejected, exit `2` (whitespace is not part of `BR-1`); the tool never trims argv silently. |
| EC-14 | `add -h 3` / `add 3 --help` | Help wins (`V-1`), usage to stdout, exit `0`. Documented precedence, not an error. |
| EC-15 | argv[0] differs (renamed binary, invoked via symlink or `python -m add`) | Behaviour is unchanged; usage text still names `add`. |
| EC-16 | stdin is a pipe/TTY with buffered data, or closed entirely | Never read; behaviour identical (`FR-11`). |
| EC-17 | Non-UTF-8 argv bytes on a byte-oriented locale | No decode exception surfaces; operand is treated as invalid → exit `2` with diagnostic. |
| EC-18 | Output stream closed early (`add 2 3 | head -c0`) | Broken-pipe condition must not produce a Python traceback (`NFR-13`); process terminates without stdout corruption. |

---

### Error handling

All error paths share one contract: **diagnostic → stderr, stdout empty, exit `2`, single line, no traceback.**

| ID | Condition | stderr content | Exit |
|---|---|---|---|
| EH-1 *(folded into `EC-1`/`EC-2`/`EC-3` messaging)* | Wrong operand count | `usage: add <int1> <int2>` followed by `add: expected exactly 2 integer operands, got <n>` | `2` |
| EH-2 *(folded into `EC-4`)* | Non-integer operand | `usage: add <int1> <int2>` followed by `add: invalid integer operand: '<value>'` | `2` |
| EH-3 *(folded into `EC-6`)* | Result too large to render | `add: operand too large` | `2` |
| EH-4 *(folded into `EC-7`)* | Unexpected internal error | `add: internal error` (no detail, no traceback) | `2` |

Diagnostic stability is required (`NFR-12`): the message text is part of the contract and must not vary by locale, platform, or Python version. If diagnostic text changes, the change is a breaking change for downstream `grep` consumers.

---

### Acceptance criteria

| ID | Criterion |
|---|---|
| AC-1 | `add 2 3` writes exactly the bytes `5\n` to stdout, nothing to stderr, exit status `0`. |
| AC-2 | `add 0 0` → `0\n`, exit `0`. |
| AC-3 | `add -2 -3` → `-5\n`, exit `0`. |
| AC-4 | `add 2 -5` → `-3\n`, exit `0`. |
| AC-5 | `add -5 5` → `0\n` (not `-0`), exit `0`. |
| AC-6 | `add 007 0003` → `10\n`, exit `0`. |
| AC-7 | `add 2 x` → stdout empty, stderr contains the offending value `x`, exit status `2`. |
| AC-8 | `add 2 3 4` → stdout empty, stderr contains `usage: add <int1> <int2>`, exit status `2`. |
| AC-9 | `add` and `add 2` → stdout empty, exit status `2`. |
| AC-10 | `add --help` → stdout contains `usage: add <int1> <int2>\n`, stderr empty, exit status `0`. |
| AC-11 | `add 99999999999999999999 1` → `100000000000000000000\n`, exit `0` (no overflow). |
| AC-12 | `LC_ALL=de_DE.UTF-8 add 1000 1` → `1001\n` (no thousands separator, no locale digits). |
| AC-13 | Running `add 2 3` 1,000 times consecutively yields byte-identical stdout every time (`NFR-4`). |
| AC-14 | Running `add 2 3` 100 times in parallel yields 100 correct outputs and 100 zero exits (`NFR-2`). |
| AC-15 | Colour/escape bytes are absent from stdout and stderr under `TERM=xterm-256color` and `--color=always`-style environments (`NFR-14`). |
| AC-16 | No file descriptor other than stdin/stdout/stderr is opened during a run; no network syscalls occur (`NFR-5`, `NFR-10`). |
| AC-17 | Under `python -W error` and with assertions enabled, no warning or exception escapes to the user on any documented path. |
| AC-18 | `add 2 3 | head -c0` produces no traceback on stderr (`EC-18`). |
| AC-19 | Source imports no module outside the Python standard library and declares no third-party dependency (`FR-12`). |
| AC-20 | Full acceptance suite passes on Linux, macOS, and Windows on CPython 3.8+ (`NFR-8`). |

---

### API behaviour

The "API" of this feature is the process contract (argv in, streams + exit status out). There is no HTTP/RPC/importable library surface for F-1.

| ID | Surface | Contract |
|---|---|---|
| API-1 | `argv` | `["add", <int1>, <int2>]` → success path. |
| API-2 | `argv` | `["add", "-h"]` or `["add", "--help"]` → help path, exit `0`. |
| API-3 | `argv` | Any other length or any non-conforming operand → error path, exit `2`. |
| API-4 | stdout | On success: the exact decimal sum as ASCII/UTF-8 bytes, terminated by one `\n`. On error: zero bytes. |
| API-5 | stderr | On success: zero bytes. On error: usage line plus one diagnostic line (each `\n`-terminated). |
| API-6 | Exit status | `0` success or help; `2` for arity error, operand error, operand-too-large, and internal error. |
| API-7 | stdin | Never read, never blocked on, never closed by the program. |
| API-8 | Filesystem / network / environment | No reads, no writes, no sockets; no environment variable changes behaviour. |
| API-9 | Concurrency | Reentrant by construction; no locks, temp files, or shared state. |
| API-10 | Versioning | The CLI contract is versioned by the tool itself; any change to stdout bytes, exit codes, or diagnostic text is a breaking change for `API-4`/`API-5`/`API-6` consumers. |

---

### Data model (informational)

| ID | Concept | Definition |
|---|---|---|
| DM-1 | Operand | A validated decimal integer literal conforming to `BR-1`, mapped to a Python arbitrary-precision `int`. |
| DM-2 | Result | The exact mathematical sum of `DM-1` and `DM-1`; rendered as `-?[0-9]+` with no leading zeros except the single value `0`. |
| DM-3 | Exit status | Enumerated set `{0, 2}` only, per `BR-8`. |
| DM-4 | Diagnostic | Immutable single-line string written to stderr on failure; part of the observable contract (`NFR-12`). |

---

### Test obligations

| ID | Test | Covers |
|---|---|---|
| T-1 | Positive, negative, zero, mixed-sign, and leading-zero addition cases. | AC-1–AC-6 |
| T-2 | Arity matrix: 0, 1, 3, 4 operands. | AC-8, AC-9 |
| T-3 | Malformed-operand matrix: `x`, `3.0`, `1e3`, `0x10`, `+3`, `1,000`, `1_000`, `٣`, `""`, `" 2"`, `"2 "`. | AC-7 |
| T-4 | Help precedence: `-h`, `--help`, `add -h 3`, `add 3 --help`. | AC-10, EC-14 |
| T-5 | Large-integer cases at and beyond the int→str digit limit. | AC-11, EC-6 |
| T-6 | Locale matrix over `LC_ALL`/`LANG`. | AC-12 |
| T-7 | Determinism and parallel-invocation harness. | AC-13, AC-14 |
| T-8 | Padding and sanitisation checks on stdout/stderr bytes. | AC-15 |
| T-9 | Resource-access audit (files/sockets) under a sandbox. | AC-16 |
| T-10 | Cross-platform acceptance run (Linux/macOS/Windows). | AC-20 |

---

### Open questions

| ID | Question | Blocks |
|---|---|---|
| OQ-1 | For operands whose decimal rendering exceeds CPython 3.11+'s default 4,300-digit int→str limit: is raising the limit (`sys.set_int_max_str_digits`) the desired behaviour, or is the documented "operand too large" error (`EC-6`) the correct contract? | `EC-6`, `NFR-3`, `AC-11` |
| OQ-2 | Should `--version` (or any version string) be added, or is the brief's "one command" scope limited to `-h`/`--help` (FR-9) only? Adding it requires scope approval. | `FR-9`, `BR-10` |
| OQ-3 | Are the exact diagnostic message texts and the choice of exit code `2` (versus `1`) acceptable as a frozen contract, given they are consumed by scripts (`API-5`, `API-6`)? | `BR-8`, `BR-9`, `EH-1`–`EH-4` |

**Priority:** must-have (the sole feature of the product; the tool has no purpose without F-1).

## F-6: Input validation and error message

**Feature ID:** F-6
**Depends on:** F-1 (`add` command entry point), F-2 (two positional integer operands), F-5 (exit-status contract).
**Boundary note:** F-2 owns *whether* an operand is accepted (the grammar). F-1 owns the arity rule and the fact that violations go to stderr with status `2`. F-5 owns the numeric exit status itself. **F-6 owns only the validation *pipeline orchestration* and the *human-readable diagnostic catalogue*** — the ordering of checks, the exact text/format of messages, the safe echoing of offending input, and the invariant that a failing run produces no stdout bytes. F-6 redefines no grammar, no arity rule, and no exit-status value.

### Requirements

#### Functional Requirements (FR)

| ID | Requirement | Priority |
|---|---|---|
| FR-126 | Validation MUST run as a fixed, deterministic pipeline: **(1)** arity check → **(2)** grammar check of the first operand → **(3)** grammar check of the second operand → **(4)** hand-off to computation/output. The first failing stage MUST abort the pipeline; later stages MUST NOT run. | must-have |
| FR-127 | An arity failure (argument count ≠ 2) MUST emit exactly two stderr lines: an error line naming the expected count and the received count, followed by a usage line. | must-have |
| FR-128 | A grammar failure MUST emit exactly one stderr line identifying the offending operand by 1-based position and echoing the offending value verbatim (subject to FR-137/FR-143). | must-have |
| FR-129 | Every emitted diagnostic line MUST be ASCII-only, free of leading and trailing whitespace, and terminated by exactly one `\n` (U+000A). | must-have |
| FR-130 | On any validation failure the program MUST write **zero bytes** to stdout. | must-have |
| FR-131 | On any validation failure the program MUST terminate with exit status `2`, as defined by F-5. | must-have |
| FR-132 | All diagnostics MUST be written to stderr only; stderr MUST be empty on a successful run. | must-have |
| FR-133 | If more than one operand is invalid, the program MUST report **only the first** offender (first operand) and MUST suppress messages about subsequent operands — exactly one diagnostic line is emitted per run for grammar failures. | must-have |
| FR-134 | Validation MUST consume only the process argument vector; it MUST NOT read stdin, environment variables, or any file — with the single exception that it MUST NOT be perturbed by locale/encoding environment variables (see NFR-84). | must-have |
| FR-135 | No input, of any length or byte content, may cause an unhandled exception, traceback, or non-`0`/non-`2` exit status. All rejections are controlled diagnostics. | must-have |
| FR-136 | Every diagnostic MUST begin with the stable, greppable prefix `add: error:` (arity and grammar alike), so that a single log filter captures all failures. | must-have |
| FR-137 | The verbatim echo MUST be rendered in an escaped-printable form: characters outside printable ASCII (U+0020–U+007E) MUST be replaced by a backslash escape (e.g. `\n`, `\t`, `\x1b`, non-ASCII as `\xNN`/`\uNNNN`). A diagnostic MUST be unable to inject extra lines or terminal control sequences. | must-have |
| FR-138 | The program MUST NOT coerce, trim, or auto-correct invalid input. `"2.0"`, `" 3"`, `"1e3"`, `"0x10"`, `"1_000"` and `"3 "` MUST all be rejected, never reinterpreted. | must-have |
| FR-139 | Diagnostics MUST NOT disclose internal implementation detail: no Python tracebacks, no exception class names, no source file paths, no module or function names, no version-build internals. | must-have |
| FR-140 | Arity MUST be checked before grammar: an invocation with three arguments where the first is also malformed MUST produce the **arity** diagnostic. | must-have |
| FR-141 | The diagnostic catalogue MUST be a fixed, closed set of message templates: exactly one distinguishable template per failure class, defined in §Business rules `BR-5`–`BR-7`. | must-have |
| FR-142 | Diagnostic text MUST be emitted in a single fixed language (English) in the C locale and MUST NOT vary with `LC_ALL`, `LANG`, or `PYTHONIOENCODING`. | should-have |
| FR-143 | A verbatim echo longer than 64 characters MUST be truncated to the first 64 characters followed by the three-character marker `...`. | should-have |
| FR-144 | Exit-status selection for validation failures MUST be delegated to F-5; F-6 MUST NOT introduce any status value other than `2`. | must-have |
| FR-145 | Because validation strictly precedes computation and output, no partial or speculative stdout write may ever occur on a failing run. | must-have |

#### Non-Functional Requirements (NFR)

| ID | Requirement | Priority |
|---|---|---|
| NFR-76 | **Performance:** On a failing invocation, the diagnostic MUST be emitted within 50 ms of process start on reference hardware, for total argv length up to 1 MiB. | must-have |
| NFR-77 | **Complexity:** Validation and diagnostic construction MUST be linear, `O(total argv length)`; no quadratic scanning or repeated concatenation of long operand strings. | should-have |
| NFR-78 | **Memory:** Validation MUST NOT allocate a copy of the full argument string beyond the echo buffer bounded by FR-143. | should-have |
| NFR-79 | **Atomicity:** Each diagnostic line MUST be written with a single write operation where the platform permits, so a message is never observed partially interleaved. | should-have |
| NFR-80 | **Scalability/Availability:** The validator is stateless and side-effect-free; concurrency across processes is unlimited (no locks, no temp files, no shared state, no network). | must-have |
| NFR-81 | **Security:** Diagnostics MUST NOT echo environment variables, current working directory, hostname, username, PID, or timestamps; stderr output MUST be derived solely from argv. | must-have |
| NFR-82 | **Determinism:** Identical argv MUST always yield byte-identical stderr and an identical exit status, across runs and machines. | must-have |
| NFR-83 | **Testability (black-box):** Every clause of §Acceptance criteria MUST be verifiable externally by asserting on `(exit_status, stdout_bytes, stderr_bytes)` without importing program internals. | must-have |
| NFR-84 | **Environment/Locale independence:** Output bytes MUST be invariant under `LC_ALL=C`, `LC_ALL=C.UTF-8`, and any other locale setting, and under `PYTHONIOENCODING` overrides. | must-have |
| NFR-85 | **Data/residency:** No data leaves the machine and nothing is persisted — validation writes only to the inherited stderr stream and retains no file, cache, or log. | must-have |
| NFR-86 | **Deployment/environment:** Validation MUST depend only on the Python 3 standard library and the Python runtime; no third-party packages, no network access, no shelling out to external binaries. | must-have |
| NFR-87 | **Coverage:** Every rejection branch enumerated in the F-2 grammar MUST have at least one corresponding test vector in §Test vectors (`T-1`–`T-12`). | should-have |
| NFR-88 | **Robustness:** Argv containing NUL-free non-UTF-8/surrogate-escaped bytes MUST be handled without raising and rendered per FR-137. | should-have |

#### User Stories (US)

| ID | Story | Priority |
|---|---|---|
| US-76 | As a CLI user, I want a clear, single-line message when I supply the wrong number of arguments, so that I can correct the invocation without consulting documentation. | must-have |
| US-77 | As a CLI user, I want the message to tell me *which* argument was rejected and show me exactly what I typed, so that I do not have to guess which of the two operands is at fault. | must-have |
| US-78 | As a shell scripter, I want every failure to produce empty stdout, an explanatory stderr message, and exit status `2`, so that I can branch on the status while still surfacing a useful error to the user. | must-have |
| US-79 | As a tool integrator, I want all failures to share a stable `add: error:` prefix, so that a single grep or regex can capture them in logs. | should-have |
| US-80 | As a security-conscious operator, I want no tracebacks, paths, environment values, or terminal-escape sequences in error output, so that logs are safe to display and forward. | must-have |

### Behaviour

The validator is a pure function of argv producing a triple `(stdout_bytes, stderr_bytes, exit_status)`:

1. **Stage 1 — Arity.** Count positional operands after the program name. If the count is not exactly 2, emit `BR-5` (two lines) and stop.
2. **Stage 2 — First operand grammar.** Apply the F-2 grammar to operand 1. If it fails, emit `BR-6` with position `1` and stop.
3. **Stage 3 — Second operand grammar.** Apply the F-2 grammar to operand 2. If it fails, emit `BR-6` with position `2` and stop.
4. **Stage 4 — Success path.** Hand both accepted operands to F-3/F-4. stderr stays empty; exit status `0`.

Properties of the whole pipeline:

- **Fail-fast, first-error-only (FR-126, FR-133):** exactly one failure is ever reported, even when several inputs are wrong.
- **Silence on success (FR-132):** a successful run writes 0 bytes to stderr.
- **Silence on failure (FR-130, FR-145):** a failing run writes 0 bytes to stdout, because stdout is never opened/written until after validation completes.
- **No side effects:** no files, no temp files, no network, no environment reads affecting output (NFR-85, FR-134).
- **Idempotence (NFR-82):** re-running with the same argv yields byte-identical results.

### Business rules

| ID | Rule |
|---|---|
| BR-1 | **Failure classes are closed.** There are exactly two externally distinguishable failure classes: *arity* and *grammar*. No other class may be introduced. |
| BR-2 | **Arity precedes grammar (FR-140).** Count is validated for all arguments before any individual argument is inspected, so a three-argument call is always an arity error regardless of argument content. |
| BR-3 | **Operand order is significant (FR-133).** Operands are validated left-to-right; the first invalid operand is reported and validation stops there. |
| BR-4 | **Echo fidelity.** The rejected operand is echoed as submitted, after escape rendering (FR-137) and truncation (FR-143). It is never normalised, trimmed, lower-cased, or re-quoted beyond the surrounding single quotes of the template. |
| BR-5 | **Arity template (FR-127).** Exactly two lines, in this order:<br>`add: error: expected exactly 2 operands, got <N>`<br>`add: usage: add <int1> <int2>`<br>where `<N>` is the observed count rendered in decimal (e.g. `0`, `1`, `3`). |
| BR-6 | **Grammar template (FR-128).** Exactly one line:<br>`add: error: invalid integer argument <P>: '<V>'`<br>where `<P>` ∈ {`1`,`2`} is the 1-based operand position and `<V>` is the escape-rendered, possibly truncated echo of the rejected operand. |
| BR-7 | **Template closure (FR-141).** No message other than BR-5 and BR-6 may be emitted by the validator. Additions require an amendment to this rule. |
| BR-8 | **No usage line on grammar failure.** The usage line is emitted only for arity failures; a grammar failure is a single line. |
| BR-9 | **No numeric analysis of invalid input.** The validator MUST NOT attempt to explain *why* an operand was invalid (no "did you mean", no range advice, no radix suggestions) — it reports only position and value. |
| BR-10 | **Zero-hypothesis on exit status (FR-144).** The validator signals failure as a boolean; the concrete status value `2` is applied by the F-5 contract. |

### Validation

| ID | Validation | Applies to | Failure outcome |
|---|---|---|---|
| V-1 | Operand count must equal exactly `2`. | Full argv | BR-5, status `2` |
| V-2 | Operand 1 must satisfy the F-2 operand grammar (optional single sign + one or more ASCII digits, nothing else). | `argv[1]` | BR-6 (`P=1`), status `2` |
| V-3 | Operand 2 must satisfy the F-2 operand grammar. | `argv[2]` | BR-6 (`P=2`), status `2` |
| V-4 | Diagnostics must contain printable ASCII only. | Emitted lines | Internal assertion; never observable |
| V-5 | Emitted lines must be ≤ 256 bytes each, guaranteed by BR-5/BR-6 and truncation FR-143. | Emitted lines | Internal assertion |
| V-6 | stdout must be 0 bytes whenever status ≠ `0`. | Full run | Internal assertion before write |

Validation is *rejection-only*: F-6 performs no semantic normalisation and cannot alter an accepted value — once V-2/V-3 pass, the operand string is forwarded byte-for-byte to F-3.

### Edge cases

| ID | Case | Required behaviour |
|---|---|---|
| EC-1 | No operands (`add`) | Arity error, `<N>` = `0`, BR-5, status `2`. |
| EC-2 | One operand (`add 5`) | Arity error, `<N>` = `1`, BR-5, status `2`. |
| EC-3 | Three-plus operands (`add 1 2 3`) | Arity error, `<N>` = `3` (actual count), BR-5, status `2`. |
| EC-4 | Three-plus operands *and* a malformed first operand (`add 1.5 2 3`) | Arity error wins (BR-2/FR-140); `<N>` = `3`; the malformed operand is not mentioned. |
| EC-5 | Both operands malformed (`add a b`) | Only `P=1` is reported (BR-3). |
| EC-6 | Second operand malformed only (`add 5 2.0`) | `P=2` reported; first operand not mentioned. |
| EC-7 | Empty-string operand (`add "" 2`) | Empty string fails V-2 (no digits) → BR-6 with `<V>` = empty, rendering `invalid integer argument 1: ''`. |
| EC-8 | Operand that is only a sign (`add - 2`, `add + 2`) | Fails V-2 → BR-6, sign echoed. |
| EC-9 | Whitespace-padded operand (`add " 5" 2`) | No trimming (FR-138) → fails V-2 → BR-6 with the leading space visible inside the quotes. |
| EC-10 | Embedded newline in an operand (`add $'1\n2' 3`) | Echo rendered as `1\n2` via FR-137; message remains a single line (never splits). |
| EC-11 | ANSI escape in an operand (`add $'\e[31m5' 2`) | Rendered as `\x1b[31m5`; no control byte reaches the terminal (FR-137, NFR-81). |
| EC-12 | Very long operand (e.g. 100 000 digits then a letter) | Echo truncated to 64 chars + `...` (FR-143); message still ≤ 256 bytes; runtime linear (NFR-77). |
| EC-13 | Non-ASCII operand (`add 5 é`) | Rejected; non-ASCII byte(s) escape-rendered (FR-137, NFR-88). |
| EC-14 | Valid but unusual accepted input (`add +0007 -0`) | **Not** an F-6 error — passes V-2/V-3 and proceeds; F-6 emits nothing. |
| EC-15 | stderr redirected to a closed descriptor | Failure must not raise or change status semantics; the process still exits `2`. |
| EC-16 | stderr redirected to a file | Exactly the template bytes are written, with no trailing whitespace and no extra blank line. |

### Error handling

| ID | Situation | Handling |
|---|---|---|
| EH-1 | Arity violation detected | Emit BR-5 to stderr in one write where possible (NFR-79); stdout untouched; resolve to status `2` via F-5. |
| EH-2 | Grammar violation detected | Emit BR-6 to stderr; stdout untouched; resolve to status `2` via F-5. |
| EH-3 | Unexpected internal error during validation | MUST NOT surface a traceback (FR-135): the program exits `2` with a message from the closed catalogue, and never exits with any other status. |
| EH-4 | Write to stderr fails (EPIPE / closed descriptor) | Swallow the write failure; do not raise; preserve the `2` exit status (EC-15). |
| EH-5 | Multiple simultaneous violations | Report only the first per FR-126/FR-133; no aggregation, no "and also" messages. |
| EH-6 | Malformed bytes in argv | Escape-render (FR-137) rather than decode-fail; no exception (NFR-88). |
| EH-7 | Any failure path | Guarantee the invariant `status ≠ 0 ⟹ stdout_bytes == 0` before any output is attempted. |

### Acceptance criteria

| ID | Criterion (black-box: assert on `status`, stdout bytes, stderr bytes) |
|---|---|
| AC-1 | `add` with 0 arguments → status `2`, stdout `b""`, stderr exactly `b"add: error: expected exactly 2 operands, got 0\nadd: usage: add <int1> <int2>\n"`. |
| AC-2 | `add 5` → status `2`, stdout `b""`, stderr with `got 1` per BR-5. |
| AC-3 | `add 1 2 3` → status `2`, stdout `b""`, stderr with `got 3` and no mention of any operand value. |
| AC-4 | `add 1.5 2` → status `2`, stdout `b""`, stderr exactly `b"add: error: invalid integer argument 1: '1.5'\n"`. |
| AC-5 | `add 5 2.0` → status `2`, stdout `b""`, stderr exactly `b"add: error: invalid integer argument 2: '2.0'\n"`. |
| AC-6 | `add a b` → status `2`, stderr contains exactly one occurrence of `argument 1` and zero occurrences of `argument 2`. |
| AC-7 | `add 1.5 2 3` → status `2`, stderr equals the AC-3 arity output (arity precedes grammar). |
| AC-8 | Every stderr line ends with exactly one `\n`; no line has leading or trailing spaces; total stderr contains no `\r`. |
| AC-9 | stderr output is pure printable ASCII (`0x20`–`0x7E` plus `\n`) for every test vector including EC-10/EC-11/EC-13. |
| AC-10 | No test vector produces a traceback: `b"Traceback"`, `b"File \""`, and `b"Exception"` never appear in stderr. |
| AC-11 | All failing vectors exit with exactly `2`; no vector exits with a status other than `0` or `2`. |
| AC-12 | Successful vectors (`add 2 3`, `add +0007 -0`, `add -5 5`) produce stderr `b""` and status `0` — F-6 emits nothing on success. |
| AC-13 | Rejection of `" 5"`, `"5 "`, `"1_000"`, `"0x10"`, `"1e3"`, `""`, `"-"`, `"+"` each yields BR-6 and never a numeric result on stdout. |
| AC-14 | With `LC_ALL=C`, `LC_ALL=C.UTF-8`, and `PYTHONIOENCODING=latin-1`, the stderr bytes for a fixed failing vector are identical. |
| AC-15 | Two consecutive identical failing runs produce byte-identical stderr (determinism, NFR-82). |
| AC-16 | A 100 000-character invalid operand completes with status `2` in < 50 ms and produces stderr ≤ 256 bytes with the `...` truncation marker present. |
| AC-17 | Every all-failing vector has stdout of length 0 (asserted for the entire catalogue). |
| AC-18 | The error prefix `add: error:` appears exactly once per grammar failure and once per arity failure. |

### API behaviour

The "API" of `add` is the process interface; F-6 defines its failure surface.

| ID | Surface | Contract |
|---|---|---|
| API-1 | **Input:** `argv[1:]` | Exactly two positional operands; no flags, no options, no `--`, no environment input. Operand grammar per F-2. |
| API-2 | **stdout** | On success only: `<sum>\n` per F-4. On **any** failure: `b""` (0 bytes). |
| API-3 | **stderr** | On success: `b""`. On arity failure: BR-5 (2 lines). On grammar failure: BR-6 (1 line). ASCII-only, `add: error:`-prefixed, each line `\n`-terminated, ≤ 256 bytes/line. |
| API-4 | **exit status** | `0` on success; `2` on every validation failure (F-5 owns the value). No other status is reachable from validation. |
| API-5 | **Failure-class discriminator** | Distinguishable without parsing prose: arity failures emit 2 stderr lines (second begins `add: usage:`); grammar failures emit 1 line. |
| API-6 | **Stability guarantee** | Templates BR-5/BR-6 and the `add: error:` prefix are a versioned public contract; changing them is a breaking change. |
| API-7 | **Side effects** | None: no files created/modified/deleted, no network, no subprocess, no signal handlers installed. |
| API-8 | **Encoding** | stderr bytes are ASCII regardless of locale; consumers may decode as ASCII/UTF-8 without loss. |

### Test vectors

| ID | argv (after program name) | Expected status | Expected stdout | Expected stderr |
|---|---|---|---|---|
| T-1 | *(none)* | `2` | empty | BR-5, `got 0` |
| T-2 | `5` | `2` | empty | BR-5, `got 1` |
| T-3 | `1 2 3` | `2` | empty | BR-5, `got 3` |
| T-4 | `1.5 2` | `2` | empty | BR-6, `1`, `'1.5'` |
| T-5 | `5 2.0` | `2` | empty | BR-6, `2`, `'2.0'` |
| T-6 | `a b` | `2` | empty | BR-6, `1`, `'a'` only |
| T-7 | `1.5 2 3` | `2` | empty | BR-5, `got 3` |
| T-8 | `"" 2` | `2` | empty | BR-6, `1`, `''` |
| T-9 | `" 5" 2` | `2` | empty | BR-6, `1`, `' 5'` |
| T-10 | `0x10 1` | `2` | empty | BR-6, `1`, `'0x10'` |
| T-11 | `2 3` | `0` | `5\n` | empty |
| T-12 | `+0007 -0` | `0` | `7\n` | empty |

### Priority

**Overall: must-have.** F-6 is the sole observable failure interface of the utility. Without it, F-1s arity rule, F-2s grammar, and F-5s status contract have no user-visible expression, and callers cannot distinguish "bad invocation" from "bad operand".

| Sub-scope | Priority | Rationale |
|---|---|---|
| Stage ordering, fail-fast, first-error-only (FR-126, FR-133, FR-140, BR-3) | must-have | Determines deterministic, testable failure classification. |
| Stream and status invariants (FR-130, FR-131, FR-132, FR-145) | must-have | The core machine contract for scripters (US-78). |
| Diagnostic templates BR-5/BR-6 and prefix (FR-127, FR-128, FR-136, FR-141) | must-have | Human usability plus greppable stability. |
| No-traceback and no-disclosure rules (FR-135, FR-138, FR-139, NFR-81) | must-have | Correctness and safety of error output. |
| Escape rendering (FR-137, NFR-88) | must-have | Prevents log injection and terminal corruption. |
| Locale invariance (FR-142, NFR-84) | should-have | Determinism across environments. |
| Echo truncation (FR-143) | should-have | Bounded, single-line output for pathological inputs. |
| Complexity/memory/atomicity targets (NFR-77, NFR-78, NFR-79) | should-have | Quality-of-implementation targets; not user-observable except at extreme sizes. |

### Open Questions

| ID | Question | Needed from |
|---|---|---|
| OQ-1 | Should the arity diagnostic tolerate a `--help`/`-h` argument as a distinct, non-error path? The current brief defines no option parsing (F-2, API-1), so any `--help` is an arity/grammar failure. Confirming "no flags at all" keeps BR-7 closed. | User |
| OQ-2 | Is the exact diagnostic wording (BR-5/BR-6) contractual for downstream consumers, or may it be reworded freely? This determines whether API-6 stability is enforced by tests. | User |
| OQ-3 | Should `add 1 2 3` suggest the correct invocation (already covered by the BR-5 usage line), and should the received-count `<N>` be capped for very large argument counts? Current rule echoes the true count uncapped. | User |

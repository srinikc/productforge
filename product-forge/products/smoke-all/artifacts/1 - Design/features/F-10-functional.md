## F-10: Usage/help output

**Feature ID:** F-10
**Depends on:** F-1 (`add` command entry point — owns arity rule and the fact that arity violations go to stderr with status 2), F-2 (two positional integer operands — owns the operand grammar, and the rule that no flags are recognized), F-5 (exit-status contract — owns the numeric status `2`), F-6 (input validation and error message — owns the error line that precedes the usage line, the check ordering, and the safe echoing rules), F-7 (standard library only).

**Boundary note:** F-10 owns **only the usage/help text surface** — its exact literal content, byte-level formatting, channel, emission count, terminators, and invariants (determinism, no runtime interpolation, no localization, no flag path). F-10 does **not** redefine arity (F-1), the operand grammar (F-2), arithmetic (F-3), stdout rendering (F-4), exit-status values (F-5), or the diagnostic error line and check pipeline (F-6). Where F-1/F-5/F-6 already fix a trigger or a status, F-10 references it and adds only the text/channel obligations.

### Requirements

#### Functional Requirements (FR)

| ID | Requirement | Priority |
|---|---|---|
| FR-226 | The program MUST emit the canonical usage line to **stderr** whenever the invocation's operand count is not exactly two (0, 1, or 3+ operands). The trigger condition and the exit status remain owned by F-1 `FR-6` and F-5 `FR-102`; F-10 owns only the text and channel of the usage line. | must-have |
| FR-227 | The canonical usage line MUST be exactly the literal `usage: add <int1> <int2>` followed by one `\n` (U+000A): 24 text bytes + 1 LF = **25 bytes** total. No other wording, casing, spacing, punctuation, or ordering is permitted. | must-have |
| FR-228 | Byte-exact formatting MUST hold: lowercase ASCII `usage`, then `:` (U+003A), then exactly one space (U+0020), then the literal program name `add`, then one space, then the literal placeholder `<int1>`, then one space, then the literal placeholder `<int2>`. There MUST be no trailing whitespace, no tab (U+0009), no CR (U+000D), no NUL (U+0000), no ANSI/SGR escape (U+001B), no color, and no bold/underline attributes. | must-have |
| FR-229 | The usage line MUST be written to **stderr (fd 2) only**. It MUST NOT be written to stdout, MUST NOT be mirrored to stdout, and MUST NOT be concatenated onto the numeric result line. | must-have |
| FR-230 | Every invocation that emits the usage line MUST terminate with exit status `2` and MUST write **0 bytes** to stdout. The status value itself is owned by F-5 (`FR-102`); F-10 asserts only that emitting usage text and exiting `0` are mutually exclusive. | must-have |
| FR-231 | The program MUST NOT recognize any help/usage token (`-h`, `--help`, `-help`, `--usage`, `-?`, `/?`, `help`, `--version`) as a flag or subcommand. All such tokens MUST be treated as ordinary operands and handled by F-1 arity rules or F-2 grammar rules. There is no exit-0 help path. | must-have |
| FR-232 | The usage line MUST be emitted **at most once** per invocation. No invocation may print it twice, and there MUST be no alternative variants (no per-arity variant, no per-operand variant, no "short help" vs "long help"). Arity 0, arity 1, and arity 3+ MUST all produce the identical single line. | must-have |
| FR-233 | The usage line MUST be byte-identical across runs and environments: independent of locale (`LANG`, `LC_ALL`, `LC_MESSAGES`), terminal (`TERM`, `COLUMNS`, TTY vs pipe vs file), `NO_COLOR`/`FORCE_COLOR`/`CLICOLOR`, current working directory, `argv[0]` spelling, environment size, and platform. The literal MUST NOT be sourced from gettext catalogs, config files, or environment variables. | must-have |
| FR-234 | The usage line MUST NOT be emitted on any successful run (exactly two operands satisfying the F-2 grammar); successful runs MUST produce empty stderr. | must-have |
| FR-235 | The usage line MUST NOT be emitted on operand-grammar failures (arity = 2, any operand rejected by F-2) or on any computation path. Those paths emit only the single-line diagnostics owned by F-1 `FR-7` / F-6 `FR-126`–`FR-127`. | must-have |
| FR-236 | The usage line MUST be the **final** stderr line of the failing invocation and MUST be terminated by its `\n`. Nothing may be written to stderr after it, and the line MUST NOT be truncated or left unterminated on any normal exit path. | must-have |
| FR-237 | The usage line MUST NOT interpolate any runtime value: no operand echo, no argument count, no program path or `argv[0]`, no hostname, no username, no PID, no timestamp, no environment value. It is a fixed constant string (the program name is the literal `add`, never a basename/path derived from `argv[0]`). | must-have |
| FR-238 | If stderr is closed or unwritable (e.g., `2>&-`, full disk on a redirected stderr), the program MUST NOT redirect the usage line or any diagnostic to stdout, MUST NOT write usage text to any file, and MUST still terminate with exit status `2` with an empty stdout. | should-have |
| FR-239 | The usage line SHOULD be issued as a **single write** of the complete 25-byte sequence so that concurrent writers on the same stderr file or pipe cannot interleave partial bytes into the middle of the line. | should-have |

#### Non-Functional Requirements (NFR)

| ID | Requirement | Target | Measurement | Priority |
|---|---|---|---|---|
| NFR-136 | Usage-path latency | The complete usage line must reach stderr within **50 ms** of process start on reference hardware, with no I/O beyond the stderr write(s) for the failing invocation | Wall-clock timing of `add` (no args) over 50 runs; median and p95 | should-have |
| NFR-137 | Scalability / availability of the usage path | Usage emission is O(1) in the number of arguments and independent of operand length: even 10 000 extra arguments must yield exactly one usage line and exit 2 within **100 ms** and with no additional stderr lines from F-10 | Invoke with 10 000 arguments; assert one usage line, status 2, bounded wall clock | should-have |
| NFR-138 | Security of the help surface | The usage line must never echo attacker-controlled bytes, so it cannot be used for terminal-escape injection, log injection, or forged-log-line injection; no environment variable may be interpolated into it | Fuzz operand bytes (ESC sequences, newlines, `\r`, NUL-adjacent, unicode bidi controls) in arity-failure invocations; assert the usage line is byte-constant and contains no ESC (0x1B) | must-have |
| NFR-139 | Data / residency / side-effect freedom | Generating usage text must collect no telemetry, write no files, create no temp files, open no sockets, and read no config or data files; the only observable side effect is the stderr write | Run in a sandbox with read-only FS and no network; assert no file/socket syscalls attributable to usage emission | must-have |
| NFR-140 | Deployment / environment portability | The usage line must be byte-identical on any POSIX-style environment running stock CPython 3.8+ with a UTF-8 or ASCII-compatible locale; no terminal capability database, pager, or color support is required or consulted | Byte-compare stderr across the supported environment matrix (see AC-10) | must-have |

#### User Stories (US)

| ID | Story | Refs | Priority |
|---|---|---|---|
| US-136 | As a first-time user who mistyped the command, I want a one-line usage message that shows the exact expected invocation, so that I can correct my command without leaving the terminal or reading documentation. | FR-226, FR-227 | must-have |
| US-137 | As a shell-script author, I want usage failures to go to stderr with a non-zero exit status and nothing on stdout, so that I can distinguish misuse from success without parsing stdout. | FR-229, FR-230 | must-have |
| US-138 | As a CI/build-log reader, I want the usage text to be a single stable, uncolored, escape-free line, so that logs stay readable, greppable, and safe to render. | FR-228, FR-232, NFR-138 | should-have |
| US-139 | As a user on a non-English or differently configured machine, I want the same usage text everywhere, so that error triage is deterministic across environments and machines. | FR-233, NFR-140 | should-have |
| US-140 | As a tooling author integrating `add`, I want the absence of a help flag to be explicit and unambiguous (`add --help` fails with status 2 rather than succeeding), so that I never accidentally rely on a help surface that does not exist. | FR-231, FR-235 | should-have |

### Behaviour

1. **Single trigger path.** Exactly one condition produces usage text: the operand count is not exactly two (0, 1, or 3+ operands). This condition is evaluated first, per the fixed pipeline owned by F-6 (`FR-126`), so usage text is emitted **before** any operand grammar check runs. A 3-argument invocation therefore never reports a grammar error and never emits a grammar-specific variant.
2. **Emission sequence (arity failure).** stderr receives: (a) the F-6 error line naming the expected operand count, then (b) the F-10 canonical usage line as the last line; then the process terminates with status `2`. stdout receives nothing.
3. **Non-emission sequence (grammar failure).** With exactly two operands where at least one fails the F-2 grammar, stderr receives **only** the single-line diagnostic owned by F-1 `FR-7` / F-6; the F-10 usage line is not emitted and the process terminates with status `2`.
4. **Success path.** Exactly two operands, both grammar-valid: the F-4 result line goes to stdout, stderr stays empty, exit status `0`. No usage text exists on this path.
5. **No help flag.** Because F-2 (`FR-26`) forbids option parsing, `-h`, `--help`, `--usage`, `-?`, `/?`, `help`, and `--version` are ordinary operands. `add --help` is a one-operand invocation → arity failure → usage line + status `2`. `add --help 1` is a two-operand invocation → `--help` fails the F-2 grammar → single diagnostic line, **no** usage line, status `2`. There is no invocation of `add` that prints help and exits `0`.
6. **Channel and format discipline.** The usage line is a fixed 25-byte constant on fd 2: no color, no bold, no cursor movement, no pagination, no pager invocation, no line wrapping at any terminal width, and no locale- or environment-dependent text.
7. **Idempotence.** A given invocation shape produces exactly one usage line, and repeated identical invocations produce byte-identical stderr (modulo the F-6 error line, which F-10 does not own).

### Business rules

| ID | Rule |
|---|---|
| BR-1 | The canonical usage line is the fixed literal `usage: add <int1> <int2>` plus one `\n` — 24 text bytes + 1 LF = 25 bytes. It is a compile-time/program-literal constant, not assembled from runtime parts. |
| BR-2 | `<int1>` and `<int2>` are literal placeholder tokens including their angle brackets (U+003C, U+003E). They are never substituted with actual argument values, argument counts, or examples. |
| BR-3 | The program name printed in usage is the fixed ASCII literal `add` — never `argv[0]`, never a path, never a basename, never a symlink name, never a `python`/`python3` script path. Invocation style does not change the text. |
| BR-4 | Exactly one line: no leading blank line, no trailing blank line, no multi-line "long help", no examples section, no options section, no version footer. |
| BR-5 | The usage line is always the final stderr line of the invocation; no byte is written to stderr after its `\n`. |
| BR-6 | Usage text is an **error-path artifact only**. There is no success-path help, no `--help` success mode, and no exit-`0` path that prints usage. |
| BR-7 | The text is English/ASCII and non-localized; it is not loaded from gettext catalogs, message files, config files, or environment variables. |
| BR-8 | The usage line is emitted at most once per process. Arity 0, arity 1, and arity 3+ share one and the same line — no variants exist. |
| BR-9 | The usage line interpolates nothing, so no operand bytes, path bytes, or environment bytes can reach the terminal through it; safe echoing of offending input (if any) on arity failures is F-6's responsibility, on the F-6 error line, not the usage line. |
| BR-10 | Usage emission never changes the exit-status contract: usage always accompanies status `2` (F-5 `FR-102`), never `0` and never `1`. |

### Validation

Validation here means both (a) the gate that decides whether the usage line is emitted, and (b) the self-checks that the emitted text satisfies its own contract.

1. **Emission gate.** Compute operand count as `len(argv) - 1`; emit usage **iff** that count ≠ 2. This is the only gate; no environment value, TTY state, or operand content may suppress or trigger the line (BR-8, FR-226).
2. **Text validation.** The candidate string must byte-compare equal to `b"usage: add <int1> <int2>\n"` (length 25) before emission. Any deviation is a defect, not a formatting choice (FR-227, FR-228).
3. **Character-class validation.** Every emitted byte must be in the set `{0x20, 0x3A, 0x3C, 0x3E, 0x0A}` ∪ ASCII letters (`u,s,a,g,e,a,d,d`) ∪ ASCII digits (`1,2`). Any byte outside this set — notably `0x1B` (ESC), `0x09` (TAB), `0x0D` (CR), `0x00` (NUL) — is a violation (FR-228, NFR-138).
4. **Channel validation.** The write target must be fd 2. A run whose stdout byte count is non-zero while usage was emitted fails validation (FR-229, FR-230).
5. **Cardinality validation.** Count occurrences of the substring `usage: add <int1> <int2>` in captured stderr; the count must be exactly 1 for an arity failure and exactly 0 for grammar failures, computation paths, and successful runs (FR-232, FR-234, FR-235).
6. **Terminator validation.** The emitted stream must end with the usage line's `\n`; the usage line must not be the only content preceding an unterminated write (FR-236).

### Edge cases

| ID | Case | Required behaviour |
|---|---|---|
| EC-1 | Zero operands: `add` | Usage line emitted as final stderr line; stdout 0 bytes; exit 2. |
| EC-2 | One operand: `add 5` | Identical to EC-1. The operand's validity is irrelevant — grammar is not evaluated. |
| EC-3 | Three operands: `add 1 2 3` | Identical usage line; `6` is **not** printed anywhere; stdout 0 bytes; exit 2. |
| EC-4 | Help-flag-shaped single argument: `add --help` | Treated as one operand → arity failure → usage line; exit 2. No success/help path. |
| EC-5 | Help-flag-shaped plus operand: `add --help 1` | Two operands → `--help` rejected by the F-2 grammar → exactly one F-1 `FR-7`/F-6 diagnostic line, **no** usage line; exit 2. |
| EC-6 | Two invalid operands: `add -h -h` | Pipeline stops at the first operand (F-6 `FR-126`) → single diagnostic, no usage line; exit 2. |
| EC-7 | Closed stderr: `add 2>&-` | No usage bytes are observable; stdout remains 0 bytes; exit status is still 2; no fallback to stdout and no file fallback. |
| EC-8 | stderr redirected to a file: `add 1 2 3 2>err.txt` | `err.txt` contains the F-6 error line followed by exactly one 25-byte usage line; no ESC, no CR, no trailing blank line. |
| EC-9 | stdout redirected on a failing arity: `add >out.txt` | `out.txt` exists/truncated by the shell but the program writes **0 bytes** to it (FR-230). |
| EC-10 | Hostile locale/terminal settings: `LC_ALL=tr_TR.UTF-8`, `LANG=de_DE.UTF-8`, `COLUMNS=20`, `TERM=dumb`, `NO_COLOR=` unset | Usage bytes are identical to the default environment; `usage:` is not capitalized, not translated, and not wrapped at 20 columns. |
| EC-11 | Alternate invocation shapes: `./add`, `/usr/local/bin/add`, symlink `sum`, `python3 add.py` | Usage line is byte-identical; the printed program name remains the literal `add` (BR-3). |
| EC-12 | Very many arguments: `add` followed by 10 000 tokens | Exactly one usage line, exit 2, bounded latency (NFR-137); no operand token appears in the usage line. |
| EC-13 | Non-UTF-8 / binary operand bytes on an arity failure (e.g., `add $'\x1b[31m' 1 2`) | The usage line remains the constant 25-byte sequence and contains no ESC byte (NFR-138). |
| EC-14 | stderr is a TTY | No color, no bold, no cursor control sequences are emitted; bytes equal the non-TTY case (FR-228, FR-233). |

### Error handling

1. **Usage emission is itself an error path.** It always travels with exit status `2`, always leaves stdout empty, and never replaces or follows a successful result (FR-230, BR-6, BR-10).
2. **No fallback channel.** On any stderr write failure or unavailability (closed fd, ENOSPC on a redirected stream), the program must not write usage text to stdout, must not create or write a file, and must not silently swallow the error such that the status becomes `0`; the mandatory observable is exit status `2` with empty stdout (FR-238).
3. **No traceback substitution.** A failure while writing usage must not cause the program to exit `1` (the exit-status contract has only `0` and `2`; F-5 owns the values). Diagnostics must not escape onto stdout under any circumstance.
4. **No double reporting.** A grammar failure or computation path must not additionally emit usage text; the arity-first pipeline (F-6 `FR-126`) guarantees the two diagnostic flavours never co-occur in the same invocation (FR-232, FR-235).
5. **No partial-line retry strategies.** The program must not attempt to work around a failed/truncated write by re-emitting the usage line, by switching streams, or by splitting/reordering output; the line is emitted once, as a single complete unit where possible (FR-236, FR-239).

### Acceptance criteria

| ID | Given / When / Then |
|---|---|
| AC-1 | Given the program, when invoked as `add` with no arguments, then the last stderr line is exactly `usage: add <int1> <int2>` + `\n`, stdout has 0 bytes, and exit status is 2. (FR-226, FR-227, FR-229, FR-230) |
| AC-2 | Given the program, when invoked as `add 7` (one argument), then output is byte-identical to AC-1. (FR-226) |
| AC-3 | Given the program, when invoked as `add 1 2 3` (three arguments), then output is byte-identical to AC-1 and the string `6` does not appear in stdout. (FR-226, FR-230, FR-232) |
| AC-4 | Given the program, when invoked as `add 2 3`, then stdout is exactly `5\n`, stderr has 0 bytes, exit status is 0, and the substring `usage:` appears nowhere. (FR-234) |
| AC-5 | Given the F-2 grammar, when invoked as `add --help`, then the last stderr line is the usage line, stdout has 0 bytes, and exit status is 2 (no exit-0 help). (FR-231) |
| AC-6 | Given the F-2 grammar, when invoked as `add --help 1`, then stderr contains exactly one line (the F-1 `FR-7`/F-6 diagnostic) that does **not** contain the substring `usage: add <int1> <int2>`, stdout has 0 bytes, exit status is 2. (FR-235) |
| AC-7 | Given captured stderr for an arity failure, then `tail -c 25` of stderr equals the byte sequence `75 73 61 67 65 3a 20 61 64 64 20 3c 69 6e 74 31 3e 20 3c 69 6e 74 32 3e 0a`. (FR-227, FR-228) |
| AC-8 | Given captured stderr for an arity failure, then it contains no `0x1B`, `0x09`, `0x0D`, or `0x00` byte, and no `0x20` byte immediately preceding the final `0x0A`. (FR-228, NFR-138) |
| AC-9 | Given 100 consecutive invocations of `add 1 2 3`, then the SHA-256 of captured stderr is identical across all runs. (FR-233) |
| AC-10 | Given the environment matrix `LANG=C`, `LANG=de_DE.UTF-8`, `LC_ALL=tr_TR.UTF-8`, `COLUMNS=20`, stderr-as-TTY, stderr-as-pipe, stderr-as-file, then the final stderr line bytes are identical in every cell, including when `argv[0]` is a path or a symlink name. (FR-233, FR-237, NFR-140) |
| AC-11 | Given any arity failure, then the captured stderr contains exactly one occurrence of the substring `usage: add <int1> <int2>`, and the 24-character usage line contains none of the operands supplied on the command line. (FR-232, FR-237) |
| AC-12 | Given `add 2>&-` (stderr closed), then stdout has 0 bytes and exit status is 2 (no fallback output, no status other than 2). (FR-238) |
| AC-13 | Given `add > out.txt 2> err.txt` with a wrong argument count, then `out.txt` is 0 bytes and `err.txt` ends with exactly one usage line followed by `\n` and nothing else. (FR-229, FR-230, FR-236) |
| AC-14 | Given 10 000 arguments after the program name, then exactly one usage line is emitted, stdout has 0 bytes, exit status is 2, and wall-clock time is within the NFR-137 budget. (FR-232, NFR-137) |
| AC-15 | Given a sandbox with a read-only filesystem and no network, when an arity failure occurs, then the usage line is still emitted on stderr with exit status 2 and no file or socket is created. (NFR-139) |

### API behaviour

| ID | Contract |
|---|---|
| API-1 | **Interface:** `add [operand ...]` → stdout (result line), stderr (diagnostic and/or usage), exit status (`0` on success, `2` on misuse). F-10 shapes only the stderr usage channel; it adds no new invocation mode, no new operand form, and no new flag. |
| API-2 | **Usage channel:** fd 2, exactly one 25-byte line (`usage: add <int1> <int2>\n`), emitted at most once, as the last stderr line, only on the arity-failure path. |
| API-3 | **Stream separation:** usage text and the numeric result are never both present on a single invocation and are never interleaved; result → fd 1, usage → fd 2, strictly. |
| API-4 | **Exit-status mapping:** usage emission ↔ status `2` (F-5 `FR-102`). There is no status value that pairs with usage other than `2`, and no usage text on the `0` path. |
| API-5 | **No success-mode help surface:** there is no `--help`/`-h`/`--version`/subcommand that prints usage and exits `0`; all such tokens are operands (FR-231). Adding a success-mode help surface would be new scope requiring user approval. |
| API-6 | **No stdin interaction:** the program does not read stdin, so piping input cannot trigger, suppress, or alter usage output; `printf 'x' | add` behaves exactly like `add`. |
| API-7 | **Machine consumption:** the usage line is greppable/parseable by the fixed literal `usage: add <int1> <int2>`; scripts may rely on the exact prefix `usage: ` and the fixed 25-byte length. |

### Priority

| Priority | Items | Rationale |
|---|---|---|
| **must-have** | FR-226, FR-227, FR-228, FR-229, FR-230, FR-231, FR-232, FR-233, FR-234, FR-235, FR-236, FR-237; NFR-138, NFR-139, NFR-140; US-136, US-137 | The usage line is the substance of the already-mandatory arity diagnostic (F-1 `FR-6`), and its channel/format/determinism rules are what make that diagnostic trustworthy in scripts, logs, and hostile-input conditions. |
| **should-have** | FR-238, FR-239; NFR-136, NFR-137; US-138, US-139, US-140 | Robustness and hygiene properties (closed-stderr behaviour, single-write atomicity, latency/scale budget) that strengthen the contract without changing any observable success behaviour. |
| **nice-to-have** | — | No optional usage/help extensions are specified here, because the brief defines no help surface beyond the arity diagnostic. |
| **blocked pending user decision** | OQ-1 | Whether an explicit success-mode help flag (`-h`/`--help` → usage on stdout, exit `0`) should exist is a **scope decision for the user**, not the designer. F-10 as written follows the existing F-2 rule (`FR-26`: no option parsing) and therefore defines usage text strictly as a stderr error-path artifact with status `2`. Introducing a success-mode help path would add new scope and contradict F-2 `FR-26`; it is deliberately not specified here. |

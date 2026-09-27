## F-7: Standard library only

**Feature ID:** F-7
**Depends on:** F-1 (`add` command entry point), F-2 (two positional integer operands), F-3 (integer addition), F-4 (print result to stdout), F-5 (exit-status contract), F-6 (input validation and error message) — F-7 does **not** re-define argument handling, the operand grammar, arithmetic, rendering, exit status, or diagnostic text. F-7 owns only the **dependency envelope**: the requirement that every runtime capability used by F-1–F-6 is satisfied by the Python 3 standard library, and the observable consequences of that envelope (no installation step, no third-party imports, no network, hermetic execution).

### Requirements

#### Functional Requirements (FR)

| ID | Requirement | Priority |
|---|---|---|
| FR-151 | The program MUST run on a stock CPython 3 interpreter (3.8 or later) with **no third-party packages installed** beyond those shipped with the interpreter distribution itself. | must-have |
| FR-152 | The implementation MUST import only modules from the Python 3 standard library, or use built-in types/functions that require no import at all. No `pip install` step, virtual-environment dependency, `requirements.txt` entry, or vendored third-party file may be required to execute `add`. | must-have |
| FR-153 | The program MUST NOT perform any network access (no socket, HTTP, DNS, or IPC-to-remote-service call) at any point in its lifecycle, including at import time and at exit. | must-have |
| FR-154 | The program MUST NOT require, read, or write any configuration file, environment variable, home-directory state, database, or on-disk cache in order to compute and print the sum. Behaviour MUST be identical when the environment is empty. | must-have |
| FR-155 | The program MUST NOT create, modify, or delete any file or filesystem entry as a side effect of a normal run (success or failure). It is a pure stdout/stderr/exit-status filter. | must-have |
| FR-156 | The integer parsing performed for F-2 and the integer arithmetic performed for F-3 MUST be provided by standard-library or built-in facilities only (built-in `int`, `str`, and `sys` are sufficient); no external numeric, bignum, or parser library may be used. | must-have |
| FR-157 | The program MUST NOT depend on any compiled extension module or platform-specific native library beyond those bundled with the standard CPython distribution. Source-only operation on a pure-Python interpreter is acceptable. | should-have |
| FR-158 | If a standard-library module is imported at module scope, the import MUST NOT introduce observable side effects (no threads, no files, no sockets, no locale mutation) before argument processing begins. | should-have |

#### Non-Functional Requirements (NFR)

| ID | Requirement | Target | Priority |
|---|---|---|---|
| NFR-91 | **Portability** — the program MUST execute correctly on at least Linux, macOS, and Windows under stock CPython 3.8+, with identical stdout bytes and exit status for identical arguments. | 3/3 platforms, byte-identical output | must-have |
| NFR-92 | **Cold-start cost** — total interpreter-plus-program startup, add, and print MUST complete within 250 ms wall-clock on a contemporaneous developer machine with no warm cache. | p95 < 250 ms | should-have |
| NFR-93 | **Dependency surface** — the number of third-party runtime dependencies MUST be exactly zero, and the number of standard-library modules imported MUST be 3 or fewer. | 0 third-party; ≤3 stdlib | must-have |
| NFR-94 | **Hermeticity** — execution MUST NOT require clock accuracy, random entropy, elevated privileges, or a writable working directory. | runs with `HOME=/nonexistent`, read-only CWD | must-have |
| NFR-95 | **Auditability** — a reviewer MUST be able to enumerate every imported module and every external capability used by reading a single source file, with no dynamic imports, `__import__` calls, or `importlib` use. | 100% statically enumerable | should-have |

#### User Stories (US)

| ID | Story | Priority |
|---|---|---|
| US-91 | As a **developer**, I want to run `add 2 3` on any machine that has Python 3, so that I do not have to install or configure anything first. | must-have |
| US-92 | As a **security reviewer**, I want the tool to make no network calls and touch no files, so that I can approve it for use in an offline or locked-down environment without a threat-model review. | must-have |
| US-93 | As a **packager / CI maintainer**, I want the tool to have zero third-party dependencies, so that there is no dependency tree to pin, audit, or patch. | should-have |

### Behaviour

- **B-1.** `add` is delivered as one or more Python source files. Running it requires only the `python3` executable already present on the target machine.
- **B-2.** On invocation, the program proceeds directly to argument handling (F-1) without reading configuration, probing the network, or inspecting the filesystem.
- **B-3.** All capabilities exercised at runtime fall into one of three buckets: (a) Python built-ins (`int`, `str`, `print`, `sys.argv`), (b) standard-library modules shipped with CPython, or (c) the operating system's own process-startup and stream machinery, which the interpreter provides.
- **B-4.** The observable output — stdout bytes, stderr bytes, exit status — is a pure function of the argument vector. No environment variable, file, locale beyond the fixed ASCII grammar, or machine property may alter it (see FR-154, NFR-94).
- **B-5.** Behaviour is identical whether the program is invoked as `python3 add.py 2 3`, as an installed console script, or via any other launcher the packaging adopting agent chooses, provided the same interpreter and the same arguments are used. The three-way contract (stdout, stderr, exit status) is unchanged.

### Business rules

| ID | Rule |
|---|---|
| BR-1 | The **allowed dependency set** for the runtime path is the Python 3 standard library exactly as defined by the CPython documentation for the target minor version, plus the language's built-in objects. Nothing else qualifies. |
| BR-2 | Build-time, test-time, and developer-tooling dependencies (linters, formatters, test runners) are **out of scope** for this rule: they may exist, but they MUST NOT be required to execute `add` and MUST NOT appear on the runtime import path. |
| BR-3 | A module is considered "third-party" if it is not part of the interpreter's own distribution. Vendoring third-party source into the repository does not launder it into a standard-library dependency; the rule is about provenance and audit surface, not packaging mechanics. |
| BR-4 | The runtime path MUST be statically resolvable: every module referenced must appear in a literal `import` statement (or be a built-in). Dynamic import mechanisms (`__import__`, `importlib.import_module`, `exec` of import strings) are prohibited on the runtime path. |
| BR-5 | The no-network rule (FR-153) is absolute and has no "optional telemetry" exception. There is no version check, no update ping, no crash reporter. |
| BR-6 | The no-filesystem-write rule (FR-155) is absolute for the runtime path. Reading is additionally prohibited by FR-154 except for the interpreter's own reading of the program's own source, which is the interpreter's action, not the program's. |
| BR-7 | Because the tool is a pure filter, its correctness is fully characterised by the mapping `argv[1:] → (stdout_bytes, stderr_bytes, exit_status)`. Any behaviour that cannot be observed through those three channels is not part of the contract. |

### Validation

| ID | Validation |
|---|---|
| V-1 | **Static import audit** — parse the source with `ast` and assert that every `Import`/`ImportFrom` node references a name in `sys.stdlib_module_names` (Python 3.10+) or an explicitly maintained allow-list for earlier versions. Fail the check on any other name. |
| V-2 | **Dynamic-import audit** — assert that the source contains no `__import__`, no reference to `importlib`, and no `exec`/`eval` applied to constructed strings on the runtime path. |
| V-3 | **Clean-environment execution test** — run `add 2 3` in a container with no site-packages, no `PYTHONPATH`, no `HOME`, and a read-only filesystem (except the interpreter's own read-only mount). Assert stdout is exactly `5\n` and exit status is `0`. |
| V-4 | **Network-denial test** — run under a sandbox that denies all outbound and inbound socket syscalls. Assert the program still succeeds with identical output. |
| V-5 | **Filesystem-write-denial test** — run with the entire filesystem mounted read-only. Assert the program still succeeds with identical output. |
| V-6 | **Portability smoke test** — run the same argument vectors (including a negative sum, a zero sum, a large-magnitude sum) on Linux, macOS, and Windows under stock CPython ≥3.8, and assert byte-identical stdout and identical exit status. |
| V-7 | **Import-count check** — count distinct standard-library modules imported on the runtime path and assert the count is ≤3 (NFR-93). |
| V-8 | **Argv-purity test** — run `add 2 3` with a large, adversarial set of environment variables set and unset; assert the tuple `(stdout, stderr, exit_status)` is unchanged across all runs. |

### Edge cases

| ID | Edge case | Expected behaviour |
|---|---|---|
| EC-1 | Python is invoked with `-S` (site disabled) and `-E` (environment ignored). | The program runs normally; no site-packages are needed (FR-152). |
| EC-2 | The interpreter has an aggressive audit hook or import hook installed that blocks third-party imports. | No third-party import is ever attempted, so the hook never fires on `add`'s behalf. |
| EC-3 | The target machine has no network interface configured at all. | Identical behaviour; startup performs no resolution or connection attempt. |
| EC-4 | The current working directory is read-only and contains no files the program could write. | Success path is unchanged; no file is written. |
| EC-5 | `HOME` points at a non-existent path and `XDG_*` variables are unset. | No configuration lookup occurs; behaviour is unchanged. |
| EC-6 | The program is run by a user with no write permission anywhere on the filesystem. | Success path is unchanged. |
| EC-7 | The interpreter is a pure-Python build (e.g. PyPy-compatible pure-Python mode, or CPython built without optional C accelerators). | Program still works; no C-extension dependency is required (FR-157). |
| EC-8 | `PYTHONPATH` points at a directory containing a hostile module with a name that shadows something the program imports. | Out of scope for F-7's own contract, but the audit V-1/V-2 ensures the program imports nothing shadowable beyond interpreter-provided names; the residual risk is documented as OQ-1. |
| EC-9 | Locale is set to a non-ASCII locale (e.g. `tr_TR.UTF-8`, `ja_JP.UTF-8`). | Parsing and rendering are ASCII-fixed (F-2, F-4); no locale-sensitive formatting call is used, so output is unchanged. |
| EC-10 | The program's source is distributed as a single `.py` file with no accompanying files. | Still runnable; no companion file, data file, or package metadata is required at runtime. |

### Error handling

| ID | Situation | Behaviour |
|---|---|---|
| EH-1 | A future maintainer adds a third-party import to the runtime path. | Detected by validation V-1 and V-2; the build's compliance gate fails. This is a spec violation of FR-152, not a runtime error path. |
| EH-2 | The interpreter is too old (<3.8) and lacks a syntax feature used by the source. | The interpreter itself reports a syntax error to stderr and exits non-zero before `add`'s own contract begins. F-7's scope is Python 3.8+; no program-level handling is required. |
| EH-3 | The sandbox denies a syscall the interpreter needs at startup (e.g. `mmap`). | Interpreter-level failure; `add` emits nothing and the interpreter supplies the diagnostic. No program-level handling; F-7 owns only the "no *program-initiated* network/file call" rule. |
| EH-4 | An audit hook raises on a standard-library import the program legitimately uses. | The interpreter reports the hook's error; `add` does not catch it. This is an environment policy decision, not a contract violation. |
| EH-5 | A dependency is discovered post-hoc to have been vendored. | Treated as a violation of BR-3 and remediated by removing the vendored code; the acceptance criteria below fail until it is removed. |

Note: EH-2 through EH-4 are environment-level failures that occur *before or around* program control, not failures the program itself generates. F-7 deliberately introduces **no new runtime error path**: F-1, F-2, F-5, and F-6 own every runtime diagnostic this tool can emit, and F-7 changes none of them.

### Acceptance criteria

| ID | Criterion |
|---|---|
| AC-1 | On a machine with stock Python 3.8+ and **no site-packages**, `add 2 3` prints `5\n` to stdout, prints nothing to stderr, and exits `0`. |
| AC-2 | The set of names imported by the program, discovered by static AST analysis, is a subset of the Python standard library and contains no third-party name (V-1). |
| AC-3 | The program's source contains no `__import__`, no `importlib`, and no `exec`/`eval` on the runtime path (V-2). |
| AC-4 | Under a sandbox with all network syscalls denied, all argument vectors that succeed outside the sandbox succeed inside it with byte-identical stdout, byte-identical stderr, and identical exit status. |
| AC-5 | Under a read-only filesystem, all argument vectors that succeed outside the sandbox succeed inside it with byte-identical stdout, byte-identical stderr, and identical exit status. |
| AC-6 | The tuple `(stdout, stderr, exit_status)` for a fixed argument vector is identical across Linux, macOS, and Windows under stock CPython 3.8+ (V-6). |
| AC-7 | The number of distinct standard-library modules imported on the runtime path is 0 or more and ≤3 (V-7, NFR-93). |
| AC-8 | The tuple `(stdout, stderr, exit_status)` for a fixed argument vector does not change when the environment is emptied with `env -i` (V-8, FR-154). |
| AC-9 | The program writes no file, creates no directory, and opens no file for writing during a normal run; verified by syscall tracing (V-5). |
| AC-10 | The tool passes its full F-1 through F-6 acceptance criteria unchanged — F-7 adds capabilities restrictions and removes none of the previously specified behaviour (see BR-7 and the "no new error path" note). |

### API behaviour

F-7 is a *constraint feature*, not an interface feature. It exposes no new API of its own; it constrains the implementation of the API defined by F-1 through F-6. Its "surface" is therefore the dependency envelope, and it is exercised through the following probes.

| ID | Probe | Contract |
|---|---|---|
| API-1 | **Static probe** — `ast.parse(source)` then walk for `Import`/`ImportFrom`. | Every imported top-level name resolves to a standard-library module for the target interpreter version. |
| API-2 | **Execution probe** — `env -i python3 -S -E add.py <args…>` in an empty directory. | Exit status and stdout/stderr bytes match the same invocation in a fully equipped environment. |
| API-3 | **Sandbox probe** — run under a seccomp/AppArmor/`bwrap` profile that denies `socket`, `connect`, `open`-for-write, and `unlink`. | Same tuple as API-2; no policy violation is logged against the `add` process. |
| API-4 | **Portability probe** — replay a fixed corpus of argument vectors on the three target OS families. | Cross-OS byte-equality of `(stdout, stderr, exit_status)`. |
| API-5 | **Audit probe** — instrument `builtins.__import__` at process start and record every call. | The recorded set equals the statically discovered set (API-1); no dynamic name appears. |

The **deterministic data model** for this feature is two-sided:

| ID | Entity | Definition |
|---|---|---|
| DM-1 | `RuntimeImportSet` | The set of module names imported by the program's runtime path, each of which MUST be a member of the interpreter's standard-library name set. |
| DM-2 | `EnvDependency` | The value `∅`. F-7 asserts the program has an empty environment dependency: no config key, no environment variable, no file path, and no service endpoint that alters behaviour. |

### Open Questions

| ID | Question | Owner |
|---|---|---|
| OQ-1 | The upstream plan fixes the language as "Python 3 standard library only" but does not fix the *minimum minor version*. Should the design target a specific floor (3.8, 3.9, 3.10, or "any currently supported CPython")? NFR-91 assumes 3.8 as the floor, matching the `sys.stdlib_module_names`-free validation path; if a higher floor is chosen, V-1 can use that attribute directly and drop the allow-list. | USER |
| OQ-2 | Should the "≤3 standard-library modules imported" cap in NFR-93 be treated as a hard gate or as a soft target? The minimum viable implementation imports `sys` only (one module); a paranoid reading would demand zero imports and route through `os.read`/`os.write`, which paradoxically increases the import count. | USER |
| OQ-3 | Is the distribution artifact expected to be a single `.py` file (EC-10), or is a small package with a `__main__.py` acceptable? F-7 is agnostic, but the answer affects how V-2's "statically enumerable" audit walks the tree. | USER |

**Priority (feature-level):** must-have. F-7 is not an optional hardening pass; the brief's scope statement — "Python 3 standard library only" — makes the empty third-party dependency set a defining property of the deliverable. Removing it would not reduce the feature's complexity, it would contradict the brief.

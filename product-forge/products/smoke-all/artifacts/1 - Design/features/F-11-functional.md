## F-11: Unit tests for the add function and CLI

**Feature ID:** F-11  
**Depends on:** F-1 (`add` command entry point), F-2 (two positional integer operands), F-3 (integer addition), F-4 (print result to stdout), F-5 (exit-status contract), F-6 (input validation and error message), F-7 (standard library only), F-8 (correct handling of negative results), F-9 (arbitrary-precision output), F-10 (usage/help output).  
**Boundary note:** F-11 owns the automated verification suite for the behaviour specified in F-1 through F-10. It does not redefine arity, grammar, arithmetic, rendering, exit status, diagnostics, or usage text; it defines what the tests must assert and how they must run.

### Requirements

#### Functional Requirements (FR)

| ID | Requirement | Priority |
|---|---|---|
| FR-251 | The project MUST include an automated unit-test suite for the internal `add` function and the `add` CLI, written in Python 3 and using only the Python 3 standard library. | must-have |
| FR-252 | The suite MUST be runnable from the project root with `python -m unittest` or `python -m unittest discover` on a stock CPython 3.8+ interpreter with no third-party packages, no network access, and no build/install step. | must-have |
| FR-253 | The implementation MUST expose a pure function `add(int1, int2)` that accepts two Python `int` values and returns their exact sum as a Python `int`, importable without side effects, so that function-level tests can exercise arithmetic directly. | must-have |
| FR-254 | The suite MUST test the CLI end-to-end in a subprocess using `sys.executable` and the project's CLI entry point (module name or script path), asserting exact stdout bytes, exact stderr bytes, and exact exit status. | must-have |
| FR-255 | The suite MUST contain at least one test for every externally observable contract in F-1 through F-10, including arity, operand grammar, sum computation, stdout rendering, exit status, validation pipeline, diagnostics, negative results, arbitrary-precision output, usage output, and the standard-library-only envelope. | must-have |
| FR-256 | The suite MUST be deterministic and hermetic: no dependence on ambient environment variables, locale, working directory, network, filesystem side effects, or test execution order. | must-have |
| FR-257 | A passing run of the suite MUST exit with status 0; any test failure MUST cause a non-zero exit status and MUST report the failing test name and expected/actual values. | must-have |
| FR-258 | The suite MUST fail (not skip or warn) when the CLI crashes with an unhandled exception, a subprocess times out, or the internal `add` function raises an unexpected exception. | must-have |

#### Non-Functional Requirements (NFR)

| ID | Requirement | Priority |
|---|---|---|
| NFR-151 | Performance: the full test suite MUST complete in under 10 seconds on a typical development machine. | should-have |
| NFR-152 | Portability: the suite MUST run on any platform supported by CPython 3.8+ where the CLI is expected to run, and MUST NOT assume a POSIX shell; subprocess invocation MUST use `sys.executable`. | must-have |
| NFR-153 | Maintainability: test cases MUST be grouped by feature area, named descriptively, and require no manual setup or external services. | should-have |

#### User Stories (US)

| ID | Story | Acceptance Criteria |
|---|---|---|
| US-151 | As a maintainer, I want a comprehensive unit-test suite for the `add` function and CLI, so that regressions in arithmetic, validation, rendering, and exit-status behaviour are caught automatically. | Running `python -m unittest` reports all tests passing after a change; introducing a bug in any contract area causes at least one test failure. |
| US-152 | As a developer onboarding to the project, I want to run the tests with a single standard-library command without installing dependencies, so that I can verify correctness immediately. | `python -m unittest` runs successfully on a stock CPython 3.8+ interpreter with no third-party packages. |
| US-153 | As a release engineer, I want deterministic test results across environments, so that a passing suite in one environment is meaningful for release. | Three consecutive runs in the same environment produce identical pass/fail results and identical test counts. |

### Behaviour

- The suite MUST verify both layers: the internal `add` function (direct arithmetic) and the CLI process (parsing, validation, rendering, exit status, and stream routing).
- Function-level tests MUST call `add(a, b)` with Python `int` literals and assert `result == expected` using exact integer equality.
- CLI tests MUST run `[sys.executable, <cli-entry-point>, <arg1>, <arg2>]` via `subprocess.run(..., capture_output=True, timeout=10)` and then assert `returncode`, `stdout`, and `stderr` exactly.
- The suite MUST include success cases and every failure category from F-1 through F-10: arity failures, grammar failures, and usage-output cases.
- The suite MUST be runnable with a single command and no setup; it MUST NOT require the `add` executable to be on `PATH`.

### Business Rules

- BR-1: The suite MUST treat the contracts in F-1 through F-10 as normative. If a test contradicts a stated contract, the test is defective and MUST be corrected, not the contract.
- BR-2: CLI tests MUST invoke the program as a subprocess using `sys.executable` and the project's CLI entry point, so tests do not depend on `PATH`, virtual environments, or installed packages.
- BR-3: CLI tests MUST assert the exact byte content of stdout and stderr and the exact integer exit status. No substring matching, trimming, or normalization is permitted.
- BR-4: Function-level tests MUST call the internal `add` function directly with Python `int` arguments and assert exact `int` equality; they MUST NOT round-trip through strings or floating-point values.
- BR-5: Test cases MUST be grouped by feature area and named descriptively (e.g., `test_arity_rejects_zero_operands`, `test_grammar_accepts_leading_zeros`, `test_sum_mixed_signs`, `test_render_negative`, `test_exit_status_success`, `test_diagnostic_arity`, `test_usage_output`).
- BR-6: The suite MUST be hermetic: no network access, no third-party imports, no database, no persistent filesystem writes, and no dependence on ambient environment variables, locale, or the current working directory.
- BR-7: If a CLI subprocess crashes (unhandled exception, signal, or Python-level error), the test MUST fail and MUST include the captured stderr in the failure message.
- BR-8: All assertion failures MUST propagate to the unittest runner; the suite MUST NOT catch, swallow, or downgrade failures to warnings.
- BR-9: CLI subprocess tests MUST use a timeout (default 10 seconds) so a hung process fails the test rather than hanging the suite.

### Validation

- The suite is validated by running `python -m unittest` from the project root; a zero exit status and an `OK` summary indicate success.
- Test discovery MUST follow the standard `unittest` pattern: files named `test*.py`, classes subclassing `unittest.TestCase`, and test methods named `test*`.
- Every functional requirement in F-1 through F-10 MUST have at least one corresponding test case, traceable via test name or a comment referencing the requirement ID.
- The suite MUST pass on a stock CPython 3.8+ interpreter with no third-party packages and no network access.
- No test MAY depend on ambient locale, environment variables, or the current working directory.

### Edge Cases

- EC-1: Arity edge cases: 0 operands, 1 operand, 3 operands, and many operands; each MUST produce exit status 2, empty stdout, and non-empty stderr.
- EC-2: Grammar acceptance edge cases: `+5`, `-5`, `+0`, `-0`, `0`, `00`, `007`, `+007`, `-007`.
- EC-3: Grammar rejection edge cases: empty string, whitespace, `1.0`, `1e3`, `0x10`, `0o10`, `0b10`, `1_000`, `1,000`, `--5`, `+-5`, `+`, `-`, `++5`.
- EC-4: Arithmetic edge cases: `0 + 0`, `0 + (-0)`, `10**100 + 1`, `-(10**100) + 10**100`, `10**1000 + (-10**1000)`, and mixed-sign pairs where magnitudes are equal.
- EC-5: Rendering edge cases: zero renders as `0\n`; positive results have no `+` prefix; negative results have a single leading `-`; no leading zeros; no trailing spaces or extra newlines.
- EC-6: Exit-status edge cases: every successful run exits 0; every arity and grammar failure exits 2; no failure writes to stdout.
- EC-7: Diagnostic/usage edge cases: arity failures emit exactly the two stderr lines specified by F-6 and F-10; grammar failures emit exactly the one diagnostic line specified by F-6; no stdout bytes in either case.
- EC-8: Environment edge cases: tests pass regardless of `LC_ALL`, `LANG`, `TZ`, and other ambient locale/environment settings; output is compared as bytes.

### Error Handling

- Subprocess tests MUST use `subprocess.run(..., timeout=10)`; on `TimeoutExpired`, the test MUST fail with the command and captured output in the message.
- If the CLI cannot be started (e.g., missing module or file), the test MUST fail with a clear diagnostic rather than being skipped.
- If the internal `add` function raises an unexpected exception, the test MUST fail via normal exception propagation.
- `AssertionError` MUST NOT be caught or suppressed anywhere in the suite.
- A failing test MUST report the test name, the expected value, and the actual value for stdout, stderr, or exit status as applicable.

### Acceptance Criteria

- AC-1: Running `python -m unittest` from the project root on a stock CPython 3.8+ interpreter with no third-party packages executes the full suite and exits 0.
- AC-2: Every functional requirement in F-1 through F-10 has at least one automated test case that exercises its externally observable behaviour.
- AC-3: Introducing a bug in any of the following areas causes at least one test failure: arity check, operand grammar, sum computation, stdout rendering, exit status, diagnostic messages, usage output, negative-result sign, arbitrary-precision output.
- AC-4: The full suite completes in under 10 seconds on a typical development machine.
- AC-5: Three consecutive runs in the same environment produce identical pass/fail results and identical test counts.
- AC-6: The suite contains no third-party imports, no network access, and no dependence on ambient environment variables or locale.

### API Behaviour

- API-1: The internal `add` function MUST be importable without side effects (no stdout/stderr output at import time) and MUST be pure: `add(int1, int2) -> int`.
- API-2: The CLI MUST be exercised via subprocess, not by calling the entry-point function in-process, so that the real process-level contract (exit status and byte streams) is verified.
- API-3: The test suite MUST be compatible with both `python -m unittest` and `python -m unittest discover`; both commands MUST discover the same complete set of tests.
- API-4: The test suite itself MUST expose no public API; it is a dev-time artifact run through the standard `unittest` runner.

### Priority

- Feature priority: **must-have** — the product plan explicitly includes unit tests for the `add` function and CLI, and the tests are the primary automated verification of all contracts in F-1 through F-10.

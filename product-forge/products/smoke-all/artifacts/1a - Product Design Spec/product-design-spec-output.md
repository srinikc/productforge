# Product Design Spec - smoke-all

_Version 1.0.0 - generated 2026-09-27T09:41:53.893697_

## Features

| Feature | Priority | Status | Description |
| --- | --- | --- | --- |
| **BR-8 — Bound of this feature.** F-3 does not re-validate grammar, does not decide arity, does not format diagnostics beyond the error-handling rules below, and does not define exit codes for arity errors | medium | planned | **BR-8 — Bound of this feature.** F-3 does not re-validate grammar, does not decide arity, does not format diagnostics beyond the error-handling rules below, and does not define exit codes for arity errors |
| **EC-14 — Digit-limit guard | medium | planned | **EC-14 — Digit-limit guard |
| **API-3 — Function-level contract | medium | planned | **API-3 — Function-level contract |
| **nice-to-have | medium | planned | ** none. F-3 is the core value-producing feature of the tool; nothing in it is optional for a correct `add`. |
| **F-5 local ID scope | medium | planned | ** `AC-1`–`AC-14`, `BR-1`–`BR-7`, `V-1`–`V-8`, `EC-1`–`EC-14`, `EH-1`–`EH-6`, `API-1`–`API-8` are scoped to this feature section and may be reused with different meanings in other feature sections. |
| **B-5.** Behaviour is identical whether the program is invoked as `python3 add.py 2 3`, as an installed console script, or via any other launcher the packaging adopting agent chooses, provided the same interpreter and the same arguments are used. The three-way contract | medium | planned | **B-5.** Behaviour is identical whether the program is invoked as `python3 add.py 2 3`, as an installed console script, or via any other launcher the packaging adopting agent chooses, provided the same interpreter and the same arguments are used. The three-way contract |
| The interpreter's own integer-string conversion ceiling | medium | planned | The interpreter's own integer-string conversion ceiling |
| **BR-7 | medium | planned | ** The interpreter's integer→string digit cap is a host artifact outside this tool's contract; for otherwise-valid input it MUST NOT be surfaced to the user as an error. |
| BR-2 | medium | planned | CLI tests MUST invoke the program as a subprocess using `sys.executable` and the project's CLI entry point, so tests do not depend on `PATH`, virtual environments, or installed packages. |
| BR-5 | medium | planned | Test cases MUST be grouped by feature area and named descriptively (e.g., `test_arity_rejects_zero_operands`, `test_grammar_accepts_leading_zeros`, `test_sum_mixed_signs`, `test_render_negative`, `test_exit_status_success`, `test_diagnostic_arity`, `test_usage_output`). |
| A failing test MUST report the test name, the expected value, and the actual value for stdout, stderr, or exit status as applicable. | medium | planned | A failing test MUST report the test name, the expected value, and the actual value for stdout, stderr, or exit status as applicable. |
| AC-2 | medium | planned | Every functional requirement in F-1 through F-10 has at least one automated test case that exercises its externally observable behaviour. |
| Feature priority | medium | planned | **must-have** — the product plan explicitly includes unit tests for the `add` function and CLI, and the tests are the primary automated verification of all contracts in F-1 through F-10. |
| **AC-2** | medium | planned | No option/flag parsing is performed; a leading `-` is treated as a sign character, not a flag. |

_Source stages: design_

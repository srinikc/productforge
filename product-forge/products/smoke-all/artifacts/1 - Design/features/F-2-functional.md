## F-2: Two positional integer operands
**Feature ID:** F-2

### Requirements

#### Functional Requirements (FR)
| ID | Requirement | Priority |
|----|-------------|----------|
| FR-26 | The program MUST treat the first command-line argument after the program name as `int1` and the second argument as `int2`, with no option parsing or flag recognition. | must-have |
| FR-27 | Each operand MUST be validated against the canonical decimal integer grammar: an optional single sign character (`+` U+002B or `-` U+002D) followed by one or more ASCII decimal digits (`0`–`9`), and nothing else. | must-have |
| FR-28 | The grammar MUST accept leading zeros (e.g., `007`, `-000`, `+00042`) and interpret them as their base-10 integer value. | must-have |
| FR-29 | The grammar MUST accept an explicit `+` sign (e.g., `+5`, `+0`, `+007`). | must-have |
| FR-30 | The grammar MUST accept a single leading `-` sign for negative numbers (e.g., `-5`, `-0`, `-007`). | must-have |
| FR-31 | The grammar MUST reject any operand containing whitespace, underscores, decimal points, commas, exponent notation (`e`/`E`), base prefixes (`0x`, `0o`, `0b`), or any character outside `[0-9+-]` (with sign permitted only at position 0). | must-have |
| FR-32 | The grammar MUST reject a lone sign (`+` or `-`), an empty operand, and multiple signs (e.g., `--5`, `++5`, `+-5`, `-+5`). | must-have |
| FR-33 | The program MUST convert each valid operand to an arbitrary-precision integer value without loss of precision, using only integer arithmetic (no floating-point conversion). | must-have |
| FR-34 | If either operand fails validation, the program MUST follow the error path defined in F-1 `FR-7`: write a single-line diagnostic to stderr naming the offending operand, write nothing to stdout, and exit with status `2`. | must-have |
| FR-35 | The program MUST NOT impose any artificial limit on the number of digits in an operand; the only practical limit is available process memory. | must-have |
| FR-36 | The program MUST treat `--` as an ordinary operand token, not as an end-of-options marker; since `--` does not match the integer grammar, it MUST be rejected as invalid. | must-have |

#### Non-Functional Requirements (NFR)
| ID | Target | Measurement |
|----|--------|-------------|
| NFR-16 | Validation of a single operand MUST complete in O(n) time, where n is the operand length. | Time complexity analysis; linear-time scan of characters. |
| NFR-17 | The program MUST handle operands of at least 10,000 digits without stack overflow, excessive memory use (≤ 10 MB extra heap), or recursion. | Benchmark with a 10,000-digit operand; measure peak RSS. |
| NFR-18 | All parsing and arithmetic MUST be exact integer operations; no floating-point types or operations may be used for parsing or summing. | Code review / static analysis for `float` usage. |
| NFR-19 | The program MUST be deterministic: identical argv inputs always produce identical stdout, stderr, and exit status. | Repeated runs with same argv; compare outputs. |
| NFR-20 | The program MUST NOT require network access, filesystem writes (other than normal process I/O), or any external service. | Run in a sandbox with no network and read-only filesystem; verify success. |
| NFR-21 | The program MUST have no third-party runtime dependencies; only the Python 3 standard library may be used. | Inspect imports; verify no `pip`-installed packages required. |
| NFR-22 | The program MUST NOT evaluate or execute any part of an operand as code (e.g., no `eval`, `exec`, `pickle`, or shell invocation). | Static analysis for dangerous functions. |
| NFR-23 | The program MUST treat operands as data only; no injection vector is possible via the integer grammar. | Security review of parsing path. |
| NFR-24 | Operands and results MUST remain local to the process; no data is transmitted over a network. | Confirm no network APIs are called. |
| NFR-25 | The program MUST run as a single command-line executable without requiring a persistent daemon, configuration file, or database. | Run in a minimal environment with no config files present. |

#### User Stories (US)
| ID | Story |
|----|-------|
| US-16 | As a shell user, I want to pass two integer operands as positional arguments, so that I can get their sum without specifying any flags or options. |
| US-17 | As a shell user, I want to use negative numbers (e.g., `add -5 3`) without the program treating `-5` as an option, so that I can add negative integers directly. |
| US-18 | As a shell user, I want to use a leading `+` sign (e.g., `add +5 3`), so that I can be explicit about positive numbers. |
| US-19 | As a shell user, I want leading zeros to be accepted (e.g., `add 007 3`), so that I can paste numbers without stripping them first. |
| US-20 | As a shell user, I want clear error messages when I provide a non-integer operand (e.g., `add 1.5 2`), so that I can correct my input. |
| US-21 | As a shell user, I want the program to handle very large integers (e.g., 1000 digits), so that I can use it for arbitrary-precision arithmetic. |
| US-22 | As a shell user, I want the program to reject operands with whitespace or other non-numeric characters, so that I don't get silently wrong results. |

### Behaviour
1. The program receives exactly two positional operands: `int1` and `int2`.
2. Each operand is independently validated against the canonical decimal integer grammar (BR-1).
3. If both operands are valid, they are converted to arbitrary-precision integers and summed (delegated to F-1 `FR-3`).
4. If either operand is invalid, no arithmetic is performed; the program writes a diagnostic to stderr, writes nothing to stdout, and exits with status `2` (F-1 `FR-7`).
5. The program does not recognize any option flags; every argument is a positional operand.
6. The program does not read from stdin; all input comes from argv.
7. The program does not use environment variables or configuration files to alter operand parsing.

### Business rules
| ID | Rule |
|----|------|
| BR-1 | The integer grammar is `^[+-]?[0-9]+$` (ASCII characters only). |
| BR-2 | The sign is optional; if present it must be exactly one character: `+` or `-`. |
| BR-3 | At least one digit (`0`–`9`) must follow the optional sign. |
| BR-4 | Leading zeros are permitted and do not change the numeric value (e.g., `007` = 7). |
| BR-5 | A `-` sign before zero yields zero (e.g., `-0` = 0). |
| BR-6 | The program does not implement option flags; all arguments are positional operands. |
| BR-7 | The token `--` is not a separator; it is an invalid operand. |
| BR-8 | Operands are parsed as base-10 integers only; no other bases are recognized. |
| BR-9 | Only ASCII digits `0`–`9` are accepted; Unicode digits or full-width digits are rejected. |
| BR-10 | No whitespace is allowed within an operand. |

### Validation
| ID | Validation step |
|----|----------------|
| V-1 | Check that the argument is not an empty string. |
| V-2 | Check that the argument matches the regex `^[+-]?[0-9]+$`. |
| V-3 | If the argument starts with `+` or `-`, ensure there is at least one digit following. |
| V-4 | Ensure that the argument contains no characters outside `[0-9+-]` (sign only at position 0). |
| V-5 | Ensure that the argument contains no whitespace (spaces, tabs, newlines, etc.). |
| V-6 | Ensure that the argument contains no underscores, dots, commas, or letters. |
| V-7 | Ensure that the argument does not use scientific notation (e.g., `1e3`). |
| V-8 | Ensure that the argument does not use base prefixes (`0x`, `0o`, `0b`). |
| V-9 | Ensure that the argument is not just a sign (`+` or `-`). |
| V-10 | If validation fails, produce the diagnostic specified in EH-1..EH-5. |

### Edge cases
| ID | Case | Expected result |
|----|------|-----------------|
| EC-1 | `+0` | valid, value 0 |
| EC-2 | `-0` | valid, value 0 |
| EC-3 | `007` | valid, value 7 |
| EC-4 | `-007` | valid, value -7 |
| EC-5 | `+007` | valid, value 7 |
| EC-6 | `0` | valid, value 0 |
| EC-7 | `-1` | valid, value -1 |
| EC-8 | `+1` | valid, value 1 |
| EC-9 | `` (empty string) | invalid |
| EC-10 | `+` | invalid |
| EC-11 | `-` | invalid |
| EC-12 | `--1` | invalid |
| EC-13 | `++1` | invalid |
| EC-14 | `+-1` | invalid |
| EC-15 | `-+1` | invalid |
| EC-16 | `1.0` | invalid |
| EC-17 | `1,000` | invalid |
| EC-18 | `1_000` | invalid |
| EC-19 | `0x10` | invalid |
| EC-20 | `1e3` | invalid |
| EC-21 | ` 5` (leading space) | invalid |
| EC-22 | `5 ` (trailing space) | invalid |
| EC-23 | `1 2` (internal space) | invalid |
| EC-24 | `٥` (Arabic-Indic digit five) | invalid |
| EC-25 | `５` (full-width digit five) | invalid |
| EC-26 | 10,000-digit integer | valid, handled by arbitrary-precision integer |
| EC-27 | `--` (double dash) | invalid |

### Error handling
| ID | Behaviour |
|----|-----------|
| EH-1 | If an operand is invalid, the program writes a diagnostic to stderr naming the offending operand and exits with status `2` (per F-1 `FR-7`). |
| EH-2 | The diagnostic includes the invalid operand string, quoted, so the user can see exactly what was rejected (e.g., `add: invalid integer operand: '1.5'`). |
| EH-3 | If both operands are invalid, the program reports the first invalid operand (the one in the first positional slot) and exits with status `2`. |
| EH-4 | No partial output is written to stdout when an operand is invalid. |
| EH-5 | The program does not swallow or transform invalid input; it rejects it outright. |

### Acceptance criteria
| ID | Criterion |
|----|-----------|
| AC-1 | `add 2 3` prints `5` to stdout and exits 0. |
| AC-2 | `add -5 3` prints `-2` to stdout and exits 0. |
| AC-3 | `add +5 3` prints `8` to stdout and exits 0. |
| AC-4 | `add 007 3` prints `10` to stdout and exits 0. |
| AC-5 | `add -007 3` prints `-4` to stdout and exits 0. |
| AC-6 | `add 0 0` prints `0` to stdout and exits 0. |
| AC-7 | `add -0 0` prints `0` to stdout and exits 0. |
| AC-8 | `add 1.5 2` prints a diagnostic to stderr naming `1.5`, prints nothing to stdout, and exits 2. |
| AC-9 | `add 1e3 2` prints a diagnostic to stderr naming `1e3`, prints nothing to stdout, and exits 2. |
| AC-10 | `add 1_000 2` prints a diagnostic to stderr naming `1_000`, prints nothing to stdout, and exits 2. |
| AC-11 | `add "" 2` (empty string) prints a diagnostic to stderr naming the empty operand, prints nothing to stdout, and exits 2. |
| AC-12 | `add + 2` prints a diagnostic to stderr naming `+`, prints nothing to stdout, and exits 2. |
| AC-13 | `add - 2` prints a diagnostic to stderr naming `-`, prints nothing to stdout, and exits 2. |
| AC-14 | `add -- 2` prints a diagnostic to stderr naming `--`, prints nothing to stdout, and exits 2. |
| AC-15 | `add 10000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000 1` prints the correct sum (arbitrary precision). |
| AC-16 | `add -5 3` does not treat `-5` as an option; it is accepted as a valid operand. |

### API behaviour
| ID | Behaviour |
|----|-----------|
| API-1 | Command-line interface: `add <int1> <int2>`. There are no options, flags, or environment variables. |
| API-2 | The program reads only from `argv`; it does not read stdin. |
| API-3 | On success, the program writes only the result to stdout; on failure, it writes only diagnostics to stderr. |
| API-4 | Exit status is `0` on success and `2` on invalid operand (and per F-1, `2` on arity error). |
| API-5 | The program does not implement `--help` or `--version`; invoking with such tokens results in either an arity error or an invalid-operand error. |
| API-6 | The program does not use any configuration files or environment variables to alter operand parsing. |

### Priority
**must-have** — both positional integer operands are fundamental to the core function of the `add` utility.

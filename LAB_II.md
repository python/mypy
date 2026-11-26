# Lab II — Generic Type Suggestions for `dmypy suggest`

## Overview

This project extends mypy's `dmypy suggest` command to recommend **generic function signatures** when relationships between input and output types can be inferred from the function body and multiple call sites.

For example, given:

```python
def identity(value):
    return value

identity(42)
identity("hello")
```

`dmypy suggest` can now output:

```text
[T](T) -> T
```

This corresponds to the Python 3.12+ annotation `def identity[T](value: T) -> T:`. The command **only suggests** a signature; it does not edit the user's Python source file.

## Supported relationships

The current implementation recognizes these common patterns:

| Function body pattern | Suggested signature |
| --- | --- |
| `return value` | `[T](T) -> T` |
| `return items[0]` (lists) | `[T](list[T]) -> T` |
| `return items[0]` (homogeneous tuples) | `[T](tuple[T, ...]) -> T` |
| `return mapping[key]` | `[K, V](dict[K, V], K) -> V` |
| `return callback(value)` | `[T, R](Callable[[T], R], T) -> R` |

The implementation also supports a simple instance-method case, such as `Box.echo(self, item)` returning `item`.

A candidate is only considered when the observed call sites provide suitable, differing type information and its structure matches one of the supported patterns. Unsupported or ambiguous cases fall back to ordinary type suggestions.

## How it works

1. **Collect call-site types.** The existing `SuggestionEngine` gathers argument types observed at calls to the target function. The new `get_generic_callsites()` method normalizes these observations for the inference helper.
2. **Inspect the function AST.** Visitors in `mypy/generic_suggestions.py` recognize direct returns, indexed collection access, dictionary lookup, and single-argument callback application. A separate visitor rejects selected patterns in which relevant arguments are rebound.
3. **Build generic candidates.** `infer_generic_candidates()` creates `CallableType` signatures using mypy's `TypeVarType`, `Instance`, and related internal types. The TypeVars generated for suggestions have the dedicated namespace `dmypy_suggest`.
4. **Validate candidates.** `SuggestionEngine` rechecks candidate signatures with `try_type()`. It rejects candidates that introduce new reported errors compared with the original diagnostics, and it compares the remaining candidates with normal suggestions using error counts and type scores.
5. **Format the result.** Accepted type variables appear in the suggested signature, for example `[K, V](dict[K, V], K) -> V`. The JSON suggestion format may also include a `type_params` field.

The error comparison is intentionally conservative: changes in the text or location of an error may cause a candidate to be rejected. This is a safety mechanism, not a formal proof of correctness for arbitrary programs.

## Additional extension: configurable call-site threshold

The `--generic-min-calls=N` option sets the minimum number of usable observed calls required before generic inference is attempted. The default is **2**.

For example:

```bash
dmypy suggest --generic-min-calls=3 demo_generic.identity
```

If the function has fewer than three suitable call sites, `dmypy suggest` falls back to its ordinary, non-generic suggestion. The current implementation disables generic inference when `N < 2` rather than reporting a CLI validation error.

## Try it locally

Run these commands from the repository root with the project installed in your Python environment:

```bash
dmypy start
dmypy check demo_generic.py
dmypy suggest demo_generic.identity
```

The committed `demo_generic.py` contains three calls with different argument types, so the expected generic output is:

```text
[T](T) -> T
```

You can also demonstrate the configuration option without changing the file:

```bash
dmypy suggest --generic-min-calls=4 demo_generic.identity
# Falls back to a non-generic signature: (object) -> object

dmypy suggest --generic-min-calls=3 demo_generic.identity
# [T](T) -> T
```

To inspect additional supported patterns, see the integration examples in `mypy/test/testgeneric_suggestions.py` and `test-data/unit/fine-grained-suggest.test`.

## Tests and checks

The following commands were run successfully during development:

```bash
# Generic inference unit tests and end-to-end integration tests
python -m pytest -n 0 -q mypy/test/testgeneric_suggestions.py

# Existing and new dmypy suggest scenarios
python -m pytest -n 0 -q mypy/test/testfinegrained.py -k "Suggest"

# General type-checker regression suite
python -m pytest -q mypy/test/testcheck.py

# Project type self-check
python runtests.py self

# Broader fast regression suite
python runtests.py pytest-fast
```

Ruff linting and formatting checks were also used for the modified Python files. The tests include positive examples (identity, collections, callbacks, methods), negative examples (insufficient or uniform calls, reassigned arguments, constrained function bodies), and checks for new diagnostic messages.

## Key changed files

| File | Purpose |
| --- | --- |
| `mypy/generic_suggestions.py` | AST analysis and generic candidate construction |
| `mypy/suggestions.py` | Call-site normalization, candidate validation, and formatting |
| `mypy/typeanal.py` | Handling of suggestion-generated type variables during reanalysis |
| `mypy/dmypy/client.py` | CLI option `--generic-min-calls` |
| `mypy/test/testgeneric_suggestions.py` | Unit and end-to-end tests |
| `mypy/test/testfinegrained.py` and `test-data/unit/fine-grained-suggest.test` | Data-driven `dmypy suggest` tests |
| `demo_generic.py` | Minimal manual demonstration |

## Limitations and design decisions

- The feature intentionally handles **recognizable patterns**, not arbitrary generic relationships or full control-flow/type inference.
- Generic candidates need at least two suitable calls by default. They may not be produced when call-site information is incomplete or contains `Any`.
- The normalization currently targets simple one-actual-argument-per-parameter calls. Complex `*args` / `**kwargs` forms are not supported by this generic path.
- Indexed access is only recognized in limited direct-return forms. Tuple inference uses homogeneous element types; callback inference handles a single argument.
- Reassignment detection and diagnostic comparison reduce false suggestions, but they cannot guarantee that every possible runtime behavior is represented.
- The feature reuses mypy's existing AST, type representation, daemon, and suggestion mechanisms, and does not require new runtime dependencies.

These restrictions are deliberate: when there is insufficient evidence, the tool prefers the existing non-generic suggestion to an unsupported guess.

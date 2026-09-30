---
name: mypyc-optimize
description: Optimize Python source files that are compiled with mypyc (or
  will be compiled). Apply the performance-related changes from the
  mypyc-migrate skill, and improve type annotations so that mypyc can
  generate faster code.
---

# Optimize Python Code Compiled with Mypyc

This skill builds on the mypyc-migrate skill (`../mypyc-migrate/SKILL.md`).
Read that skill first; it has examples and details for the steps below.

Don't change behavior in significant ways. If an improvement would require
non-trivial refactoring or might change behavior, mention it in your summary
instead.

## Steps from the Migrate Skill

In the target files, make sure that all the changes described in the migrate
skill have been applied. These are especially important for performance:

* Annotate all constants in module top level and class bodies using `Final`
  (import from `typing`). Reading `Final` values is much faster than reading
  regular module-level variables. Don't make a value `Final` if any code or
  test reassigns it.
* Annotate all class variables using `ClassVar` (import from `typing`),
  unless they are already `Final`. Without `ClassVar`, mypyc treats a class
  variable as an instance attribute, which takes space in each instance.
* Add `@final` to classes that aren't intended to be subclassed (see the
  rules in the migrate skill).
* Move classes nested within functions or other classes to the module top
  level.
* Don't cache bound methods or global functions in local variables.

Also go through the compatibility checks in "Code That Won't Compile or Will
Break" in the migrate skill, and fix any issues.

## Improve Type Annotations

Precise type annotations let mypyc use fast, specialized operations. Values
with type `Any` and values in functions without annotations use slow,
generic operations.

* Add type annotations to functions that have missing annotations, including
  missing return type annotations (use `-> None` if a function doesn't return
  a value). A function without any annotations isn't type checked by mypy
  (when using default strictness options), and mypyc compiles it using generic
  operations.
* Replace `Any` types with precise types where possible. For example, use
  `list[str]` or `dict[str, int]` instead of `Any`, `list[Any]` or
  `dict[str, Any]` when the item types are known. Prefer concrete types such
  as `list[...]` over abstract types such as `Sequence[...]` when the concrete
  type is known.
* Annotate variables that get their value from untyped code (for example,
  a library without type annotations), so that the variable doesn't have type
  `Any`.

Only use a type if you are confident that it's correct. Compiled code checks
types at runtime and raises `TypeError` if a value has the wrong type (see
"Annotations Are Enforced at Runtime" in the migrate skill). Check callers,
including tests and non-compiled code, to make sure that they never pass
values of other types, such as `None`. Adding annotations to a function that
previously had none also causes mypy to type check its body; fix any new type
errors that this produces.

## Keep Classes Native

Native classes are much faster than regular Python classes (non-native
classes). Making an important class native is often the biggest single
improvement. A class is silently compiled as a non-native class if it uses
an unsupported metaclass or class decorator (see "Class Decorators" in the
migrate skill). Where possible, remove the cause.

For example, a class decorator that registers the class can often be
replaced with an explicit call:

```
@register
class JsonHandler:  # Non-native, due to the class decorator
    ...
```

Call `register` after the class definition instead:

```
class JsonHandler:  # Native
    ...

register(JsonHandler)
```

This is only equivalent if the decorator returns the original class
(instead of a wrapper or a different class). Check the implementation of
the decorator.

If a performance-critical class has non-trivial base classes (other than
`object`, `ABC`, `Generic[...]` or native classes in the same project), a
metaclass other than `ABCMeta`, or class decorators, add `@mypyc_attr(native_class=True)` (import from `mypy_extensions`), so
that the class can't accidentally become non-native later. Don't add it to
other classes, as they are unlikely to become non-native.

### Replace Dataclasses with Regular Classes

Dataclasses are supported, but they aren't as efficient as regular native
classes. Consider replacing performance-critical dataclasses with regular
classes:

```
from dataclasses import dataclass

@dataclass(frozen=True)
class Point:
    x: int
    y: int
    label: str = ""
```

Define `__init__` and `__repr__` explicitly. For a frozen dataclass, declare
the attributes as `Final` in `__init__`, since they can't be assigned to after
initialization:

```
from typing import Final, final

@final
class Point:
    def __init__(self, x: int, y: int, label: str = "") -> None:
        self.x: Final = x
        self.y: Final = y
        self.label: Final = label

    def __repr__(self) -> str:
        return f"Point(x={self.x!r}, y={self.y!r}, label={self.label!r})"
```

Dataclasses also generate other methods, such as `__eq__` (and `__hash__`
for frozen dataclasses, and ordering methods if `order=True`). If any code
compares instances, uses them as dictionary keys or in sets, or sorts them,
define these methods explicitly, as otherwise the behavior changes. Also
check for uses of `dataclasses` functions such as `dataclasses.replace`,
`dataclasses.asdict` or `dataclasses.fields` on the class. Don't replace the
dataclass if these are used.

## Avoid Mutable Module-level Variables

Reading and writing a module-level variable that isn't `Final` requires a
dictionary lookup in the module namespace, which is slow. If a mutable
module-level variable is used frequently (for example, a counter or a cache
updated using `global`), store the state in an attribute of a `Final`
instance of a native class:

```
_calls = 0
_errors = 0

def record(ok: bool) -> None:
    global _calls, _errors
    _calls += 1
    if not ok:
        _errors += 1
```

Use a `Final` object instead:

```
from typing import Final, final

@final
class _Stats:
    def __init__(self) -> None:
        self.calls = 0
        self.errors = 0

_stats: Final = _Stats()

def record(ok: bool) -> None:
    _stats.calls += 1
    if not ok:
        _stats.errors += 1
```

Only do this for internal (often underscore-prefixed) variables that
aren't accessed from other modules or tests, since the variables will no
longer be available as module attributes.

## Avoid Optional Primitive Types in Performance-critical Code

`int`, `float`, `bool` and fixed-length tuple values are unboxed in
compiled code, but union types such as `int | None` are always boxed
(heap-allocated), and operations on them are slower. If `None` is only used
as a marker for a missing value, and there is an otherwise unused value
that can be used as a marker instead, use it in internal code:

```
class Parser:
    def __init__(self) -> None:
        self.error_pos: int | None = None  # Boxed

    def has_error(self) -> bool:
        return self.error_pos is not None
```

Use `-1` to represent a missing position:

```
class Parser:
    def __init__(self) -> None:
        self.error_pos = -1  # -1 if no error; unboxed

    def has_error(self) -> bool:
        return self.error_pos >= 0
```

Only do this if the attribute or variable isn't part of a public interface
and all uses can be updated, and document the marker value in a comment.

## Use librt

The `librt` package has faster alternatives to some standard library
features, optimized for compiled code:

* `librt.strings.StringWriter`: build a `str` (faster than `io.StringIO`
  or `"".join(list_of_parts)`).
* `librt.strings.BytesWriter`: build a `bytes` object (faster than
  `io.BytesIO`, `bytearray` or `b"".join(...)`).
* `librt.base64`: `b64encode`, `b64decode` and related functions (faster
  than the `base64` module).
* `librt.random`: pseudorandom numbers (faster than the `random` module).
* `librt.time.time()`: faster than `time.time()`.
* `librt.threading.Lock`: faster than `threading.Lock`.

Example of using `StringWriter`:

```
def join_items(items: list[str]) -> str:
    parts = []
    for s in items:
        parts.append(s)
        parts.append(",")
    return "".join(parts)
```

Use `StringWriter` instead:

```
from librt.strings import StringWriter

def join_items(items: list[str]) -> str:
    w = StringWriter()
    for s in items:
        w.write(s)
        w.append(ord(","))  # ord(...) of a literal is a compile-time constant
    return w.getvalue()
```

These aren't always drop-in replacements. Check the librt documentation
(`mypyc/doc/librt*.rst` in the mypy repository, or
https://mypyc.readthedocs.io/) before replacing anything. Examples of
differences:

* The `librt.base64` decode functions behave differently for malformed data,
  and don't support the `altchars` and `validate` arguments.
* `librt.random` produces different values than `random` for the same seed,
  and isn't suitable for cryptographic use (neither is `random`).
* Calls to `librt.time.time()` can't be monkey patched in tests.
* `librt.threading.Lock` doesn't support timeouts, subclassing or use with
  `threading.Condition`.

Only use `librt` if the project already depends on it (or you add it as a
dependency). It's installed together with mypy, but compiled code
deployed without mypy needs an explicit dependency.

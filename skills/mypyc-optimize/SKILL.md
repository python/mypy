---
name: mypyc-optimize
description: Optimize Python source files that are compiled with mypyc (or
  will be compiled), or identify performance bottlenecks and optimization
  opportunities in them without making changes. Also apply the
  performance-related changes from the mypyc-migrate skill, and improve
  type annotations so that mypyc can generate faster code.
---

# Optimize Python Code Compiled with Mypyc

This skill builds on the mypyc-migrate skill (`../mypyc-migrate/SKILL.md`).
Read that skill first; it has examples and details for the steps below.

This skill can also be used to only identify bottlenecks and optimization
opportunities, without changing the code. In this case, use the
techniques below (profiling, inspecting generated code, and so on) to find
issues, and report them to the user, ordered by expected impact.

Don't change behavior in significant ways. If an improvement would require
non-trivial refactoring or might change behavior, mention it in your summary
instead.

## Workflow

Optimize incrementally:

1. Find the hot functions using a profile of a realistic workload (see
   "Profiling"), unless the user already told you what to optimize. If
   no profile is available, make educated guesses about likely hot
   functions (e.g. error handling is likely not hot).
2. Make one change, or a small set of related changes, at a time.
3. Run the project's tests after each change, including tests that run
   the compiled code, if there are any. If running the tests or
   benchmarks is slow, you can make changes in larger batches to make
   the process faster.
4. Measure whether the change helps (see "Measure Performance"). Revert
   changes that don't clearly help, unless they are simple or also make
   the code cleaner (such as adding missing annotations). Keep simple
   changes even if their effect can't be measured: many simple changes
   are helpful, but the impact of each one in isolation is often too small
   to measure. If no benchmark is available, first try to show the impact
   using extracted synthetic microbenchmarks that simulate the actual
   code. If this isn't practical, assume that changes that follow the
   instructions below (including their conditions) improve performance.

In your summary, list the changes you made and the measured effect, if
any. Also list changes that you tried but reverted since they didn't help,
and potential bottlenecks that you found but didn't fix (see "Report Other
Potential Bottlenecks").

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
* If you can infer a more precise type for a value from the surrounding
  context, but there's no `isinstance` check (or similar) that would narrow
  the type, use `cast` (import from `typing`) to give mypyc the precise type.
  Assign the result to a new variable, since mypyc uses the declared type of
  a variable.

Only use a type if you are confident that it's correct. Compiled code checks
types at runtime and raises `TypeError` if a value has the wrong type (see
"Annotations Are Enforced at Runtime" in the migrate skill). Check callers,
including tests and non-compiled code, to make sure that they never pass
values of other types, such as `None`. Adding annotations to a function that
previously had none also causes mypy to type check its body; fix any new type
errors that this produces.

## Measure Performance

The speedup from the optimizations below varies a lot, depending on the
code, and some changes don't help at all in a particular case. Measure
whether a change helps before keeping it, especially if it makes the code
more verbose or harder to read.

If the target code is self-contained enough, write a throwaway benchmark
script that imports the compiled modules and runs a realistic workload
(for example, the main entry point on representative input). Run it before
and after each change (or set of related changes, and don't run it too
often if the benchmark runs slowly). Make sure each benchmark run isn't
very slow -- since these are synthetic workloads, they may not show very
minor performance changes reliably.

If the code isn't self-contained (for example, it needs a server, a
database, or a large application to run), extract the hot functions into a
separate module and write microbenchmarks that simulate the behavior of
the original functions. Keep the same type annotations and similar data
(types, sizes and shapes of the values), since these determine what code
mypyc generates. Use these microbenchmarks as synthetic proxies for the
performance of the real code, for example to decide which of several ways
of writing a function is fastest.

When benchmarking:

* Compile benchmarks in a temporary directory, since `mypyc` writes build
  files to the `build/` directory under the current working directory.
* Check that the benchmarked module was actually compiled
  (`mod.__file__` should end in `.so` or `.pyd`), and that mypyc reported
  no errors.
* Run the benchmarked code many times, or in a loop, so that each
  measurement takes at least several milliseconds, and take the best (or
  the median) of several runs using `time.perf_counter()`. Timings can be
  noisy, so only trust differences that are clearly larger than the
  variation between runs.
* Don't leave throwaway benchmarks in the project, unless asked to.

Benchmarks can also be profiled to find where time is spent (see
"Profiling").

## Profiling

Profile the code (or a benchmark) to find the hot functions before
optimizing, and to check where time is spent after a change. Use a native
(sampling) profiler that shows C-level frames. Good options to try, if
they are available:

* `py-spy record --native -o profile.svg -- python3 bench.py` (native
  frames are supported on Linux and Windows)
* `perf` on Linux (`perf record -g python3 bench.py`, then `perf report`)
* On macOS: Instruments (Time Profiler), `samply`, or `sample`
* On Windows: the Visual Studio profiler, or Windows Performance Recorder
  and Analyzer

If the profiled workload seems realistic enough, focus most optimization
effort on the functions where the profile shows the most time is spent
(including time spent in functions they call). Optimizing code that
barely shows up in the profile rarely makes a noticeable difference, and
makes the code more verbose for little gain. The simple, mechanical steps
from the migrate skill can still be applied everywhere.

Don't use `cProfile` or `profile`. They don't produce native frames, and
don't see calls within compiled code, so the results are misleading for
compiled modules.

Compiled functions have names with the prefix `CPyDef_` in profiles (e.g.
`CPyDef_mod___parse` for function `parse` in module `mod`). Functions with
the prefix `CPyPy_` are wrappers used when compiled functions are called
from non-compiled code.

Call stacks can be incomplete if CPython or the compiled extensions were
built without frame pointers. A custom CPython build (and compiled modules)
with `-fno-omit-frame-pointer`, or a profiler mode that uses DWARF debug
information for stack unwinding, can give better results. Look up the
current recommended approach for the profiler and Python version used.

## Inspect Generated Code

Looking at the code mypyc generates can reveal bottlenecks that aren't
obvious from the source code, such as unexpected `Any` types that cause
slow, generic operations to be used.

Mypyc writes the generated intermediate representation (IR) to
`build/ops.txt` and the generated C code to `build/__native*.c`. The IR is
easier to read than C. Signs of generic operations include calls to
C API functions such as `PyObject_GetAttr`, `CPyObject_GetAttr`,
`PyObject_GetItem`, `PyObject_Vectorcall`, `PyObject_GetIter`,
`PyIter_Next` or `PyNumber_Add` (and other `PyNumber_` functions) in a
hot function. Specialized operations have names such as `CPyTagged_Add`
(for `int` values) or `CPyList_GetItem`, or use native attribute access.
Common causes of generic operations include values with type `Any`,
missing annotations, non-native classes, and values that come from
non-compiled modules. Fix these using the other techniques in this skill,
such as annotating variables that get their value from untyped code.

### Operations with Fast Implementations

The mypyc documentation lists the operations that have fast,
specialized implementations for each primitive type. Operations that
aren't listed use generic operations. Check these when choosing between
alternative ways of writing a hot function:

* `mypyc/doc/native_operations.rst` (native classes and functions)
* `mypyc/doc/int_operations.rst`, `float_operations.rst` and
  `bool_operations.rst`
* `mypyc/doc/str_operations.rst`, `bytes_operations.rst` and
  `bytearray_operations.rst`
* `mypyc/doc/list_operations.rst`, `dict_operations.rst`,
  `set_operations.rst`, `frozenset_operations.rst` and
  `tuple_operations.rst`

These files are in the mypy repository, and they are also available at
https://mypyc.readthedocs.io/. For example, a `str` method that isn't
listed in `str_operations.rst` is called using a generic method call.

## Compile Related Modules Together

All modules compiled in a single mypyc invocation (a single `mypyc`
command, or a single `mypycify(...)` call in `setup.py`) form a
*compilation unit*. Calls to functions, methods and classes within a
compilation unit use fast, direct calls, and `Final` values are inlined.
References to other compilation units use slow, generic operations, and
are about as slow as references to non-compiled modules. Using
`separate=True` with `mypycify` still keeps all the modules in the same
compilation unit.

If modules that frequently call each other are compiled using separate
invocations, suggest compiling them together, or report this to the
user. Similarly, if a hot function frequently calls a module that isn't
compiled, consider compiling that module too (after applying the
migrate skill to it). Don't change the build configuration without
asking the user, since it may affect packaging and build times.

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
metaclass other than `ABCMeta`, or class decorators, add
`@mypyc_attr(native_class=True)` (import from `mypy_extensions`), so that the
class can't accidentally become non-native later. Don't add it to other
classes, as they are unlikely to become non-native.

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

## Declare Attributes Assigned Only in `__init__` as `Final`

Reading a `Final` attribute of a native class can be faster, since mypyc
knows that the attribute can't be reassigned after construction. For example,
mypyc can often avoid reference count manipulation when reading the attribute,
and reads are cheaper on free-threaded Python builds:

```
from typing import Final, final

@final
class Span:
    def __init__(self, start: int, end: int) -> None:
        self.start: Final = start
        self.end: Final = end
```

A `Final` attribute is read-only at runtime, so assigning it outside
`__init__` fails, including assignments in non-compiled code (such as tests)
that mypy may not check.
Only make an attribute `Final` if it's clearly assigned only in `__init__`
(for example, in an internal class that is only used in a few places), and
you have access to the tests, so that you can verify that they don't assign
the attribute (for example, to set up a test scenario, or using
monkeypatching).

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

## Use Native Classes Instead of Dictionaries as Records

Dictionaries with a fixed set of string keys are often used as records.
Creating a native class instance and accessing its attributes is much
faster (about 4x faster than `dict[str, Any]` and 2.5x faster than a
`TypedDict` in a benchmark):

```
def make_loc(name: str, line: int) -> dict[str, Any]:
    return {"name": name, "line": line}

def next_line(loc: dict[str, Any]) -> int:
    return loc["line"] + 1
```

Use a native class instead:

```
from typing import final

@final
class Loc:
    def __init__(self, name: str, line: int) -> None:
        self.name = name
        self.line = line

def make_loc(name: str, line: int) -> Loc:
    return Loc(name, line)

def next_line(loc: Loc) -> int:
    return loc.line + 1
```

This also gives precise attribute types instead of `Any`. Only do this if
you can find and update all code that uses the dictionaries. Don't do this
if the dictionaries are part of a public interface, if keys are added or
removed dynamically, or if the dictionaries are passed to code that
requires a dictionary (for example, `json.dumps`, `**` unpacking, iteration
over keys, or `.get()` with a default).

## Dictionary Lookups

### Use a Single `dict.get` Instead of `in` Followed by Indexing

Checking for a key using `in` and then indexing performs two dictionary
lookups. A single `get` is faster if the key is usually present:

```
if key in counts:
    total += counts[key]
```

Use `get` instead:

```
n = counts.get(key)
if n is not None:
    total += n
```

This is only equivalent if the dictionary never contains `None` values.
If the key is usually missing, `in` alone is slightly faster, so only do
this if the key is expected to be present in most cases.

### Replace `defaultdict` with a Plain `dict`

Mypyc has fast, specialized operations for `dict`, but `defaultdict` is
a subclass that doesn't get all of these optimizations. Replacing an
internal `defaultdict` with a plain `dict` is somewhat faster:

```
from collections import defaultdict

counts: defaultdict[str, int] = defaultdict(int)
groups: defaultdict[str, list[int]] = defaultdict(list)
for i, key in enumerate(keys):
    counts[key] += 1
    groups[key].append(i)
```

Use `get` and `setdefault` with a plain `dict` instead:

```
counts: dict[str, int] = {}
groups: dict[str, list[int]] = {}
for i, key in enumerate(keys):
    counts[key] = counts.get(key, 0) + 1
    groups.setdefault(key, []).append(i)
```

Mypyc special-cases `setdefault` with an empty `[]`, `{}` or `set()`
default, so that the empty collection is only created if the key is
missing. Other default values are evaluated on each call, even if the key
is present.

Only do this if the dictionary is internal (it's not returned to callers
or stored in a public attribute), since code that reads a `defaultdict`
may rely on missing keys getting a default value. Check all places where
the dictionary is indexed. The benefit is small, so prioritize this only
in very hot code.

## Return Multiple Values Using Fixed-length Tuples

Fixed-length tuple types such as `tuple[int, str]` are unboxed in
compiled code: returning and unpacking them doesn't allocate an object.
Other ways of returning multiple values are much slower. In a benchmark,
returning two `int` values as a `tuple[int, int]` was about 7x faster than
returning a native class instance, 8x faster than `tuple[int, ...]`, and
40x faster than a `NamedTuple`.

Named tuples are particularly inefficient for this, since creating a named
tuple instance is slow in compiled code (about 7x slower than creating a
native class instance in a benchmark). Accessing items by name, by index or
by unpacking is fairly fast (about as fast as with a regular tuple), but
still slower than accessing native class attributes:

```
from typing import NamedTuple

class QR(NamedTuple):
    q: int
    r: int

def div(a: int, b: int) -> QR:
    return QR(a // b, a % b)

q, r = div(x, 7)
```

Use a fixed-length tuple type instead:

```
def div(a: int, b: int) -> tuple[int, int]:
    return a // b, a % b

q, r = div(x, 7)
```

Only do this for internal functions where all callers can be updated,
since callers may access items by name (such as `div(x, 7).q`), and
named tuples have a different `repr`. If there are more than a few items,
or the names are important for readability, use a small native class
instead (see below). Use a precise, fixed-length tuple type in annotations
instead of `tuple[int, ...]` when the length is known.

### Replace Named Tuples with Native Classes

A simple named tuple that is used like a record (items are accessed by
name) can be replaced with a native class with `Final` attributes. In a
benchmark, creating instances was about 7x faster and accessing attributes
about 3.5x faster. This helps most if many instances are created:

```
from typing import NamedTuple

class Span(NamedTuple):
    start: int
    end: int
```

Use a native class instead:

```
from typing import Final, final

@final
class Span:
    def __init__(self, start: int, end: int) -> None:
        self.start: Final = start
        self.end: Final = end

    def __repr__(self) -> str:
        return f"Span(start={self.start!r}, end={self.end!r})"
```

Only do this if the tuple behavior isn't needed. Check that no code
unpacks the values (`start, end = span`), indexes or iterates over them,
compares them using `==` or `<`, hashes them (uses them as dictionary keys
or in sets), passes them where a tuple is expected, or uses named tuple
methods such as `_replace` or `_asdict`. If equality or hashing is needed,
define `__eq__` and `__hash__` explicitly.

## Initialize Attributes Before `self` Escapes in `__init__`

Mypyc analyzes `__init__` methods to find attributes that are always
initialized. Reading these attributes doesn't need a check for an undefined
value (which would raise `AttributeError`), which makes reads faster. The
analysis stops once `self` may escape: `self` is passed to a function, a
method is called on `self`, or a property of `self` is accessed. Attributes
assigned after this point aren't considered always defined. Calls that
don't involve `self` are fine.

```
class Connection:
    def __init__(self, host: str) -> None:
        self.host = host
        self.register()  # 'self' escapes
        self.retries = 0  # Not always defined
```

Assign attributes before `self` escapes, when this doesn't change behavior:

```
class Connection:
    def __init__(self, host: str) -> None:
        self.host = host
        self.retries = 0  # Always defined
        self.register()
```

A call to `super().__init__()` only makes `self` escape if the base class
`__init__` makes `self` escape (for example, if it calls a method of
`self`). In this case, initialize attributes defined in the subclass before
calling `super().__init__()`, if the values don't depend on `self`:

```
class Base:
    def __init__(self, name: str) -> None:
        self.name = name
        self.setup()  # 'self' escapes

class Child(Base):
    def __init__(self, name: str) -> None:
        # Always defined, since assigned before super().__init__()
        self.count = 0
        super().__init__(name)
```

Only reorder assignments if the code that runs after `self` escapes (the
called methods, including methods overridden in subclasses, and the base
class `__init__`) doesn't read or assign the attributes being moved, and if
the assigned values don't depend on anything that is initialized later.

The analysis is only performed for native classes where all subclasses are
known at compile time. It's not performed for classes with
`allow_interpreted_subclasses=True` or `serializable=True`, for example.
An attribute defined in a base class is only always defined if it's always
defined in all subclasses.

## Use `is` to Compare Enum Values

Comparing an enum value using `is` can be much faster than `==`, when the
value has an optional type such as `Color | None` (about 6x faster in a
benchmark), or when the enum class is defined in a module that isn't compiled
together with the target files. If both operands have the same enum type and
the enum is compiled, `==` is already fast.

```
def is_red(c: Color | None) -> bool:
    return c == Color.RED  # Slow
```

Use `is` (and `is not` instead of `!=`):

```
def is_red(c: Color | None) -> bool:
    return c is Color.RED  # Fast
```

This changes behavior for `IntEnum`, `StrEnum` and other enums that
inherit from a type such as `int` or `str`, since `==` also matches plain
`int` or `str` values, and for enums that define `__eq__`. Only use `is`
with these if you are sure that the other operand is always an enum member.

## Use Integer Code Points Instead of One-character Strings

When processing strings character by character, operating on integer code
points is much faster in compiled code than operating on one-character
strings (often 5x to 15x faster in benchmarks). `ord(s[i])` is a fast
operation when `s` has type `str`, and `ord("x")` of a string literal is a
compile-time constant:

```
def count_separators(s: str) -> int:
    n = 0
    for c in s:
        if c == "," or c == ";":
            n += 1
    return n

def count_digits(s: str) -> int:
    n = 0
    for c in s:
        if "0" <= c <= "9":
            n += 1
    return n
```

Use `ord(...)` instead:

```
def count_separators(s: str) -> int:
    n = 0
    for i in range(len(s)):
        c = ord(s[i])
        if c == ord(",") or c == ord(";"):
            n += 1
    return n

def count_digits(s: str) -> int:
    n = 0
    for i in range(len(s)):
        c = ord(s[i])
        if ord("0") <= c <= ord("9"):
            n += 1
    return n
```

For `str` methods such as `c.isdigit()`, `c.isspace()`, `c.isalpha()`,
`c.isalnum()`, `c.upper()` and `c.lower()` on a one-character string, use the
corresponding functions in `librt.strings` that take a code point (see "Use
librt" below), e.g. `isdigit(ord(s[i]))`. Note that `librt.strings.toupper`
and `tolower` leave code points unchanged if the result would have multiple
code points (e.g. `"ß".upper()` is `"SS"`).

To build a string from code points, use `librt.strings.StringWriter`
(`w.append(c)`).

These changes make code slower when it's not compiled, so only do this in
modules that are compiled.

## Move Nested Functions to Module Level or Methods

Each time the enclosing function is called, a nested function (or a
lambda) must be allocated, together with an environment object for the
captured variables. This is relatively slow, and it adds up if the
enclosing function is called often. Module-level functions and methods
don't have this overhead:

```
def total(a: list[int], k: int) -> int:
    def weight(x: int) -> int:
        return x * k + 1

    t = 0
    for x in a:
        t += weight(x)
    return t
```

Move the nested function to the module level, and pass captured variables
as arguments:

```
def _weight(x: int, k: int) -> int:
    return x * k + 1

def total(a: list[int], k: int) -> int:
    t = 0
    for x in a:
        t += _weight(x, k)
    return t
```

If the nested function is within a method and uses `self`, make it a
method instead (e.g. `self._weight(x)`).

Only do this if the nested function is simple enough (it captures only a
few variables, and it doesn't assign captured variables using
`nonlocal`), or if it's very performance-critical. Otherwise the
refactored code may be harder to read.

If the function is only used as a callback, such as
`sorted(a, key=lambda x: x[0])`, or passed as an argument with type
`Callable[...]`, it's called using a generic operation either way. In
these cases, the only benefit is avoiding the allocation, so move the
function only if the enclosing function is called often.

## Use `vec` Instead of `list` for Packed Item Types

`vec` (from `librt.vecs`) is a growable array type that stores items of
certain types, such as `i64`, `i32`, `u8`, `float` and `bool`, in a packed
binary representation, without boxing. Building, iterating over, and
indexing a `vec` with a packed item type is much faster than with a
`list[int]` or `list[float]` in compiled code, and uses much less memory.
Consider using a `vec` instead of an internal list of integers or floats
in performance-critical code:

```
class Offsets:
    def __init__(self) -> None:
        self.offsets: list[int] = []

    def add(self, x: int) -> None:
        self.offsets.append(x)

    def total(self) -> int:
        t = 0
        for x in self.offsets:
            t += x
        return t
```

Use `vec[i64]` instead:

```
from librt.vecs import append, vec
from mypy_extensions import i64

class Offsets:
    def __init__(self) -> None:
        self.offsets = vec[i64]()

    def add(self, x: i64) -> None:
        self.offsets = append(self.offsets, x)

    def total(self) -> i64:
        t: i64 = 0
        for x in self.offsets:
            t += x
        return t
```

Only do this if the list is internal and changing it doesn't change a
public API. Check all uses of the list, including in tests and
non-compiled code. Be careful to preserve behavior:

* The length of a `vec` value can't be changed. `append`, `extend`,
  `remove` and `pop` are functions that return a new value, which must be
  assigned back (as in `add` above). If other code holds a reference to
  the same list (for example, it was passed to another object that also
  appends to it), the references no longer share changes. Don't convert
  lists that are shared like this.
* `vec` isn't a full sequence type, and it doesn't support all `list`
  operations and methods (such as `sort`). Don't pass it to code that
  expects a `list`.
* Integer values must fit in the item type (e.g. 64 bits for `i64`).
  Arithmetic on native integer types isn't checked for overflow. Use
  native integer types for related local variables too (such as `t`
  above), since conversions between `int` and native integers have a
  cost.
* In free-threaded Python builds, `vec` gives fewer thread safety
  guarantees than `list`.

Avoid union types that include vecs, such as `vec[i64] | vec[float]`,
in performance-critical code. Operations on these use slow, generic
operations, which can make the code much slower than with a `list`.
Optional types such as `vec[i64] | None` are also slower than `vec[i64]`,
even after narrowing using `is not None`. If `None` is only used to mean
"no items", use an empty `vec` instead (an empty `vec` is cheap, since it
doesn't allocate a buffer).

Check the `librt.vecs` documentation (`mypyc/doc/librt_vecs.rst` in the
mypy repository) first, and only use `vec` if the project depends on
`librt` (see "Use librt"). The benefit is much smaller for other item
types, such as `str`, which aren't packed, and there is no benefit in
non-compiled code.

## Generators

Generators are efficient in compiled code. Don't replace a generator with
a function that returns a `list`, even if the result is always fully
consumed, as building the list is usually slower.

An exception is a generator that yields values of a type that `vec` (from
`librt.vecs`) stores in a packed representation, such as `i64` or `float`.
Returning a `vec` can be faster than a generator, especially if the caller
also uses native integer types:

```
from typing import Iterator

def evens(a: list[int]) -> Iterator[int]:
    for x in a:
        if x % 2 == 0:
            yield x
```

Return a `vec` instead:

```
from librt.vecs import append, vec
from mypy_extensions import i64

def evens(a: list[int]) -> vec[i64]:
    result = vec[i64]()
    for x in a:
        if x % 2 == 0:
            result = append(result, x)
    return result
```

This doesn't help for other item types, such as `vec[str]`. Only do this
for internal functions where all callers can be updated, if the values fit
in the fixed-size type, and if the project depends on `librt` (see "Use
librt"). Check the `librt.vecs` documentation first, since `vec` isn't a
full sequence type. Measure the change using a benchmark (see "Measure
Performance").

## Replace `@contextmanager` with a Class

`contextlib.contextmanager` is implemented in non-compiled Python code,
and entering and exiting the context manager involves several slow
operations, even if the decorated generator function is compiled. This is
significant if the `with` statement is on a hot path and the context
manager does little work:

```
from contextlib import contextmanager
from typing import Iterator

@contextmanager
def nested(s: State) -> Iterator[None]:
    s.depth += 1
    try:
        yield
    finally:
        s.depth -= 1
```

Use a native class with `__enter__` and `__exit__` methods instead. Use
precise types for the `__exit__` arguments (instead of `*args`), as this
may be faster:

```
from types import TracebackType
from typing import final

@final
class nested:
    def __init__(self, s: State) -> None:
        self.s = s

    def __enter__(self) -> None:
        self.s.depth += 1

    def __exit__(
        self,
        typ: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.s.depth -= 1
```

The `with nested(s):` statements don't need to be changed. Be careful to
preserve behavior:

* Code after `yield` in a `finally:` block runs whether or not there was
  an exception, and so does `__exit__`. Code after `yield` that isn't
  in a `finally:` block only runs if there was no exception, so in
  `__exit__`, only run it if `typ is None`.
* If the generator catches exceptions raised at `yield` (using
  `except`), the exception is suppressed unless it's re-raised. Return
  `True` from `__exit__` to suppress an exception, and make the return
  type `bool`.
* If the generator yields a value (used as `with nested(s) as x:`),
  return it from `__enter__`.

## Replace itertools and functools with Plain Code

Mypyc compiles `for` loops over lists, `range(...)` and other primitive
types into fast code, but `itertools` and `functools` functions are called
through the generic Python API. Replacing them with plain loops and calls
is often 2x to 10x faster in performance-critical code (and 20x faster in a
benchmark where a callback created using `functools.partial` was replaced
with a direct call):

```
import functools
import itertools
import operator

def total(a: list[int], b: list[int]) -> int:
    t = 0
    for x in itertools.chain(a, b):
        t += x
    return t

def grid_sum(a: list[int], b: list[int]) -> int:
    t = 0
    for x, y in itertools.product(a, b):
        t += x * y
    return t

def deltas(a: list[int]) -> int:
    t = 0
    for x, y in itertools.pairwise(a):
        t += y - x
    return t

def sum_all(a: list[int]) -> int:
    return functools.reduce(operator.add, a, 0)

def triple_all(a: list[int]) -> int:
    return apply_all(functools.partial(scale, 3), a)
```

Use plain loops, indexing and lambdas instead:

```
def total(a: list[int], b: list[int]) -> int:
    t = 0
    for x in a:
        t += x
    for x in b:
        t += x
    return t

def grid_sum(a: list[int], b: list[int]) -> int:
    t = 0
    for x in a:
        for y in b:
            t += x * y
    return t

def deltas(a: list[int]) -> int:
    t = 0
    for i in range(1, len(a)):
        t += a[i] - a[i - 1]
    return t

def sum_all(a: list[int]) -> int:
    t = 0
    for x in a:
        t += x
    return t

def triple_all(a: list[int]) -> int:
    return apply_all(lambda x: scale(3, x), a)
```

If the function that receives the callback is simple and in the same
module, calling `scale` directly in a loop instead is even faster.

Be careful to preserve behavior:

* Replacing `itertools.product` with nested loops is only equivalent if the
  inner iterable can be iterated multiple times (`product` makes a copy of
  each iterable first).
* Indexing only works for sequences such as lists, not for arbitrary
  iterables or iterators.
* `functools.partial` evaluates its arguments once when it's created, but a
  lambda evaluates the expressions each time it's called. If an argument is
  a variable that may be reassigned later, or an expression with side
  effects, assign it to a local variable first.
* A `partial` object has attributes such as `func` and `args`, and a
  different `repr`. Check that no code depends on these.

Only do this in modules that are compiled, as the plain code can be slower
when it's not compiled.

The speedup depends on the function, the types involved and how much work
each iteration does. For functions not covered above, or if you aren't sure
which replacement to use (e.g. a lambda, a small native class with
`__call__`, or inlining the call into a loop), write a short
microbenchmark that compares the variants first (see "Measure
Performance"), and only refactor if there is a clear win.

## Use librt

The `librt` package has faster alternatives to some standard library
features, optimized for compiled code:

* `librt.strings.StringWriter`: build a `str` (faster than `io.StringIO`
  or `"".join(list_of_parts)`).
* `librt.strings.BytesWriter`: build a `bytes` object (faster than
  `io.BytesIO`, `bytearray` or `b"".join(...)`).
* `librt.strings` `read_*` and `write_*` functions: read and write packed
  binary integers and floats (much faster than `struct`, `int.from_bytes` and
  `int.to_bytes`; see "Reading and Writing Binary Data" below).
* `librt.base64`: `b64encode`, `b64decode` and related functions (faster
  than the `base64` module).
* `librt.random`: pseudorandom numbers (faster than the `random` module).
* `librt.time.time()`: faster than `time.time()`.
* `librt.threading.Lock`: faster than `threading.Lock`.
* `librt.vecs.vec`: a growable array type with a packed representation
  for item types such as `i64` and `float` (see "Use `vec` Instead of
  `list` for Packed Item Types").

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

### Reading and Writing Binary Data

`librt.strings` has `read_*` and `write_*` functions for signed 16, 32 and
64-bit integers (`i16`, `i32`, `i64`) and 32 and 64-bit floats (`f32`,
`f64`), in little-endian (`_le`) and big-endian (`_be`) byte order. In
compiled code they are much faster than `struct` and `int.from_bytes`,
which use generic operations:

```
import struct

def total(data: bytes) -> int:
    t = 0
    for i in range(0, len(data), 4):
        t += struct.unpack_from("<i", data, i)[0]
        # or: t += int.from_bytes(data[i:i + 4], "little", signed=True)
    return t

def encode(items: list[int]) -> bytes:
    return b"".join(struct.pack("<i", n) for n in items)
```

Use `read_i32_le` and `write_i32_le` instead:

```
from librt.strings import BytesWriter, read_i32_le, write_i32_le

def total(data: bytes) -> int:
    t = 0
    for i in range(0, len(data), 4):
        t += int(read_i32_le(data, i))
    return t

def encode(items: list[int]) -> bytes:
    b = BytesWriter()
    for n in items:
        write_i32_le(b, n)
    return b.getvalue()
```

Read single bytes using `data[i]`, and write them using `BytesWriter.append`.
Check these differences before replacing anything:

* The integer `read_*` functions return native integers (such as `i32`).
  Arithmetic on native integers that overflows has undefined behavior, so
  convert the result using `int(...)` before using it in arithmetic that could
  exceed the range, such as computing a sum (as above).
* There are no unsigned variants. To read an unsigned 16 or 32-bit value,
  mask the result (`int(read_i32_le(data, i)) & 0xFFFFFFFF`). Leave
  unsigned 64-bit values and unsigned writes as they are, unless you can
  verify that all values fit in the signed range.
* Only replace `struct` formats with an explicit standard byte order (`<`,
  `>` or `!`). Native formats (`@`, `=` or no prefix) can use a different
  byte order, size or alignment.
* `read_*` functions only accept `bytes` (not `bytearray` or `memoryview`),
  and raise `IndexError` instead of `struct.error` if there isn't enough
  data. Passing a value that doesn't fit to a `write_*` function raises
  `ValueError` instead of `struct.error`. Check whether any code catches
  `struct.error`.

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

## Tune Garbage Collection

Compiled code often allocates objects faster than non-compiled code, so a
larger fraction of CPU time can be spent in the CPython garbage collector
(GC). Only consider tuning the GC if the GC shows up as expensive in a CPU
profile of a realistic workload (look for CPython functions related to
garbage collection, which usually have names that start with `gc_`).

Options include making collections less frequent (`gc.set_threshold`),
moving long-lived objects out of GC tracking after startup
(`gc.freeze()`), or disabling the GC during an allocation-heavy phase
(`gc.disable()` followed by `gc.enable()`). The effects vary a lot between
Python versions, since the GC implementation changes between releases,
and some of these can make performance worse or increase memory use.
Measure the effect using a realistic workload.

GC settings affect the whole process, so they belong in the application
entry point, not in library code. Suggest the change to the user instead
of making it, unless you were asked to tune the application as a whole.

## Report Other Potential Bottlenecks

Some code patterns are slow in compiled code, but replacing them often
requires non-trivial tradeoffs, such as changing an API, losing
flexibility, or duplicating code. Don't change these. Instead, report them
to the user as potential bottlenecks if they are on a hot path, and
explain what could be done:

* Calls to functions that take `*args` or `**kwargs`, and calls that use
  `*args` or `**kwargs` to pass arguments. These use slow, generic calls
  instead of fast, direct calls. Explicit parameters would be faster.
* Functions decorated using wrapper decorators (decorators other than
  special-cased ones such as `@property`, `@staticmethod` and
  `@classmethod`), for example decorators used for logging,
  tracing, caching or validation. Calls to decorated functions go through
  the wrapper using generic calls, and often also use `*args` and
  `**kwargs`, which can make each call much slower than calling an
  undecorated function. Possible fixes include calling an undecorated
  helper from the hot path, or removing the decorator where it's not
  needed. If the decorator runs code before and after each call (such as
  for tracing or timing), a `with` statement in the function body that
  uses a native context manager class (see "Replace `@contextmanager`
  with a Class") can be much faster:

  ```
  @traced
  def parse(s: str) -> Node:
      ...
  ```

  Use a `with` statement instead (`tracing` is a native class with
  `__enter__` and `__exit__` methods):

  ```
  def parse(s: str) -> Node:
      with tracing("parse"):
          ...
  ```

  This is only equivalent if the decorator doesn't change the arguments
  or the return value, and if nothing depends on the function being
  wrapped (for example, by checking for attributes added by the
  decorator).

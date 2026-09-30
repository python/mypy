---
name: prepare-for-mypyc
description: Migrate Python source files to be compiled with mypyc.
  Useful for migrating existing code and newly written Python code.
  Make changes that are needed for compatibility and to avoid major
  performance bottlenecks, but the code won't be fully optimized.
---

# Migrate Python Code to be Compiled with Mypyc

## Summary of Key Changes

* In target files, perform these simple refactoring (don't modify behavior):
  * Annotate all constants in module top level and class bodies using `Final` annotation.
    Import `Final` from `typing`.
  * Annotate all class variables using `ClassVar` imported from `typing`. Prefer
    `Final` to `ClassVar` when possible, but don't use both.
  * Replace uses of the `six` package with the modern Python 3 ways of doing things.
  * Add `@final` class decorator to internal/helper classes that conform to these rules,
    if the class clearly isn't intended to be subclassed:
    * They don't have any subclasses in the codebase.
    * They aren't an ABC or a protocol.
    * They aren't an exception class.
    * They don't subclass any stdlib class (other than `object`).
  * Refactor classes defined within functions into top-level classes with
    an underscore name prefix to mark it as internal. Mypyc doesn't support
    classes defined within functions.
  * Refactor classes defined within classes into top-level classes. If other
    code refers to the class by name, you can add an alias to class body
    like `NestedClass: Final = _NestedClass`.
  * Use `@mypyc_attr(native_class=False)` (import from `mypy_extensions`)
    for classes that have non-trivial metaclasses (`ABCMeta` is trivial,
    and also `GenericMeta`).
  * Also make class non-native if class has an unsupported base class from
    `stdlib` or a third-party library (see
    https://mypyc.readthedocs.io/en/stable/native_classes.html#inheritance).
* Check for code patterns that won't compile or will behave differently when
  compiled, and fix them (see "Code That Won't Compile or Will Break" below).
* Apply the simple performance improvements described in "Cheap Performance
  Wins" below.

## Basic Examples

### Annotate Constant

Module-level constant should be annotated:

```
MAX_ITEMS = 100
```

Add `Final` annotation:

```
from typing import Final

MAX_ITEMS: Final = 100
```

Class-level should also be annotated:

```
class Foo:
    MAX_ITEMS = 100
```

Add `Final`:

```
from typing import Final

class Foo:
    MAX_ITEMS: Final = 100
```

## Class Variable

Class variables should always be annotated, since otherwise mypyc treats
them as instance attributes that take space in each instance:

```
class User:
    next_id = 0

    def __init__(self) -> None:
        self.id = User.next_id
        User.next_id += 1
```

Annotate it like this:

```
from typing import ClassVar

class User:
    next_id: ClassVar = 0

    def __init__(self) -> None:
        self.id = User.next_id
        User.next_id += 1
```

### Six Usage

Example of removing use of `six`:

```
import six

def foo(x: object) -> bool:
    return isinstance(x, six.string_types)
```

Use `str` instead of `six.string_types`:

```
def foo(x: object) -> bool:
    return isinstance(x, str)
```

Another example of using `six` usage:

```
def f(d: dict[str, int]) -> None:
   for x in six.itervalues(d):
       print(x)
```

Just use the `values()` method:

```
def f(d: dict[str, int]) -> None:
   for x in d.values():
       print(x)
```

### Add @final Decorator

Assume class definitions like this:

```
class Node:
    def __init__(self, name: str, value: int) -> None:
        self.name = name
        self.value = value
```

Now we can mark `Node` as final, assuming there are no subclasses
anywhere in the repository, since it looks like a simple utility
class that is unlikely to be subclasses:

```
from typing import final

@final
class Node:
    ...
```

Another example:

```
class MyError(Exception):
    pass
```

`MyError` shouldn't be final, since is an exception class and also subclasses
a stdlib class. It doesn't help to make these final.

### Class Nested within Function

Mypyc doesn't support classes defined within functions, so move them to
the module top level:

```
def process(items: list[str]) -> list[str]:
    class Visitor:
        def __init__(self) -> None:
            self.seen: set[str] = set()

        def visit(self, item: str) -> bool:
            if item in self.seen:
                return False
            self.seen.add(item)
            return True

    v = Visitor()
    return [item for item in items if v.visit(item)]
```

Move the class to the top level and add an underscore prefix to the name
to mark it as internal (also add `@final` if the rules above allow it):

```
from typing import final

@final
class _Visitor:
    def __init__(self) -> None:
        self.seen: set[str] = set()

    def visit(self, item: str) -> bool:
        if item in self.seen:
            return False
        self.seen.add(item)
        return True


def process(items: list[str]) -> list[str]:
    v = _Visitor()
    return [item for item in items if v.visit(item)]
```

If the nested class refers to local variables or arguments of the enclosing
function, it can't be moved as is. Pass the values explicitly to the
constructor and store them as attributes instead:

```
def make_filter(prefix: str) -> Callable[[str], bool]:
    class PrefixFilter:
        def __call__(self, s: str) -> bool:
            return s.startswith(prefix)

    return PrefixFilter()
```

Make `prefix` an explicit attribute:

```
from typing import Callable, final

@final
class _PrefixFilter:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix

    def __call__(self, s: str) -> bool:
        return s.startswith(self.prefix)


def make_filter(prefix: str) -> Callable[[str], bool]:
    return _PrefixFilter(prefix)
```

If the captured variable is reassigned after the class is defined (in the
enclosing function or via `nonlocal` in a method), the class sees the
updated value. Preserve these semantics, for example by storing a
reference to a shared mutable object instead of a copy of the value.
If this gets complicated, leave the class nested and mention it in
your summary.

Don't move the class if it's intentionally created anew on each call,
for example if it's built with a base class or class attributes that
depend on function arguments, or if the code relies on each call producing
a distinct class object. Also check whether anything depends on the class
name (e.g. `__name__` or `__qualname__` used in reprs, logging, pickling or
test assertions), since moving and renaming the class changes these.

## Code That Won't Compile or Will Break

Before migrating, check the target files for these patterns. Many of them
need a search across the whole repository (including tests), since the
problem is often in code that uses the migrated module, not in the module
itself. If a fix would change behavior, or would require non-trivial
refactoring, mention it in your summary instead of guessing.

### Type Check Errors

The target files must type check cleanly with mypy, since mypyc won't compile
code with type errors. Don't use `# type: ignore` to silence errors in
compiled code unless there is no alternative, as it can result in incorrect
compiled code.

### Unsupported Mypy Options

Mypyc refuses to compile code if these mypy options are used:

* `--no-strict-optional` (`strict_optional = False` in a config file)
* `--no-strict-bytes` (`strict_bytes = False` in a config file)

Check the mypy configuration (`mypy.ini`, `setup.cfg`, `pyproject.toml`),
including per-module sections that match the target files, and inline
`# mypy: no-strict-optional` comments in the target files. If these options
are used, the target files must type check without them. This can
produce new type errors that need to be fixed, such as missing `None` in
types (`str` instead of `str | None`), or `bytearray` or `memoryview` values
used where `bytes` is expected.

### `if TYPE_CHECKING` and `if MYPY` Blocks

Mypy treats `TYPE_CHECKING` (and a module-level `MYPY = False` constant) as
always true, so it considers any code that only runs when the condition is
false at runtime unreachable. Mypyc compiles such unreachable code into code
that raises `RuntimeError: Reached allegedly unreachable code!`. In a
compiled module, these all fail at runtime (at import time if at module
level):

```
if TYPE_CHECKING:
    from foo import Foo
else:
    Foo = object  # RuntimeError (even if the else block is just "pass")

if not TYPE_CHECKING:
    setup_runtime_hooks()  # RuntimeError

def f() -> str:
    if TYPE_CHECKING:
        return "a"
    else:
        return "b"  # RuntimeError when f() is called
```

An `if TYPE_CHECKING:` block without an `else` branch works as expected: it
isn't executed at runtime. This is the recommended way to import names
only used in annotations, e.g. to break an import cycle. Annotations that use
these names are still checked at runtime:

```
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from foo import Foo

def process(x: Foo) -> None:  # OK
    ...
```

Fix code that runs when the condition is false at runtime:

* Remove `else` branches that only define placeholder names for annotations
  (such as `Foo = object` above). Use `from __future__ import annotations` or
  string literal annotations instead, so that the names aren't needed at
  runtime.
* Move other code in `else` branches and `if not TYPE_CHECKING:` blocks out
  of the conditional, so that it runs unconditionally. If the `if
  TYPE_CHECKING:` branch defines the same name (e.g. a more precise
  type for mypy), you may need to restructure the code. If it's not
  clear how to do this without changing behavior, mention it in your summary.
* Replace `if MYPY:` with `if TYPE_CHECKING:` (import it from `typing`), and
  remove the `MYPY = False` definition.

### Annotations Are Enforced at Runtime

Compiled code checks argument, return and attribute types at runtime,
and raises `TypeError` if a value has the wrong type. Code that worked
despite an inaccurate annotation may fail after compilation:

```
def greet(name: str) -> str:
    if name is None:
        return "Hello!"
    return f"Hello, {name}!"

greet(None)  # TypeError when compiled: str object expected; got None
```

If callers can pass `None` (e.g. from non-compiled or untyped code), fix
the annotation:

```
def greet(name: str | None) -> str:
    ...
```

Look for signs of inaccurate annotations, such as `is None` checks on values
whose type doesn't include `None`, or `isinstance` checks against types that
aren't allowed by the annotation.

### Assigning `int` Values to `float` Variables

Mypy allows an `int` value to be used where a `float` is expected, but
`int` and `float` values have different runtime representations in compiled
code. Assigning an `int` value to a variable or attribute declared as
`float` is a compile error, even in the initial assignment:

```
def average(values: list[float], n: int) -> float:
    total: float = 0  # Error
    for v in values:
        total += v
    if n == 0:
        total = n  # Error
    return total / max(n, 1)
```

Use a float literal, or convert explicitly using `float(...)`:

```
def average(values: list[float], n: int) -> float:
    total = 0.0
    for v in values:
        total += v
    if n == 0:
        total = float(n)
    return total / max(n, 1)
```

The same applies to attributes, such as `self.ratio: float = 1` in
`__init__`. Passing an `int` value as a `float` argument or returning it from
a function with a `float` return type works.

### Surrogate Code Points in String Literals

String literals can't contain lone surrogate code points (U+D800 to U+DFFF),
such as `"\ud800"`. Use `chr(...)`, or compare against the integer code point
using `ord(...)`:

```
from typing import Final

HIGH_SURROGATE: Final = chr(0xD800)  # Instead of "\ud800"

def is_high_surrogate(c: str) -> bool:
    return 0xD800 <= ord(c) <= 0xDBFF  # Instead of "\ud800" <= c <= "\udbff"
```

### Conditional Function and Class Definitions

Defining the same function or class in multiple branches of an `if`
statement is a compile error:

```
if HAS_FAST_IMPL:
    def process(data: bytes) -> bytes:
        return fast_process(data)
else:
    def process(data: bytes) -> bytes:  # Error
        return slow_process(data)
```

Define the function once, and move the condition inside it:

```
def process(data: bytes) -> bytes:
    if HAS_FAST_IMPL:
        return fast_process(data)
    else:
        return slow_process(data)
```

A single definition guarded by a runtime condition compiles, but the function
is always defined, even if the condition is false. Look out for code that
checks for the existence of the function (e.g. using `hasattr` or
`globals()`).

Checks against `sys.version_info` and `sys.platform` are fine, since mypy
evaluates them statically. A `try`/`except ImportError` fallback definition
also works.

### `if __name__ == "__main__"`

The `__name__` of a compiled module is never `"__main__"`, and compiled
modules can't be run using `python -m`. Move the main block to a separate
script that isn't compiled and that imports the module:

```
# mod.py (compiled)
def main() -> None:
    ...

# mod_main.py (not compiled)
from mod import main

if __name__ == "__main__":
    main()
```

### Async Generators

Async generators (`async def` functions that contain `yield`) aren't
supported by mypyc. This includes functions decorated with
`@asynccontextmanager`. Rewrite them as classes that implement the async
iterator protocol (`__aiter__` and `__anext__`) or the async context
manager protocol (`__aenter__` and `__aexit__`). Keep the original function
as a thin wrapper, so that callers don't need to change.

An async generator used as an async iterator:

```
from typing import AsyncIterator

async def countdown(n: int) -> AsyncIterator[int]:
    while n > 0:
        yield n
        n -= 1
```

Rewrite as a class with `__aiter__` and `__anext__`. Local variables that are
preserved between `yield`s become attributes, and `StopAsyncIteration` is
raised at the end of iteration:

```
from typing import AsyncIterator, final

@final
class _Countdown:
    def __init__(self, n: int) -> None:
        self.n = n

    def __aiter__(self) -> "_Countdown":
        return self

    async def __anext__(self) -> int:
        if self.n <= 0:
            raise StopAsyncIteration
        n = self.n
        self.n -= 1
        return n


def countdown(n: int) -> AsyncIterator[int]:
    return _Countdown(n)
```

An async context manager:

```
from contextlib import asynccontextmanager
from typing import AsyncIterator

@asynccontextmanager
async def connect(name: str) -> AsyncIterator[str]:
    print("open")
    try:
        yield name
    finally:
        print("close")
```

Rewrite as a class with `__aenter__` and `__aexit__`. Code before `yield`
goes into `__aenter__`, and the yielded value is returned from it. Code
after `yield` (or in a `finally` block) goes into `__aexit__`:

```
from contextlib import AbstractAsyncContextManager
from types import TracebackType
from typing import final

@final
class _Connection:
    def __init__(self, name: str) -> None:
        self.name = name

    async def __aenter__(self) -> str:
        print("open")
        return self.name

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        print("close")


def connect(name: str) -> AbstractAsyncContextManager[str]:
    return _Connection(name)
```

If the original function catches exceptions raised within the `async with`
block (an `except` clause around `yield`), handle them in `__aexit__` using
`exc`, and return `True` from `__aexit__` if the exception should be
suppressed (declare the return type as `bool` in this case). If the async
generator is complex (e.g. it has multiple `yield` statements in different
places), mention it in your summary instead of rewriting it.

### Monkey Patching and Mocking

Functions and classes in compiled modules can't be monkey patched. Calls
within the same compilation unit are bound at compile time, so replacing a
module attribute has no effect on compiled callers, and replacing methods of
native classes fails:

```
# In a test
with mock.patch("mylib.util.fetch") as m:  # Compiled code calling fetch() isn't affected
    ...

with mock.patch.object(Client, "send"):  # Error: can't set attributes of native class
    ...

Client.send = fake_send  # Error
```

Search the tests (and other code) for `mock.patch`, `patch.object`,
`monkeypatch.setattr` and direct assignments that target the migrated
modules. Possible fixes:

* Inject the dependency explicitly (e.g. as an argument or an attribute)
  instead of patching it.
* Patch something outside the compiled modules.
* Make the class non-native using `@mypyc_attr(native_class=False)`, if
  methods of the class need to be patched (this is slower).

### Undeclared Attributes

Native classes only support attributes that are assigned in the class body
or in methods of the class (similar to `__slots__`). Setting other
attributes from outside the class raises `AttributeError`:

```
class Request:
    def __init__(self, url: str) -> None:
        self.url = url

req = Request("...")
req.retry_count = 0  # Error at runtime
```

Declare the attribute in the class body (or initialize it in `__init__`):

```
class Request:
    retry_count: int = 0

    def __init__(self, url: str) -> None:
        self.url = url
```

Also look for `setattr()` calls with attribute names that aren't known in
advance and uses of `obj.__dict__` or `vars(obj)`, since instances of native
classes don't have a `__dict__`. Make the class non-native if these are
needed.

### Deleting Attributes

Attributes of native classes can't be deleted by default. List any attributes
that are deleted using `del` in `__deletable__` in the class body:

```
class Cache:
    value: int | None

    __deletable__ = ["value"]

    def clear(self) -> None:
        del self.value
```

### Unsupported Dunder Methods

`__getattribute__`, `__delattr__` and `__index__` don't work in native
classes. Make classes that define them non-native.

### Descriptors

Native classes only support `@property`, `@staticmethod` and `@classmethod`
descriptors. Other descriptors, such as `functools.cached_property` or custom
descriptor classes used as class attributes, require a non-native class, or
the code must be rewritten. For example, `cached_property` can be replaced
with a property that stores the value in an attribute:

```
class Config:
    @cached_property
    def settings(self) -> dict[str, str]:
        return load_settings()
```

Rewrite as:

```
class Config:
    def __init__(self) -> None:
        self._settings: dict[str, str] | None = None

    @property
    def settings(self) -> dict[str, str]:
        if self._settings is None:
            self._settings = load_settings()
        return self._settings
```

### Class Decorators

Classes that use class decorators other than `@dataclass`,
`@attr.s(auto_attribs=True)`, `@trait` and `@mypyc_attr` are silently
compiled as non-native classes (similar to classes with unsupported
metaclasses). This is slow but works. Mark them explicitly using
`@mypyc_attr(native_class=False)` to make this clear.

Conversely, you can use `@mypyc_attr(native_class=True)` for important
classes to make it a compile error if the class can't be native.

### Multiple Inheritance

Native classes only support single inheritance, with the exception of trait
types. Mixin classes can often be turned into traits using `@trait` (import
from `mypy_extensions`). Traits must come after the regular base class:

```
from mypy_extensions import trait

@trait
class LoggingMixin:
    def log(self, msg: str) -> None:
        print(msg)

class Service(BaseService, LoggingMixin):  # Trait must come last
    ...
```

If this doesn't work, make the class non-native.

### Pickling and Copying

Instances of native classes can't be pickled or copied using `copy.copy` or
`copy.deepcopy` if `__init__` has required arguments. Search for uses of
`pickle`, `copy` (and libraries that pickle objects, such as
`multiprocessing`) involving migrated classes, and use
`@mypyc_attr(serializable=True)` for these classes:

```
from mypy_extensions import mypyc_attr

@mypyc_attr(serializable=True)
class Job:
    def __init__(self, job_id: int) -> None:
        self.job_id = job_id
```

### Subclassing in Non-compiled Code

By default, native classes can't be subclassed in non-compiled code, or in
another compilation unit. Search for subclasses of migrated classes outside
the migrated files, including test doubles and fakes in tests. Use
`@mypyc_attr(allow_interpreted_subclasses=True)` for these classes (and don't
make them `@final`):

```
from mypy_extensions import mypyc_attr

@mypyc_attr(allow_interpreted_subclasses=True)
class Handler:
    def handle(self, item: str) -> None:
        ...
```

Also don't mark methods `@final` if they are overridden in non-compiled
subclasses, since compiled code will ignore the overrides.

### Class Attributes Overridden in Non-compiled Subclasses

If a non-compiled subclass assigns a new value to an attribute in the class
body, compiled code in the base class won't see the new value, since a class
attribute without a `ClassVar` annotation is an instance attribute with a
default value in a native class:

```
# Compiled
@mypyc_attr(allow_interpreted_subclasses=True)
class Base:
    timeout = 10

    def get_timeout(self) -> int:
        return self.timeout

# Not compiled
class Child(Base):
    timeout = 30

Child().timeout  # 30
Child().get_timeout()  # 10 (!)
```

Search for subclasses that override class attributes. If the attribute is
never assigned via an instance, annotate it with `ClassVar` in the base class
(but not `Final`, since that prevents overriding):

```
from typing import ClassVar

@mypyc_attr(allow_interpreted_subclasses=True)
class Base:
    timeout: ClassVar = 10
```

Otherwise the subclass can assign the attribute in `__init__` instead
(`self.timeout = 30`).

The same problem affects instance attributes that are assigned in methods
of the base class, if a non-compiled subclass defines a class attribute with
the same name. Compiled code and non-compiled code then see different
values, and compiled code may fail with `AttributeError` if the attribute
was never assigned (normal Python would fall back to the class attribute):

```
# Compiled
@mypyc_attr(allow_interpreted_subclasses=True)
class Connection:
    def __init__(self) -> None:
        self.retries = 3

    def get_retries(self) -> int:
        return self.retries

@mypyc_attr(allow_interpreted_subclasses=True)
class Job:
    result: str  # Only assigned in run()

    def get_result(self) -> str:
        return self.result

    def run(self) -> None:
        self.result = "done"

# Not compiled
class FastConnection(Connection):
    retries = 1  # Class attribute shadows an instance attribute

c = FastConnection()
c.retries  # 1 (would be 3 in normal Python)
c.get_retries()  # 3

class DefaultJob(Job):
    result = "pending"

DefaultJob().get_result()  # AttributeError (would be "pending")
```

Fix these by assigning the value in the subclass `__init__` (after calling
`super().__init__()`), instead of using a class attribute:

```
class FastConnection(Connection):
    def __init__(self) -> None:
        super().__init__()
        self.retries = 1
```

For attributes that are only sometimes assigned, such as `Job.result`, it
may be simpler to give the attribute a default value in the base class and
set it in the subclass `__init__`.

### Reassigned Final Values

References to `Final` module-level constants and class attributes are
replaced with the value at compile time, when the value is known during
compilation. If other code or tests reassign a constant (e.g.
`config.MAX_RETRIES = 0` or `monkeypatch.setattr(config, "MAX_RETRIES", 0)`),
compiled code won't see the new value. Don't make these `Final`; leave
them as regular variables.

## Cheap Performance Wins

These changes are simple and don't change behavior, but they can make a big
difference in compiled code.

### Don't Cache Bound Methods in Local Variables

Caching a method in a local variable is a common CPython optimization, but it
makes compiled code slower, since the call can no longer be bound at compile
time:

```
def squares(n: int) -> list[int]:
    a = []
    append = a.append  # Slow in compiled code
    for i in range(n):
        append(i * i)
    return a
```

Call the method directly:

```
def squares(n: int) -> list[int]:
    a = []
    for i in range(n):
        a.append(i * i)
    return a
```

The same applies to caching global functions or module attributes in local
variables or default argument values (e.g. `def f(x, _len=len)`) — refer to
them directly instead.

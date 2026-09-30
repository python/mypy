---
name: prepare-for-mypyc
description: Migrate Python source files to be compiled with mypyc.
  Useful for migrating existing code and newly written Python code.
  Make changes that are needed for compatibility and to avoid major
  performance bottlenecks, but the code won't be fully optimized.
---

# Migrate Python Code to be Compiled with Mypyc

## Summary of Key Changes

* In target files, perform these refactoring (don't modify behavior):
  * Annotate all constants in module top level and class bodies using `Final` annotation.
    Import `Final` from `typing`.
  * Annotate all class variables using `ClassVar` imported from `typing`. Prefer
    `Final` to `ClassVar` when possible, but don't use both.
  * Replace uses of the `six` package with the modern Python 3 ways of doing things.
  * Add `@final` class decorator to internal/helper classes that conform to these rules,
    if the class clearly isn't intended to be subclasses:
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
  * Also make class non-native if class has an unsupported baseclass from
    `stdlib` or a third-party library (see
    https://mypyc.readthedocs.io/en/stable/native_classes.html#inheritance).

## Examples

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

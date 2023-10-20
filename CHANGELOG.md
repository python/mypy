# Mypy Release Notes

## Unreleased

...

#### Other Notable Changes and Fixes
...

#### Acknowledgements
...

## Mypy 1.6

[Tuesday, 10 October 2023](https://mypy-lang.blogspot.com/2023/10/mypy-16-released.html)

We’ve just uploaded mypy 1.6 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

#### Introduce Error Subcodes for Import Errors

Mypy now uses the error code import-untyped if an import targets an installed library that doesn’t support static type checking, and no stub files are available. Other invalid imports produce the import-not-found error code. They both are subcodes of the import error code, which was previously used for both kinds of import-related errors.

Use \--disable-error-code=import-untyped to only ignore import errors about installed libraries without stubs. This way mypy will still report errors about typos in import statements, for example.

If you use \--warn-unused-ignore or \--strict, mypy will complain if you use \# type: ignore\[import\] to ignore an import error. You are expected to use one of the more specific error codes instead. Otherwise, ignoring the import error code continues to silence both errors.

This feature was contributed by Shantanu (PR [15840](https://github.com/python/mypy/pull/15840), PR [14740](https://github.com/python/mypy/pull/14740)).

#### Remove Support for Targeting Python 3.6 and Earlier

Running mypy with \--python-version 3.6, for example, is no longer supported. Python 3.6 hasn’t been properly supported by mypy for some time now, and this makes it explicit. This was contributed by Nikita Sobolev (PR [15668](https://github.com/python/mypy/pull/15668)).

#### Selective Filtering of \--disallow-untyped-calls Targets

Using \--disallow-untyped-calls could be annoying when using libraries with missing type information, as mypy would generate many errors about code that uses the library. Now you can use \--untyped-calls-exclude=acme, for example, to disable these errors about calls targeting functions defined in the acme package. Refer to the [documentation](https://mypy.readthedocs.io/en/latest/command_line.html#cmdoption-mypy-untyped-calls-exclude) for more information.

This feature was contributed by Ivan Levkivskyi (PR [15845](https://github.com/python/mypy/pull/15845)).

#### Improved Type Inference between Callable Types

Mypy now does a better job inferring type variables inside arguments of callable types. For example, this code fragment now type checks correctly:

```python
def f(c: Callable[[T, S], None]) -> Callable[[str, T, S], None]: ...
def g(*x: int) -> None: ...

reveal_type(f(g))  # Callable[[str, int, int], None]
```

This was contributed by Ivan Levkivskyi (PR [15910](https://github.com/python/mypy/pull/15910)).

#### Don’t Consider None and TypeVar to Overlap in Overloads

Mypy now doesn’t consider an overload item with an argument type None to overlap with a type variable:

```python
@overload
def f(x: None) -> None: ..
@overload
def f(x: T) -> Foo[T]: ...
...
```

Previously mypy would generate an error about the definition of f above. This is slightly unsafe if the upper bound of T is object, since the value of the type variable could be None. We relaxed the rules a little, since this solves a common issue.

This feature was contributed by Ivan Levkivskyi (PR [15846](https://github.com/python/mypy/pull/15846)).

#### Improvements to \--new-type-inference

The experimental new type inference algorithm (polymorphic inference) introduced as an opt-in feature in mypy 1.5 has several improvements:

*   Improve transitive closure computation during constraint solving (Ivan Levkivskyi, PR [15754](https://github.com/python/mypy/pull/15754))
*   Add support for upper bounds and values with \--new-type-inference (Ivan Levkivskyi, PR [15813](https://github.com/python/mypy/pull/15813))
*   Basic support for variadic types with \--new-type-inference (Ivan Levkivskyi, PR [15879](https://github.com/python/mypy/pull/15879))
*   Polymorphic inference: support for parameter specifications and lambdas (Ivan Levkivskyi, PR [15837](https://github.com/python/mypy/pull/15837))
*   Invalidate cache when adding \--new-type-inference (Marc Mueller, PR [16059](https://github.com/python/mypy/pull/16059))

**Note:** We are planning to enable \--new-type-inference by default in mypy 1.7. Please try this out and let us know if you encounter any issues.

#### ParamSpec Improvements

*   Support self-types containing ParamSpec (Ivan Levkivskyi, PR [15903](https://github.com/python/mypy/pull/15903))
*   Allow “…” in Concatenate, and clean up ParamSpec literals (Ivan Levkivskyi, PR [15905](https://github.com/python/mypy/pull/15905))
*   Fix ParamSpec inference for callback protocols (Ivan Levkivskyi, PR [15986](https://github.com/python/mypy/pull/15986))
*   Infer ParamSpec constraint from arguments (Ivan Levkivskyi, PR [15896](https://github.com/python/mypy/pull/15896))
*   Fix crash on invalid type variable with ParamSpec (Ivan Levkivskyi, PR [15953](https://github.com/python/mypy/pull/15953))
*   Fix subtyping between ParamSpecs (Ivan Levkivskyi, PR [15892](https://github.com/python/mypy/pull/15892))

#### Stubgen Improvements

*   Add option to include docstrings with stubgen (chylek, PR [13284](https://github.com/python/mypy/pull/13284))
*   Add required ... initializer to NamedTuple fields with default values (Nikita Sobolev, PR [15680](https://github.com/python/mypy/pull/15680))

#### Stubtest Improvements

*   Fix \_\_mypy-replace false positives (Alex Waygood, PR [15689](https://github.com/python/mypy/pull/15689))
*   Fix edge case for bytes enum subclasses (Alex Waygood, PR [15943](https://github.com/python/mypy/pull/15943))
*   Generate error if typeshed is missing modules from the stdlib (Alex Waygood, PR [15729](https://github.com/python/mypy/pull/15729))
*   Fixes to new check for missing stdlib modules (Alex Waygood, PR [15960](https://github.com/python/mypy/pull/15960))
*   Fix stubtest enum.Flag edge case (Alex Waygood, PR [15933](https://github.com/python/mypy/pull/15933))

#### Documentation Improvements

*   Do not advertise to create your own assert\_never helper (Nikita Sobolev, PR [15947](https://github.com/python/mypy/pull/15947))
*   Fix all the missing references found within the docs (Albert Tugushev, PR [15875](https://github.com/python/mypy/pull/15875))
*   Document await-not-async error code (Shantanu, PR [15858](https://github.com/python/mypy/pull/15858))
*   Improve documentation of disabling error codes (Shantanu, PR [15841](https://github.com/python/mypy/pull/15841))

#### Other Notable Changes and Fixes

*   Make unsupported PEP 695 features (introduced in Python 3.12) give a reasonable error message (Shantanu, PR [16013](https://github.com/python/mypy/pull/16013))
*   Remove the \--py2 command-line argument (Marc Mueller, PR [15670](https://github.com/python/mypy/pull/15670))
*   Change empty tuple from tuple\[\] to tuple\[()\] in error messages (Nikita Sobolev, PR [15783](https://github.com/python/mypy/pull/15783))
*   Fix assert\_type failures when some nodes are deferred (Nikita Sobolev, PR [15920](https://github.com/python/mypy/pull/15920))
*   Generate error on unbound TypeVar with values (Nikita Sobolev, PR [15732](https://github.com/python/mypy/pull/15732))
*   Fix over-eager types-google-cloud-ndb suggestion (Shantanu, PR [15347](https://github.com/python/mypy/pull/15347))
*   Fix type narrowing of \== None and in (None,) conditions (Marti Raudsepp, PR [15760](https://github.com/python/mypy/pull/15760))
*   Fix inference for attrs.fields (Shantanu, PR [15688](https://github.com/python/mypy/pull/15688))
*   Make “await in non-async function” a non-blocking error and give it an error code (Gregory Santosa, PR [15384](https://github.com/python/mypy/pull/15384))
*   Add basic support for decorated overloads (Ivan Levkivskyi, PR [15898](https://github.com/python/mypy/pull/15898))
*   Fix TypeVar regression with self types (Ivan Levkivskyi, PR [15945](https://github.com/python/mypy/pull/15945))
*   Add \_\_match\_args\_\_ to dataclasses with no fields (Ali Hamdan, PR [15749](https://github.com/python/mypy/pull/15749))
*   Include stdout and stderr in dmypy verbose output (Valentin Stanciu, PR [15881](https://github.com/python/mypy/pull/15881))
*   Improve match narrowing and reachability analysis (Shantanu, PR [15882](https://github.com/python/mypy/pull/15882))
*   Support \_\_bool\_\_ with Literal in \--warn-unreachable (Jannic Warken, PR [15645](https://github.com/python/mypy/pull/15645))
*   Fix inheriting from generic @frozen attrs class (Ilya Priven, PR [15700](https://github.com/python/mypy/pull/15700))
*   Correctly narrow types for tuple\[type\[X\], ...\] (Nikita Sobolev, PR [15691](https://github.com/python/mypy/pull/15691))
*   Don't flag intentionally empty generators unreachable (Ilya Priven, PR [15722](https://github.com/python/mypy/pull/15722))
*   Add tox.ini to mypy sdist (Marcel Telka, PR [15853](https://github.com/python/mypy/pull/15853))
*   Fix mypyc regression with pretty (Shantanu, PR [16124](https://github.com/python/mypy/pull/16124))

#### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=6a8d653a671925b0a3af61729ff8cf3f90c9c662+0&branch=main&path=stdlib) for full list of typeshed changes.

#### Acknowledgements

Thanks to Max Murin, who did most of the release manager work for this release (I just did the final steps).

Thanks to all mypy contributors who contributed to this release:

*   Albert Tugushev
*   Alex Waygood
*   Ali Hamdan
*   chylek
*   EXPLOSION
*   Gregory Santosa
*   Ilya Priven
*   Ivan Levkivskyi
*   Jannic Warken
*   KotlinIsland
*   Marc Mueller
*   Marcel Johannesmann
*   Marcel Telka
*   Mark Byrne
*   Marti Raudsepp
*   Max Murin
*   Nikita Sobolev
*   Shantanu
*   Valentin Stanciu

Posted by Jukka Lehtosalo


## Mypy 1.5

[Thursday, 10 August 2023](https://mypy-lang.blogspot.com/2023/08/mypy-15-released.html)

We’ve just uploaded mypy 1.5 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, deprecations and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

#### Drop Support for Python 3.7

Mypy no longer supports running with Python 3.7, which has reached end-of-life. This was contributed by Shantanu (PR [15566](https://github.com/python/mypy/pull/15566)).

#### Optional Check to Require Explicit @override

If you enable the explicit-override error code, mypy will generate an error if a method override doesn’t use the @typing.override decorator (as discussed in [PEP 698](https://peps.python.org/pep-0698/#strict-enforcement-per-project)). This way mypy will detect accidentally introduced overrides. Example:

```python
# mypy: enable-error-code="explicit-override"

from typing_extensions import override

class C:
    def foo(self) -> None: pass
    def bar(self) -> None: pass

class D(C):
    # Error: Method "foo" is not using @override but is
    # overriding a method
    def foo(self) -> None:
        ...

    @override
    def bar(self) -> None:  # OK
        ...
```

You can enable the error code via \--enable-error-code=explicit-override on the mypy command line or enable\_error\_code = explicit-override in the mypy config file.

The override decorator will be available in typing in Python 3.12, but you can also use the backport from a recent version of `typing_extensions` on all supported Python versions.

This feature was contributed by Marc Mueller(PR [15512](https://github.com/python/mypy/pull/15512)).

#### More Flexible TypedDict Creation and Update

Mypy was previously overly strict when type checking TypedDict creation and update operations. Though these checks were often technically correct, they sometimes triggered for apparently valid code. These checks have now been relaxed by default. You can enable stricter checking by using the new \--extra-checks flag.

Construction using the `**` syntax is now more flexible:

```python
from typing import TypedDict

class A(TypedDict):
    foo: int
    bar: int

class B(TypedDict):
    foo: int

a: A = {"foo": 1, "bar": 2}
b: B = {"foo": 3}
a2: A = { **a, **b}  # OK (previously an error)
```

You can also call update() with a TypedDict argument that contains a subset of the keys in the updated TypedDict:
```python
a.update(b)  # OK (previously an error)
```

This feature was contributed by Ivan Levkivskyi (PR [15425](https://github.com/python/mypy/pull/15425)).

#### Deprecated Flag: \--strict-concatenate

The behavior of \--strict-concatenate is now included in the new \--extra-checks flag, and the old flag is deprecated.

#### Optionally Show Links to Error Code Documentation

If you use \--show-error-code-links, mypy will add documentation links to (many) reported errors. The links are not shown for error messages that are sufficiently obvious, and they are shown once per error code only.

Example output:
```
a.py:1: error: Need type annotation for "foo" (hint: "x: List[<type>] = ...")  [var-annotated]
a.py:1: note: See https://mypy.rtfd.io/en/stable/_refs.html#code-var-annotated for more info
```
This was contributed by Ivan Levkivskyi (PR [15449](https://github.com/python/mypy/pull/15449)).

#### Consistently Avoid Type Checking Unreachable Code

If a module top level has unreachable code, mypy won’t type check the unreachable statements. This is consistent with how functions behave. The behavior of \--warn-unreachable is also more consistent now.

This was contributed by Ilya Priven (PR [15386](https://github.com/python/mypy/pull/15386)).

#### Experimental Improved Type Inference for Generic Functions

You can use \--new-type-inference to opt into an experimental new type inference algorithm. It fixes issues when calling a generic functions with an argument that is also a generic function, in particular. This current implementation is still incomplete, but we encourage trying it out and reporting bugs if you encounter regressions. We are planning to enable the new algorithm by default in a future mypy release.

This feature was contributed by Ivan Levkivskyi (PR [15287](https://github.com/python/mypy/pull/15287)).

#### Partial Support for Python 3.12

Mypy and mypyc now support running on recent Python 3.12 development versions. Not all new Python 3.12 features are supported, and we don’t ship compiled wheels for Python 3.12 yet.

*   Fix ast warnings for Python 3.12 (Nikita Sobolev, PR [15558](https://github.com/python/mypy/pull/15558))
*   mypyc: Fix multiple inheritance with a protocol on Python 3.12 (Jukka Lehtosalo, PR [15572](https://github.com/python/mypy/pull/15572))
*   mypyc: Fix self-compilation on Python 3.12 (Jukka Lehtosalo, PR [15582](https://github.com/python/mypy/pull/15582))
*   mypyc: Fix 3.12 issue with pickling of instances with \_\_dict\_\_ (Jukka Lehtosalo, PR [15574](https://github.com/python/mypy/pull/15574))
*   mypyc: Fix i16 on Python 3.12 (Jukka Lehtosalo, PR [15510](https://github.com/python/mypy/pull/15510))
*   mypyc: Fix int operations on Python 3.12 (Jukka Lehtosalo, PR [15470](https://github.com/python/mypy/pull/15470))
*   mypyc: Fix generators on Python 3.12 (Jukka Lehtosalo, PR [15472](https://github.com/python/mypy/pull/15472))
*   mypyc: Fix classes with \_\_dict\_\_ on 3.12 (Jukka Lehtosalo, PR [15471](https://github.com/python/mypy/pull/15471))
*   mypyc: Fix coroutines on Python 3.12 (Jukka Lehtosalo, PR [15469](https://github.com/python/mypy/pull/15469))
*   mypyc: Don't use \_PyErr\_ChainExceptions on 3.12, since it's deprecated (Jukka Lehtosalo, PR [15468](https://github.com/python/mypy/pull/15468))
*   mypyc: Add Python 3.12 feature macro (Jukka Lehtosalo, PR [15465](https://github.com/python/mypy/pull/15465))

#### Improvements to Dataclasses

*   Improve signature of dataclasses.replace (Ilya Priven, PR [14849](https://github.com/python/mypy/pull/14849))
*   Fix dataclass/protocol crash on joining types (Ilya Priven, PR [15629](https://github.com/python/mypy/pull/15629))
*   Fix strict optional handling in dataclasses (Ivan Levkivskyi, PR [15571](https://github.com/python/mypy/pull/15571))
*   Support optional types for custom dataclass descriptors (Marc Mueller, PR [15628](https://github.com/python/mypy/pull/15628))
*   Add `__slots__` attribute to dataclasses (Nikita Sobolev, PR [15649](https://github.com/python/mypy/pull/15649))
*   Support better \_\_post\_init\_\_ method signature for dataclasses (Nikita Sobolev, PR [15503](https://github.com/python/mypy/pull/15503))

#### Mypyc Improvements

*   Support unsigned 8-bit native integer type: mypy\_extensions.u8 (Jukka Lehtosalo, PR [15564](https://github.com/python/mypy/pull/15564))
*   Support signed 16-bit native integer type: mypy\_extensions.i16 (Jukka Lehtosalo, PR [15464](https://github.com/python/mypy/pull/15464))
*   Define mypy\_extensions.i16 in stubs (Jukka Lehtosalo, PR [15562](https://github.com/python/mypy/pull/15562))
*   Document more unsupported features and update supported features (Richard Si, PR [15524](https://github.com/python/mypy/pull/15524))
*   Fix final NamedTuple classes (Richard Si, PR [15513](https://github.com/python/mypy/pull/15513))
*   Use C99 compound literals for undefined tuple values (Jukka Lehtosalo, PR [15453](https://github.com/python/mypy/pull/15453))
*   Don't explicitly assign NULL values in setup functions (Logan Hunt, PR [15379](https://github.com/python/mypy/pull/15379))

#### Stubgen Improvements

*   Teach stubgen to work with complex and unary expressions (Nikita Sobolev, PR [15661](https://github.com/python/mypy/pull/15661))
*   Support ParamSpec and TypeVarTuple (Ali Hamdan, PR [15626](https://github.com/python/mypy/pull/15626))
*   Fix crash on non-str docstring (Ali Hamdan, PR [15623](https://github.com/python/mypy/pull/15623))

#### Documentation Updates

*   Add documentation for additional error codes (Ivan Levkivskyi, PR [15539](https://github.com/python/mypy/pull/15539))
*   Improve documentation of type narrowing (Ilya Priven, PR [15652](https://github.com/python/mypy/pull/15652))
*   Small improvements to protocol documentation (Shantanu, PR [15460](https://github.com/python/mypy/pull/15460))
*   Remove confusing instance variable example in cheat sheet (Adel Atallah, PR [15441](https://github.com/python/mypy/pull/15441))

#### Other Notable Fixes and Improvements

*   Constant fold additional unary and binary expressions (Richard Si, PR [15202](https://github.com/python/mypy/pull/15202))
*   Exclude the same special attributes from Protocol as CPython (Kyle Benesch, PR [15490](https://github.com/python/mypy/pull/15490))
*   Change the default value of the slots argument of attrs.define to True, to match runtime behavior (Ilya Priven, PR [15642](https://github.com/python/mypy/pull/15642))
*   Fix type of class attribute if attribute is defined in both class and metaclass (Alex Waygood, PR [14988](https://github.com/python/mypy/pull/14988))
*   Handle type the same as typing.Type in the first argument of classmethods (Erik Kemperman, PR [15297](https://github.com/python/mypy/pull/15297))
*   Fix \--find-occurrences flag (Shantanu, PR [15528](https://github.com/python/mypy/pull/15528))
*   Fix error location for class patterns (Nikita Sobolev, PR [15506](https://github.com/python/mypy/pull/15506))
*   Fix re-added file with errors in mypy daemon (Ivan Levkivskyi, PR [15440](https://github.com/python/mypy/pull/15440))
*   Fix dmypy run on Windows (Ivan Levkivskyi, PR [15429](https://github.com/python/mypy/pull/15429))
*   Fix abstract and non-abstract variant error for property deleter (Shantanu, PR [15395](https://github.com/python/mypy/pull/15395))
*   Remove special casing for "cannot" in error messages (Ilya Priven, PR [15428](https://github.com/python/mypy/pull/15428))
*   Add runtime `__slots__` attribute to attrs classes (Nikita Sobolev, PR [15651](https://github.com/python/mypy/pull/15651))
*   Add get\_expression\_type to CheckerPluginInterface (Ilya Priven, PR [15369](https://github.com/python/mypy/pull/15369))
*   Remove parameters that no longer exist from NamedTuple.\_make() (Alex Waygood, PR [15578](https://github.com/python/mypy/pull/15578))
*   Allow using typing.Self in `__all__` with an explicit @staticmethod decorator (Erik Kemperman, PR [15353](https://github.com/python/mypy/pull/15353))
*   Fix self types in subclass methods without Self annotation (Ivan Levkivskyi, PR [15541](https://github.com/python/mypy/pull/15541))
*   Check for abstract class objects in tuples (Nikita Sobolev, PR [15366](https://github.com/python/mypy/pull/15366))

#### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=fc7d4722eaa54803926cee5730e1f784979c0531+0&branch=main&path=stdlib) for full list of typeshed changes.

#### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Adel Atallah
*   Alex Waygood
*   Ali Hamdan
*   Erik Kemperman
*   Federico Padua
*   Ilya Priven
*   Ivan Levkivskyi
*   Jelle Zijlstra
*   Jared Hance
*   Jukka Lehtosalo
*   Kyle Benesch
*   Logan Hunt
*   Marc Mueller
*   Nikita Sobolev
*   Richard Si
*   Shantanu
*   Stavros Ntentos
*   Valentin Stanciu

Posted by Valentin Stanciu


## Mypy 1.4

[Tuesday, 20 June 2023](https://mypy-lang.blogspot.com/2023/06/mypy-140-released.html)

We’ve just uploaded mypy 1.4 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

#### The Override Decorator

Mypy can now ensure that when renaming a method, overrides are also renamed. You can explicitly mark a method as overriding a base class method by using the @typing.override decorator ([PEP 698](https://peps.python.org/pep-0698/)). If the method is then renamed in the base class while the method override is not, mypy will generate an error. The decorator will be available in typing in Python 3.12, but you can also use the backport from a recent version of `typing_extensions` on all supported Python versions.

This feature was contributed byThomas M Kehrenberg (PR [14609](https://github.com/python/mypy/pull/14609)).

#### Propagating Type Narrowing to Nested Functions

Previously, type narrowing was not propagated to nested functions because it would not be sound if the narrowed variable changed between the definition of the nested function and the call site. Mypy will now propagate the narrowed type if the variable is not assigned to after the definition of the nested function:

```python
def outer(x: str | None = None) -> None:
    if x is None:
        x = calculate_default()
    reveal_type(x)  # "str" (narrowed)

    def nested() -> None:
        reveal_type(x)  # Now "str" (used to be "str | None")

    nested()
```

This may generate some new errors because asserts that were previously necessary may become tautological or no-ops.

This was contributed by Jukka Lehtosalo (PR [15133](https://github.com/python/mypy/pull/15133)).

#### Narrowing Enum Values Using “==”

Mypy now allows narrowing enum types using the \== operator. Previously this was only supported when using the is operator. This makes exhaustiveness checking with enum types more usable, as the requirement to use the is operator was not very intuitive. In this example mypy can detect that the developer forgot to handle the value MyEnum.C in example

```python
from enum import Enum

class MyEnum(Enum):
    A = 0
    B = 1
    C = 2

def example(e: MyEnum) -> str:  # Error: Missing return statement
    if e == MyEnum.A:
        return 'x'
    elif e == MyEnum.B:
        return 'y'
```

Adding an extra elif case resolves the error:

```python
...
def example(e: MyEnum) -> str:  # No error -- all values covered
    if e == MyEnum.A:
        return 'x'
    elif e == MyEnum.B:
        return 'y'
    elif e == MyEnum.C:
        return 'z'
```

This change can cause false positives in test cases that have assert statements like assert o.x == SomeEnum.X when using \--strict-equality. Example:

```python
# mypy: strict-equality

from enum import Enum

class MyEnum(Enum):
    A = 0
    B = 1

class C:
    x: MyEnum
    ...

def test_something() -> None:
    c = C(...)
    assert c.x == MyEnum.A
    c.do_something_that_changes_x()
    assert c.x == MyEnum.B  # Error: Non-overlapping equality check
```

These errors can be ignored using \# type: ignore\[comparison-overlap\], or you can perform the assertion using a temporary variable as a workaround:

```python
...
def test_something() -> None:
    ...
    x = c.x
    assert x == MyEnum.A  # Does not narrow c.x
    c.do_something_that_changes_x()
    x = c.x
    assert x == MyEnum.B  # OK
```

This feature was contributed by Shantanu (PR [11521](https://github.com/python/mypy/pull/11521)).

#### Performance Improvements

*   Speed up simplification of large union types and also fix a recursive tuple crash (Shantanu, PR [15128](https://github.com/python/mypy/pull/15128))
*   Speed up union subtyping (Shantanu, PR [15104](https://github.com/python/mypy/pull/15104))
*   Don't type check most function bodies when type checking third-party library code, or generally when ignoring errors (Jukka Lehtosalo, PR [14150](https://github.com/python/mypy/pull/14150))

#### Improvements to Plugins

*   attrs.evolve: Support generics and unions (Ilya Konstantinov, PR [15050](https://github.com/python/mypy/pull/15050))
*   Fix ctypes plugin (Alex Waygood)

#### Fixes to Crashes

*   Fix a crash when function-scope recursive alias appears as upper bound (Ivan Levkivskyi, PR [15159](https://github.com/python/mypy/pull/15159))
*   Fix crash on follow\_imports\_for\_stubs (Ivan Levkivskyi, PR [15407](https://github.com/python/mypy/pull/15407))
*   Fix stubtest crash in explicit init subclass (Shantanu, PR [15399](https://github.com/python/mypy/pull/15399))
*   Fix crash when indexing TypedDict with empty key (Shantanu, PR [15392](https://github.com/python/mypy/pull/15392))
*   Fix crash on NamedTuple as attribute (Ivan Levkivskyi, PR [15404](https://github.com/python/mypy/pull/15404))
*   Correctly track loop depth for nested functions/classes (Ivan Levkivskyi, PR [15403](https://github.com/python/mypy/pull/15403))
*   Fix crash on joins with recursive tuples (Ivan Levkivskyi, PR [15402](https://github.com/python/mypy/pull/15402))
*   Fix crash with custom ErrorCode subclasses (Marc Mueller, PR [15327](https://github.com/python/mypy/pull/15327))
*   Fix crash in dataclass protocol with self attribute assignment (Ivan Levkivskyi, PR [15157](https://github.com/python/mypy/pull/15157))
*   Fix crash on lambda in generic context with generic method in body (Ivan Levkivskyi, PR [15155](https://github.com/python/mypy/pull/15155))
*   Fix recursive type alias crash in make\_simplified\_union (Ivan Levkivskyi, PR [15216](https://github.com/python/mypy/pull/15216))

#### Improvements to Error Messages

*   Use lower-case built-in collection types such as list\[…\] instead of List\[…\] in errors when targeting Python 3.9+ (Max Murin, PR [15070](https://github.com/python/mypy/pull/15070))
*   Use X | Y union syntax in error messages when targeting Python 3.10+ (Omar Silva, PR [15102](https://github.com/python/mypy/pull/15102))
*   Use type instead of Type in errors when targeting Python 3.9+ (Rohit Sanjay, PR [15139](https://github.com/python/mypy/pull/15139))
*   Do not show unused-ignore errors in unreachable code, and make it a real error code (Ivan Levkivskyi, PR [15164](https://github.com/python/mypy/pull/15164))
*   Don’t limit the number of errors shown by default (Rohit Sanjay, PR [15138](https://github.com/python/mypy/pull/15138))
*   Improver message for truthy functions (madt2709, PR [15193](https://github.com/python/mypy/pull/15193))
*   Output distinct types when type names are ambiguous (teresa0605, PR [15184](https://github.com/python/mypy/pull/15184))
*   Update message about invalid exception type in try (AJ Rasmussen, PR [15131](https://github.com/python/mypy/pull/15131))
*   Add explanation if argument type is incompatible because of an unsupported numbers type (Jukka Lehtosalo, PR [15137](https://github.com/python/mypy/pull/15137))
*   Add more detail to 'signature incompatible with supertype' messages for non-callables (Ilya Priven, PR [15263](https://github.com/python/mypy/pull/15263))

#### Documentation Updates

*   Add \--local-partial-types note to dmypy docs (Alan Du, PR [15259](https://github.com/python/mypy/pull/15259))
*   Update getting started docs for mypyc for Windows (Valentin Stanciu, PR [15233](https://github.com/python/mypy/pull/15233))
*   Clarify usage of callables regarding type object in docs (Viicos, PR [15079](https://github.com/python/mypy/pull/15079))
*   Clarify difference between disallow\_untyped\_defs and disallow\_incomplete\_defs (Ilya Priven, PR [15247](https://github.com/python/mypy/pull/15247))
*   Use attrs and @attrs.define in documentation and tests (Ilya Priven, PR [15152](https://github.com/python/mypy/pull/15152))

#### Mypyc Improvements

*   Fix unexpected TypeError for certain variables with an inferred optional type (Richard Si, PR [15206](https://github.com/python/mypy/pull/15206))
*   Inline math literals (Logan Hunt, PR [15324](https://github.com/python/mypy/pull/15324))
*   Support unpacking mappings in dict display (Richard Si, PR [15203](https://github.com/python/mypy/pull/15203))

#### Changes to Stubgen

*   Do not remove Generic from base classes (Ali Hamdan, PR [15316](https://github.com/python/mypy/pull/15316))
*   Support yield from statements (Ali Hamdan, PR [15271](https://github.com/python/mypy/pull/15271))
*   Fix missing total from TypedDict class (Ali Hamdan, PR [15208](https://github.com/python/mypy/pull/15208))
*   Fix call-based namedtuple omitted from class bases (Ali Hamdan, PR [14680](https://github.com/python/mypy/pull/14680))
*   Support TypedDict alternative syntax (Ali Hamdan, PR [14682](https://github.com/python/mypy/pull/14682))
*   Make stubgen respect MYPY\_CACHE\_DIR (Henrik Bäärnhielm, PR [14722](https://github.com/python/mypy/pull/14722))
*   Fixes and simplifications (Ali Hamdan, PR [15232](https://github.com/python/mypy/pull/15232))

#### Other Notable Fixes and Improvements

*   Fix nested async functions when using TypeVar value restriction (Jukka Lehtosalo, PR [14705](https://github.com/python/mypy/pull/14705))
*   Always allow returning Any from lambda (Ivan Levkivskyi, PR [15413](https://github.com/python/mypy/pull/15413))
*   Add foundation for TypeVar defaults (PEP 696) (Marc Mueller, PR [14872](https://github.com/python/mypy/pull/14872))
*   Update semantic analyzer for TypeVar defaults (PEP 696) (Marc Mueller, PR [14873](https://github.com/python/mypy/pull/14873))
*   Make dict expression inference more consistent (Ivan Levkivskyi, PR [15174](https://github.com/python/mypy/pull/15174))
*   Do not block on duplicate base classes (Nikita Sobolev, PR [15367](https://github.com/python/mypy/pull/15367))
*   Generate an error when both staticmethod and classmethod decorators are used (Juhi Chandalia, PR [15118](https://github.com/python/mypy/pull/15118))
*   Fix assert\_type behaviour with literals (Carl Karsten, PR [15123](https://github.com/python/mypy/pull/15123))
*   Fix match subject ignoring redefinitions (Vincent Vanlaer, PR [15306](https://github.com/python/mypy/pull/15306))
*   Support `__all__`.remove (Shantanu, PR [15279](https://github.com/python/mypy/pull/15279))

#### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=877e06ad1cfd9fd9967c0b0340a86d0c23ea89ce+0&branch=main&path=stdlib) for full list of typeshed changes.

#### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Adrian Garcia Badaracco
*   AJ Rasmussen
*   Alan Du
*   Alex Waygood
*   Ali Hamdan
*   Carl Karsten
*   dosisod
*   Ethan Smith
*   Gregory Santosa
*   Heather White
*   Henrik Bäärnhielm
*   Ilya Konstantinov
*   Ilya Priven
*   Ivan Levkivskyi
*   Juhi Chandalia
*   Jukka Lehtosalo
*   Logan Hunt
*   madt2709
*   Marc Mueller
*   Max Murin
*   Nikita Sobolev
*   Omar Silva
*   Özgür
*   Richard Si
*   Rohit Sanjay
*   Shantanu
*   teresa0605
*   Thomas M Kehrenberg
*   Tin Tvrtković
*   Tushar Sadhwani
*   Valentin Stanciu
*   Viicos
*   Vincent Vanlaer
*   Wesley Collin Wright
*   William Santosa
*   yaegassy

I’d also like to thank my employer, Dropbox, for supporting mypy development.

Posted by Jared Hance


## Mypy 1.3

[Wednesday, 10 May 2023](https://mypy-lang.blogspot.com/2023/05/mypy-13-released.html)

 We’ve just uploaded mypy 1.3 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

#### Performance Improvements

*   Improve performance of union subtyping (Shantanu, PR [15104](https://github.com/python/mypy/pull/15104))
*   Add negative subtype caches (Ivan Levkivskyi, PR [14884](https://github.com/python/mypy/pull/14884))

#### Stub Tooling Improvements

*   Stubtest: Check that the stub is abstract if the runtime is, even when the stub is an overloaded method (Alex Waygood, PR [14955](https://github.com/python/mypy/pull/14955))
*   Stubtest: Verify stub methods or properties are decorated with @final if they are decorated with @final at runtime (Alex Waygood, PR [14951](https://github.com/python/mypy/pull/14951))
*   Stubtest: Fix stubtest false positives with TypedDicts at runtime (Alex Waygood, PR [14984](https://github.com/python/mypy/pull/14984))
*   Stubgen: Support @functools.cached\_property (Nikita Sobolev, PR [14981](https://github.com/python/mypy/pull/14981))
*   Improvements to stubgenc (Chad Dombrova, PR [14564](https://github.com/python/mypy/pull/14564))

#### Improvements to attrs

*   Add support for converters with TypeVars on generic attrs classes (Chad Dombrova, PR [14908](https://github.com/python/mypy/pull/14908))
*   Fix attrs.evolve on bound TypeVar (Ilya Konstantinov, PR [15022](https://github.com/python/mypy/pull/15022))

#### Documentation Updates

*   Improve async documentation (Shantanu, PR [14973](https://github.com/python/mypy/pull/14973))
*   Improvements to cheat sheet (Shantanu, PR [14972](https://github.com/python/mypy/pull/14972))
*   Add documentation for bytes formatting error code (Shantanu, PR [14971](https://github.com/python/mypy/pull/14971))
*   Convert insecure links to use HTTPS (Marti Raudsepp, PR [14974](https://github.com/python/mypy/pull/14974))
*   Also mention overloads in async iterator documentation (Shantanu, PR [14998](https://github.com/python/mypy/pull/14998))
*   stubtest: Improve allowlist documentation (Shantanu, PR [15008](https://github.com/python/mypy/pull/15008))
*   Clarify "Using types... but not at runtime" (Jon Shea, PR [15029](https://github.com/python/mypy/pull/15029))
*   Fix alignment of cheat sheet example (Ondřej Cvacho, PR [15039](https://github.com/python/mypy/pull/15039))
*   Fix error for callback protocol matching against callable type object (Shantanu, PR [15042](https://github.com/python/mypy/pull/15042))

#### Error Reporting Improvements

*   Improve bytes formatting error (Shantanu, PR [14959](https://github.com/python/mypy/pull/14959))

#### Mypyc Improvements

*   Fix unions of bools and ints (Tomer Chachamu, PR [15066](https://github.com/python/mypy/pull/15066))

#### Other Fixes and Improvements

*   Fix narrowing union types that include Self with isinstance (Christoph Tyralla, PR [14923](https://github.com/python/mypy/pull/14923))
*   Allow objects matching SupportsKeysAndGetItem to be unpacked (Bryan Forbes, PR [14990](https://github.com/python/mypy/pull/14990))
*   Check type guard validity for staticmethods (EXPLOSION, PR [14953](https://github.com/python/mypy/pull/14953))
*   Fix sys.platform when cross-compiling with emscripten (Ethan Smith, PR [14888](https://github.com/python/mypy/pull/14888))

#### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=b0ed50e9392a23e52445b630a808153e0e256976+0&branch=main&path=stdlib) for full list of typeshed changes.

#### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Alex Waygood
*   Amin Alaee
*   Bryan Forbes
*   Chad Dombrova
*   Charlie Denton
*   Christoph Tyralla
*   dosisod
*   Ethan Smith
*   EXPLOSION
*   Ilya Konstantinov
*   Ivan Levkivskyi
*   Jon Shea
*   Jukka Lehtosalo
*   KotlinIsland
*   Marti Raudsepp
*   Nikita Sobolev
*   Ondřej Cvacho
*   Shantanu
*   sobolevn
*   Tomer Chachamu
*   Yaroslav Halchenko

Posted by Wesley Collin Wright.


## Mypy 1.2

[Thursday, 6 April 2023](https://mypy-lang.blogspot.com/2023/04/mypy-12-released.html)

We’ve just uploaded mypy 1.2 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

#### Improvements to Dataclass Transforms

*   Support implicit default for "init" parameter in field specifiers (Wesley Collin Wright and Jukka Lehtosalo, PR [15010](https://github.com/python/mypy/pull/15010))
*   Support descriptors in dataclass transform (Jukka Lehtosalo, PR [15006](https://github.com/python/mypy/pull/15006))
*   Fix frozen\_default in incremental mode (Wesley Collin Wright)
*   Fix frozen behavior for base classes with direct metaclasses (Wesley Collin Wright, PR [14878](https://github.com/python/mypy/pull/14878))

#### Mypyc: Native Floats

Mypyc now uses a native, unboxed representation for values of type float. Previously these were heap-allocated Python objects. Native floats are faster and use less memory. Code that uses floating-point operations heavily can be several times faster when using native floats.

Various float operations and math functions also now have optimized implementations. Refer to the [documentation](https://mypyc.readthedocs.io/en/latest/float_operations.html) for a full list.

This can change the behavior of existing code that uses subclasses of float. When assigning an instance of a subclass of float to a variable with the float type, it gets implicitly converted to a float instance when compiled:

```python
from lib import MyFloat  # MyFloat ia a subclass of "float"

def example() -> None:
    x = MyFloat(1.5)
    y: float = x  # Implicit conversion from MyFloat to float
    print(type(y))  # float, not MyFloat
```

Previously, implicit conversions were applied to int subclasses but not float subclasses.

Also, int values can no longer be assigned to a variable with type float in compiled code, since these types now have incompatible representations. An explicit conversion is required:

```python
def example(n: int) -> None:
    a: float = 1  # Error: cannot assign "int" to "float"
    b: float = 1.0  # OK
    c: float = n  # Error
    d: float = float(n)  # OK
```

This restriction only applies to assignments, since they could otherwise narrow down the type of a variable from float to int. int values can still be implicitly converted to float when passed as arguments to functions that expect float values.

Note that mypyc still doesn’t support arrays of unboxed float values. Using list\[float\] involves heap-allocated float objects, since list can only store boxed values. Support for efficient floating point arrays is one of the next major planned mypyc features.

Related changes:

*   Use a native unboxed representation for floats (Jukka Lehtosalo, PR [14880](https://github.com/python/mypy/pull/14880))
*   Document native floats and integers (Jukka Lehtosalo, PR [14927](https://github.com/python/mypy/pull/14927))
*   Fixes to float to int conversion (Jukka Lehtosalo, PR [14936](https://github.com/python/mypy/pull/14936))

#### Mypyc: Native Integers

Mypyc now supports signed 32-bit and 64-bit integer types in addition to the arbitrary-precision int type. You can use the types mypy\_extensions.i32 and mypy\_extensions.i64 to speed up code that uses integer operations heavily.

Simple example:
```python
from mypy_extensions import i64

def inc(x: i64) -> i64:
    return x + 1
```

Refer to the [documentation](https://mypyc.readthedocs.io/en/latest/using_type_annotations.html#native-integer-types) for more information. This feature was contributed by Jukka Lehtosalo.

#### Other Mypyc Fixes and Improvements

*   Support iterating over a TypedDict (Richard Si, PR [14747](https://github.com/python/mypy/pull/14747))
*   Faster coercions between different tuple types (Jukka Lehtosalo, PR [14899](https://github.com/python/mypy/pull/14899))
*   Faster calls via type aliases (Jukka Lehtosalo, PR [14784](https://github.com/python/mypy/pull/14784))
*   Faster classmethod calls via cls (Jukka Lehtosalo, PR [14789](https://github.com/python/mypy/pull/14789))

#### Fixes to Crashes

*   Fix crash on class-level import in protocol definition (Ivan Levkivskyi, PR [14926](https://github.com/python/mypy/pull/14926))
*   Fix crash on single item union of alias (Ivan Levkivskyi, PR [14876](https://github.com/python/mypy/pull/14876))
*   Fix crash on ParamSpec in incremental mode (Ivan Levkivskyi, PR [14885](https://github.com/python/mypy/pull/14885))

#### Documentation Updates

*   Update adopting \--strict documentation for 1.0 (Shantanu, PR [14865](https://github.com/python/mypy/pull/14865))
*   Some minor documentation tweaks (Jukka Lehtosalo, PR [14847](https://github.com/python/mypy/pull/14847))
*   Improve documentation of top level mypy: disable-error-code comment (Nikita Sobolev, PR [14810](https://github.com/python/mypy/pull/14810))

#### Error Reporting Improvements

*   Add error code to `typing_extensions` suggestion (Shantanu, PR [14881](https://github.com/python/mypy/pull/14881))
*   Add a separate error code for top-level await (Nikita Sobolev, PR [14801](https://github.com/python/mypy/pull/14801))
*   Don’t suggest two obsolete stub packages (Jelle Zijlstra, PR [14842](https://github.com/python/mypy/pull/14842))
*   Add suggestions for pandas-stubs and lxml-stubs (Shantanu, PR [14737](https://github.com/python/mypy/pull/14737))

#### Other Fixes and Improvements

*   Multiple inheritance considers callable objects as subtypes of functions (Christoph Tyralla, PR [14855](https://github.com/python/mypy/pull/14855))
*   stubtest: Respect @final runtime decorator and enforce it in stubs (Nikita Sobolev, PR [14922](https://github.com/python/mypy/pull/14922))
*   Fix false positives related to type\[<type-var>\] (sterliakov, PR [14756](https://github.com/python/mypy/pull/14756))
*   Fix duplication of ParamSpec prefixes and properly substitute ParamSpecs (EXPLOSION, PR [14677](https://github.com/python/mypy/pull/14677))
*   Fix line number if `__iter__` is incorrectly reported as missing (Jukka Lehtosalo, PR [14893](https://github.com/python/mypy/pull/14893))
*   Fix incompatible overrides of overloaded generics with self types (Shantanu, PR [14882](https://github.com/python/mypy/pull/14882))
*   Allow SupportsIndex in slice expressions (Shantanu, PR [14738](https://github.com/python/mypy/pull/14738))
*   Support if statements in bodies of dataclasses and classes that use dataclass\_transform (Jacek Chałupka, PR [14854](https://github.com/python/mypy/pull/14854))
*   Allow iterable class objects to be unpacked (including enums) (Alex Waygood, PR [14827](https://github.com/python/mypy/pull/14827))
*   Fix narrowing for walrus expressions used in match statements (Shantanu, PR [14844](https://github.com/python/mypy/pull/14844))
*   Add signature for attr.evolve (Ilya Konstantinov, PR [14526](https://github.com/python/mypy/pull/14526))
*   Fix Any inference when unpacking iterators that don't directly inherit from typing.Iterator (Alex Waygood, PR [14821](https://github.com/python/mypy/pull/14821))
*   Fix unpack with overloaded `__iter__` method (Nikita Sobolev, PR [14817](https://github.com/python/mypy/pull/14817))
*   Reduce size of JSON data in mypy cache (dosisod, PR [14808](https://github.com/python/mypy/pull/14808))
*   Improve “used before definition” checks when a local definition has the same name as a global definition (Stas Ilinskiy, PR [14517](https://github.com/python/mypy/pull/14517))
*   Honor NoReturn as \_\_setitem\_\_ return type to mark unreachable code (sterliakov, PR [12572](https://github.com/python/mypy/pull/12572))

#### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=a544b75320e97424d2d927605316383c755cdac0+0&branch=main&path=stdlib) for full list of typeshed changes.

#### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Alex Waygood
*   Avasam
*   Christoph Tyralla
*   dosisod
*   EXPLOSION
*   Ilya Konstantinov
*   Ivan Levkivskyi
*   Jacek Chałupka
*   Jelle Zijlstra
*   Jukka Lehtosalo
*   Marc Mueller
*   Max Murin
*   Nikita Sobolev
*   Richard Si
*   Shantanu
*   Stas Ilinskiy
*   sterliakov
*   Wesley Collin Wright

Posted by Jukka Lehtosalo


## Mypy 1.1.1

[Monday, 6 March 2023](https://mypy-lang.blogspot.com/2023/03/mypy-111-released.html)

 We’ve just uploaded mypy 1.1.1 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

#### Support for `dataclass_transform``

This release adds full support for the dataclass\_transform decorator defined in [PEP 681](https://peps.python.org/pep-0681/#decorator-function-example). This allows decorators, base classes, and metaclasses that generate a \_\_init\_\_ method or other methods based on the properties of that class (similar to dataclasses) to have those methods recognized by mypy.

This was contributed by Wesley Collin Wright.

#### Dedicated Error Code for Method Assignments

Mypy can’t safely check all assignments to methods (a form of monkey patching), so mypy generates an error by default. To make it easier to ignore this error, mypy now uses the new error code method-assign for this. By disabling this error code in a file or globally, mypy will no longer complain about assignments to methods if the signatures are compatible.

Mypy also supports the old error code assignment for these assignments to prevent a backward compatibility break. More generally, we can use this mechanism in the future if we wish to split or rename another existing error code without causing backward compatibility issues.

This was contributed by Ivan Levkivskyi (PR [14570](https://github.com/python/mypy/pull/14570)).

#### Fixes to Crashes

*   Fix a crash on walrus in comprehension at class scope (Ivan Levkivskyi, PR [14556](https://github.com/python/mypy/pull/14556))
*   Fix crash related to value-constrained TypeVar (Shantanu, PR [14642](https://github.com/python/mypy/pull/14642))

#### Fixes to Cache Corruption

*   Fix generic TypedDict/NamedTuple caching (Ivan Levkivskyi, PR [14675](https://github.com/python/mypy/pull/14675))

#### Mypyc Fixes and Improvements

*   Raise "non-trait base must be first..." error less frequently (Richard Si, PR [14468](https://github.com/python/mypy/pull/14468))
*   Generate faster code for bool comparisons and arithmetic (Jukka Lehtosalo, PR [14489](https://github.com/python/mypy/pull/14489))
*   Optimize \_\_(a)enter\_\_/\_\_(a)exit\_\_ for native classes (Jared Hance, PR [14530](https://github.com/python/mypy/pull/14530))
*   Detect if attribute definition conflicts with base class/trait (Jukka Lehtosalo, PR [14535](https://github.com/python/mypy/pull/14535))
*   Support \_\_(r)divmod\_\_ dunders (Richard Si, PR [14613](https://github.com/python/mypy/pull/14613))
*   Support \_\_pow\_\_, \_\_rpow\_\_, and \_\_ipow\_\_ dunders (Richard Si, PR [14616](https://github.com/python/mypy/pull/14616))
*   Fix crash on star unpacking to underscore (Ivan Levkivskyi, PR [14624](https://github.com/python/mypy/pull/14624))
*   Fix iterating over a union of dicts (Richard Si, PR [14713](https://github.com/python/mypy/pull/14713))

#### Fixes to Detecting Undefined Names (used-before-def)

*   Correctly handle walrus operator (Stas Ilinskiy, PR [14646](https://github.com/python/mypy/pull/14646))
*   Handle walrus declaration in match subject correctly (Stas Ilinskiy, PR [14665](https://github.com/python/mypy/pull/14665))

#### Stubgen Improvements

Stubgen is a tool for automatically generating draft stubs for libraries.

*   Allow aliases below the top level (Chad Dombrova, PR [14388](https://github.com/python/mypy/pull/14388))
*   Fix crash with PEP 604 union in type variable bound (Shantanu, PR [14557](https://github.com/python/mypy/pull/14557))
*   Preserve PEP 604 unions in generated .pyi files (hamdanal, PR [14601](https://github.com/python/mypy/pull/14601))

#### Stubtest Improvements

Stubtest is a tool for testing that stubs conform to the implementations.

*   Update message format so that it’s easier to go to error location (Avasam, PR [14437](https://github.com/python/mypy/pull/14437))
*   Handle name-mangling edge cases better (Alex Waygood, PR [14596](https://github.com/python/mypy/pull/14596))

#### Changes to Error Reporting and Messages

*   Add new TypedDict error code typeddict-unknown-key (JoaquimEsteves, PR [14225](https://github.com/python/mypy/pull/14225))
*   Give arguments a more reasonable location in error messages (Max Murin, PR [14562](https://github.com/python/mypy/pull/14562))
*   In error messages, quote just the module's name (Ilya Konstantinov, PR [14567](https://github.com/python/mypy/pull/14567))
*   Improve misleading message about Enum() (Rodrigo Silva, PR [14590](https://github.com/python/mypy/pull/14590))
*   Suggest importing from `typing_extensions` if definition is not in typing (Shantanu, PR [14591](https://github.com/python/mypy/pull/14591))
*   Consistently use type-abstract error code (Ivan Levkivskyi, PR [14619](https://github.com/python/mypy/pull/14619))
*   Consistently use literal-required error code for TypedDicts (Ivan Levkivskyi, PR [14621](https://github.com/python/mypy/pull/14621))
*   Adjust inconsistent dataclasses plugin error messages (Wesley Collin Wright, PR [14637](https://github.com/python/mypy/pull/14637))
*   Consolidate literal bool argument error messages (Wesley Collin Wright, PR [14693](https://github.com/python/mypy/pull/14693))

#### Other Fixes and Improvements

*   Check that type guards accept a positional argument (EXPLOSION, PR [14238](https://github.com/python/mypy/pull/14238))
*   Fix bug with in operator used with a union of Container and Iterable (Max Murin, PR [14384](https://github.com/python/mypy/pull/14384))
*   Support protocol inference for type\[T\] via metaclass (Ivan Levkivskyi, PR [14554](https://github.com/python/mypy/pull/14554))
*   Allow overlapping comparisons between bytes-like types (Shantanu, PR [14658](https://github.com/python/mypy/pull/14658))
*   Fix mypy daemon documentation link in README (Ivan Levkivskyi, PR [14644](https://github.com/python/mypy/pull/14644))

#### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=5ebf892d0710a6e87925b8d138dfa597e7bb11cc+0&branch=main&path=stdlib) for full list of typeshed changes.

#### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Alex Waygood
*   Avasam
*   Chad Dombrova
*   dosisod
*   EXPLOSION
*   hamdanal
*   Ilya Konstantinov
*   Ivan Levkivskyi
*   Jared Hance
*   JoaquimEsteves
*   Jukka Lehtosalo
*   Marc Mueller
*   Max Murin
*   Michael Lee
*   Michael R. Crusoe
*   Richard Si
*   Rodrigo Silva
*   Shantanu
*   Stas Ilinskiy
*   Wesley Collin Wright
*   Yilei "Dolee" Yang
*   Yurii Karabas

We’d also like to thank our employer, Dropbox, for funding the mypy core team.

Posted by Max Murin


## Mypy 1.0

[Monday, 6 February 2023](https://mypy-lang.blogspot.com/2023/02/mypy-10-released.html)

We’ve just uploaded mypy 1.0 to the Python Package Index ([PyPI](https://pypi.org/project/mypy/)). Mypy is a static type checker for Python. This release includes new features, performance improvements and bug fixes. You can install it as follows:

    python3 -m pip install -U mypy

You can read the full documentation for this release on [Read the Docs](http://mypy.readthedocs.io).

#### New Release Versioning Scheme

Now that mypy reached 1.0, we’ll switch to a new versioning scheme. Mypy version numbers will be of form x.y.z.

Rules:

*   The major release number (x) is incremented if a feature release includes a significant backward incompatible change that affects a significant fraction of users.
*   The minor release number (y) is incremented on each feature release. Minor releases include updated stdlib stubs from typeshed.
*   The point release number (z) is incremented when there are fixes only.

Mypy doesn't use SemVer, since most minor releases have at least minor backward incompatible changes in typeshed, at the very least. Also, many type checking features find new legitimate issues in code. These are not considered backward incompatible changes, unless the number of new errors is very high.

Any significant backward incompatible change must be announced in the blog post for the previous feature release, before making the change. The previous release must also provide a flag to explicitly enable or disable the new behavior (whenever practical), so that users will be able to prepare for the changes and report issues. We should keep the feature flag for at least a few releases after we've switched the default.

See [”Release Process” in the mypy wiki](https://github.com/python/mypy/wiki/Release-Process) for more details and for the most up-to-date version of the versioning scheme.

#### Performance Improvements

Mypy 1.0 is up to 40% faster than mypy 0.991 when type checking the Dropbox internal codebase. We also set up a daily job to measure the performance of the most recent development version of mypy to make it easier to track changes in performance.

Many optimizations contributed to this improvement:

*   Improve performance for errors on class with many attributes (Shantanu, PR [14379](https://github.com/python/mypy/pull/14379))
*   Speed up make\_simplified\_union (Jukka Lehtosalo, PR [14370](https://github.com/python/mypy/pull/14370))
*   Micro-optimize get\_proper\_type(s) (Jukka Lehtosalo, PR [14369](https://github.com/python/mypy/pull/14369))
*   Micro-optimize flatten\_nested\_unions (Jukka Lehtosalo, PR [14368](https://github.com/python/mypy/pull/14368))
*   Some semantic analyzer micro-optimizations (Jukka Lehtosalo, PR [14367](https://github.com/python/mypy/pull/14367))
*   A few miscellaneous micro-optimizations (Jukka Lehtosalo, PR [14366](https://github.com/python/mypy/pull/14366))
*   Optimization: Avoid a few uses of contextmanagers in semantic analyzer (Jukka Lehtosalo, PR [14360](https://github.com/python/mypy/pull/14360))
*   Optimization: Enable always defined attributes in Type subclasses (Jukka Lehtosalo, PR [14356](https://github.com/python/mypy/pull/14356))
*   Optimization: Remove expensive context manager in type analyzer (Jukka Lehtosalo, PR [14357](https://github.com/python/mypy/pull/14357))
*   subtypes: fast path for Union/Union subtype check (Hugues, PR [14277](https://github.com/python/mypy/pull/14277))
*   Micro-optimization: avoid Bogus\[int\] types that cause needless boxing (Jukka Lehtosalo, PR [14354](https://github.com/python/mypy/pull/14354))
*   Avoid slow error message logic if errors not shown to user (Jukka Lehtosalo, PR [14336](https://github.com/python/mypy/pull/14336))
*   Speed up the implementation of hasattr() checks (Jukka Lehtosalo, PR [14333](https://github.com/python/mypy/pull/14333))
*   Avoid the use of a context manager in hot code path (Jukka Lehtosalo, PR [14331](https://github.com/python/mypy/pull/14331))
*   Change various type queries into faster bool type queries (Jukka Lehtosalo, PR [14330](https://github.com/python/mypy/pull/14330))
*   Speed up recursive type check (Jukka Lehtosalo, PR [14326](https://github.com/python/mypy/pull/14326))
*   Optimize subtype checking by avoiding a nested function (Jukka Lehtosalo, PR [14325](https://github.com/python/mypy/pull/14325))
*   Optimize type parameter checks in subtype checking (Jukka Lehtosalo, PR [14324](https://github.com/python/mypy/pull/14324))
*   Speed up freshening type variables (Jukka Lehtosalo, PR [14323](https://github.com/python/mypy/pull/14323))
*   Optimize implementation of TypedDict types for \*\*kwds (Jukka Lehtosalo, PR [14316](https://github.com/python/mypy/pull/14316))

#### Warn About Variables Used Before Definition

Mypy will now generate an error if you use a variable before it’s defined. This feature is enabled by default. By default mypy reports an error when it infers that a variable is always undefined.
```python
y = x  # E: Name "x" is used before definition [used-before-def]
x = 0
```
This feature was contributed by Stas Ilinskiy.

#### Detect Possibly Undefined Variables (Experimental)

A new experimental possibly-undefined error code is now available that will detect variables that may be undefined:
```python
    if b:
        x = 0
    print(x)  # Error: Name "x" may be undefined [possibly-undefined]
```
The error code is disabled be default, since it can generate false positives.

This feature was contributed by Stas Ilinskiy.

#### Support the “Self” Type

There is now a simpler syntax for declaring [generic self types](https://mypy.readthedocs.io/en/stable/generics.html#generic-methods-and-generic-self) introduced in [PEP 673](https://peps.python.org/pep-0673/): the Self type. You no longer have to define a type variable to use “self types”, and you can use them with attributes. Example from mypy documentation:
```python
from typing import Self

class Friend:
    other: Self | None = None

    @classmethod
    def make_pair(cls) -> tuple[Self, Self]:
        a, b = cls(), cls()
        a.other = b
        b.other = a
        return a, b

class SuperFriend(Friend):
    pass

# a and b have the inferred type "SuperFriend", not "Friend"
a, b = SuperFriend.make_pair()
```
The feature was introduced in Python 3.11. In earlier Python versions a backport of Self is available in `typing_extensions`.

This was contributed by Ivan Levkivskyi (PR [14041](https://github.com/python/mypy/pull/14041)).

#### Support ParamSpec in Type Aliases

ParamSpec and Concatenate can now be used in type aliases. Example:
```python
from typing import ParamSpec, Callable

P = ParamSpec("P")
A = Callable[P, None]

def f(c: A[int, str]) -> None:
    c(1, "x")
```
This feature was contributed by Ivan Levkivskyi (PR [14159](https://github.com/python/mypy/pull/14159)).

#### ParamSpec and Generic Self Types No Longer Experimental

Support for ParamSpec ([PEP 612](https://www.python.org/dev/peps/pep-0612/)) and generic self types are no longer considered experimental.

#### Miscellaneous New Features

*   Minimal, partial implementation of dataclass\_transform ([PEP 681](https://peps.python.org/pep-0681/)) (Wesley Collin Wright, PR [14523](https://github.com/python/mypy/pull/14523))
*   Add basic support for `typing_extensions`.TypeVar (Marc Mueller, PR [14313](https://github.com/python/mypy/pull/14313))
*   Add \--debug-serialize option (Marc Mueller, PR [14155](https://github.com/python/mypy/pull/14155))
*   Constant fold initializers of final variables (Jukka Lehtosalo, PR [14283](https://github.com/python/mypy/pull/14283))
*   Enable Final instance attributes for attrs (Tin Tvrtković, PR [14232](https://github.com/python/mypy/pull/14232))
*   Allow function arguments as base classes (Ivan Levkivskyi, PR [14135](https://github.com/python/mypy/pull/14135))
*   Allow super() with mixin protocols (Ivan Levkivskyi, PR [14082](https://github.com/python/mypy/pull/14082))
*   Add type inference for dict.keys membership (Matthew Hughes, PR [13372](https://github.com/python/mypy/pull/13372))
*   Generate error for class attribute access if attribute is defined with `__slots__` (Harrison McCarty, PR [14125](https://github.com/python/mypy/pull/14125))
*   Support additional attributes in callback protocols (Ivan Levkivskyi, PR [14084](https://github.com/python/mypy/pull/14084))

#### Fixes to Crashes

*   Fix crash on prefixed ParamSpec with forward reference (Ivan Levkivskyi, PR [14569](https://github.com/python/mypy/pull/14569))
*   Fix internal crash when resolving the same partial type twice (Shantanu, PR [14552](https://github.com/python/mypy/pull/14552))
*   Fix crash in daemon mode on new import cycle (Ivan Levkivskyi, PR [14508](https://github.com/python/mypy/pull/14508))
*   Fix crash in mypy daemon (Ivan Levkivskyi, PR [14497](https://github.com/python/mypy/pull/14497))
*   Fix crash on Any metaclass in incremental mode (Ivan Levkivskyi, PR [14495](https://github.com/python/mypy/pull/14495))
*   Fix crash in await inside comprehension outside function (Ivan Levkivskyi, PR [14486](https://github.com/python/mypy/pull/14486))
*   Fix crash in Self type on forward reference in upper bound (Ivan Levkivskyi, PR [14206](https://github.com/python/mypy/pull/14206))
*   Fix a crash when incorrect super() is used outside a method (Ivan Levkivskyi, PR [14208](https://github.com/python/mypy/pull/14208))
*   Fix crash on overriding with frozen attrs (Ivan Levkivskyi, PR [14186](https://github.com/python/mypy/pull/14186))
*   Fix incremental mode crash on generic function appearing in nested position (Ivan Levkivskyi, PR [14148](https://github.com/python/mypy/pull/14148))
*   Fix daemon crash on malformed NamedTuple (Ivan Levkivskyi, PR [14119](https://github.com/python/mypy/pull/14119))
*   Fix crash during ParamSpec inference (Ivan Levkivskyi, PR [14118](https://github.com/python/mypy/pull/14118))
*   Fix crash on nested generic callable (Ivan Levkivskyi, PR [14093](https://github.com/python/mypy/pull/14093))
*   Fix crashes with unpacking SyntaxError (Shantanu, PR [11499](https://github.com/python/mypy/pull/11499))
*   Fix crash on partial type inference within a lambda (Ivan Levkivskyi, PR [14087](https://github.com/python/mypy/pull/14087))
*   Fix crash with enums (Michael Lee, PR [14021](https://github.com/python/mypy/pull/14021))
*   Fix crash with malformed TypedDicts and disllow-any-expr (Michael Lee, PR [13963](https://github.com/python/mypy/pull/13963))

#### Error Reporting Improvements

*   More helpful error for missing self (Shantanu, PR [14386](https://github.com/python/mypy/pull/14386))
*   Add error-code truthy-iterable (Marc Mueller, PR [13762](https://github.com/python/mypy/pull/13762))
*   Fix pluralization in error messages (KotlinIsland, PR [14411](https://github.com/python/mypy/pull/14411))

#### Mypyc: Support Match Statement

Mypyc can now compile Python 3.10 match statements.

This was contributed by dosisod (PR [13953](https://github.com/python/mypy/pull/13953)).

#### Other Mypyc Fixes and Improvements

*   Optimize int(x)/float(x)/complex(x) on instances of native classes (Richard Si, PR [14450](https://github.com/python/mypy/pull/14450))
*   Always emit warnings (Richard Si, PR [14451](https://github.com/python/mypy/pull/14451))
*   Faster bool and integer conversions (Jukka Lehtosalo, PR [14422](https://github.com/python/mypy/pull/14422))
*   Support attributes that override properties (Jukka Lehtosalo, PR [14377](https://github.com/python/mypy/pull/14377))
*   Precompute set literals for "in" operations and iteration (Richard Si, PR [14409](https://github.com/python/mypy/pull/14409))
*   Don't load targets with forward references while setting up non-extension class `__all__` (Richard Si, PR [14401](https://github.com/python/mypy/pull/14401))
*   Compile away NewType type calls (Richard Si, PR [14398](https://github.com/python/mypy/pull/14398))
*   Improve error message for multiple inheritance (Joshua Bronson, PR [14344](https://github.com/python/mypy/pull/14344))
*   Simplify union types (Jukka Lehtosalo, PR [14363](https://github.com/python/mypy/pull/14363))
*   Fixes to union simplification (Jukka Lehtosalo, PR [14364](https://github.com/python/mypy/pull/14364))
*   Fix for typeshed changes to Collection (Shantanu, PR [13994](https://github.com/python/mypy/pull/13994))
*   Allow use of enum.Enum (Shantanu, PR [13995](https://github.com/python/mypy/pull/13995))
*   Fix compiling on Arch Linux (dosisod, PR [13978](https://github.com/python/mypy/pull/13978))

#### Documentation Improvements

*   Various documentation and error message tweaks (Jukka Lehtosalo, PR [14574](https://github.com/python/mypy/pull/14574))
*   Improve Generics documentation (Shantanu, PR [14587](https://github.com/python/mypy/pull/14587))
*   Improve protocols documentation (Shantanu, PR [14577](https://github.com/python/mypy/pull/14577))
*   Improve dynamic typing documentation (Shantanu, PR [14576](https://github.com/python/mypy/pull/14576))
*   Improve the Common Issues page (Shantanu, PR [14581](https://github.com/python/mypy/pull/14581))
*   Add a top-level TypedDict page (Shantanu, PR [14584](https://github.com/python/mypy/pull/14584))
*   More improvements to getting started documentation (Shantanu, PR [14572](https://github.com/python/mypy/pull/14572))
*   Move truthy-function documentation from “optional checks” to “enabled by default” (Anders Kaseorg, PR [14380](https://github.com/python/mypy/pull/14380))
*   Avoid use of implicit optional in decorator factory documentation (Tom Schraitle, PR [14156](https://github.com/python/mypy/pull/14156))
*   Clarify documentation surrounding install-types (Shantanu, PR [14003](https://github.com/python/mypy/pull/14003))
*   Improve searchability for module level type ignore errors (Shantanu, PR [14342](https://github.com/python/mypy/pull/14342))
*   Advertise mypy daemon in README (Ivan Levkivskyi, PR [14248](https://github.com/python/mypy/pull/14248))
*   Add link to error codes in README (Ivan Levkivskyi, PR [14249](https://github.com/python/mypy/pull/14249))
*   Document that report generation disables cache (Ilya Konstantinov, PR [14402](https://github.com/python/mypy/pull/14402))
*   Stop saying mypy is beta software (Ivan Levkivskyi, PR [14251](https://github.com/python/mypy/pull/14251))
*   Flycheck-mypy is deprecated, since its functionality was merged to Flycheck (Ivan Levkivskyi, PR [14247](https://github.com/python/mypy/pull/14247))
*   Update code example in "Declaring decorators" (ChristianWitzler, PR [14131](https://github.com/python/mypy/pull/14131))

#### Stubtest Improvements

Stubtest is a tool for testing that stubs conform to the implementations.

*   Improve error message for `__all__`\-related errors (Alex Waygood, PR [14362](https://github.com/python/mypy/pull/14362))
*   Improve heuristics for determining whether global-namespace names are imported (Alex Waygood, PR [14270](https://github.com/python/mypy/pull/14270))
*   Catch BaseException on module imports (Shantanu, PR [14284](https://github.com/python/mypy/pull/14284))
*   Associate exported symbol error with `__all__` object\_path (Nikita Sobolev, PR [14217](https://github.com/python/mypy/pull/14217))
*   Add \_\_warningregistry\_\_ to the list of ignored module dunders (Nikita Sobolev, PR [14218](https://github.com/python/mypy/pull/14218))
*   If a default is present in the stub, check that it is correct (Jelle Zijlstra, PR [14085](https://github.com/python/mypy/pull/14085))

#### Stubgen Improvements

Stubgen is a tool for automatically generating draft stubs for libraries.

*   Treat dlls as C modules (Shantanu, PR [14503](https://github.com/python/mypy/pull/14503))

#### Other Notable Fixes and Improvements

*   Update stub suggestions based on recent typeshed changes (Alex Waygood, PR [14265](https://github.com/python/mypy/pull/14265))
*   Fix attrs protocol check with cache (Marc Mueller, PR [14558](https://github.com/python/mypy/pull/14558))
*   Fix strict equality check if operand item type has custom \_\_eq\_\_ (Jukka Lehtosalo, PR [14513](https://github.com/python/mypy/pull/14513))
*   Don't consider object always truthy (Jukka Lehtosalo, PR [14510](https://github.com/python/mypy/pull/14510))
*   Properly support union of TypedDicts as dict literal context (Ivan Levkivskyi, PR [14505](https://github.com/python/mypy/pull/14505))
*   Properly expand type in generic class with Self and TypeVar with values (Ivan Levkivskyi, PR [14491](https://github.com/python/mypy/pull/14491))
*   Fix recursive TypedDicts/NamedTuples defined with call syntax (Ivan Levkivskyi, PR [14488](https://github.com/python/mypy/pull/14488))
*   Fix type inference issue when a class inherits from Any (Shantanu, PR [14404](https://github.com/python/mypy/pull/14404))
*   Fix false positive on generic base class with six (Ivan Levkivskyi, PR [14478](https://github.com/python/mypy/pull/14478))
*   Don't read scripts without extensions as modules in namespace mode (Tim Geypens, PR [14335](https://github.com/python/mypy/pull/14335))
*   Fix inference for constrained type variables within unions (Christoph Tyralla, PR [14396](https://github.com/python/mypy/pull/14396))
*   Fix Unpack imported from typing (Marc Mueller, PR [14378](https://github.com/python/mypy/pull/14378))
*   Allow trailing commas in ini configuration of multiline values (Nikita Sobolev, PR [14240](https://github.com/python/mypy/pull/14240))
*   Fix false negatives involving Unions and generators or coroutines (Shantanu, PR [14224](https://github.com/python/mypy/pull/14224))
*   Fix ParamSpec constraint for types as callable (Vincent Vanlaer, PR [14153](https://github.com/python/mypy/pull/14153))
*   Fix type aliases with fixed-length tuples (Jukka Lehtosalo, PR [14184](https://github.com/python/mypy/pull/14184))
*   Fix issues with type aliases and new style unions (Jukka Lehtosalo, PR [14181](https://github.com/python/mypy/pull/14181))
*   Simplify unions less aggressively (Ivan Levkivskyi, PR [14178](https://github.com/python/mypy/pull/14178))
*   Simplify callable overlap logic (Ivan Levkivskyi, PR [14174](https://github.com/python/mypy/pull/14174))
*   Try empty context when assigning to union typed variables (Ivan Levkivskyi, PR [14151](https://github.com/python/mypy/pull/14151))
*   Improvements to recursive types (Ivan Levkivskyi, PR [14147](https://github.com/python/mypy/pull/14147))
*   Make non-numeric non-empty FORCE\_COLOR truthy (Shantanu, PR [14140](https://github.com/python/mypy/pull/14140))
*   Fix to recursive type aliases (Ivan Levkivskyi, PR [14136](https://github.com/python/mypy/pull/14136))
*   Correctly handle Enum name on Python 3.11 (Ivan Levkivskyi, PR [14133](https://github.com/python/mypy/pull/14133))
*   Fix class objects falling back to metaclass for callback protocol (Ivan Levkivskyi, PR [14121](https://github.com/python/mypy/pull/14121))
*   Correctly support self types in callable ClassVar (Ivan Levkivskyi, PR [14115](https://github.com/python/mypy/pull/14115))
*   Fix type variable clash in nested positions and in attributes (Ivan Levkivskyi, PR [14095](https://github.com/python/mypy/pull/14095))
*   Allow class variable as implementation for read only attribute (Ivan Levkivskyi, PR [14081](https://github.com/python/mypy/pull/14081))
*   Prevent warnings from causing dmypy to fail (Andrzej Bartosiński, PR [14102](https://github.com/python/mypy/pull/14102))
*   Correctly process nested definitions in mypy daemon (Ivan Levkivskyi, PR [14104](https://github.com/python/mypy/pull/14104))
*   Don't consider a branch unreachable if there is a possible promotion (Ivan Levkivskyi, PR [14077](https://github.com/python/mypy/pull/14077))
*   Fix incompatible overrides of overloaded methods in concrete subclasses (Shantanu, PR [14017](https://github.com/python/mypy/pull/14017))
*   Fix new style union syntax in type aliases (Jukka Lehtosalo, PR [14008](https://github.com/python/mypy/pull/14008))
*   Fix and optimise overload compatibility checking (Shantanu, PR [14018](https://github.com/python/mypy/pull/14018))
*   Improve handling of redefinitions through imports (Shantanu, PR [13969](https://github.com/python/mypy/pull/13969))
*   Preserve (some) implicitly exported types (Shantanu, PR [13967](https://github.com/python/mypy/pull/13967))

#### Typeshed Updates

Typeshed is now modular and distributed as separate PyPI packages for everything except the standard library stubs. Please see [git log](https://github.com/python/typeshed/commits/main?after=ea0ae2155e8a04c9837903c3aff8dd5ad5f36ebc+0&branch=main&path=stdlib) for full list of typeshed changes.

#### Acknowledgements

Thanks to all mypy contributors who contributed to this release:

*   Alessio Izzo
*   Alex Waygood
*   Anders Kaseorg
*   Andrzej Bartosiński
*   Avasam
*   ChristianWitzler
*   Christoph Tyralla
*   dosisod
*   Harrison McCarty
*   Hugo van Kemenade
*   Hugues
*   Ilya Konstantinov
*   Ivan Levkivskyi
*   Jelle Zijlstra
*   jhance
*   johnthagen
*   Jonathan Daniel
*   Joshua Bronson
*   Jukka Lehtosalo
*   KotlinIsland
*   Lakshay Bisht
*   Lefteris Karapetsas
*   Marc Mueller
*   Matthew Hughes
*   Michael Lee
*   Nick Drozd
*   Nikita Sobolev
*   Richard Si
*   Shantanu
*   Stas Ilinskiy
*   Tim Geypens
*   Tin Tvrtković
*   Tom Schraitle
*   Valentin Stanciu
*   Vincent Vanlaer

We’d also like to thank our employer, Dropbox, for funding the mypy core team.

Posted by Stas Ilinskiy

## Previous releases

For information about previous releases, refer to the posts at https://mypy-lang.blogspot.com/

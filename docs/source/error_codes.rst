.. _error-codes:

Error codes
===========

Mypy can optionally display an error code such as ``[attr-defined]``
after each error message. Error codes serve two purposes:

1. It's possible to silence specific error codes on a line using ``#
   type: ignore[code]``. This way you won't accidentally ignore other,
   potentially more serious errors.

2. The error code can be used to find documentation about the error.
   The next two topics (:ref:`error-code-list` and
   :ref:`error-codes-optional`) document the various error codes
   mypy can report.

Most error codes are shared between multiple related error messages.
Error codes may change in future mypy releases.


.. _silence-error-codes:

Silencing errors based on error codes
-------------------------------------

You can use a special comment ``# type: ignore[code, ...]`` to only
ignore errors with a specific error code (or codes) on a particular
line.  This can be used even if you have not configured mypy to show
error codes.

This example shows how to ignore an error about an imported name mypy
thinks is undefined:

.. code-block:: python

   # 'foo' is defined in 'foolib', even though mypy can't see the
   # definition.
   from foolib import foo  # type: ignore[attr-defined]

Enabling/disabling specific error codes globally
------------------------------------------------

There are command-line flags and config file settings for enabling
certain optional error codes, such as :option:`--disallow-untyped-defs <mypy --disallow-untyped-defs>`,
which enables the ``no-untyped-def`` error code.

You can use :option:`--enable-error-code <mypy --enable-error-code>`
and :option:`--disable-error-code <mypy --disable-error-code>`
to enable or disable specific error codes that don't have a dedicated
command-line flag or config file setting.

Per-module enabling/disabling error codes
-----------------------------------------

You can use :ref:`configuration file <config-file>` sections to enable or
disable specific error codes only in some modules. For example, this ``mypy.ini``
config will enable non-annotated empty containers in tests, while keeping
other parts of code checked in strict mode:

.. code-block:: ini

   [mypy]
   strict = True

   [mypy-tests.*]
   allow_untyped_defs = True
   allow_untyped_calls = True
   disable_error_code = var-annotated, has-type

Note that per-module enabling/disabling acts as override over the global
options. So that you don't need to repeat the error code lists for each
module if you have them in global config section. For example:

.. code-block:: ini

   [mypy]
   enable_error_code = truthy-bool, ignore-without-code, unused-awaitable

   [mypy-extensions.*]
   disable_error_code = unused-awaitable

The above config will allow unused awaitables in extension modules, but will
still keep the other two error codes enabled. The overall logic is following:

* Command line and/or config main section set global error codes

* Individual config sections *adjust* them per glob/module

* Inline ``# mypy: disable-error-code="..."`` and ``# mypy: enable-error-code="..."``
  comments can further *adjust* them for a specific file.
  For example:

.. code-block:: python

  # mypy: enable-error-code="truthy-bool, ignore-without-code"

So one can e.g. enable some code globally, disable it for all tests in
the corresponding config section, and then re-enable it with an inline
comment in some specific test.

Subcodes of error codes
-----------------------

In some cases, mostly for backwards compatibility reasons, an error
code may be covered also by another, wider error code. For example, an error with
code ``[method-assign]`` can be ignored by ``# type: ignore[assignment]``.
Similar logic works for disabling error codes globally. If a given error code
is a subcode of another one, it will be mentioned in the documentation for the narrower
code. This hierarchy is not nested: there cannot be subcodes of other
subcodes.


Requiring error codes
---------------------

It's possible to require error codes be specified in ``type: ignore`` comments.
See :ref:`ignore-without-code<code-ignore-without-code>` for more information.

.. _error-code-list:

Error codes enabled by default
------------------------------

This section documents various errors codes that mypy can generate
with default options. See :ref:`error-codes` for general documentation
about error codes. :ref:`error-codes-optional` documents additional
error codes that you can enable.

.. _code-attr-defined:

Check that attribute exists [attr-defined]
------------------------------------------

Mypy checks that an attribute is defined in the target class or module
when using the dot operator. This applies to both getting and setting
an attribute. New attributes are defined by assignments in the class
body, or assignments to ``self.x`` in methods. These assignments don't
generate ``attr-defined`` errors.

Example:

.. code-block:: python

   class Resource:
       def __init__(self, name: str) -> None:
           self.name = name

   r = Resource('x')
   print(r.name)  # OK
   print(r.id)  # Error: "Resource" has no attribute "id"  [attr-defined]
   r.id = 5  # Error: "Resource" has no attribute "id"  [attr-defined]

This error code is also generated if an imported name is not defined
in the module in a ``from ... import`` statement (as long as the
target module can be found):

.. code-block:: python

    # Error: Module "os" has no attribute "non_existent"  [attr-defined]
    from os import non_existent

A reference to a missing attribute is given the ``Any`` type. In the
above example, the type of ``non_existent`` will be ``Any``, which can
be important if you silence the error.

.. _code-union-attr:

Check that attribute exists in each union item [union-attr]
-----------------------------------------------------------

If you access the attribute of a value with a union type, mypy checks
that the attribute is defined for *every* type in that
union. Otherwise the operation can fail at runtime. This also applies
to optional types.

Example:

.. code-block:: python

   class Cat:
       def sleep(self) -> None: ...
       def miaow(self) -> None: ...

   class Dog:
       def sleep(self) -> None: ...
       def follow_me(self) -> None: ...

   def func(animal: Cat | Dog) -> None:
       # OK: 'sleep' is defined for both Cat and Dog
       animal.sleep()
       # Error: Item "Cat" of "Cat | Dog" has no attribute "follow_me"  [union-attr]
       animal.follow_me()

You can often work around these errors by using ``assert isinstance(obj, ClassName)``
or ``assert obj is not None`` to tell mypy that you know that the type is more specific
than what mypy thinks.

.. _code-name-defined:

Check that name is defined [name-defined]
-----------------------------------------

Mypy expects that all references to names have a corresponding
definition in an active scope, such as an assignment, function
definition or an import. This can catch missing definitions, missing
imports, and typos.

This example accidentally calls ``sort()`` instead of :py:func:`sorted`:

.. code-block:: python

    x = sort([3, 2, 4])  # Error: Name "sort" is not defined  [name-defined]

.. _code-used-before-def:

Check that a variable is not used before it's defined [used-before-def]
-----------------------------------------------------------------------

Mypy will generate an error if a name is used before it's defined.
While the name-defined check will catch issues with names that are undefined,
it will not flag if a variable is used and then defined later in the scope.
used-before-def check will catch such cases.

Example:

.. code-block:: python

    print(x)  # Error: Name "x" is used before definition [used-before-def]
    x = 123

.. _code-call-arg:

Check arguments in calls [call-arg]
-----------------------------------

Mypy expects that the number and names of arguments match the called function.
Note that argument type checks have a separate error code ``arg-type``.

Example:

.. code-block:: python

    def greet(name: str) -> None:
         print('hello', name)

    greet('jack')  # OK
    greet('jill', 'jack')  # Error: Too many arguments for "greet"  [call-arg]

.. _code-arg-type:

Check argument types [arg-type]
-------------------------------

Mypy checks that argument types in a call match the declared argument
types in the signature of the called function (if one exists).

Example:

.. code-block:: python

    def first(x: list[int]) -> int:
        return x[0] if x else 0

    t = (5, 4)
    # Error: Argument 1 to "first" has incompatible type "tuple[int, int]";
    #        expected "list[int]"  [arg-type]
    print(first(t))

.. _code-call-overload:

Check calls to overloaded functions [call-overload]
---------------------------------------------------

When you call an overloaded function, mypy checks that at least one of
the signatures of the overload items match the argument types in the
call.

Example:

.. code-block:: python

   from typing import overload

   @overload
   def inc_maybe(x: None) -> None: ...

   @overload
   def inc_maybe(x: int) -> int: ...

   def inc_maybe(x: int | None) -> int | None:
        if x is None:
            return None
        else:
            return x + 1

   inc_maybe(None)  # OK
   inc_maybe(5)  # OK

   # Error: No overload variant of "inc_maybe" matches argument type "float"  [call-overload]
   inc_maybe(1.2)

.. _code-valid-type:

Check validity of types [valid-type]
------------------------------------

Mypy checks that each type annotation and any expression that
represents a type is a valid type. Examples of valid types include
classes, union types, callable types, type aliases, and literal types.
Examples of invalid types include bare integer literals, functions,
variables, and modules.

This example incorrectly uses the function ``log`` as a type:

.. code-block:: python

    def log(x: object) -> None:
        print('log:', repr(x))

    # Error: Function "t.log" is not valid as a type  [valid-type]
    def log_all(objs: list[object], f: log) -> None:
        for x in objs:
            f(x)

You can use :py:class:`~collections.abc.Callable` as the type for callable objects:

.. code-block:: python

    from collections.abc import Callable

    # OK
    def log_all(objs: list[object], f: Callable[[object], None]) -> None:
        for x in objs:
            f(x)

.. _code-nonetype-type:

Check that NoneType is not used as a type (annotation) [nonetype-type]
----------------------------------------------------------------------

The preferred way to annotate the type of `None` is `None`.
`NoneType` is equivalent, but mypy won't allow it by default.

.. code-block:: python

    from types import NoneType
    def f(x: None) -> None:
        reveal_type(x) # note: Revealed type is "None"

    # error: NoneType should not be used as a type, please use None instead  [nonetype-type]
    def g(x: NoneType) -> None:
        reveal_type(x) # note: Revealed type is "None"

    # error: NoneType should not be used as a type, please use None instead  [nonetype-type]
    x1: NoneType = None
    x2: None = None # OK

.. _code-metaclass:

Check the validity of a class's metaclass [metaclass]
-----------------------------------------------------

Mypy checks whether the metaclass of a class is valid. The metaclass
must be a subclass of ``type``. Further, the class hierarchy must yield
a consistent metaclass. For more details, see the
`Python documentation <https://docs.python.org/3.13/reference/datamodel.html#determining-the-appropriate-metaclass>`_

Note that mypy's metaclass checking is limited and may produce false-positives.
See also :ref:`limitations`.

Example with an error:

.. code-block:: python

    class GoodMeta(type):
        pass

    class BadMeta:
        pass

    class A1(metaclass=GoodMeta):  # OK
        pass

    class A2(metaclass=BadMeta):  # Error:  Metaclasses not inheriting from "type" are not supported  [metaclass]
        pass

.. _code-var-annotated:

Require annotation if variable type is unclear [var-annotated]
--------------------------------------------------------------

In some cases mypy can't infer the type of a variable without an
explicit annotation. Mypy treats this as an error. This typically
happens when you initialize a variable with an empty collection or
``None``.  If mypy can't infer the collection item type, mypy replaces
any parts of the type it couldn't infer with ``Any`` and generates an
error.

Example with an error:

.. code-block:: python

    class Bundle:
        def __init__(self) -> None:
            # Error: Need type annotation for "items"
            #        (hint: "items: list[<type>] = ...")  [var-annotated]
            self.items = []

    reveal_type(Bundle().items)  # list[Any]

To address this, we add an explicit annotation:

.. code-block:: python

    class Bundle:
        def __init__(self) -> None:
            self.items: list[str] = []  # OK

   reveal_type(Bundle().items)  # list[str]

.. _code-override:

Check validity of overrides [override]
--------------------------------------

Mypy checks that an overridden method or attribute is compatible with
the base class.  A method in a subclass must accept all arguments
that the base class method accepts, and the return type must conform
to the return type in the base class (Liskov substitution principle).

Argument types can be more general is a subclass (i.e., they can vary
contravariantly).  The return type can be narrowed in a subclass
(i.e., it can vary covariantly).  It's okay to define additional
arguments in a subclass method, as long all extra arguments have default
values or can be left out (``*args``, for example).

Example:

.. code-block:: python

   class Base:
       def method(self,
                  arg: int) -> int | None:
           ...

   class Derived(Base):
       def method(self,
                  arg: int | str) -> int:  # OK
           ...

   class DerivedBad(Base):
       # Error: Argument 1 of "method" is incompatible with "Base"  [override]
       def method(self,
                  arg: bool) -> int:
           ...

.. _code-return:

Check that function returns a value [return]
--------------------------------------------

If a function has a non-``None`` return type, mypy expects that the
function always explicitly returns a value (or raises an exception).
The function should not fall off the end of the function, since this
is often a bug.

Example:

.. code-block:: python

    # Error: Missing return statement  [return]
    def show(x: int) -> int:
        print(x)

    # Error: Missing return statement  [return]
    def pred1(x: int) -> int:
        if x > 0:
            return x - 1

    # OK
    def pred2(x: int) -> int:
        if x > 0:
            return x - 1
        else:
            raise ValueError('not defined for zero')

.. _code-empty-body:

Check that functions don't have empty bodies outside stubs [empty-body]
-----------------------------------------------------------------------

This error code is similar to the ``[return]`` code but is emitted specifically
for functions and methods with empty bodies (if they are annotated with
non-trivial return type). Such a distinction exists because in some contexts
an empty body can be valid, for example for an abstract method or in a stub
file. Also old versions of mypy used to unconditionally allow functions with
empty bodies, so having a dedicated error code simplifies cross-version
compatibility.

Note that empty bodies are allowed for methods in *protocols*, and such methods
are considered implicitly abstract:

.. code-block:: python

   from abc import abstractmethod
   from typing import Protocol

   class RegularABC:
       @abstractmethod
       def foo(self) -> int:
           pass  # OK
       def bar(self) -> int:
           pass  # Error: Missing return statement  [empty-body]

   class Proto(Protocol):
       def bar(self) -> int:
           pass  # OK

.. _code-return-value:

Check that return value is compatible [return-value]
----------------------------------------------------

Mypy checks that the returned value is compatible with the type
signature of the function.

Example:

.. code-block:: python

   def func(x: int) -> str:
       # Error: Incompatible return value type (got "int", expected "str")  [return-value]
       return x + 1

.. _code-assignment:

Check types in assignment statement [assignment]
------------------------------------------------

Mypy checks that the assigned expression is compatible with the
assignment target (or targets).

Example:

.. code-block:: python

    class Resource:
        def __init__(self, name: str) -> None:
            self.name = name

    r = Resource('A')

    r.name = 'B'  # OK

    # Error: Incompatible types in assignment (expression has type "int",
    #        variable has type "str")  [assignment]
    r.name = 5

.. _code-method-assign:

Check that assignment target is not a method [method-assign]
------------------------------------------------------------

In general, assigning to a method on class object or instance (a.k.a.
monkey-patching) is ambiguous in terms of types, since Python's static type
system cannot express the difference between bound and unbound callable types.
Consider this example:

.. code-block:: python

   class A:
       def f(self) -> None: pass
       def g(self) -> None: pass

   def h(self: A) -> None: pass

   A.f = h  # Type of h is Callable[[A], None]
   A().f()  # This works
   A.f = A().g  # Type of A().g is Callable[[], None]
   A().f()  # ...but this also works at runtime

To prevent the ambiguity, mypy will flag both assignments by default. If this
error code is disabled, mypy will treat the assigned value in all method assignments as unbound,
so only the second assignment will still generate an error.

.. note::

    This error code is a subcode of the more general ``[assignment]`` code.

.. _code-type-var:

Check type variable values [type-var]
-------------------------------------

Mypy checks that value of a type variable is compatible with a value
restriction or the upper bound type.

Example (Python 3.12 syntax):

.. code-block:: python

    def add[T1: (int, float)](x: T1, y: T1) -> T1:
        return x + y

    add(4, 5.5)  # OK

    # Error: Value of type variable "T1" of "add" cannot be "str"  [type-var]
    add('x', 'y')

.. _code-operator:

Check uses of various operators [operator]
------------------------------------------

Mypy checks that operands support a binary or unary operation, such as
``+`` or ``~``. Indexing operations are so common that they have their
own error code ``index`` (see below).

Example:

.. code-block:: python

   # Error: Unsupported operand types for + ("int" and "str")  [operator]
   1 + 'x'

.. _code-index:

Check indexing operations [index]
---------------------------------

Mypy checks that the indexed value in indexing operation such as
``x[y]`` supports indexing, and that the index expression has a valid
type.

Example:

.. code-block:: python

   a = {'x': 1, 'y': 2}

   a['x']  # OK

   # Error: Invalid index type "int" for "dict[str, int]"; expected type "str"  [index]
   print(a[1])

   # Error: Invalid index type "bytes" for "dict[str, int]"; expected type "str"  [index]
   a[b'x'] = 4

.. _code-list-item:

Check list items [list-item]
----------------------------

When constructing a list using ``[item, ...]``, mypy checks that each item
is compatible with the list type that is inferred from the surrounding
context.

Example:

.. code-block:: python

    # Error: List item 0 has incompatible type "int"; expected "str"  [list-item]
    a: list[str] = [0]

.. _code-dict-item:

Check dict items [dict-item]
----------------------------

When constructing a dictionary using ``{key: value, ...}`` or ``dict(key=value, ...)``,
mypy checks that each key and value is compatible with the dictionary type that is
inferred from the surrounding context.

Example:

.. code-block:: python

    # Error: Dict entry 0 has incompatible type "str": "str"; expected "str": "int"  [dict-item]
    d: dict[str, int] = {'key': 'value'}

.. _code-typeddict-item:

Check TypedDict items [typeddict-item]
--------------------------------------

When constructing a TypedDict object, mypy checks that each key and value is compatible
with the TypedDict type that is inferred from the surrounding context.

When getting a TypedDict item, mypy checks that the key
exists. When assigning to a TypedDict, mypy checks that both the
key and the value are valid.

Example:

.. code-block:: python

    from typing import TypedDict

    class Point(TypedDict):
        x: int
        y: int

    # Error: Incompatible types (expression has type "float",
    #        TypedDict item "x" has type "int")  [typeddict-item]
    p: Point = {'x': 1.2, 'y': 4}

.. _code-typeddict-unknown-key:

Check TypedDict Keys [typeddict-unknown-key]
--------------------------------------------

When constructing a TypedDict object, mypy checks whether the
definition contains unknown keys, to catch invalid keys and
misspellings. On the other hand, mypy will not generate an error when
a previously constructed TypedDict value with extra keys is passed
to a function as an argument, since TypedDict values support
structural subtyping ("static duck typing") and the keys are assumed
to have been validated at the point of construction. Example:

.. code-block:: python

    from typing import TypedDict

    class Point(TypedDict):
        x: int
        y: int

    class Point3D(Point):
        z: int

    def add_x_coordinates(a: Point, b: Point) -> int:
        return a["x"] + b["x"]

    a: Point = {"x": 1, "y": 4}
    b: Point3D = {"x": 2, "y": 5, "z": 6}

    add_x_coordinates(a, b)  # OK

    # Error: Extra key "z" for TypedDict "Point"  [typeddict-unknown-key]
    add_x_coordinates(a, {"x": 1, "y": 4, "z": 5})

Setting a TypedDict item using an unknown key will also generate this
error, since it could be a misspelling:

.. code-block:: python

    a: Point = {"x": 1, "y": 2}
    # Error: Extra key "z" for TypedDict "Point"  [typeddict-unknown-key]
    a["z"] = 3

Reading an unknown key will generate the more general (and serious)
``typeddict-item`` error, which is likely to result in an exception at
runtime:

.. code-block:: python

    a: Point = {"x": 1, "y": 2}
    # Error: TypedDict "Point" has no key "z"  [typeddict-item]
    _ = a["z"]

.. note::

    This error code is a subcode of the wider ``[typeddict-item]`` code.

.. _code-has-type:

Check that type of target is known [has-type]
---------------------------------------------

Mypy sometimes generates an error when it hasn't inferred any type for
a variable being referenced. This can happen for references to
variables that are initialized later in the source file, and for
references across modules that form an import cycle. When this
happens, the reference gets an implicit ``Any`` type.

In this example the definitions of ``x`` and ``y`` are circular:

.. code-block:: python

   class Problem:
       def set_x(self) -> None:
           # Error: Cannot determine type of "y"  [has-type]
           self.x = self.y

       def set_y(self) -> None:
           self.y = self.x

To work around this error, you can add an explicit type annotation to
the target variable or attribute. Sometimes you can also reorganize
the code so that the definition of the variable is placed earlier than
the reference to the variable in a source file. Untangling cyclic
imports may also help.

We add an explicit annotation to the ``y`` attribute to work around
the issue:

.. code-block:: python

   class Problem:
       def set_x(self) -> None:
           self.x = self.y  # OK

       def set_y(self) -> None:
           self.y: int = self.x  # Added annotation here

.. _code-import:

Check for an issue with imports [import]
----------------------------------------

Mypy generates an error if it can't resolve an `import` statement.
This is a parent error code of `import-not-found` and `import-untyped`

See :ref:`ignore-missing-imports` for how to work around these errors.

.. _code-import-not-found:

Check that import target can be found [import-not-found]
--------------------------------------------------------

Mypy generates an error if it can't find the source code or a stub file
for an imported module.

Example:

.. code-block:: python

    # Error: Cannot find implementation or library stub for module named "m0dule_with_typo"  [import-not-found]
    import m0dule_with_typo

See :ref:`ignore-missing-imports` for how to work around these errors.

.. _code-import-untyped:

Check that import target can be found [import-untyped]
------------------------------------------------------

Mypy generates an error if it can find the source code for an imported module,
but that module does not provide type annotations (via :ref:`PEP 561 <installed-packages>`).

Example:

.. code-block:: python

    # Error: Library stubs not installed for "bs4"  [import-untyped]
    import bs4
    # Error: Skipping analyzing "no_py_typed": module is installed, but missing library stubs or py.typed marker  [import-untyped]
    import no_py_typed

In some cases, these errors can be fixed by installing an appropriate
stub package. See :ref:`ignore-missing-imports` for more details.

.. _code-no-redef:

Check that each name is defined once [no-redef]
-----------------------------------------------

Mypy may generate an error if you have multiple definitions for a name
in the same namespace.  The reason is that this is often an error, as
the second definition may overwrite the first one. Also, mypy often
can't be able to determine whether references point to the first or
the second definition, which would compromise type checking.

If you silence this error, all references to the defined name refer to
the *first* definition.

Example:

.. code-block:: python

   class A:
       def __init__(self, x: int) -> None: ...

   class A:  # Error: Name "A" already defined on line 1  [no-redef]
       def __init__(self, x: str) -> None: ...

   # Error: Argument 1 to "A" has incompatible type "str"; expected "int"
   #        (the first definition wins!)
   A('x')

.. _code-func-returns-value:

Check that called function returns a value [func-returns-value]
---------------------------------------------------------------

Mypy reports an error if you call a function with a ``None``
return type and don't ignore the return value, as this is
usually (but not always) a programming error.

In this example, the ``if f()`` check is always false since ``f``
returns ``None``:

.. code-block:: python

   def f() -> None:
       ...

   # OK: we don't do anything with the return value
   f()

   # Error: "f" does not return a value (it only ever returns None)  [func-returns-value]
   if f():
        print("not false")

.. _code-abstract:

Check instantiation of abstract classes [abstract]
--------------------------------------------------

Mypy generates an error if you try to instantiate an abstract base
class (ABC). An abstract base class is a class with at least one
abstract method or attribute. (See also :py:mod:`abc` module documentation)

Sometimes a class is made accidentally abstract, often due to an
unimplemented abstract method. In a case like this you need to provide
an implementation for the method to make the class concrete
(non-abstract).

Example:

.. code-block:: python

    from abc import ABCMeta, abstractmethod

    class Persistent(metaclass=ABCMeta):
        @abstractmethod
        def save(self) -> None: ...

    class Thing(Persistent):
        def __init__(self) -> None:
            ...

        ...  # No "save" method

    # Error: Cannot instantiate abstract class "Thing" with abstract attribute "save"  [abstract]
    t = Thing()

.. _code-type-abstract:

Safe handling of abstract type object types [type-abstract]
-----------------------------------------------------------

Mypy always allows instantiating (calling) type objects typed as ``type[t]``,
even if it is not known that ``t`` is non-abstract, since it is a common
pattern to create functions that act as object factories (custom constructors).
Therefore, to prevent issues described in the above section, when an abstract
type object is passed where ``type[t]`` is expected, mypy will give an error.
Example (Python 3.12 syntax):

.. code-block:: python

   from abc import ABCMeta, abstractmethod

   class Config(metaclass=ABCMeta):
       @abstractmethod
       def get_value(self, attr: str) -> str: ...

   def make_many[T](typ: type[T], n: int) -> list[T]:
       return [typ() for _ in range(n)]  # This will raise if typ is abstract

   # Error: Only concrete class can be given where "type[Config]" is expected [type-abstract]
   make_many(Config, 5)

.. _code-safe-super:

Check that call to an abstract method via super is valid [safe-super]
---------------------------------------------------------------------

Abstract methods often don't have any default implementation, i.e. their
bodies are just empty. Calling such methods in subclasses via ``super()``
will cause runtime errors, so mypy prevents you from doing so:

.. code-block:: python

   from abc import abstractmethod
   class Base:
       @abstractmethod
       def foo(self) -> int: ...
   class Sub(Base):
       def foo(self) -> int:
           return super().foo() + 1  # error: Call to abstract method "foo" of "Base" with
                                     # trivial body via super() is unsafe  [safe-super]
   Sub().foo()  # This will crash at runtime.

Mypy considers the following as trivial bodies: a ``pass`` statement, a literal
ellipsis ``...``, a docstring, and a ``raise NotImplementedError`` statement.

.. _code-valid-newtype:

Check the target of NewType [valid-newtype]
-------------------------------------------

The target of a :py:class:`~typing.NewType` definition must be a class type. It can't
be a union type, ``Any``, or various other special types.

You can also get this error if the target has been imported from a
module whose source mypy cannot find, since any such definitions are
treated by mypy as values with ``Any`` types. Example:

.. code-block:: python

   from typing import NewType

   # The source for "acme" is not available for mypy
   from acme import Entity  # type: ignore

   # Error: Argument 2 to NewType(...) must be subclassable (got "Any")  [valid-newtype]
   UserEntity = NewType('UserEntity', Entity)

To work around the issue, you can either give mypy access to the sources
for ``acme`` or create a stub file for the module.  See :ref:`ignore-missing-imports`
for more information.

.. _code-exit-return:

Check the return type of __exit__ [exit-return]
-----------------------------------------------

If mypy can determine that :py:meth:`__exit__ <object.__exit__>` always returns ``False``, mypy
checks that the return type is *not* ``bool``.  The boolean value of
the return type affects which lines mypy thinks are reachable after a
``with`` statement, since any :py:meth:`__exit__ <object.__exit__>` method that can return
``True`` may swallow exceptions. An imprecise return type can result
in mysterious errors reported near ``with`` statements.

To fix this, use either ``typing.Literal[False]`` or
``None`` as the return type. Returning ``None`` is equivalent to
returning ``False`` in this context, since both are treated as false
values.

Example:

.. code-block:: python

   class MyContext:
       ...
       def __exit__(self, exc, value, tb) -> bool:  # Error
           print('exit')
           return False

This produces the following output from mypy:

.. code-block:: text

   example.py:3: error: "bool" is invalid as return type for "__exit__" that always returns False
   example.py:3: note: Use "typing_extensions.Literal[False]" as the return type or change it to
       "None"
   example.py:3: note: If return type of "__exit__" implies that it may return True, the context
       manager may swallow exceptions

You can use ``Literal[False]`` to fix the error:

.. code-block:: python

   from typing import Literal

   class MyContext:
       ...
       def __exit__(self, exc, value, tb) -> Literal[False]:  # OK
           print('exit')
           return False

You can also use ``None``:

.. code-block:: python

   class MyContext:
       ...
       def __exit__(self, exc, value, tb) -> None:  # Also OK
           print('exit')

.. _code-name-match:

Check that naming is consistent [name-match]
--------------------------------------------

The definition of a named tuple or a TypedDict must be named
consistently when using the call-based syntax. Example:

.. code-block:: python

    from typing import NamedTuple

    # Error: First argument to namedtuple() should be "Point2D", not "Point"
    Point2D = NamedTuple("Point", [("x", int), ("y", int)])

.. _code-literal-required:

Check that literal is used where expected [literal-required]
------------------------------------------------------------

There are some places where only a (string) literal value is expected for
the purposes of static type checking, for example a ``TypedDict`` key, or
a ``__match_args__`` item. Providing a ``str``-valued variable in such contexts
will result in an error. Note that in many cases you can also use ``Final``
or ``Literal`` variables. Example:

.. code-block:: python

   from typing import Final, Literal, TypedDict

   class Point(TypedDict):
       x: int
       y: int

   def test(p: Point) -> None:
       X: Final = "x"
       p[X]  # OK

       Y: Literal["y"] = "y"
       p[Y]  # OK

       key = "x"  # Inferred type of key is `str`
       # Error: TypedDict key must be a string literal;
       #   expected one of ("x", "y")  [literal-required]
       p[key]

.. _code-no-overload-impl:

Check that overloaded functions have an implementation [no-overload-impl]
-------------------------------------------------------------------------

Overloaded functions outside of stub files must be followed by a non overloaded
implementation.

.. code-block:: python

   from typing import overload

   @overload
   def func(value: int) -> int:
       ...

   @overload
   def func(value: str) -> str:
       ...

   # presence of required function below is checked
   def func(value):
       pass  # actual implementation

.. _code-unused-coroutine:

Check that coroutine return value is used [unused-coroutine]
------------------------------------------------------------

Mypy ensures that return values of async def functions are not
ignored, as this is usually a programming error, as the coroutine
won't be executed at the call site.

.. code-block:: python

   async def f() -> None:
       ...

   async def g() -> None:
       f()  # Error: missing await
       await f()  # OK

You can work around this error by assigning the result to a temporary,
otherwise unused variable:

.. code-block:: python

       _ = f()  # No error

.. _code-top-level-await:

Warn about top level await expressions [top-level-await]
--------------------------------------------------------

This error code is separate from the general ``[syntax]`` errors, because in
some environments (e.g. IPython) a top level ``await`` is allowed. In such
environments a user may want to use ``--disable-error-code=top-level-await``,
which allows one to still have errors for other improper uses of ``await``,
for example:

.. code-block:: python

   async def f() -> None:
       ...

   top = await f()  # Error: "await" outside function  [top-level-await]

.. _code-await-not-async:

Warn about await expressions used outside of coroutines [await-not-async]
-------------------------------------------------------------------------

``await`` must be used inside a coroutine.

.. code-block:: python

   async def f() -> None:
       ...

   def g() -> None:
       await f()  # Error: "await" outside coroutine ("async def")  [await-not-async]

.. _code-assert-type:

Check types in assert_type [assert-type]
----------------------------------------

The inferred type for an expression passed to ``assert_type`` must match
the provided type.

.. code-block:: python

   from typing_extensions import assert_type

   assert_type([1], list[int])  # OK

   assert_type([1], list[str])  # Error

.. _code-truthy-function:

Check that function isn't used in boolean context [truthy-function]
-------------------------------------------------------------------

Functions will always evaluate to true in boolean contexts.

.. code-block:: python

    def f():
        ...

    if f:  # Error: Function "Callable[[], Any]" could always be true in boolean context  [truthy-function]
        pass

.. _code-str-format:

Check that string formatting/interpolation is type-safe [str-format]
--------------------------------------------------------------------

Mypy will check that f-strings, ``str.format()`` calls, and ``%`` interpolations
are valid (when corresponding template is a literal string). This includes
checking number and types of replacements, for example:

.. code-block:: python

    # Error: Cannot find replacement for positional format specifier 1 [str-format]
    "{} and {}".format("spam")
    "{} and {}".format("spam", "eggs")  # OK
    # Error: Not all arguments converted during string formatting [str-format]
    "{} and {}".format("spam", "eggs", "cheese")

    # Error: Incompatible types in string interpolation
    # (expression has type "float", placeholder has type "int") [str-format]
    "{:d}".format(3.14)

.. _code-str-bytes-safe:

Check for implicit bytes coercions [str-bytes-safe]
---------------------------------------------------

Warn about cases where a bytes object may be converted to a string in an unexpected manner.

.. code-block:: python

    b = b"abc"

    # Error: If x = b'abc' then f"{x}" or "{}".format(x) produces "b'abc'", not "abc".
    # If this is desired behavior, use f"{x!r}" or "{!r}".format(x).
    # Otherwise, decode the bytes [str-bytes-safe]
    print(f"The alphabet starts with {b}")

    # Okay
    print(f"The alphabet starts with {b!r}")  # The alphabet starts with b'abc'
    print(f"The alphabet starts with {b.decode('utf-8')}")  # The alphabet starts with abc

.. _code-str-unpack:

Check that ``str`` is not unpacked [str-unpack]
-----------------------------------------------

It can sometimes be surprising that ``str`` is iterable, especially when unpacking
in an assignment.

Example:

.. code-block:: python

    def print_dict(d: dict[str, str]) -> int:
        # We meant to do d.items(), but instead we're unpacking the str keys of d

        # Error: Unpacking a string is disallowed
        for k, v in d:
            print(k, v)

.. _code-overload-overlap:

Check that overloaded functions don't overlap [overload-overlap]
----------------------------------------------------------------

Warn if multiple ``@overload`` variants overlap in potentially unsafe ways.
This guards against the following situation:

.. code-block:: python

    from typing import overload

    class A: ...
    class B(A): ...

    @overload
    def foo(x: B) -> int: ...  # Error: Overloaded function signatures 1 and 2 overlap with incompatible return types  [overload-overlap]
    @overload
    def foo(x: A) -> str: ...
    def foo(x): ...

    def takes_a(a: A) -> str:
        return foo(a)

    a: A = B()
    value = takes_a(a)
    # mypy will think that value is a str, but it could actually be an int
    reveal_type(value) # Revealed type is "builtins.str"


Note that in cases where you ignore this error, mypy will usually still infer the
types you expect.

See :ref:`overloading <function-overloading>` for more explanation.


.. _code-overload-cannot-match:

Check for overload signatures that cannot match [overload-cannot-match]
-----------------------------------------------------------------------

Warn if an ``@overload`` variant can never be matched, because an earlier
overload has a wider signature. For example, this can happen if the two
overloads accept the same parameters and each parameter on the first overload
has the same type or a wider type than the corresponding parameter on the second
overload.

Example:

.. code-block:: python

    from typing import overload, Union

    @overload
    def process(response1: object, response2: object) -> object:
        ...
    @overload
    def process(response1: int, response2: int) -> int: # E: Overloaded function signature 2 will never be matched: signature 1's parameter type(s) are the same or broader  [overload-cannot-match]
        ...

    def process(response1: object, response2: object) -> object:
        return response1 + response2

.. _code-annotation-unchecked:

Notify about an annotation in an unchecked function [annotation-unchecked]
--------------------------------------------------------------------------

Sometimes a user may accidentally omit an annotation for a function, and mypy
will not check the body of this function (unless one uses
:option:`--check-untyped-defs <mypy --check-untyped-defs>` or
:option:`--disallow-untyped-defs <mypy --disallow-untyped-defs>`). To avoid
such situations go unnoticed, mypy will show a note, if there are any type
annotations in an unchecked function:

.. code-block:: python

    def test_assignment():  # "-> None" return annotation is missing
        # Note: By default the bodies of untyped functions are not checked,
        # consider using --check-untyped-defs [annotation-unchecked]
        x: int = "no way"

Note that mypy will still exit with return code ``0``, since such behaviour is
specified by :pep:`484`.

.. _code-prop-decorator:

Decorator preceding property not supported [prop-decorator]
-----------------------------------------------------------

Mypy does not yet support analysis of decorators that precede the property
decorator. If the decorator does not preserve the declared type of the property,
mypy will not infer the correct type for the declaration. If the decorator cannot
be moved after the ``@property`` decorator, then you must use a type ignore
comment:

.. code-block:: python

    class MyClass:
        @special  # type: ignore[prop-decorator]
        @property
        def magic(self) -> str:
            return ""

.. note::

    For backward compatibility, this error code is a subcode of the generic ``[misc]`` code.

.. _code-syntax:

Report syntax errors [syntax]
-----------------------------

If the code being checked is not syntactically valid, mypy issues a
syntax error. Most, but not all, syntax errors are *blocking errors*:
they can't be ignored with a ``# type: ignore`` comment.

.. _code-typeddict-readonly-mutated:

ReadOnly key of a TypedDict is mutated [typeddict-readonly-mutated]
-------------------------------------------------------------------

Consider this example:

.. code-block:: python

    from datetime import datetime
    from typing import TypedDict
    from typing_extensions import ReadOnly

    class User(TypedDict):
        username: ReadOnly[str]
        last_active: datetime

    user: User = {'username': 'foobar', 'last_active': datetime.now()}
    user['last_active'] = datetime.now()  # ok
    user['username'] = 'other'  # error: ReadOnly TypedDict key "key" TypedDict is mutated  [typeddict-readonly-mutated]

`PEP 705 <https://peps.python.org/pep-0705>`_ specifies
how ``ReadOnly`` special form works for ``TypedDict`` objects.

.. _code-narrowed-type-not-subtype:

Check that ``TypeIs`` narrows types [narrowed-type-not-subtype]
---------------------------------------------------------------

:pep:`742` requires that when ``TypeIs`` is used, the narrowed
type must be a subtype of the original type::

    from typing_extensions import TypeIs

    def f(x: int) -> TypeIs[str]:  # Error, str is not a subtype of int
        ...

    def g(x: object) -> TypeIs[str]:  # OK
        ...

.. _code-maybe-unrecognized-str-typeform:

String appears in a context which expects a TypeForm [maybe-unrecognized-str-typeform]
--------------------------------------------------------------------------------------

TypeForm literals may contain string annotations:

.. code-block:: python

   typx1: TypeForm = str | None
   typx2: TypeForm = 'str | None'  # OK
   typx3: TypeForm = 'str' | None  # OK

However TypeForm literals containing a string annotation can only be recognized
by mypy in the following locations:

.. code-block:: python

   typx_var: TypeForm = 'str | None'  # assignment r-value

   def func(typx_param: TypeForm) -> TypeForm:
       return 'str | None'  # returned expression

   func('str | None')  # callable's argument

If you try to use a string annotation in some other location
which expects a TypeForm, the string value will always be treated as a ``str``
even if a ``TypeForm`` would be more appropriate and this error code
will be generated:

.. code-block:: python

   # Error: TypeForm containing a string annotation cannot be recognized here. Surround with TypeForm(...) to recognize.  [maybe-unrecognized-str-typeform]
   # Error: List item 0 has incompatible type "str"; expected "TypeForm[Any]"  [list-item]
   list_of_typx: list[TypeForm] = ['str | None', float]

Fix the error by surrounding the entire type with ``TypeForm(...)``:

.. code-block:: python

   list_of_typx: list[TypeForm] = [TypeForm('str | None'), float]  # OK

Similarly, if you try to use a string literal in a location which expects a
TypeForm, this error code will be generated:

.. code-block:: python

   dict_of_typx = {'str_or_none': TypeForm(str | None)}
   # Error: TypeForm containing a string annotation cannot be recognized here. Surround with TypeForm(...) to recognize.  [maybe-unrecognized-str-typeform]
   list_of_typx: list[TypeForm] = [dict_of_typx['str_or_none']]

Fix the error by adding ``# type: ignore[maybe-unrecognized-str-typeform]``
to the line with the string literal:

.. code-block:: python

   dict_of_typx = {'str_or_none': TypeForm(str | None)}
   list_of_typx: list[TypeForm] = [dict_of_typx['str_or_none']]  # type: ignore[maybe-unrecognized-str-typeform]

.. _code-misc:

Miscellaneous checks [misc]
---------------------------

Mypy performs numerous other, less commonly failing checks that don't
have specific error codes. These use the ``misc`` error code. Other
than being used for multiple unrelated errors, the ``misc`` error code
is not special. For example, you can ignore all errors in this
category by using ``# type: ignore[misc]`` comment. Since these errors
are not expected to be common, it's unlikely that you'll see two
*different* errors with the ``misc`` code on a single line -- though
this can certainly happen once in a while.

.. note::

    Future mypy versions will likely add new error codes for some errors
    that currently use the ``misc`` error code.

.. _error-codes-optional:

Error codes for optional checks
-------------------------------

This section documents various errors codes that mypy generates only
if you enable certain options. See :ref:`error-codes` for general
documentation about error codes and their configuration.
:ref:`error-code-list` documents error codes that are enabled by default.

.. note::

   The examples in this section use :ref:`inline configuration
   <inline-config>` to specify mypy options. You can also set the same
   options by using a :ref:`configuration file <config-file>` or
   :ref:`command-line options <command-line>`.

.. _code-type-arg:

Check that type arguments exist [type-arg]
------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--disallow-any-generics` to enable it.

If you use :option:`--disallow-any-generics <mypy --disallow-any-generics>`, mypy requires that each generic
type has values for each type argument. For example, the types ``list`` or
``dict`` would be rejected. You should instead use types like ``list[int]`` or
``dict[str, int]``. Any omitted generic type arguments get implicit ``Any``
values. The type ``list`` is equivalent to ``list[Any]``, and so on.

Example:

.. code-block:: python

    # mypy: disallow-any-generics

    # Error: Missing type arguments for generic type "list"  [type-arg]
    def remove_dups(items: list) -> list:
        ...

.. _code-no-untyped-def:

Check that every function has an annotation [no-untyped-def]
------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--disallow-untyped-defs` to enable it.

If you use :option:`--disallow-untyped-defs <mypy --disallow-untyped-defs>`, mypy requires that all functions
have annotations (either a Python 3 annotation or a type comment).

Example:

.. code-block:: python

    # mypy: disallow-untyped-defs

    def inc(x):  # Error: Function is missing a type annotation  [no-untyped-def]
        return x + 1

    def inc_ok(x: int) -> int:  # OK
        return x + 1

    class Counter:
         # Error: Function is missing a type annotation  [no-untyped-def]
         def __init__(self):
             self.value = 0

    class CounterOk:
         # OK: An explicit "-> None" is needed if "__init__" takes no arguments
         def __init__(self) -> None:
             self.value = 0

.. _code-redundant-cast:

Check that cast is not redundant [redundant-cast]
-------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--warn-redundant-casts` to enable it.

If you use :option:`--warn-redundant-casts <mypy --warn-redundant-casts>`, mypy will generate an error if the source
type of a cast is the same as the target type.

Example:

.. code-block:: python

    # mypy: warn-redundant-casts

    from typing import cast

    Count = int

    def example(x: Count) -> int:
        # Error: Redundant cast to "int"  [redundant-cast]
        return cast(int, x)

.. _code-redundant-self:

Check that methods do not have redundant Self annotations [redundant-self]
--------------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``redundant-self`` to enable it.

If a method uses the ``Self`` type in the return type or the type of a
non-self argument, there is no need to annotate the ``self`` argument
explicitly. Such annotations are allowed by :pep:`673` but are
redundant. If you enable this error code, mypy will generate an error if
there is a redundant ``Self`` type.

Example:

.. code-block:: python

   # mypy: enable-error-code="redundant-self"

   from typing import Self

   class C:
       # Error: Redundant "Self" annotation for the first method argument
       def copy(self: Self) -> Self:
           return type(self)()

.. _code-comparison-overlap:

Check that comparisons are overlapping [comparison-overlap]
-----------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--strict-equality` to enable it.

If you use :option:`--strict-equality <mypy --strict-equality>`, mypy will generate an error if it
thinks that a comparison operation is always true or false. These are
often bugs. Sometimes mypy is too picky and the comparison can
actually be useful. Instead of disabling strict equality checking
everywhere, you can use ``# type: ignore[comparison-overlap]`` to
ignore the issue on a particular line only.

Example:

.. code-block:: python

    # mypy: strict-equality

    def is_magic(x: bytes) -> bool:
        # Error: Non-overlapping equality check (left operand type: "bytes",
        #        right operand type: "str")  [comparison-overlap]
        return x == 'magic'

We can fix the error by changing the string literal to a bytes
literal:

.. code-block:: python

    # mypy: strict-equality

    def is_magic(x: bytes) -> bool:
        return x == b'magic'  # OK

:option:`--strict-equality <mypy --strict-equality>` does not include comparisons with
``None``:

.. code-block:: python

    # mypy: strict-equality

    def is_none(x: str) -> bool:
        return x is None  # OK

If you want such checks, you must also activate
:option:`--strict-equality-for-none <mypy --strict-equality-for-none>` (we might merge
these two options later).

.. code-block:: python

    # mypy: strict-equality strict-equality-for-none

    def is_none(x: str) -> bool:
        # Error: Non-overlapping identity check
        #        (left operand type: "str", right operand type: "None")
        return x is None

.. _code-no-untyped-call:

Check that no untyped functions are called [no-untyped-call]
------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--disallow-untyped-calls` to enable it.

If you use :option:`--disallow-untyped-calls <mypy --disallow-untyped-calls>`, mypy generates an error when you
call an unannotated function in an annotated function.

Example:

.. code-block:: python

    # mypy: disallow-untyped-calls

    def do_it() -> None:
        # Error: Call to untyped function "bad" in typed context  [no-untyped-call]
        bad()

    def bad():
        ...

.. _code-no-any-return:

Check that function does not return Any value [no-any-return]
-------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--warn-return-any` to enable it.

If you use :option:`--warn-return-any <mypy --warn-return-any>`, mypy generates an error if you return a
value with an ``Any`` type in a function that is annotated to return a
non-``Any`` value.

Example:

.. code-block:: python

    # mypy: warn-return-any

    def fields(s):
         return s.split(',')

    def first_field(x: str) -> str:
        # Error: Returning Any from function declared to return "str"  [no-any-return]
        return fields(x)[0]

.. _code-no-any-unimported:

Check that types have no Any components due to missing imports [no-any-unimported]
----------------------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--disallow-any-unimported` to enable it.

If you use :option:`--disallow-any-unimported <mypy --disallow-any-unimported>`, mypy generates an error if a component of
a type becomes ``Any`` because mypy couldn't resolve an import. These "stealth"
``Any`` types can be surprising and accidentally cause imprecise type checking.

In this example, we assume that mypy can't find the module ``animals``, which means
that ``Cat`` falls back to ``Any`` in a type annotation:

.. code-block:: python

    # mypy: disallow-any-unimported

    from animals import Cat  # type: ignore

    # Error: Argument 1 to "feed" becomes "Any" due to an unfollowed import  [no-any-unimported]
    def feed(cat: Cat) -> None:
        ...

.. _code-unreachable:

Check that statement or expression is unreachable [unreachable]
---------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--warn-unreachable` to enable it.

If you use :option:`--warn-unreachable <mypy --warn-unreachable>`, mypy generates an error if it
thinks that a statement or expression will never be executed. In most cases, this is due to
incorrect control flow or conditional checks that are accidentally always true or false.

.. code-block:: python

    # mypy: warn-unreachable

    def example(x: int) -> None:
        # Error: Right operand of "or" is never evaluated  [unreachable]
        assert isinstance(x, int) or x == 'unused'

        return
        # Error: Statement is unreachable  [unreachable]
        print('unreachable')

.. _code-deprecated:

Check that imported or used feature is deprecated [deprecated]
--------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``deprecated`` to enable it.

If you use :option:`--enable-error-code deprecated <mypy --enable-error-code>`,
mypy generates an error if your code imports a deprecated feature explicitly with a
``from mod import depr`` statement or uses a deprecated feature imported otherwise or defined
locally.  Features are considered deprecated when decorated with ``warnings.deprecated``, as
specified in `PEP 702 <https://peps.python.org/pep-0702>`_.
Use the :option:`--report-deprecated-as-note <mypy --report-deprecated-as-note>` option to
turn all such errors into notes.
Use :option:`--deprecated-calls-exclude <mypy --deprecated-calls-exclude>` to hide warnings
for specific functions, classes and packages.

.. note::

    The ``warnings`` module provides the ``@deprecated`` decorator since Python 3.13.
    To use it with older Python versions, import it from ``typing_extensions`` instead.

Examples:

.. code-block:: python

    # mypy: report-deprecated-as-error

    # Error: abc.abstractproperty is deprecated: Deprecated, use 'property' with 'abstractmethod' instead
    from abc import abstractproperty

    from typing_extensions import deprecated

    @deprecated("use new_function")
    def old_function() -> None:
        print("I am old")

    # Error: __main__.old_function is deprecated: use new_function
    old_function()
    old_function()  # type: ignore[deprecated]


.. _code-redundant-expr:

Check that expression is redundant [redundant-expr]
---------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``redundant-expr`` to enable it.

If you use :option:`--enable-error-code redundant-expr <mypy --enable-error-code>`,
mypy generates an error if it thinks that an expression is redundant.

.. code-block:: python

    # mypy: enable-error-code="redundant-expr"

    def example(x: int) -> None:
        # Error: Left operand of "and" is always true  [redundant-expr]
        if isinstance(x, int) and x > 0:
            pass

        # Error: If condition is always true  [redundant-expr]
        1 if isinstance(x, int) else 0

        # Error: If condition in comprehension is always true  [redundant-expr]
        [i for i in range(x) if isinstance(i, int)]


.. _code-possibly-undefined:

Warn about variables that are defined only in some execution paths [possibly-undefined]
---------------------------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``possibly-undefined`` to enable it.

If you use :option:`--enable-error-code possibly-undefined <mypy --enable-error-code>`,
mypy generates an error if it cannot verify that a variable will be defined in
all execution paths. This includes situations when a variable definition
appears in a loop, in a conditional branch, in an except handler, etc. For
example:

.. code-block:: python

    # mypy: enable-error-code="possibly-undefined"

    from collections.abc import Iterable

    def test(values: Iterable[int], flag: bool) -> None:
        if flag:
            a = 1
        z = a + 1  # Error: Name "a" may be undefined [possibly-undefined]

        for v in values:
            b = v
        z = b + 1  # Error: Name "b" may be undefined [possibly-undefined]

.. _code-truthy-bool:

Check that expression is not implicitly true in boolean context [truthy-bool]
-----------------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``truthy-bool`` to enable it.

Warn when the type of an expression in a boolean context does not
implement ``__bool__`` or ``__len__``. Unless one of these is
implemented by a subtype, the expression will always be considered
true, and there may be a bug in the condition.

As an exception, the ``object`` type is allowed in a boolean context.
Using an iterable value in a boolean context has a separate error code
(see below).

.. code-block:: python

    # mypy: enable-error-code="truthy-bool"

    class Foo:
        pass
    foo = Foo()
    # Error: "foo" has type "Foo" which does not implement __bool__ or __len__ so it could always be true in boolean context
    if foo:
         ...

.. _code-truthy-iterable:

Check that iterable is not implicitly true in boolean context [truthy-iterable]
-------------------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``truthy-iterable`` to enable it.

Generate an error if a value of type ``Iterable`` is used as a boolean
condition, since ``Iterable`` does not implement ``__len__`` or ``__bool__``.

Example:

.. code-block:: python

    from collections.abc import Iterable

    def transform(items: Iterable[int]) -> list[int]:
        # Error: "items" has type "Iterable[int]" which can always be true in boolean context. Consider using "Collection[int]" instead.  [truthy-iterable]
        if not items:
            return [42]
        return [x + 1 for x in items]

If ``transform`` is called with a ``Generator`` argument, such as
``int(x) for x in []``, this function would not return ``[42]`` unlike
what might be intended. Of course, it's possible that ``transform`` is
only called with ``list`` or other container objects, and the ``if not
items`` check is actually valid. If that is the case, it is
recommended to annotate ``items`` as ``Collection[int]`` instead of
``Iterable[int]``.

.. _code-ignore-without-code:

Check that ``# type: ignore`` include an error code [ignore-without-code]
-------------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``ignore-without-code`` to enable it.

Warn when a ``# type: ignore`` comment does not specify any error codes.
This clarifies the intent of the ignore and ensures that only the
expected errors are silenced.

Example:

.. code-block:: python

    # mypy: enable-error-code="ignore-without-code"

    class Foo:
        def __init__(self, name: str) -> None:
            self.name = name

    f = Foo('foo')

    # This line has a typo that mypy can't help with as both:
    # - the expected error 'assignment', and
    # - the unexpected error 'attr-defined'
    # are silenced.
    # Error: "type: ignore" comment without error code (consider "type: ignore[attr-defined]" instead)
    f.nme = 42  # type: ignore

    # This line warns correctly about the typo in the attribute name
    # Error: "Foo" has no attribute "nme"; maybe "name"?
    f.nme = 42  # type: ignore[assignment]

.. _code-unused-awaitable:

Check that awaitable return value is used [unused-awaitable]
------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``unused-awaitable`` to enable it.

If you use :option:`--enable-error-code unused-awaitable <mypy --enable-error-code>`,
mypy generates an error if you don't use a returned value that defines ``__await__``.

Example:

.. code-block:: python

    # mypy: enable-error-code="unused-awaitable"

    import asyncio

    async def f() -> int: ...

    async def g() -> None:
        # Error: Value of type "Task[int]" must be used
        #        Are you missing an await?
        asyncio.create_task(f())

You can assign the value to a temporary, otherwise unused variable to
silence the error:

.. code-block:: python

    async def g() -> None:
        _ = asyncio.create_task(f())  # No error

.. _code-unused-ignore:

Check that ``# type: ignore`` comment is used [unused-ignore]
-------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--warn-unused-ignores` to enable it.

If you use :option:`--enable-error-code unused-ignore <mypy --enable-error-code>`,
or :option:`--warn-unused-ignores <mypy --warn-unused-ignores>`
mypy generates an error if you don't use a ``# type: ignore`` comment, i.e. if
there is a comment, but there would be no error generated by mypy on this line
anyway.

Example:

.. code-block:: python

    # Use "mypy --warn-unused-ignores ..."

    def add(a: int, b: int) -> int:
        # Error: unused "type: ignore" comment
        return a + b  # type: ignore

Note that due to a specific nature of this comment, the only way to selectively
silence it, is to include the error code explicitly. Also note that this error is
not shown if the ``# type: ignore`` is not used due to code being statically
unreachable (e.g. due to platform or version checks).

Example:

.. code-block:: python

    # Use "mypy --warn-unused-ignores ..."

    import sys

    try:
        # The "[unused-ignore]" is needed to get a clean mypy run
        # on both Python 3.8, and 3.9 where this module was added
        import graphlib  # type: ignore[import,unused-ignore]
    except ImportError:
        pass

    if sys.version_info >= (3, 9):
        # The following will not generate an error on either
        # Python 3.8, or Python 3.9
        42 + "testing..."  # type: ignore

.. _code-explicit-override:

Check that ``@override`` is used when overriding a base class method [explicit-override]
----------------------------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``explicit-override`` to enable it.

If you use :option:`--enable-error-code explicit-override <mypy --enable-error-code>`
mypy generates an error if you override a base class method without using the
``@override`` decorator. An error will not be emitted for overrides of ``__init__``
or ``__new__``. See `PEP 698 <https://peps.python.org/pep-0698/#strict-enforcement-per-project>`_.

.. note::

    Starting with Python 3.12, the ``@override`` decorator can be imported from ``typing``.
    To use it with older Python versions, import it from ``typing_extensions`` instead.

Example:

.. code-block:: python

    # mypy: enable-error-code="explicit-override"

    from typing import override

    class Parent:
        def f(self, x: int) -> None:
            pass

        def g(self, y: int) -> None:
            pass


    class Child(Parent):
        def f(self, x: int) -> None:  # Error: Missing @override decorator
            pass

        @override
        def g(self, y: int) -> None:
            pass

.. _code-mutable-override:

Check that overrides of mutable attributes are safe [mutable-override]
----------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``mutable-override`` to enable it.

`mutable-override` will enable the check for unsafe overrides of mutable attributes.
For historical reasons, and because this is a relatively common pattern in Python,
this check is not enabled by default. The example below is unsafe, and will be
flagged when this error code is enabled:

.. code-block:: python

    from typing import Any

    class C:
        x: float
        y: float
        z: float

    class D(C):
        x: int  # Error: Covariant override of a mutable attribute
                # (base class "C" defined the type as "float",
                # expression has type "int")  [mutable-override]
        y: float  # OK
        z: Any  # OK

    def f(c: C) -> None:
        c.x = 1.1
    d = D()
    f(d)
    d.x >> 1  # This will crash at runtime, because d.x is now float, not an int

.. _code-unimported-reveal:

Check that ``reveal_type`` is imported from typing or typing_extensions [unimported-reveal]
-------------------------------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``unimported-reveal`` to enable it.

Mypy used to have ``reveal_type`` as a special builtin
that only existed during type-checking.
In runtime it fails with expected ``NameError``,
which can cause real problem in production, hidden from mypy.

But, in Python3.11 :py:func:`typing.reveal_type` was added.
``typing_extensions`` ported this helper to all supported Python versions.

Now users can actually import ``reveal_type`` to make the runtime code safe.

.. note::

    Starting with Python 3.11, the ``reveal_type`` function can be imported from ``typing``.
    To use it with older Python versions, import it from ``typing_extensions`` instead.

.. code-block:: python

    # mypy: enable-error-code="unimported-reveal"

    x = 1
    reveal_type(x)  # Note: Revealed type is "builtins.int" \
                    # Error: Name "reveal_type" is not defined

Correct usage:

.. code-block:: python

    # mypy: enable-error-code="unimported-reveal"
    from typing import reveal_type   # or `typing_extensions`

    x = 1
    # This won't raise an error:
    reveal_type(x)  # Note: Revealed type is "builtins.int"

When this code is enabled, using ``reveal_locals`` is always an error,
because there's no way one can import it.


.. _code-explicit-any:

Check that explicit Any type annotations are not allowed [explicit-any]
-----------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--disallow-any-explicit` to enable it.

If you use :option:`--disallow-any-explicit <mypy --disallow-any-explicit>`, mypy generates an error
if you use an explicit ``Any`` type annotation.

Example:

.. code-block:: python

    # mypy: disallow-any-explicit
    from typing import Any
    x: Any = 1  # Error: Explicit "Any" type annotation  [explicit-any]


.. _code-exhaustive-match:

Check that match statements match exhaustively [exhaustive-match]
-----------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--enable-error-code <mypy --enable-error-code>` ``exhaustive-match`` to enable it.

If enabled with :option:`--enable-error-code exhaustive-match <mypy --enable-error-code>`,
mypy generates an error if a match statement does not match all possible cases/types.


Example:

.. code-block:: python

        import enum


        class Color(enum.Enum):
            RED = 1
            BLUE = 2

        val: Color = Color.RED

        # OK without --enable-error-code exhaustive-match
        match val:
            case Color.RED:
                print("red")

        # With --enable-error-code exhaustive-match
        # Error: Match statement has unhandled case for values of type "Literal[Color.BLUE]"
        match val:
            case Color.RED:
                print("red")

        # OK with or without --enable-error-code exhaustive-match, since all cases are handled
        match val:
            case Color.RED:
                print("red")
            case _:
                print("other")

.. _code-untyped-decorator:

Error if an untyped decorator makes a typed function effectively untyped [untyped-decorator]
--------------------------------------------------------------------------------------------

.. note::
   This error code is disabled by default. Use :option:`--disallow-untyped-decorators` to enable it.

If enabled with :option:`--disallow-untyped-decorators <mypy --disallow-untyped-decorators>`
mypy generates an error if a typed function is wrapped by an untyped decorator
(as this would effectively remove the benefits of typing the function).

Example:

.. code-block:: python

        def printing_decorator(func):
            def wrapper(*args,  kwds):
                print("Calling", func)
                return func(*args,  kwds)
            return wrapper
        # A decorated function.
        @printing_decorator  # E: Untyped decorator makes function "add_forty_two" untyped  [untyped-decorator]
        def add_forty_two(value: int) -> int:
            return value + 42
.. _error-code-list:

Error codes enabled by default
==============================

This section documents various errors codes that mypy can generate
with default options. See :ref:`error-codes` for general documentation
about error codes. :ref:`error-codes-optional` documents additional
error codes that you can enable.

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

   r = Resouce('x')
   print(r.name)  # OK
   print(r.id)  # Error: "Resource" has no attribute "id"  [attr-defined]
   r.id = 5  # Error: "Resource" has no attribute "id"  [attr-defined]

This error code is also generated if an imported name is not defined
in the module in a ``from ... import`` statement (as long as the
target module can be found):

.. code-block:: python

    # Error: Module 'os' has no attribute 'non_existent'  [attr-defined]
    from os import non_existent

A reference to a missing attribute is given the ``Any`` type. In the
above example, the type of ``non_existent`` will be ``Any``, which can
be important if you silence the error.

Check that attribute exists in each union item [union-attr]
-----------------------------------------------------------

If you access the attribute of a value with a union type, mypy checks
that the attribute is defined for *every* type in that
union. Otherwise the operation can fail at runtime. This also applies
to optional types.

Example:

.. code-block:: python

   from typing import Union

   class Cat:
       def sleep(self) -> None: ...
       def miaow(self) -> None: ...

   class Dog:
       def sleep(self) -> None: ...
       def follow_me(self) -> None: ...

   def func(animal: Union[Cat, Dog]) -> None:
       # OK: 'sleep' is defined for both Cat and Dog
       animal.sleep()
       # Error: Item "Cat" of "Union[Cat, Dog]" has no attribute "follow_me"  [union-attr]
       animal.follow_me()

You can often work around these errors by using ``assert isinstance(obj, ClassName)``
or ``assert obj is not None`` to tell mypy that you know that the type is more specific
than what mypy thinks.

Check that name is defined [name-defined]
-----------------------------------------

Mypy expects that all references to names have a corresponding
definition in an active scope, such as an assignment, function
definition or an import. This can catch missing definitions, missing
imports, and typos.

This example accidentally calls ``sort()`` instead of :py:func:`sorted`:

.. code-block:: python

    x = sort([3, 2, 4])  # Error: Name 'sort' is not defined  [name-defined]

Check arguments in calls [call-arg]
-----------------------------------

Mypy expects that the number and names of arguments match the called function.
Note that argument type checks have a separate error code ``arg-type``.

Example:

.. code-block:: python

    from typing import Sequence

    def greet(name: str) -> None:
         print('hello', name)

    greet('jack')  # OK
    greet('jill', 'jack')  # Error: Too many arguments for "greet"  [call-arg]

Check argument types [arg-type]
-------------------------------

Mypy checks that argument types in a call match the declared argument
types in the signature of the called function (if one exists).

Example:

.. code-block:: python

   from typing import List, Optional

   def first(x: List[int]) -> Optional[int]:
        return x[0] if x else 0

   t = (5, 4)
   # Error: Argument 1 to "first" has incompatible type "Tuple[int, int]";
   #        expected "List[int]"  [arg-type]
   print(first(t))

Check calls to overloaded functions [call-overload]
---------------------------------------------------

When you call an overloaded function, mypy checks that at least one of
the signatures of the overload items match the argument types in the
call.

Example:

.. code-block:: python

   from typing import overload, Optional

   @overload
   def inc_maybe(x: None) -> None: ...

   @overload
   def inc_maybe(x: int) -> int: ...

   def inc_maybe(x: Optional[int]) -> Optional[int]:
        if x is None:
            return None
        else:
            return x + 1

   inc_maybe(None)  # OK
   inc_maybe(5)  # OK

   # Error: No overload variant of "inc_maybe" matches argument type "float"  [call-overload]
   inc_maybe(1.2)

Check validity of types [valid-type]
------------------------------------

Mypy checks that each type annotation and any expression that
represents a type is a valid type. Examples of valid types include
classes, union types, callable types, type aliases, and literal types.
Examples of invalid types include bare integer literals, functions,
variables, and modules.

This example incorrectly uses the function ``log`` as a type:

.. code-block:: python

   from typing import List

   def log(x: object) -> None:
       print('log:', repr(x))

   # Error: Function "t.log" is not valid as a type  [valid-type]
   def log_all(objs: List[object], f: log) -> None:
       for x in objs:
           f(x)

You can use :py:data:`~typing.Callable` as the type for callable objects:

.. code-block:: python

   from typing import List, Callable

   # OK
   def log_all(objs: List[object], f: Callable[[object], None]) -> None:
       for x in objs:
           f(x)

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
           # Error: Need type annotation for 'items'
           #        (hint: "items: List[<type>] = ...")  [var-annotated]
           self.items = []

   reveal_type(Bundle().items)  # list[Any]

To address this, we add an explicit annotation:

.. code-block:: python

   from typing import List

   class Bundle:
       def __init__(self) -> None:
           self.items: List[str] = []  # OK

   reveal_type(Bundle().items)  # list[str]

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

   from typing import Optional, Union

   class Base:
       def method(self,
                  arg: int) -> Optional[int]:
           ...

   class Derived(Base):
       def method(self,
                  arg: Union[int, str]) -> int:  # OK
           ...

   class DerivedBad(Base):
       # Error: Argument 1 of "method" is incompatible with "Base"  [override]
       def method(self,
                  arg: bool) -> int:
           ...

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

Check that return value is compatible [return-value]
----------------------------------------------------

Mypy checks that the returned value is compatible with the type
signature of the function.

Example:

.. code-block:: python

   def func(x: int) -> str:
       # Error: Incompatible return value type (got "int", expected "str")  [return-value]
       return x + 1

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

Check type variable values [type-var]
-------------------------------------

Mypy checks that value of a type variable is compatible with a value
restriction or the upper bound type.

Example:

.. code-block:: python

    from typing import TypeVar

    T1 = TypeVar('T1', int, float)

    def add(x: T1, y: T1) -> T1:
        return x + y

    add(4, 5.5)  # OK

    # Error: Value of type variable "T1" of "add" cannot be "str"  [type-var]
    add('x', 'y')

Check uses of various operators [operator]
------------------------------------------

Mypy checks that operands support a binary or unary operation, such as
``+`` or ``~``. Indexing operations are so common that they have their
own error code ``index`` (see below).

Example:

.. code-block:: python

   # Error: Unsupported operand types for + ("int" and "str")  [operator]
   1 + 'x'

Check indexing operations [index]
---------------------------------

Mypy checks that the indexed value in indexing operation such as
``x[y]`` supports indexing, and that the index expression has a valid
type.

Example:

.. code-block:: python

   a = {'x': 1, 'y': 2}

   a['x']  # OK

   # Error: Invalid index type "int" for "Dict[str, int]"; expected type "str"  [index]
   print(a[1])

   # Error: Invalid index type "bytes" for "Dict[str, int]"; expected type "str"  [index]
   a[b'x'] = 4

Check list items [list-item]
----------------------------

When constructing a list using ``[item, ...]``, mypy checks that each item
is compatible with the list type that is inferred from the surrounding
context.

Example:

.. code-block:: python

    from typing import List

    # Error: List item 0 has incompatible type "int"; expected "str"  [list-item]
    a: List[str] = [0]

Check dict items [dict-item]
----------------------------

When constructing a dictionary using ``{key: value, ...}`` or ``dict(key=value, ...)``,
mypy checks that each key and value is compatible with the dictionary type that is
inferred from the surrounding context.

Example:

.. code-block:: python

    from typing import Dict

    # Error: Dict entry 0 has incompatible type "str": "str"; expected "str": "int"  [dict-item]
    d: Dict[str, int] = {'key': 'value'}

Check TypedDict items [typeddict-item]
--------------------------------------

When constructing a ``TypedDict`` object, mypy checks that each key and value is compatible
with the ``TypedDict`` type that is inferred from the surrounding context.

Example:

.. code-block:: python

    from typing_extensions import TypedDict

    class Point(TypedDict):
        x: int
        y: int

    # Error: Incompatible types (expression has type "float",
    #        TypedDict item "x" has type "int")  [typeddict-item]
    p: Point = {'x': 1.2, 'y': 4}

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
           # Error: Cannot determine type of 'y'  [has-type]
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

Check that import target can be found [import]
----------------------------------------------

Mypy generates an error if it can't find the source code or a stub file
for an imported module.

Example:

.. code-block:: python

    # Error: Cannot find implementation or library stub for module named 'acme'  [import]
    import acme

See :ref:`ignore-missing-imports` for how to work around these errors.

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

   class A:  # Error: Name 'A' already defined on line 1  [no-redef]
       def __init__(self, x: str) -> None: ...

   # Error: Argument 1 to "A" has incompatible type "str"; expected "int"
   #        (the first definition wins!)
   A('x')

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

   # Error: "f" does not return a value  [func-returns-value]
   if f():
        print("not false")

Check instantiation of abstract classes [abstract]
--------------------------------------------------

Mypy generates an error if you try to instantiate an abstract base
class (ABC). An abtract base class is a class with at least one
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

    # Error: Cannot instantiate abstract class 'Thing' with abstract attribute 'save'  [abstract]
    t = Thing()

Check the target of NewType [valid-newtype]
-------------------------------------------

The target of a :py:func:`NewType <typing.NewType>` definition must be a class type. It can't
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

Check the return type of __exit__ [exit-return]
-----------------------------------------------

If mypy can determine that :py:meth:`__exit__ <object.__exit__>` always returns ``False``, mypy
checks that the return type is *not* ``bool``.  The boolean value of
the return type affects which lines mypy thinks are reachable after a
``with`` statement, since any :py:meth:`__exit__ <object.__exit__>` method that can return
``True`` may swallow exceptions. An imprecise return type can result
in mysterious errors reported near ``with`` statements.

To fix this, use either ``typing_extensions.Literal[False]`` or
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

   from typing_extensions import Literal

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


Report syntax errors [syntax]
-----------------------------

If the code being checked is not syntactically valid, mypy issues a
syntax error. Most, but not all, syntax errors are *blocking errors*:
they can't be ignored with a ``# type: ignore`` comment.

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

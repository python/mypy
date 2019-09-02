.. _error-code-list:

List of error codes (default checks)
====================================

This section documents various errors codes that mypy can generate
with default options. See :ref:`error-codes` for general documentation
about error codes. See :ref:`error-codes-optional` for additional
error codes that you can enable.

Check that attribute exists [attr-defined]
------------------------------------------

Mypy that an attribute is defined in the target class or module. This
applies to reading an attribute and setting an attribute. Attribute
assignments in a class body or through the ``self`` argument are
considered to define new attributes. Mypy doesn't allow defining
attributes outside a class definition.

Example:

.. code-block:: python

   class Resource:
       def __init__(self, name: str) -> None:
           self.name = name

   r = Resouce('x')
   print(r.name)  # OK
   print(r.id)  # "Resource" has no attribute "id"  [attr-defined]
   r.id = 5  # "Resource" has no attribute "id"  [attr-defined]

Check that attribute exists in each union item [union-attr]
-----------------------------------------------------------

If you access the attribute of a value with a union type, mypy checks
that the attribute is defined for every union item. Otherwise the
operation can fail at runtime.

Example:

.. code-block:: python

   from typing import Union

   class Cat:
       def sleep(self) -> None: ...
       def miaow(self) -> None: ...

   class Dog:
       def sleep(self) -> None: ...
       def follow_me(self) -> None: ...

   def f(animal: Union[Cat, Dog]) -> None:
       # OK: 'sleep' is defined for both Cat and Dog
       animal.sleep()
       # Error: Item "Cat" of "Union[Cat, Dog]" has no attribute "follow_me"  [union-attr]
       animal.follow_me()

Check that name is defined [name-defined]
-----------------------------------------

Mypy expects that all name references contain a definitinon, such as
an assignment, function definition or an import. This can catch missing
definitions, missing imports, and typos.

Example:

.. code-block:: python

    x = func(1)  # Name 'func' is not defined  [name-defined]

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
    greet('hi', 'jack')  # Too many arguments for "greet"  [call-arg]

Check argument types [arg-type]
-------------------------------

Mypy checks that argument types in a call match the declared argument
types in the signature.

Example:

.. code-block:: python

   from typing import List, Optional

   def first(x: List[int]) -> Optional[int]:
        return x[0] if x else 0

   t = (5, 4)
   # Argument 1 to "first" has incompatible type "Tuple[int, int]";
   # expected "List[int]"  [arg-type]
   print(first(t))

Check calls to overloaded functions [call-overload]
---------------------------------------------------

When you call an overloaded function, mypy checks that at least one of
the signatures of the overload items match the argument types in the
call.

Check validity of types [valid-type]
------------------------------------

Mypy checks that each type annotation and any expression that
represents a type is a valid type. Examples of valid types include
classes, union types, callable types, type aliases, and literal types.
Examples of invalid types include bare integer literals, functions,
variables, and undefined names.

Require annotation if variable type is unclear [var-annotated]
--------------------------------------------------------------

In some cases mypy can't infer the type of a variable without an
explicit annotation. Mypy treats this as an error. This often happens
when you initialize a variable with an empty collection, and mypy
can't infer the collection item type. Mypy replaces any parts of the
type it couldn't infer with ``Any``.

Example with an error:

.. code-block:: python

   class Bundle:
       def __init__(self) -> None:
           # Error: Need type annotation for 'items'
           # (hint: "items: List[<type>] = ...")  [var-annotated]
           self.items = []

   reveal_type(Bundle().items)  # list[Any]

In this example we have an explicit annotation to silence the error:

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
to the return type in the base class.

Argument typess can be more general is a subclass (i.e., they can vary
contravariantly).  Return type can be narrowed in a subclass (i.e., it
can vary covariantly).  It's okay to define additional arguments in
a subclass method, as long all extra arguments can be left out.

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
       # Argument 1 of "method" is incompatible with "Base"  [override]
       def method(self,
                  arg: bool) -> int:
           ...

Check that function returns a value [return]
--------------------------------------------

TODO


Check that return value is compatible [return-value]
----------------------------------------------------

TODO

Check compatibility of assignment statement [assignment]
--------------------------------------------------------

TODO

Check that type arguments exist [type-arg]
------------------------------------------

TODO

Check type variable values [type-var]
-------------------------------------

TODO

Check indexing operations [index]
---------------------------------

TODO

Check uses of various operators [operator]
------------------------------------------

TODO

Check list items [list-item]
----------------------------

TODO

Check dict items [dict-item]
----------------------------

TODO

Check TypedDict items [typeddict-item]
--------------------------------------

TODO

Check that type of target is known [has-type]
---------------------------------------------

TODO

Check that import target can be found [import]
----------------------------------------------

TODO

Check that each name is defined once [no-redef]
-----------------------------------------------

TODO

Check that called functions return a value [func-returns-value]
---------------------------------------------------------------

Mypy reports an error if you call a function with a ``None``
return type and don't ignore the return value, as this is
usually (but not always) a programming error. For example,
the ``if f()`` check is always false since ``f`` returns
``None``:

.. code-block:: python

   def f() -> None:
       ...

   # "f" does not return a value  [func-returns-value]
   if f():
        print("not false")

Check instantiation of abstract classes [abstract]
--------------------------------------------------

Mypy generates an error if you try to instantiate an abstract base
class (ABC). An abtract base class is a class with at least once
abstract method or attribute. (See also `Python
abc module documentation <https://docs.python.org/3/library/abc.html>`_.)

Sometimes a class is accidentally abstract, due to an
unimplemented abstract method, for example. In a case like this you
need to provide an implementation for the method to make the class
concrete (non-abstract).

Example:

.. code-block:: python

    from abc import ABCMeta, abstractmethod

    class Persistable(metaclass=ABCMeta):
        @abstractmethod
        def save(self) -> None: ...

    class Thing(Persistable):
        def __init__(self) -> None:
            ...

        ...  # No "save" method

    # Cannot instantiate abstract class 'Thing' with abstract attribute 'save'  [abstract]
    t = Thing()

Check the target of NewType [valid-newtype]
-------------------------------------------

The target of a ``NewType`` definition must be a class type. It can't
be a union type, ``Any``, or various other special types.

You can also get this error also if the target has been imported from
a module mypy can't find the source for, since any such definitions
are treated by mypy as values with ``Any`` types.

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
is not special in other ways. For example, you can ignore all errors
in this category by using ``# type: ignore[misc]`` comment. Since these
errors are not expected to be common, it's unlikely that you'll see
two *different* errors with the ``misc`` code on a single line -- though this
can certainly happen once in a while.

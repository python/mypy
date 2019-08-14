List of error codes
===================

This section documents various errors codes that mypy can generate.
See :ref:`error-codes` for general documentation about error codes.


Checking that attribute exists [attr-defined]
---------------------------------------------

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


Checking that name is defined [name-defined]
--------------------------------------------

Mypy expects that all name references contain a definitinon, such as
an assignment, function definition or an import. This can catch missing
definitions, missing imports, and typos.

Example:

.. code-block:: python

    x = func(1)  # Name 'func' is not defined  [name-defined]

Checking arguments in calls [call-arg]
--------------------------------------

Mypy expects that the number and names of arguments match the called function.
Note that argument type checks have a separate error code ``arg-type``.

Example:

.. code-block:: python

    from typing import Sequence

    def greet(name: str) -> None:
         print('hello', name)

    greet('jack')  # OK
    greet('hi', 'jack')  # Too many arguments for "greet"  [call-arg]

Checking argument types [arg-type]
----------------------------------

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


Checking validity of overrides [override]
-----------------------------------------

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

Miscellaneous checks [misc]
---------------------------

Mypy performs numerous other, more rarely failing checks that don't
have a specific error codes. These use the ``misc`` error code. This
error code is not special. For example, you can ignore all errors in
this category by using ``# type: ignore[misc]`` comment.

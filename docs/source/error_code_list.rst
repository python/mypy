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

TODO

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

TODO

Check validity of type annotations [valid-type]
-----------------------------------------------

TODO

Require annotation if variable type is unclear [var-annotated]
--------------------------------------------------------------

TODO

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

TODO

Check instantiation of abstract classes [abstract]
--------------------------------------------------

TODO

Check the target of NewType [valid-newtype]
-------------------------------------------

TODO

Report syntax errors [syntax]
-----------------------------

TODO

Miscellaneous checks [misc]
---------------------------

Mypy performs numerous other, more rarely failing checks that don't
have a specific error codes. These use the ``misc`` error code. This
error code is not special. For example, you can ignore all errors in
this category by using ``# type: ignore[misc]`` comment.

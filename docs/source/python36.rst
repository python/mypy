.. _python-36:

New features in Python 3.6
==========================

Mypy has supported all language features new in Python 3.6 starting with mypy
0.510. This section introduces Python 3.6 features that interact with
type checking.

Syntax for variable annotations (:pep:`526`)
--------------------------------------------

Python 3.6 introduced a new syntax for variable annotations (in
global, class and local scopes).  There are two variants of the
syntax, with or without an initializer expression:

.. code-block:: python

   from typing import Optional
   foo: Optional[int]  # No initializer
   bar: List[str] = []  # Initializer

.. _class-var:

You can also mark names intended to be used as class variables with
:py:data:`~typing.ClassVar`. In a pinch you can also use :py:data:`~typing.ClassVar` in ``# type``
comments.  Example:

.. code-block:: python

   from typing import ClassVar

   class C:
       x: int  # Instance variable
       y: ClassVar[int]  # Class variable
       z = None  # type: ClassVar[int]

       def foo(self) -> None:
           self.x = 0  # OK
           self.y = 0  # Error: Cannot assign to class variable "y" via instance

   C.y = 0  # This is OK


.. _async_generators_and_comprehensions:

Asynchronous generators (:pep:`525`) and comprehensions (:pep:`530`)
--------------------------------------------------------------------

Python 3.6 allows coroutines defined with ``async def`` (:pep:`492`) to be
generators, i.e. contain ``yield`` expressions. It also introduced a syntax for
asynchronous comprehensions. This example uses the :py:class:`~typing.AsyncIterator` type to
define an async generator:

.. code-block:: python

   from typing import AsyncIterator

   async def gen() -> AsyncIterator[bytes]:
       lst = [b async for b in gen()]  # Inferred type is "List[bytes]"
       yield 'no way'  # Error: Incompatible types (got "str", expected "bytes")

New named tuple syntax
----------------------

Python 3.6 supports an alternative, class-based syntax for named tuples.
See :ref:`named-tuples` for the details.

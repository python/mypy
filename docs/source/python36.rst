.. _python-36:

New features in Python 3.6
==========================

Python 3.6 was `released
<https://www.python.org/downloads/release/python-360/>`_ in
December 2016.  As of mypy 0.510 all language features new in Python
3.6 are supported.

Syntax for variable annotations (`PEP 526 <https://www.python.org/dev/peps/pep-0526>`_)
---------------------------------------------------------------------------------------

Python 3.6 feature: variables (in global, class or local scope) can
now have type annotations using either of the two forms:

.. code-block:: python

   from typing import Optional
   foo: Optional[int]
   bar: List[str] = []

Mypy fully supports this syntax, interpreting them as equivalent to

.. code-block:: python

   foo = None  # type: Optional[int]
   bar = []  # type: List[str]

.. _class-var:

An additional feature defined in PEP 526 is also supported: you can
mark names intended to be used as class variables with ``ClassVar``.
In a pinch you can also use ClassVar in ``# type`` comments.
Example:

.. code-block:: python

   from typing import ClassVar

   class C:
       x: int  # instance variable
       y: ClassVar[int]  # class variable
       z = None  # type: ClassVar[int]

       def foo(self) -> None:
           self.x = 0  # OK
           self.y = 0  # Error: Cannot assign to class variable "y" via instance

   C.y = 0  # This is OK


Literal string formatting (`PEP 498 <https://www.python.org/dev/peps/pep-0498>`_)
---------------------------------------------------------------------------------

Python 3.6 feature: string literals of the form
``f"text {expression} text"`` evaluate ``expression`` using the
current evaluation context (locals and globals).

Mypy fully supports this syntax and type-checks the ``expression``.

Underscores in numeric literals (`PEP 515 <https://www.python.org/dev/peps/pep-0515>`_)
---------------------------------------------------------------------------------------

Python 3.6 feature: numeric literals can contain underscores,
e.g. ``1_000_000``.

Mypy fully supports this syntax:

.. code-block:: python

   precise_val = 1_000_000.000_000_1
   hexes: List[int] = []
   hexes.append(0x_FF_FF_FF_FF)

.. _async_generators_and_comprehensions:

Asynchronous generators (`PEP 525 <https://www.python.org/dev/peps/pep-0525>`_) and comprehensions (`PEP 530 <https://www.python.org/dev/peps/pep-0530>`_)
----------------------------------------------------------------------------------------------------------------------------------------------------------

Python 3.6 allows coroutines defined with ``async def`` (PEP 492) to be
generators, i.e. contain ``yield`` expressions, and introduces a syntax for
asynchronous comprehensions. Mypy fully supports these features, for example:

.. code-block:: python

   from typing import AsyncIterator

   async def gen() -> AsyncIterator[bytes]:
       lst = [b async for b in gen()]  # Inferred type is "List[bytes]"
       yield 'no way'  # Error: Incompatible types (got "str", expected "bytes")

New named tuple syntax
----------------------

Python 3.6 supports an alternative syntax for named tuples. See :ref:`named-tuples`.

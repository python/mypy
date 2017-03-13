.. _python-36:

New features in Python 3.6
==========================

Python 3.6 was `released
<https://www.python.org/downloads/release/python-360/>`_ in
December 2016.  As of mypy 0.500 most language features new in Python
3.6 are supported, with the exception of asynchronous generators and
comprehensions.

Syntax for variable annotations (`PEP 526 <https://www.python.org/dev/peps/pep-0526>`_)
---------------------------------------------------------------------------------------

Python 3.6 feature: variables (in global, class or local scope) can
now have type annotations using either of the two forms:

.. code-block:: python

   foo: Optional[int]
   bar: List[str] = []

Mypy fully supports this syntax, interpreting them as equivalent to

.. code-block:: python

   foo = None  # type: Optional[int]
   bar = []  # type: List[str]

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

Asynchronous generators (`PEP 525 <https://www.python.org/dev/peps/pep-0525>`_)
-------------------------------------------------------------------------------

Python 3.6 feature: coroutines defined with ``async def`` (PEP 492)
can now also be generators, i.e. contain ``yield`` expressions.

Mypy does not yet support this.

Asynchronous comprehensions (`PEP 530 <https://www.python.org/dev/peps/pep-0530>`_)
-----------------------------------------------------------------------------------

Python 3.6 feature: coroutines defined with ``async def`` (PEP 492)
can now also contain list, set and dict comprehensions that use
``async for`` syntax.

Mypy does not yet support this.

New named tuple syntax
----------------------

Python 3.6 supports an alternative syntax for named tuples. See :ref:`named-tuples`.

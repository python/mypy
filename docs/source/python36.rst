.. _python-36:

New features in Python 3.6
==========================

Python 3.6 will be `released
<https://www.python.org/dev/peps/pep-0494>`_ in December 2016.  The
`first beta <https://www.python.org/downloads/release/python-360b1/>`_
came out in September and adds some exciting features.  Here's the
support matrix for these in mypy (to be updated with each new mypy
release).  The intention is to support all of these by the time Python
3.6 is released.

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

Mypy does not yet support this.

Underscores in numeric literals (`PEP 515 <https://www.python.org/dev/peps/pep-0515>`_)
---------------------------------------------------------------------------------------

Python 3.6 feature: numeric literals can contain underscores,
e.g. ``1_000_000``.

Mypy does not yet support this.

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

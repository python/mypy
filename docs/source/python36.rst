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

.. note::

   Mypy only understands Python 3.6 syntax if you use the ``--fast-parser`` flag.
   This requires that the `typed_ast <https://pypi.python.org/pypi/typed-ast>`_ package is
   installed and has at least version 0.6.1.  Use ``pip3 install -U typed_ast``.
   If running mypy on an earlier Python version, you also need to enable 3.6 support
   through ``--python-version 3.6``.

   Example command line (or use :ref:`config-file`):

     .. code-block:: text

        $ pip3 install -U typed_ast
        $ mypy --fast-parser --python-version 3.6 program.py

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

.. note::

   See above for how to enable Python 3.6 syntax.

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

Mypy fully supports this syntax:

.. code-block:: python

   precise_val = 1_000_000.000_000_1
   hexes: List[int] = []
   hexes.append(0x_FF_FF_FF_FF)

.. note::

   This requires the ``--fast-parser`` flag and it requires that the
   `typed_ast <https://pypi.python.org/pypi/typed-ast>`_ package is
   installed and has at least version 0.6.2.  Use ``pip3 install -U typed_ast``.

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

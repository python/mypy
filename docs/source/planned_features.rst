Planned features
================

This section introduces some language features that are still work in
progress.

Type checking of None
---------------------

Currently, ``None`` is a valid value for each type, similar to
``null`` or ``NULL`` in many languages. However, it is likely that
this decision will be reversed, and types would not include ``None``
by default. The ``Optional`` type modifier would be used to define
a type variant that includes ``None``, such as ``Optional[int]``:

.. code-block:: python

   def f() -> Optional[int]:
       return None # OK

   def g() -> int:
       ...
       return None # Error: None not compatible with int

Also, most operations would not be supported on ``None`` values:

.. code-block:: python

   def f(x: Optional[int]) -> int:
       return x + 1  # Error: Cannot add None and int

Instead, an explicit ``None`` check would be required. This would
benefit from more powerful type inference:

.. code-block:: python

   def f(x: Optional[int]) -> int:
       if x is None:
           return 0
       else:
           # The inferred type of x is just int here.
           return x + 1

We would infer the type of ``x`` to be ``int`` in the else block due to the
check against ``None`` in the if condition.

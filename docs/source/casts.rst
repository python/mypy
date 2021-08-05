.. _casts:

Casts and type assertions
=========================

Mypy supports type casts that are usually used to coerce a statically
typed value to a subtype. Unlike languages such as Java or C#,
however, mypy casts are only used as hints for the type checker, and they
don't perform a runtime type check. Use the function :py:func:`~typing.cast` to perform a
cast:

.. code-block:: python

   from typing import cast, List

   o: object = [1]
   x = cast(List[int], o)  # OK
   y = cast(List[str], o)  # OK (cast performs no actual runtime check)

To support runtime checking of casts such as the above, we'd have to check
the types of all list items, which would be very inefficient for large lists.
Casts are used to silence spurious
type checker warnings and give the type checker a little help when it can't
quite understand what is going on.

.. note::

   You can use an assertion if you want to perform an actual runtime check:

   .. code-block:: python

      def foo(o: object) -> None:
          print(o + 5)  # Error: can't add 'object' and 'int'
          assert isinstance(o, int)
          print(o + 5)  # OK: type of 'o' is 'int' here

You don't need a cast for expressions with type ``Any``, or when
assigning to a variable with type ``Any``, as was explained earlier.
You can also use ``Any`` as the cast target type -- this lets you perform
any operations on the result. For example:

.. code-block:: python

    from typing import cast, Any

    x = 1
    x.whatever()  # Type check error
    y = cast(Any, x)
    y.whatever()  # Type check OK (runtime error)

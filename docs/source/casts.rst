.. _casts:

Casts
=====

Mypy supports type casts that are usually used to coerce a statically
typed value to a subtype. Unlike languages such as Java or C#,
however, mypy casts are only used as hints for the type checker, and they
don't perform a runtime type check. Use the function ``cast`` to perform a
cast:

.. code-block:: python

   from typing import cast, List

   o = [1] # type: object
   x = cast(List[int], o)  # OK
   y = cast(List[str], o)  # OK (cast performs no actual runtime check)

To support runtime checking of casts such as the above, we'd have to check
the types of all list items, which would be very inefficient for large lists.
Use assertions if you want to
perform an actual runtime check. Casts are used to silence spurious
type checker warnings and give the type checker a little help when it can't
quite understand what is going on.

You don't need a cast for expressions with type ``Any``, or when
assigning to a variable with type ``Any``, as was explained earlier.
You can also use ``Any`` as the cast target type -- this lets you perform
any operations on the result. For example:

.. code-block:: python

    from typing import cast, Any

    x = 1
    x + 'x'   # Type check error
    y = cast(Any, x)
    y + 'x'   # Type check OK (runtime error)

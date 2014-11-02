.. _casts:

Casts
=====

Mypy supports type casts that are usually used to coerce a statically
typed value to a subtype. Unlike languages such as Java or C#,
however, mypy casts are only used as hints for the type checker when
using Python semantics, and they have no runtime effect. Use the
function ``cast`` to perform a cast:

.. code-block:: python

   from typing import cast

   o = [1] # type: object
   x = cast(List[int], o)  # OK
   y = cast(List[str], o)  # OK (cast performs no actual runtime check)

Supporting runtime checking of casts such as the above when using
Python semantics would require emulating reified generics and this
would be difficult to do and would likely degrade performance and make
code more difficult to read. You should not rely in your programs on
casts being checked at runtime. Use an assertion if you want to
perform an actual runtime check. Casts are used to silence spurious
type checker warnings.

You don't need a cast for expressions with type ``Any``, of when
assigning to a variable with type ``Any``, as was explained earlier.

Any() as a cast
***************

You can cast to a dynamically typed value by just calling ``Any``;
this is equivalent to ``cast(Any, ...)`` but shorter:

.. code-block:: python

   from typing import Any

   def f(x: object) -> None:
       Any(x).foo()   # OK

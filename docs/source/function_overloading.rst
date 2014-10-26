Function overloading
====================

You can define multiple instances of a function with the same name but
different signatures. The first matching signature is selected at
runtime when evaluating each individual call. This enables also a form
of multiple dispatch.

.. code-block:: python

   from typing import overload

   @overload
   def abs(n: int) -> int:
       return n if n >= 0 else -n

   @overload
   def abs(n: float) -> float:
       return n if n >= 0.0 else -n

   abs(-2)     # 2 (int)
   abs(-1.5)   # 1.5 (float)

Overloaded function variants still define a single runtime object; the
following code is valid:

.. code-block:: python

   my_abs = abs
   my_abs(-2)      # 2 (int)
   my_abs(-1.5)    # 1.5 (float)

The overload variants must be adjacent in the code. This makes code
clearer, and otherwise there would be awkward corner cases such as
partially defined overloaded functions that could surprise the unwary
programmer.

.. note::

   As generic type variables are erased at runtime, an overloaded
   function cannot dispatch based on a generic type argument,
   e.g. List[int] versus List[str].

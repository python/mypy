Function overloading in stubs
=============================

Sometimes you have a library function that seems to call for two or
more signatures.  That's okay -- you can define multiple *overloaded*
instances of a function with the same name but different signatures in
a stub file (this feature is not supported for user code, at least not
yet) using the ``@overload`` decorator. For example, we can define an
``abs`` function that works for both ``int`` and ``float`` arguments:

.. code-block:: python

   # This is a stub file!

   from typing import overload

   @overload
   def abs(n: int) -> int: pass

   @overload
   def abs(n: float) -> float: pass

Note that we can't use ``Union[int, float]`` as the argument type,
since this wouldn't allow us to express that the return
type depends on the argument type.

Now if we import ``abs`` as defined in the above library stub, we can
write code like this, and the types are inferred correctly:

.. code-block:: python

   n = abs(-2)     # 2 (int)
   f = abs(-1.5)   # 1.5 (float)

Overloaded function variants are still ordinary Python functions and
they still define a single runtime object. The following code is
thus valid:

.. code-block:: python

   my_abs = abs
   my_abs(-2)      # 2 (int)
   my_abs(-1.5)    # 1.5 (float)

The overload variants must be adjacent in the code. This makes code
clearer, as you don't have to hunt for overload variants across the
file.

.. note::

   As generic type variables are erased at runtime when constructing
   instances of generic types, an overloaded function cannot have
   variants that only differ in a generic type argument,
   e.g. ``List[int]`` versus ``List[str]``.

.. note::

   If you are writing a regular module rather than a stub, you can
   often use a type variable with a value restriction to represent
   functions as ``abs`` above (see :ref:`type-variable-value-restriction`).

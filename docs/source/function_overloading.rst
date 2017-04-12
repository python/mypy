Function Overloading
====================

Sometimes the types in a function depend on each other in ways that
can't be captured with a simple ``Union``.  For example, the
``__getitem__`` (``[]`` bracket indexing) method can take an integer
and return a single item, or take a ``slice`` and return a
``Sequence`` of items.  You might be tempted to annotate it like so:

.. code-block:: python

    class MyList(Sequence[T]):
        def __getitem__(self, index: Union[int, slice]) -> Union[T, Sequence[T]]:
            if isinstance(index, int):
                ...  # Return a T here
            elif isinstance(index, slice):
                ...  # Return a sequence of Ts here
            else:
                assert False, "Unsupported argument %r" % (index,)
    
But this is a little loose, as it implies that when you put in an
``int`` you might sometimes get out a single item or sometimes a
sequence.  To capture a constraint such as a return type that depends
on a parameter type, we can use `overloading
<https://www.python.org/dev/peps/pep-0484/#function-method-overloading>`_
to give the same function multiple type annotations (signatures).

.. code-block:: python

    from typing import Generic, Sequence, overload
    T = TypeVar('T')

    class MyList(Sequence[T]):

        # The @overload definitions are just for the type checker,
        # and overwritten by the real implementation below.
        @overload
        def __getitem__(self, index: int) -> T:
            pass  # Don't put code here

        # All overloads and the implementation must be adjacent
        # in the source file, and overload order may matter.
        @overload
        def __getitem__(self, index: slice) -> Sequence[T]:
            pass  # Don't put code here

        # Actual implementation goes last, without @overload.
        # It may or may not have type hints; if it does,
        # these are checked against the overload definitions
        # as well as against the implementation body.
        def __getitem__(self, index):
            # This is exactly the same as before.
            if isinstance(index, int):
                ...  # Return a T here
            elif isinstance(index, slice):
                ...  # Return a sequence of Ts here
            else:
                assert False, "Unsupported argument %r" % (index,)

Overloaded function variants are still ordinary Python functions and
they still define a single runtime object. There is no multiple
dispatch happening, and you must manually handle the different types
(usually with :func:`isinstance` checks, as shown in the example).

The overload variants must be adjacent in the code. This makes code
clearer, as you don't have to hunt for overload variants across the
file.

Overloads in stub files are exactly the same, except there is no
implementation.

.. note::

   As generic type variables are erased at runtime when constructing
   instances of generic types, an overloaded function cannot have
   variants that only differ in a generic type argument,
   e.g. ``List[int]`` and ``List[str]``.

.. note::

   If you just need to constrain a type variable to certain types or
   subtypes, you can use a :ref:`value restriction
   <type-variable-value-restriction>`.

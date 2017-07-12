.. _function-overloading:

Function Overloading
====================

Sometimes the types in a function depend on each other in ways that
can't be captured with a ``Union``.  For example, the ``__getitem__``
(``[]`` bracket indexing) method can take an integer and return a
single item, or take a ``slice`` and return a ``Sequence`` of items.
You might be tempted to annotate it like so:

.. code-block:: python

    from typing import Sequence, TypeVar, Union
    T = TypeVar('T')

    class MyList(Sequence[T]):
        def __getitem__(self, index: Union[int, slice]) -> Union[T, Sequence[T]]:
            if isinstance(index, int):
                ...  # Return a T here
            elif isinstance(index, slice):
                ...  # Return a sequence of Ts here
            else:
                raise TypeError(...)

But this is too loose, as it implies that when you pass in an ``int``
you might sometimes get out a single item and sometimes a sequence.
The return type depends on the parameter type in a way that can't be
expressed using a type variable.  Instead, we can use `overloading
<https://www.python.org/dev/peps/pep-0484/#function-method-overloading>`_
to give the same function multiple type annotations (signatures) and
accurately describe the function's behavior.

.. code-block:: python

    from typing import overload, Sequence, TypeVar, Union
    T = TypeVar('T')

    class MyList(Sequence[T]):

        # The @overload definitions are just for the type checker,
        # and overwritten by the real implementation below.
        @overload
        def __getitem__(self, index: int) -> T:
            pass  # Don't put code here

        # All overloads and the implementation must be adjacent
        # in the source file, and overload order may matter:
        # when two overloads may overlap, the more specific one
        # should come first.
        @overload
        def __getitem__(self, index: slice) -> Sequence[T]:
            pass  # Don't put code here

        # The implementation goes last, without @overload.
        # It may or may not have type hints; if it does,
        # these are checked against the overload definitions
        # as well as against the implementation body.
        def __getitem__(self, index: Union[int, slice]) -> Union[T, Sequence[T]]:
            # This is exactly the same as before.
            if isinstance(index, int):
                ...  # Return a T here
            elif isinstance(index, slice):
                ...  # Return a sequence of Ts here
            else:
                raise TypeError(...)

Calls to overloaded functions are type checked against the variants,
not against the implementation. A call like ``my_list[5]`` would have
type ``T``, not ``Union[T, Sequence[T]]`` because it matches the
first overloaded definition, and ignores the type annotations on the
implementation of ``__getitem__``. The code in the body of the
definition of ``__getitem__`` is checked against the annotations on
the the corresponding declaration. In this case the body is checked
with ``index: Union[int, slice]`` and a return type
``Union[T, Sequence[T]]``. If there are no annotations on the
corresponding definition, then code in the function body is not type
checked.

The annotations on the function body must be compatible with the
types given for the overloaded variants listed above it. The type
checker will verify that all the types listed the overloaded variants
are compatible with the types given for the implementation. In this
case it checks that the parameter type ``int`` and the return type
``T`` are compatible with ``Union[int, slice]`` and
``Union[T, Sequence[T]]`` for the first variant. For the second
variant it verifies that the parameter type ``slice`` are the return
type ``Sequence[T]`` are compatible with ``Union[int, slice]`` and
``Union[T, Sequence[T]]``.

Overloaded function variants are still ordinary Python functions and
they still define a single runtime object. There is no automatic
dispatch happening, and you must manually handle the different types
in the implementation (usually with :func:`isinstance` checks, as
shown in the example).

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

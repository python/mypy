.. _error-codes-optional:

Error codes for optional checks
===============================

This section documents various errors codes that mypy generates only
if you enable certain options. See :ref:`error-codes` for general
documentation about error codes. :ref:`error-code-list` documents
error codes that are enabled by default.

.. note::

   The examples in this section use :ref:`inline configuration
   <inline-config>` to specify mypy options. You can also set the same
   options by using a :ref:`configuration file <config-file>` or
   :ref:`command-line options <command-line>`.

Check that type arguments exist [type-arg]
------------------------------------------

If you use :option:`--disallow-any-generics <mypy --disallow-any-generics>`, mypy requires that each generic
type has values for each type argument. For example, the types ``List`` or
``dict`` would be rejected. You should instead use types like ``List[int]`` or
``Dict[str, int]``. Any omitted generic type arguments get implicit ``Any``
values. The type ``List`` is equivalent to ``List[Any]``, and so on.

Example:

.. code-block:: python

    # mypy: disallow-any-generics

    from typing import List

    # Error: Missing type parameters for generic type "List"  [type-arg]
    def remove_dups(items: List) -> List:
        ...

Check that every function has an annotation [no-untyped-def]
------------------------------------------------------------

If you use :option:`--disallow-untyped-defs <mypy --disallow-untyped-defs>`, mypy requires that all functions
have annotations (either a Python 3 annotation or a type comment).

Example:

.. code-block:: python

    # mypy: disallow-untyped-defs

    def inc(x):  # Error: Function is missing a type annotation  [no-untyped-def]
        return x + 1

    def inc_ok(x: int) -> int:  # OK
        return x + 1

    class Counter:
         # Error: Function is missing a type annotation  [no-untyped-def]
         def __init__(self):
             self.value = 0

    class CounterOk:
         # OK: An explicit "-> None" is needed if "__init__" takes no arguments
         def __init__(self) -> None:
             self.value = 0

Check that cast is not redundant [redundant-cast]
-------------------------------------------------

If you use :option:`--warn-redundant-casts <mypy --warn-redundant-casts>`, mypy will generate an error if the source
type of a cast is the same as the target type.

Example:

.. code-block:: python

    # mypy: warn-redundant-casts

    from typing import cast

    Count = int

    def example(x: Count) -> int:
        # Error: Redundant cast to "int"  [redundant-cast]
        return cast(int, x)

Check that comparisons are overlapping [comparison-overlap]
-----------------------------------------------------------

If you use :option:`--strict-equality <mypy --strict-equality>`, mypy will generate an error if it
thinks that a comparison operation is always true or false. These are
often bugs. Sometimes mypy is too picky and the comparison can
actually be useful. Instead of disabling strict equality checking
everywhere, you can use ``# type: ignore[comparison-overlap]`` to
ignore the issue on a particular line only.

Example:

.. code-block:: python

    # mypy: strict-equality

    def is_magic(x: bytes) -> bool:
        # Error: Non-overlapping equality check (left operand type: "bytes",
        #        right operand type: "str")  [comparison-overlap]
        return x == 'magic'

We can fix the error by changing the string literal to a bytes
literal:

.. code-block:: python

    # mypy: strict-equality

    def is_magic(x: bytes) -> bool:
        return x == b'magic'  # OK

Check that no untyped functions are called [no-untyped-call]
------------------------------------------------------------

If you use :option:`--disallow-untyped-calls <mypy --disallow-untyped-calls>`, mypy generates an error when you
call an unannotated function in an annotated function.

Example:

.. code-block:: python

    # mypy: disallow-untyped-calls

    def do_it() -> None:
        # Error: Call to untyped function "bad" in typed context  [no-untyped-call]
        bad()

    def bad():
        ...


Check that function does not return Any value [no-any-return]
-------------------------------------------------------------

If you use :option:`--warn-return-any <mypy --warn-return-any>`, mypy generates an error if you return a
value with an ``Any`` type in a function that is annotated to return a
non-``Any`` value.

Example:

.. code-block:: python

    # mypy: warn-return-any

    def fields(s):
         return s.split(',')

    def first_field(x: str) -> str:
        # Error: Returning Any from function declared to return "str"  [no-any-return]
        return fields(x)[0]

Check that types have no Any components due to missing imports [no-any-unimported]
----------------------------------------------------------------------------------

If you use :option:`--disallow-any-unimported <mypy --disallow-any-unimported>`, mypy generates an error if a component of
a type becomes ``Any`` because mypy couldn't resolve an import. These "stealth"
``Any`` types can be surprising and accidentally cause imprecise type checking.

In this example, we assume that mypy can't find the module ``animals``, which means
that ``Cat`` falls back to ``Any`` in a type annotation:

.. code-block:: python

    # mypy: disallow-any-unimported

    from animals import Cat  # type: ignore

    # Error: Argument 1 to "feed" becomes "Any" due to an unfollowed import  [no-any-unimported]
    def feed(cat: Cat) -> None:
        ...

Check that statement or expression is unreachable [unreachable]
---------------------------------------------------------------

If you use :option:`--warn-unreachable <mypy --warn-unreachable>`, mypy generates an error if it
thinks that a statement or expression will never be executed. In most cases, this is due to
incorrect control flow or conditional checks that are accidentally always true or false.

.. code-block:: python

    # mypy: warn-unreachable

    def example(x: int) -> None:
        # Error: Right operand of 'or' is never evaluated  [unreachable]
        assert isinstance(x, int) or x == 'unused'

        return
        # Error: Statement is unreachable  [unreachable]
        print('unreachable')

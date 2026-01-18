.. _type-inference-and-annotations:

Type inference and type annotations
===================================

Type inference
**************

For most variables, if you do not explicitly specify its type, mypy will
infer the correct type based on what is initially assigned to the variable.

.. code-block:: python

    # Mypy will infer the type of these variables, despite no annotations
    i = 1
    reveal_type(i)  # Revealed type is "builtins.int"
    l = [1, 2]
    reveal_type(l)  # Revealed type is "builtins.list[builtins.int]"


.. note::

    Note that mypy will not use type inference in dynamically typed functions
    (those without a function type annotation) — every local variable type
    defaults to ``Any`` in such functions. For more details, see :ref:`dynamic-typing`.

    .. code-block:: python

        def untyped_function():
            i = 1
            reveal_type(i) # Revealed type is "Any"
                           # 'reveal_type' always outputs 'Any' in unchecked functions

.. _explicit-var-types:

Explicit types for variables
****************************

You can override the inferred type of a variable by using a
variable type annotation:

.. code-block:: python

   x: int | str = 1

Without the type annotation, the type of ``x`` would be just ``int``. We
use an annotation to give it a more general type ``int | str`` (this
type means that the value can be either an ``int`` or a ``str``).

The best way to think about this is that the type annotation sets the type of
the variable, not the type of the expression. For instance, mypy will complain
about the following code:

.. code-block:: python

   x: int | str = 1.1  # error: Incompatible types in assignment
                       # (expression has type "float", variable has type "int | str")

.. note::

   To explicitly override the type of an expression you can use
   :py:func:`cast(\<type\>, \<expression\>) <typing.cast>`.
   See :ref:`casts` for details.

Note that you can explicitly declare the type of a variable without
giving it an initial value:

.. code-block:: python

   # We only unpack two values, so there's no right-hand side value
   # for mypy to infer the type of "cs" from:
   a, b, *cs = 1, 2  # error: Need type annotation for "cs"

   rs: list[int]  # no assignment!
   p, q, *rs = 1, 2  # OK

Explicit types for collections
******************************

The type checker cannot always infer the type of a list or a
dictionary. This often arises when creating an empty list or
dictionary and assigning it to a new variable that doesn't have an explicit
variable type. Here is an example where mypy can't infer the type
without some help:

.. code-block:: python

   l = []  # Error: Need type annotation for "l"

In these cases you can give the type explicitly using a type annotation:

.. code-block:: python

   l: list[int] = []       # Create empty list of int
   d: dict[str, int] = {}  # Create empty dictionary (str -> int)

.. note::

   Using type arguments (e.g. ``list[int]``) on builtin collections like
   :py:class:`list`,  :py:class:`dict`, :py:class:`tuple`, and  :py:class:`set`
   only works in Python 3.9 and later. For Python 3.8 and earlier, you must use
   :py:class:`~typing.List` (e.g. ``List[int]``), :py:class:`~typing.Dict`, and
   so on.


Compatibility of container types
********************************

A quick note: container types can sometimes be unintuitive. We'll discuss this
more in :ref:`variance`. For example, the following program generates a mypy error,
because mypy treats ``list[int]`` as incompatible with ``list[object]``:

.. code-block:: python

   def f(l: list[object], k: list[int]) -> None:
       l = k  # error: Incompatible types in assignment

The reason why the above assignment is disallowed is that allowing the
assignment could result in non-int values stored in a list of ``int``:

.. code-block:: python

   def f(l: list[object], k: list[int]) -> None:
       l = k
       l.append('x')
       print(k[-1])  # Ouch; a string in list[int]

Other container types like :py:class:`dict` and :py:class:`set` behave similarly.

You can still run the above program; it prints ``x``. This illustrates the fact
that static types do not affect the runtime behavior of programs. You can run
programs with type check failures, which is often very handy when performing a
large refactoring. Thus you can always 'work around' the type system, and it
doesn't really limit what you can do in your program.

Context in type inference
*************************

Type inference is *bidirectional* and takes context into account.

Mypy will take into account the type of the variable on the left-hand side
of an assignment when inferring the type of the expression on the right-hand
side. For example, the following will type check:

.. code-block:: python

   def f(l: list[object]) -> None:
       l = [1, 2]  # Infer type list[object] for [1, 2], not list[int]


The value expression ``[1, 2]`` is type checked with the additional
context that it is being assigned to a variable of type ``list[object]``.
This is used to infer the type of the *expression* as ``list[object]``.

Declared argument types are also used for type context. In this program
mypy knows that the empty list ``[]`` should have type ``list[int]`` based
on the declared type of ``arg`` in ``foo``:

.. code-block:: python

    def foo(arg: list[int]) -> None:
        print('Items:', ''.join(str(a) for a in arg))

    foo([])  # OK

However, context only works within a single statement. Here mypy requires
an annotation for the empty list, since the context would only be available
in the following statement:

.. code-block:: python

    def foo(arg: list[int]) -> None:
        print('Items:', ', '.join(arg))

    a = []  # Error: Need type annotation for "a"
    foo(a)

Working around the issue is easy by adding a type annotation:

.. code-block:: Python

    ...
    a: list[int] = []  # OK
    foo(a)

.. _silencing-type-errors:

Silencing type errors
*********************

You might want to disable type checking on specific lines, or within specific
files in your codebase. To do that, you can use a ``# type: ignore`` comment.

For example, say in its latest update, the web framework you use can now take an
integer argument to ``run()``, which starts it on localhost on that port.
Like so:

.. code-block:: python

    # Starting app on http://localhost:8000
    app.run(8000)

However, the devs forgot to update their type annotations for
``run``, so mypy still thinks ``run`` only expects ``str`` types.
This would give you the following error:

.. code-block:: text

    error: Argument 1 to "run" of "A" has incompatible type "int"; expected "str"

If you cannot directly fix the web framework yourself, you can temporarily
disable type checking on that line, by adding a ``# type: ignore``:

.. code-block:: python

    # Starting app on http://localhost:8000
    app.run(8000)  # type: ignore

This will suppress any mypy errors that would have raised on that specific line.

You should probably add some more information on the ``# type: ignore`` comment,
to explain why the ignore was added in the first place. This could be a link to
an issue on the repository responsible for the type stubs, or it could be a
short explanation of the bug. To do that, use this format:

.. code-block:: python

    # Starting app on http://localhost:8000
    app.run(8000)  # type: ignore  # `run()` in v2.0 accepts an `int`, as a port

Type ignore error codes
-----------------------

By default, mypy displays an error code for each error:

.. code-block:: text

   error: "str" has no attribute "trim"  [attr-defined]


It is possible to add a specific error-code in your ignore comment (e.g.
``# type: ignore[attr-defined]``) to clarify what's being silenced. You can
find more information about error codes :ref:`here <silence-error-codes>`.

Other ways to silence errors
----------------------------

You can get mypy to silence errors about a specific variable by dynamically
typing it with ``Any``. See :ref:`dynamic-typing` for more information.

.. code-block:: python

    from typing import Any

    def f(x: Any, y: str) -> None:
        x = 'hello'
        x += 1  # OK

You can ignore all mypy errors in a file by adding a
``# mypy: ignore-errors`` at the top of the file:

.. code-block:: python

    # mypy: ignore-errors
    # This is a test file, skipping type checking in it.
    import unittest
    ...

You can also specify per-module configuration options in your :ref:`config-file`.
For example:

.. code-block:: ini

    # Don't report errors in the 'package_to_fix_later' package
    [mypy-package_to_fix_later.*]
    ignore_errors = True

    # Disable specific error codes in the 'tests' package
    # Also don't require type annotations
    [mypy-tests.*]
    disable_error_code = var-annotated, has-type
    allow_untyped_defs = True

    # Silence import errors from the 'library_missing_types' package
    [mypy-library_missing_types.*]
    ignore_missing_imports = True

Finally, adding a ``@typing.no_type_check`` decorator to a class, method or
function causes mypy to avoid type checking that class, method or function
and to treat it as not having any type annotations.

.. code-block:: python

    @typing.no_type_check
    def foo() -> str:
       return 12345  # No error!

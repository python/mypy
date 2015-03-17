Basics
======

This chapter introduces some core concepts of mypy, including function
annotations, the ``typing`` module and library stubs. Read it carefully,
as the rest of documentation may not make much sense otherwise.

Function signatures
*******************

A function without a type signature is dynamically typed. You can
declare the signature of a function using the Python 3 annotation
syntax. This makes the function statically typed (the type checker
reports type errors within the function). A function without a
type annotation is dynamically typed, and identical to ordinary
Python:

.. code-block:: python

   def greeting(name):
       return 'Hello, {}'.format(name)

This version of the above function is statically typed (but it's still
valid Python):

.. code-block:: python

   def greeting(name: str) -> str:
       return 'Hello, {}'.format(name)

A ``None`` return type indicates a function that does not explicitly
return a value. Using a ``None`` result in a statically typed context
results in a type check error:

.. code-block:: python

   def p() -> None:
       print('hello')

   a = p()   # Type check error: p has None return value

The typing module
*****************

We cheated a bit in the above examples: a module is type checked only
if it imports the module ``typing``. Here is a complete statically typed
example from the previous section:

.. code-block:: python

   import typing

   def greeting(name: str) -> str:
       return 'Hello, {}'.format(name)

The ``typing`` module contains many definitions that are useful in
statically typed code. You can also use ``from ... import`` to import
them (we'll explain ``Iterable`` later in this document):

.. code-block:: python

   from typing import Iterable

   def greet_all(names: Iterable[str]) -> None:
       for name in names:
           print('Hello, {}'.format(name))

For brevity, we often omit the ``typing`` import in code examples, but
you should always include it in modules that contain statically typed
code.

You can still have dynamically typed functions in modules that import ``typing``:

.. code-block:: python

   import typing

   def f():
       1 + 'x'  # No static type error (dynamically typed)

   def g() -> None:
       1 + 'x'  # Type check error (statically typed)

Mixing dynamic and static typing within a single file is often
useful. For example, if you are migrating existing Python code to
static typing, it may be easiest to do this incrementally, such as by
migrating a few functions at a time. Also, when prototyping a new
feature, you may decide to first implement the relevant code using
dynamic typing and only add type signatures later, when the code is
more stable.

.. note::

   Currently the type checker checks the top levels and annotated
   functions of all modules, even those that don't import
   ``typing``. However, you should not rely on this, as this will change
   in the future.

Type checking and running programs
**********************************

You can type check a program by using the ``mypy`` tool, which is
basically a linter — it checks your program for errors without actually
running it::

   $ mypy program.py

You can always run a mypy program as a Python program, without type
checking, even if it has type errors::

   $ python3 program.py

All errors reported by mypy are essentially warnings that you are free
to ignore, if you so wish.

The `README <https://github.com/JukkaL/mypy/blob/master/README.md>`_
explains how to download and install mypy.

.. note::

   Depending on how mypy is configured, you may have to explicitly use
   the Python interpreter to run mypy. The mypy tool is an ordinary
   mypy (and so also Python) program.

.. _library-stubs:

Library stubs
*************

In order to type check code that uses library modules such as those
included in the Python standard library, you need to have library
*stubs*. A library stub defines a skeleton of the public interface
of the library, including classes, variables and functions, and
their types.

For example, consider this code:

.. code-block:: python

  x = chr(4)

Without a library stub, the type checker has no way of inferring the
type of ``x`` and checking that the argument to ``chr`` has a valid
type. Mypy comes with a library stub for Python builtins that contains
a definition like this for ``chr``:

.. code-block:: python

    def chr(code: int) -> str: pass

Mypy complains if it can't find a stub for a library module that you
import.  You can create a stub easily; here is an overview:

* Write a stub file for the library and store it as a ``.py`` file in
  a directory reserved for stubs (e.g., ``myproject/stubs``).
* Set the environment variable ``MYPYPATH`` to refer to the above directory.
  For example::

      $ export MYPYPATH=~/work/myproject/stubs

Use the normal Python file name conventions for modules, e.g. ``csv.py``
for module ``csv``, and use a subdirectory with ``__init__.py`` for packages.

That's it! Now you can access the module in mypy programs and type check
code that uses the library. If you write a stub for a library module,
consider making it available for other programmers that use mypy or
contributing it to mypy.

There is more information about creating stubs in the
`mypy wiki <http://www.mypy-lang.org/wiki/CreatingStubsForPythonModules>`_.
The following sections explain the kinds of type annotations you can use
in your programs and stub files.

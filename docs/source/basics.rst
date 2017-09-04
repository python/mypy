Basics
======

This chapter introduces some core concepts of mypy, including function
annotations, the ``typing`` module and library stubs. Read it carefully,
as the rest of documentation may not make much sense otherwise.

Function signatures
*******************

A function without a type annotation is considered dynamically typed:

.. code-block:: python

   def greeting(name):
       return 'Hello, {}'.format(name)

You can declare the signature of a function using the Python 3
annotation syntax (Python 2 is discussed later in :ref:`python2`).
This makes the function statically typed, and that causes type
checker report type errors within the function.

Here's a version of the above function that is statically typed and
will be type checked:

.. code-block:: python

   def greeting(name: str) -> str:
       return 'Hello, {}'.format(name)

If a function does not explicitly return a value we give the return
type as ``None``. Using a ``None`` result in a statically typed
context results in a type check error:

.. code-block:: python

   def p() -> None:
       print('hello')

   a = p()   # Type check error: p has None return value

Arguments with default values can be annotated as follows:

.. code-block:: python

   def greeting(name: str, prefix: str = 'Mr.') -> str:
      return 'Hello, {} {}'.format(name, prefix)

Mixing dynamic and static typing
********************************

Mixing dynamic and static typing within a single file is often
useful. For example, if you are migrating existing Python code to
static typing, it may be easiest to do this incrementally, such as by
migrating a few functions at a time. Also, when prototyping a new
feature, you may decide to first implement the relevant code using
dynamic typing and only add type signatures later, when the code is
more stable.

.. code-block:: python

   def f():
       1 + 'x'  # No static type error (dynamically typed)

   def g() -> None:
       1 + 'x'  # Type check error (statically typed)

.. note::

   The earlier stages of mypy, known as the semantic analysis, may
   report errors even for dynamically typed functions. However, you
   should not rely on this, as this may change in the future.

The typing module
*****************

The ``typing`` module contains many definitions that are useful in
statically typed code. You typically use ``from ... import`` to import
them (we'll explain ``Iterable`` later in this document):

.. code-block:: python

   from typing import Iterable

   def greet_all(names: Iterable[str]) -> None:
       for name in names:
           print('Hello, {}'.format(name))

For brevity, we often omit the ``typing`` import in code examples, but
you should always include it in modules that contain statically typed
code.

The presence or absence of the ``typing`` module does not affect
whether your code is type checked; it is only required when you use
one or more special features it defines.

Type checking programs
**********************

You can type check a program by using the ``mypy`` tool, which is
basically a linter -- it checks your program for errors without actually
running it::

   $ mypy program.py

All errors reported by mypy are essentially warnings that you are free
to ignore, if you so wish.

The next chapter explains how to download and install mypy:
:ref:`getting-started`.

More command line options are documented in :ref:`command-line`.

.. note::

   Depending on how mypy is configured, you may have to explicitly use
   the Python 3 interpreter to run mypy. The mypy tool is an ordinary
   mypy (and so also Python) program. For example::

     $ python3 -m mypy program.py

.. _library-stubs:

Library stubs and the Typeshed repo
***********************************

In order to type check code that uses library modules such as those
included in the Python standard library, you need to have library
*stubs*. A library stub defines a skeleton of the public interface
of the library, including classes, variables and functions and
their types, but dummy function bodies.

For example, consider this code:

.. code-block:: python

  x = chr(4)

Without a library stub, the type checker would have no way of
inferring the type of ``x`` and checking that the argument to ``chr``
has a valid type. Mypy incorporates the `typeshed
<https://github.com/python/typeshed>`_ project, which contains library
stubs for the Python builtins and the standard library. The stub for
the builtins contains a definition like this for ``chr``:

.. code-block:: python

    def chr(code: int) -> str: ...

In stub files we don't care about the function bodies, so we use 
an ellipsis instead.  That ``...`` is three literal dots!

Mypy complains if it can't find a stub (or a real module) for a
library module that you import. You can create a stub easily; here is
an overview:

* Write a stub file for the library and store it as a ``.pyi`` file in
  the same directory as the library module.
* Alternatively, put your stubs (``.pyi`` files) in a directory
  reserved for stubs (e.g., ``myproject/stubs``). In this case you
  have to set the environment variable ``MYPYPATH`` to refer to the
  directory.  For example::

    $ export MYPYPATH=~/work/myproject/stubs

Use the normal Python file name conventions for modules, e.g. ``csv.pyi``
for module ``csv``. Use a subdirectory with ``__init__.pyi`` for packages.

If a directory contains both a ``.py`` and a ``.pyi`` file for the
same module, the ``.pyi`` file takes precedence. This way you can
easily add annotations for a module even if you don't want to modify
the source code. This can be useful, for example, if you use 3rd party
open source libraries in your program (and there are no stubs in
typeshed yet).

That's it! Now you can access the module in mypy programs and type check
code that uses the library. If you write a stub for a library module,
consider making it available for other programmers that use mypy 
by contributing it back to the typeshed repo.

There is more information about creating stubs in the
`mypy wiki <https://github.com/python/mypy/wiki/Creating-Stubs-For-Python-Modules>`_.
The following sections explain the kinds of type annotations you can use
in your programs and stub files.

.. note::

   You may be tempted to point ``MYPYPATH`` to the standard library or
   to the ``site-packages`` directory where your 3rd party packages
   are installed. This is almost always a bad idea -- you will likely
   get tons of error messages about code you didn't write and that
   mypy can't analyze all that well yet, and in the worst case
   scenario mypy may crash due to some construct in a 3rd party
   package that it didn't expect.

Getting started
===============

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

Installing mypy
***************

Mypy requires Python 3.4 or later to run.  Once you've
`installed Python 3 <https://www.python.org/downloads/>`_,
you can install mypy with:

.. code-block:: text

    python3 -m pip install mypy

Note that even though you need Python 3 to run ``mypy``, type checking
Python 2 code is fully supported, as discussed in :ref:`python2`.

Running mypy
************

You can type check a program by using the ``mypy`` tool, which is
basically a linter -- it checks your program for errors without actually
running it::

   $ mypy program.py

All errors reported by mypy are essentially warnings that you are free
to ignore, if you so wish.

More command line options are documented in :ref:`command-line`.

.. note::

   Depending on how mypy is configured, you may have to run mypy like
   this::

     $ python3 -m mypy program.py

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
mypy will give an error if you use definitions such as ``Iterable``
without first importing them.

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

.. _stubs-intro:

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
library module that you import. You can
:ref:`create a stub easily <stub-files>`.

Next steps
**********

If you are in a hurry and don't want to read lots of documentation
before getting started, here are some pointers to quick learning
resources:

* Read the :ref:`mypy cheatsheet <cheat-sheet-py3>` (also for
  :ref:`Python 2 <cheat-sheet-py2>`).

* Read :ref:`existing-code` if you have a significant existing
  codebase without many type annotations.

* Read the `blog post <http://blog.zulip.org/2016/10/13/static-types-in-python-oh-mypy/>`_
  about the Zulip project's experiences with adopting mypy.

* If you prefer watching talks instead of reading, here are
  some ideas:

  * Carl Meyer:
    `Type Checked Python in the Real World <https://us.pycon.org/2018/schedule/presentation/102/>`_
    (PyCon 2018)

  * Greg Price:
    `Clearer Code at Scale: Static Types at Zulip and Dropbox <https://www.youtube.com/watch?v=0c46YHS3RY8>`_
    (PyCon 2018)

* Look at :ref:`solutions to common issues <common_issues>` with mypy if
  you encounter problems.

* You can ask questions about mypy in the
  `mypy issue tracker <https://github.com/python/mypy/issues>`_ and
  typing `Gitter chat <https://gitter.im/python/typing>`_.

You can also continue reading this document and skip sections that
aren't relevant for you. You don't need to read sections in order.

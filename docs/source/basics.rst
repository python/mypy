Basics
======

Function Signatures
*******************

A function without a type signature is dynamically typed. You can declare the signature of a function using the Python 3 annotation syntax This makes the function statically typed (the type checker reports type errors within the function):

.. code-block:: python

   # Dynamically typed (identical to Python)

   def greeting(name):
       return 'Hello, {}'.format(name)

.. code-block:: python

   # Statically typed (still valid Python)

   def greeting(name: str) -> str:
       return 'Hello, {}'.format(name)

A None return type indicates a function that does not explicitly return a value. Using a None result in a statically typed context results in a type check error:

.. code-block:: python

   def p() -> None:
       print('hello')

   a = p()   # Type check error: p has None return value

The typing module
*****************

We cheated a bit in the above examples: a module is type checked only if it imports the module typing. Here is a complete statically typed example from the previous section:

.. code-block:: python

   import typing

   def greeting(name: str) -> str:
       return 'Hello, {}'.format(name)

The typing module contains many definitions that are useful in statically typed code. You can also use from ... import to import them (we'll explain Iterable later in this document):

.. code-block:: python

   from typing import Iterable

   def greet_all(names: Iterable[str]) -> None:
       for name in names:
           print('Hello, {}'.format(name))

For brevity, we often omit the typing import in code examples, but you should always include it in modules that contain statically typed code.

You can still have dynamically typed functions in modules that import typing:

.. code-block:: python

   import typing

   def f():
       1 + 'x'  # No static type error (dynamically typed)

   def g() -> None:
       1 + 'x'  # Type check error (statically typed)

Mixing dynamic and static typing within a single file is often useful. For example, if you are migrating existing Python code to static typing, it may be easiest to do this incrementally, such as by migrating a few functions at a time. Also, when prototyping a new feature, you may decide to first implement the relevant code using dynamic typing and only add type signatures later, when the code is more stable.

.. note::

   Currently the type checker checks the top levels and annotated functions of all modules, even those that don't import typing. However, you should not rely on this, as this will change in the future.

Type checking and running programs
**********************************

You can type check a program by using the mypy tool, which is basically a linter — it checks you program for errors without actually running it::

   $ mypy program.py

You can always run a mypy program as a Python program, without type checking, even it it has type errors::

   $ python3 program.py

All errors reported by mypy are essentially warnings that you are free to ignore, if you so wish.

The `README <https://github.com/JukkaL/mypy/blob/master/README.md>`_ explains how to download and install mypy.

.. note::

   Depending on how mypy is configured, you may have to explicitly use the Python interpreter to run mypy. The mypy tool is an ordinary mypy (and so also Python) program.

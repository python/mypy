.. _stub-files:

Stub files
==========

A *stub file* is a file containing a skeleton of the public interface
of that Python module, including classes, variables, functions -- and
most importantly, their types.

Mypy uses stub files stored in the
`typeshed <https://github.com/python/typeshed>`_ repository to determine
the types of standard library and third-party library functions, classes,
and other definitions. You can also create your own stubs that will be
used to type check your code.

Creating a stub
***************

Here is an overview of how to create a stub file:

* Write a stub file for the library (or an arbitrary module) and store it as
  a ``.pyi`` file in the same directory as the library module.
* Alternatively, put your stubs (``.pyi`` files) in a directory
  reserved for stubs (e.g., :file:`myproject/stubs`). In this case you
  have to set the environment variable ``MYPYPATH`` to refer to the
  directory.  For example::

    $ export MYPYPATH=~/work/myproject/stubs

Use the normal Python file name conventions for modules, e.g. :file:`csv.pyi`
for module ``csv``. Use a subdirectory with :file:`__init__.pyi` for packages. Note
that :pep:`561` stub-only packages must be installed, and may not be pointed
at through the ``MYPYPATH`` (see :ref:`PEP 561 support <installed-packages>`).

If a directory contains both a ``.py`` and a ``.pyi`` file for the
same module, the ``.pyi`` file takes precedence. This way you can
easily add annotations for a module even if you don't want to modify
the source code. This can be useful, for example, if you use 3rd party
open source libraries in your program (and there are no stubs in
typeshed yet).

That's it!

Now you can access the module in mypy programs and type check
code that uses the library. If you write a stub for a library module,
consider making it available for other programmers that use mypy
by contributing it back to the typeshed repo.

Mypy also ships with two tools for making it easier to create and maintain
stubs: :ref:`stubgen` and :ref:`stubtest`.

The following sections explain the kinds of type annotations you can use
in your programs and stub files.

.. note::

   You may be tempted to point ``MYPYPATH`` to the standard library or
   to the :file:`site-packages` directory where your 3rd party packages
   are installed. This is almost always a bad idea -- you will likely
   get tons of error messages about code you didn't write and that
   mypy can't analyze all that well yet, and in the worst case
   scenario mypy may crash due to some construct in a 3rd party
   package that it didn't expect.

Stub file syntax
****************

Stub files are written in normal Python syntax, but generally
leaving out runtime logic like variable initializers, function bodies,
and default arguments.

If it is not possible to completely leave out some piece of runtime
logic, the recommended convention is to replace or elide them with ellipsis
expressions (``...``). Each ellipsis below is literally written in the
stub file as three dots:

.. code-block:: python

    # Variables with annotations do not need to be assigned a value.
    # So by convention, we omit them in the stub file.
    x: int

    # Function bodies cannot be completely removed. By convention,
    # we replace them with `...` instead of the `pass` statement.
    def func_1(code: str) -> int: ...

    # We can do the same with default arguments.
    def func_2(a: int, b: int = ...) -> int: ...

.. note::

    The ellipsis ``...`` is also used with a different meaning in
    :ref:`callable types <callable-types>` and :ref:`tuple types
    <tuple-types>`.

Using stub file syntax at runtime
*********************************

You may also occasionally need to elide actual logic in regular
Python code -- for example, when writing methods in
:ref:`overload variants <function-overloading>` or
:ref:`custom protocols <protocol-types>`.

The recommended style is to use ellipses to do so, just like in
stub files. It is also considered stylistically acceptable to
throw a :py:exc:`NotImplementedError` in cases where the user of the
code may accidentally call functions with no actual logic.

You can also elide default arguments as long as the function body
also contains no runtime logic: the function body only contains
a single ellipsis, the pass statement, or a ``raise NotImplementedError()``.
It is also acceptable for the function body to contain a docstring.
For example:

.. code-block:: python

    from typing import Protocol

    class Resource(Protocol):
        def ok_1(self, foo: list[str] = ...) -> None: ...

        def ok_2(self, foo: list[str] = ...) -> None:
            raise NotImplementedError()

        def ok_3(self, foo: list[str] = ...) -> None:
            """Some docstring"""
            pass

        # Error: Incompatible default for argument "foo" (default has
        # type "ellipsis", argument has type "list[str]")
        def not_ok(self, foo: list[str] = ...) -> None:
            print(foo)

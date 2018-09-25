.. _stub-files:

Stub files
==========

Mypy uses stub files stored in the
`typeshed <https://github.com/python/typeshed>`_ repository to determine
the types of standard library and third-party library functions, classes,
and other definitions. You can also create your own stubs that will be
used to type check your code. The basic properties of stubs were introduced
back in :ref:`stubs-intro`.

Creating a stub
***************

Here is an overview of how to create a stub file:

* Write a stub file for the library (or an arbitrary module) and store it as
  a ``.pyi`` file in the same directory as the library module.
* Alternatively, put your stubs (``.pyi`` files) in a directory
  reserved for stubs (e.g., ``myproject/stubs``). In this case you
  have to set the environment variable ``MYPYPATH`` to refer to the
  directory.  For example::

    $ export MYPYPATH=~/work/myproject/stubs

Use the normal Python file name conventions for modules, e.g. ``csv.pyi``
for module ``csv``. Use a subdirectory with ``__init__.pyi`` for packages. Note
that `PEP 561 <https://www.python.org/dev/peps/pep-0561/>`_ stub-only packages
must be installed, and may not be pointed at through the ``MYPYPATH``
(see :ref:`PEP 561 support <installed-packages>`).

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

Stub file syntax
****************

Stub files are written in normal Python 3 syntax, but generally
leaving out runtime logic like variable initializers, function bodies,
and default arguments, or replacing them with ellipses.

In this example, each ellipsis ``...`` is literally written in the
stub file as three dots:

.. code-block:: python

    x: int

    def afunc(code: str) -> int: ...
    def afunc(a: int, b: int = ...) -> int: ...

.. note::

    The ellipsis ``...`` is also used with a different meaning in
    :ref:`callable types <callable-types>` and :ref:`tuple types
    <tuple-types>`.

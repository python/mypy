.. _stugen:

Automatic stub generation
=========================

Stub files (see `PEP 484 <https://www.python.org/dev/peps/pep-0484/#stub-files>`_)
are files containing only type hints not the actual runtime implementation.
They can be useful for C extension modules, third-party modules whose authors
have not yet added type hints, etc.

Mypy comes with a ``stubgen`` tool for automatic generation of
stub files (``.pyi`` files) from Python source files. For example,
this source file:

.. code-block:: python

   from other_module import dynamic

   BORDER_WIDTH = 15

   class Window:
       parent = dynamic()
       def __init__(self, width, hight):
           self.width = width
           self.hight = hight

   def create_empty() -> Window:
       return Window(0, 0)

will be transformed into the following stub file:

.. code-block:: python

   from typing import Any

   BORDER_WIDTH: int = ...

   class Window:
       parent: Any = ...
       width: Any = ...
       height: Any: ...
       def __init__(self, width, height) -> None: ...

   def create_empty() -> Window: ...

In most cases, the auto-generated stub files require manual check for
completeness. This section documents stubgen's command line interface.
You can view a quick summary of the available flags by running
``stubgen --help``.

.. note::

   Stubgen tool is still experimental and will evolve. Command line flags
   are liable to change between releases.

Specifying what to stub
***********************

By default, you can specify for what code you want to generate
stub files by passing in the paths to the sources::

    $ stubgen foo.py bar.py some_directory

Note that directories are checked recursively.

Stubgen also lets you specify modules for stub generation in two
other ways. The relevant flags are:

``-m MODULE``, ``--module MODULE``
    Asks stubgen to generate stub file for the provided module. This flag
    may be repeated multiple times.

    Stubgen *will not* recursively generate stubs for any submodules of
    the provided module.

``-p PACKAGE``, ``--package PACKAGE``
    Asks stubgen to generate stubs for the provided package. This flag may
    be repeated multiple times.

    Stubgen *will* recursively generate stubs for all submodules of
    the provided package. This flag is identical to ``--module`` apart from
    this behavior.

.. note::

   You can use either module/package mode or source code mode, these two
   can't be mixed together in the same stubgen invocation.

Specifying how to generate stubs
********************************

By default stubgen will try to import the modules and packages given.
This has an advantage of possibility to discover and stub also C modules.
By default stubgen will use mypy to semantically analyze the Python
sources found. To alter this behavior, you can use following flags:

``--no-import``
    Don't try to import modules, instead use mypy's normal mechanisms to find
    sources. This will not find any C extension modules. Stubgen also uses
    runtime introspection to find actual value of ``__all__``, so with this flag
    the set of re-exported names may be incomplete. This flag will be useful if
    importing the module causes an error.

``--parse-only``
    Don't perform mypy semantic analysis of source files. This may generate
    worse stubs: in particular some module, class, and function aliases may
    be typed as variables with ``Any`` type. This can be useful if semantic
    analysis causes a critical mypy error.

``--doc-dir PATH``
    Try to infer function and class signatures by parsing .rst documentation
    in ``PATH``. This may result in better stubs, but currently only works for
    C modules.

Additional flags
****************

``--py2``
    Run stubgen in Python 2 mode (the default is Python 3 mode).

``--ignore-errors``
    Ignore any errors when trying to generate stubs for modules and packages.
    This may be useful for C modules where runtime introspection is used
    intensively.

``--include-private``
    Generate stubs for objects and members considered private (with single
    leading underscore and no trailing underscores).

``--search-path PATH``
    Specify module search directories, separated by colons (currently only
    used if ``--no-import`` is given).

``--python-executable PATH``
    Use Python interpreter at ``PATH`` for module finding and runtime
    introspection (has no effect with ``--no-import``). Currently only works
    for Python 2. In Python 3 mode only the default interpreter will be used.

``-o PATH``, ``--output PATH``
    Change the output directory. By default the stubs are written in
    ``./out`` directory. The output directory will be created if it didn't
    exist. Existing stubs in the output directory will be overwritten without
    warning.

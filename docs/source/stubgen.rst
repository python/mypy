.. _stubgen:

.. program:: stubgen

Automatic stub generation (stubgen)
===================================

A stub file (see :pep:`484`) contains only type hints for the public
interface of a module, with empty function bodies. Mypy can use a stub
file instead of the real implementation to provide type information
for the module. They are useful for third-party modules whose authors
have not yet added type hints (and when no stubs are available in
typeshed) and C extension modules (which mypy can't directly process).

Mypy includes the ``stubgen`` tool that can automatically generate
stub files (``.pyi`` files) for Python modules and C extension modules.
For example, consider this source file:

.. code-block:: python

   from other_module import dynamic

   BORDER_WIDTH = 15

   class Window:
       parent = dynamic()
       def __init__(self, width, height):
           self.width = width
           self.height = height

   def create_empty() -> Window:
       return Window(0, 0)

Stubgen can generate this stub file based on the above file:

.. code-block:: python

   from typing import Any

   BORDER_WIDTH: int = ...

   class Window:
       parent: Any = ...
       width: Any = ...
       height: Any = ...
       def __init__(self, width, height) -> None: ...

   def create_empty() -> Window: ...

Stubgen generates *draft* stubs. The auto-generated stub files often
require some manual updates, and most types will default to ``Any``.
The stubs will be much more useful if you add more precise type annotations,
at least for the most commonly used functionality.

The rest of this section documents the command line interface of stubgen.
Run :option:`stubgen --help` for a quick summary of options.

.. note::

  The command-line flags may change between releases.

Specifying what to stub
***********************

You can give stubgen paths of the source files for which you want to
generate stubs::

    $ stubgen foo.py bar.py

This generates stubs ``out/foo.pyi`` and ``out/bar.pyi``. The default
output directory ``out`` can be overridden with :option:`-o DIR <-o>`.

You can also pass directories, and stubgen will recursively search
them for any ``.py`` files and generate stubs for all of them::

    $ stubgen my_pkg_dir

Alternatively, you can give module or package names using the
:option:`-m` or :option:`-p` options::

    $ stubgen -m foo -m bar -p my_pkg_dir

Details of the options:

.. option:: -m MODULE, --module MODULE

    Generate a stub file for the given module. This flag may be repeated
    multiple times.

    Stubgen *will not* recursively generate stubs for any submodules of
    the provided module.

.. option:: -p PACKAGE, --package PACKAGE

    Generate stubs for the given package. This flag maybe repeated
    multiple times.

    Stubgen *will* recursively generate stubs for all submodules of
    the provided package. This flag is identical to :option:`--module` apart from
    this behavior.

.. note::

   You can't mix paths and :option:`-m`/:option:`-p` options in the same stubgen
   invocation.

Stubgen applies heuristics to avoid generating stubs for submodules
that include tests or vendored third-party packages.

Specifying how to generate stubs
********************************

By default stubgen will try to import the target modules and packages.
This allows stubgen to use runtime introspection to generate stubs for C
extension modules and to improve the quality of the generated
stubs. By default, stubgen will also use mypy to perform light-weight
semantic analysis of any Python modules. Use the following flags to
alter the default behavior:

.. option:: --no-import

    Don't try to import modules. Instead only use mypy's normal search mechanism to find
    sources. This does not support C extension modules. This flag also disables
    runtime introspection functionality, which mypy uses to find the value of
    ``__all__``. As result the set of exported imported names in stubs may be
    incomplete. This flag is generally only useful when importing a module causes
    unwanted side effects, such as the running of tests. Stubgen tries to skip test
    modules even without this option, but this does not always work.

.. option:: --no-analysis

    Don't perform semantic analysis of source files. This may generate
    worse stubs -- in particular, some module, class, and function aliases may
    be represented as variables with the ``Any`` type. This is generally only
    useful if semantic analysis causes a critical mypy error.  Does not apply to
    C extension modules.  Incompatible with :option:`--inspect-mode`.

.. option:: --inspect-mode

    Import and inspect modules instead of parsing source code. This is the default
    behavior for C modules and pyc-only packages.  The flag is useful to force
    inspection for pure Python modules that make use of dynamically generated
    members that would otherwise be omitted when using the default behavior of
    code parsing.  Implies :option:`--no-analysis` as analysis requires source
    code.

.. option:: --doc-dir PATH

    Try to infer better signatures by parsing .rst documentation in ``PATH``.
    This may result in better stubs, but currently it only works for C extension
    modules.

Additional flags
****************

.. option:: -h, --help

    Show help message and exit.

.. option:: --ignore-errors

    If an exception was raised during stub generation, continue to process any
    remaining modules instead of immediately failing with an error.

.. option:: --include-private

    Include definitions that are considered private in stubs (with names such
    as ``_foo`` with single leading underscore and no trailing underscores).

.. option:: --export-less

    Don't export all names imported from other modules within the same package.
    Instead, only export imported names that are not referenced in the module
    that contains the import.

.. option:: --include-docstrings

    Include docstrings in stubs. This will add docstrings to Python function and
    classes stubs and to C extension function stubs.

.. option:: --search-path PATH

    Specify module search directories, separated by colons (only used if
    :option:`--no-import` is given).

.. option:: -o PATH, --output PATH

    Change the output directory. By default the stubs are written in the
    ``./out`` directory. The output directory will be created if it doesn't
    exist. Existing stubs in the output directory will be overwritten without
    warning.

.. option:: -v, --verbose

    Produce more verbose output.

.. option:: -q, --quiet

    Produce less verbose output.

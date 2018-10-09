.. _command-line:

The mypy command line
=====================

This section documents mypy's command line interface. You can view
a quick summary of the available flags by running ``mypy --help``.

.. note::

   Command line flags are liable to change between releases.


Specifying what to type check
*****************************

By default, you can specify what code you want mypy to type check
by passing in the paths to what you want to have type checked::

    $ mypy foo.py bar.py some_directory

Note that directories are checked recursively.

Mypy also lets you specify what code to type check in several other
ways. A short summary of the relevant flags is included below:
for full details, see :ref:`running-mypy`.

``-m MODULE``, ``--module MODULE``
    Asks mypy to type check the provided module. This flag may be
    repeated multiple times.

    Mypy *will not* recursively type check any submodules of the provided
    module.

``-p PACKAGE``, ``--package PACKAGE``
    Asks mypy to type check the provided package. This flag may be
    repeated multiple times.

    Mypy *will* recursively type check any submodules of the provided
    package. This flag is identical to ``-module`` apart from this
    behavior.

``-c PROGRAM_TEXT``, ``--command PROGRAM_TEXT``
    Asks mypy to type check the provided string as a program.


.. _config-file-flag:

Config file
***********

``--config-file CONFIG_FILE``
    This flag makes mypy read configuration settings from the given file.

    By default settings are read from ``mypy.ini`` or ``setup.cfg`` in the
    current directory, or ``.mypy.ini`` in the user's home directory.
    Settings override mypy's built-in defaults and command line flags
    can override settings.

    See :ref:`config-file` for the syntax of configuration files.

``--warn-unused-configs``
    This flag makes mypy warn about unused ``[mypy-<pattern>]`` config
    file sections.


.. _import-discovery:

Import discovery
****************

The following flags customize how exactly mypy discovers and follows
imports.

``--namespace-packages``
    This flag enables import discovery to use namespace packages (see
    `PEP 420`_).  In particular, this allows discovery of imported
    packages that don't have an ``__init__.py`` (or ``__init__.pyi``)
    file.

    Namespace packages are found (using the PEP 420 rules, which
    prefers "classic" packages over namespace packages) along the
    module search path -- this is primarily set from the source files
    passed on the command line, the ``MYPYPATH`` environment variable,
    and the :ref:`mypy_path config option
    <config-file-import-discovery-global>`.

    Note that this only affects import discovery -- for modules and
    packages explicitly passed on the command line, mypy still
    searches for ``__init__.py[i]`` files in order to determine the
    fully-qualified module/package name.

``--ignore-missing-imports``
    This flag makes mypy ignore all missing imports. It is equivalent
    to adding ``# type: ignore`` comments to all unresolved imports
    within your codebase.

    Note that this flag does *not* suppress errors about missing names
    in successfully resolved modules. For example, if one has the
    following files::

        package/__init__.py
        package/mod.py

    Then mypy will generate the following errors with ``--ignore-missing-imports``:

    .. code-block:: python

        import package.unknown      # No error, ignored
        x = package.unknown.func()  # OK. 'func' is assumed to be of type 'Any'

        from package import unknown          # No error, ignored
        from package.mod import NonExisting  # Error: Module has no attribute 'NonExisting'

    For more details, see :ref:`ignore-missing-imports`.

``--follow-imports {normal,silent,skip,error}``
    This flag adjusts how mypy follows imported modules that were not
    explicitly passed in via the command line.

    The default option is ``normal``: mypy will follow and type check
    all modules. For more information on what the other options do,
    see :ref:`Following imports <follow-imports>`.

``--python-executable EXECUTABLE``
    This flag will have mypy collect type information from `PEP 561`_
    compliant packages installed for the Python executable ``EXECUTABLE``.
    If not provided, mypy will use PEP 561 compliant packages installed for
    the Python executable running mypy.

    See :ref:`installed-packages` for more on making PEP 561 compliant packages.
    This flag will attempt to set ``--python-version`` if not already set.

``--no-site-packages``
    This flag will disable searching for `PEP 561`_ compliant packages. This
    will also disable searching for a usable Python executable.

    Use this  flag if mypy cannot find a Python executable for the version of
    Python being checked, and you don't need to use PEP 561 typed packages.
    Otherwise, use ``--python-executable``.

``--no-silence-site-packages``
    By default, mypy will suppress any error messages generated within PEP 561
    compliant packages. Adding this flag will disable this behavior.


.. _platform-configuration:

Platform configuration
**********************

By default, mypy will assume that you intend to run your code using the same
operating system and Python version you are using to run mypy itself. The
following flags let you modify this behavior.

For more information on how to use these flags, see :ref:`version_and_platform_checks`.

``--python-version X.Y``
    This flag will make mypy type check your code as if it were
    run under Python version X.Y. Without this option, mypy will default to using
    whatever version of Python is running mypy. Note that the ``-2`` and
    ``--py2`` flags are aliases for ``--python-version 2.7``.

    This flag will attempt to find a Python executable of the corresponding
    version to search for `PEP 561`_ compliant packages. If you'd like to
    disable this, use the ``--no-site-packages`` flag (see
    :ref:`import-discovery` for more details).

``-2``, ``--py2``
    Equivalent to running ``--python-version 2.7``.

``--platform PLATFORM``
    This flag will make mypy type check your code as if it were
    run under the given operating system. Without this option, mypy will
    default to using whatever operating system you are currently using.

    The ``PLATFORM`` parameter may be any string supported by
    `sys.platform <https://docs.python.org/3/library/sys.html#sys.platform>`_.

.. _always-true:

``--always-true NAME``
    This flag will treat all variables named ``NAME`` as
    compile-time constants that are always true.  This flag may
    be repeated.

``--always-false NAME``
    This flag will treat all variables named ``NAME`` as
    compile-time constants that are always false.  This flag may
    be repeated.

.. _disallow-dynamic-typing:

Disallow dynamic typing
***********************

The ``Any`` type is used represent a value that has a :ref:`dynamic type <dynamic-typing>`.
The ``--disallow-any`` family of flags will disallow various uses of the ``Any`` type in
a module -- this lets us strategically disallow the use of dynamic typing in a controlled way.

The following options are available:

``--disallow-any-unimported``
    This flag disallows usage of types that come from unfollowed imports
    (such types become aliases for ``Any``). Unfollowed imports occur either
    when the imported module does not exist or when ``--follow-imports=skip``
    is set.

``--disallow-any-expr``
    This flag disallows all expressions in the module that have type ``Any``.
    If an expression of type ``Any`` appears anywhere in the module
    mypy will output an error unless the expression is immediately
    used as an argument to ``cast`` or assigned to a variable with an
    explicit type annotation.

    In addition, declaring a variable of type ``Any``
    or casting to type ``Any`` is not allowed. Note that calling functions
    that take parameters of type ``Any`` is still allowed.

``--disallow-any-decorated``
    This flag disallows functions that have ``Any`` in their signature
    after decorator transformation.

``--disallow-any-explicit``
    This flag disallows explicit ``Any`` in type positions such as type
    annotations and generic type parameters.

``--disallow-any-generics``
    This flag disallows usage of generic types that do not specify explicit
    type parameters. Moreover, built-in collections (such as ``list`` and
    ``dict``) become disallowed as you should use their aliases from the typing
    module (such as ``List[int]`` and ``Dict[str, str]``).

``--disallow-subclassing-any``
    This flag reports an error whenever a class subclasses a value of
    type ``Any``.  This may occur when the base class is imported from
    a module that doesn't exist (when using
    :ref:`--ignore-missing-imports <ignore-missing-imports>`) or is
    ignored due to :ref:`--follow-imports=skip <follow-imports>` or a
    ``# type: ignore`` comment on the ``import`` statement.

    Since the module is silenced, the imported class is given a type of ``Any``.
    By default mypy will assume that the subclass correctly inherited
    the base class even though that may not actually be the case.  This
    flag makes mypy raise an error instead.

.. _untyped-definitions-and-calls:

Untyped definitions and calls
*****************************

The following flags configure how mypy handles untyped function
definitions or calls.

``--disallow-untyped-calls``
    This flag reports an error whenever a function with type annotations
    calls a function defined without annotations.

``--disallow-untyped-defs``
    This flag reports an error whenever it encounters a function definition
    without type annotations.

``--disallow-incomplete-defs``
    This flag reports an error whenever it encounters a partly annotated
    function definition.

``--check-untyped-defs``
    This flag is less severe than the previous two options -- it type checks
    the body of every function, regardless of whether it has type annotations.
    (By default the bodies of functions without annotations are not type
    checked.)

    It will assume all arguments have type ``Any`` and always infer ``Any``
    as the return type.

``--disallow-untyped-decorators``
    This flag reports an error whenever a function with type annotations
    is decorated with a decorator without annotations.

.. _none-and-optional-handling:

None and Optional handling
**************************

The following flags adjust how mypy handles values of type `None`.
For more details, see :ref:`no_strict_optional`.

.. _no-implicit-optional:

``--no-implicit-optional``
    This flag causes mypy to stop treating arguments with a ``None``
    default value as having an implicit ``Optional[...]`` type.

    For example, by default mypy will assume that the ``x`` parameter
    is of type ``Optional[int]`` in the code snippet below since
    the default parameter is ``None``:

    .. code-block:: python

        def foo(x: int = None) -> None:
            print(x)

    If this flag is set, the above snippet will no longer type check:
    we must now explicitly indicate that the type is ``Optional[int]``:

    .. code-block:: python

        def foo(x: Optional[int] = None) -> None:
            print(x)

``--no-strict-optional``
    This flag disables strict checking of ``Optional[...]``
    types and ``None`` values. With this option, mypy doesn't
    generally check the use of ``None`` values -- they are valid
    everywhere. See :ref:`no_strict_optional` for more about this feature.

.. note::
    Strict optional checking was enabled by default starting in
    mypy 0.600, and in previous versions it had to be explicitly enabled
    using ``--strict-optional`` (which is still accepted).

.. _configuring-warnings:

Configuring warnings
********************

The follow flags enable warnings for code that is sound but is
potentially problematic or redundant in some way.

``--warn-redundant-casts``
    This flag will make mypy report an error whenever your code uses
    an unnecessary cast that can safely be removed.

``--warn-unused-ignores``
    This flag will make mypy report an error whenever your code uses
    a ``# type: ignore`` comment on a line that is not actually
    generating an error message.

    This flag, along with the ``--warn-unsued-casts`` flag, are both
    particularly useful when you are upgrading mypy. Previously,
    you may have needed to add casts or ``# type: ignore`` annotations
    to work around bugs in mypy or missing stubs for 3rd party libraries.

    These two flags let you discover cases where either workarounds are
    no longer necessary.

``--no-warn-no-return``
    By default, mypy will generate errors when a function is missing
    return statements in some execution paths. The only exceptions
    are when:

    -   The function has a ``None`` or ``Any`` return type
    -   The function has an empty body or a body that is just
        ellipsis (``...``). Empty functions are often used for
        abstract methods.

    Passing in ``--no-warn-no-return`` will disable these error
    messages in all cases.

``--warn-return-any``
    This flag causes mypy to generate a warning when returning a value
    with type ``Any`` from a function declared with a non- ``Any`` return type.

Miscellaneous strictness flags
******************************

This section documents any other flags that do not neatly fall under any
of the above sections.

``--allow-untyped-globals``
    This flag causes mypy to suppress errors caused by not being able to fully
    infer the types of global and class variables.

``--strict``
    This flag mode enables all optional error checking flags.  You can see the
    list of flags enabled by strict mode in the full ``mypy --help`` output.

    Note: the exact list of flags enabled by running ``--strict`` may change
    over time.

.. _configuring-error-messages:

Configuring error messages
**************************

The following flags let you adjust how much detail mypy displays
in error messages.

``--show-error-context``
    This flag will precede all errors with "note" messages explaining the
    context of the error. For example, consider the following program:

    .. code-block:: python

        class Test:
            def foo(self, x: int) -> int:
                return x + "bar"

    Mypy normally displays an error message that looks like this::

        main.py:3: error: Unsupported operand types for + ("int" and "str")

    If we enable this flag, the error message now looks like this::

        main.py: note: In member "foo" of class "Test":
        main.py:3: error: Unsupported operand types for + ("int" and "str")

``--show-column-numbers``
    This flag will add column offsets to error messages,
    for example, the following indicates an error in line 12, column 9
    (note that column offsets are 0-based)::

        main.py:12:9: error: Unsupported operand types for / ("int" and "str")


.. _incremental:

Incremental mode
****************

By default, mypy will store type information into a cache. Mypy
will use this information to avoid unnecessary recomputation when
it type checks your code again.  This can help speed up the type
checking process, especially when most parts of your program have
not changed since the previous mypy run.

If you want to speed up how long it takes to recheck your code
beyond what incremental mode can offer, try running mypy in
:ref:`daemon mode <mypy_daemon>`.

``--no-incremental``
    This flag disables incremental mode: mypy will no longer reference
    the cache when re-run.

    Note that mypy will still write out to the cache even when
    incremental mode is disabled: see the ``--cache-dir`` flag below
    for more details.

``--cache-dir DIR``
    By default, mypy stores all cache data inside of a folder named
    ``.mypy_cache`` in the current directory. This flag lets you
    change this folder. This flag can also be useful for controlling
    cache use when using :ref:`remote caching <remote-cache>`.

    Mypy will also always write to the cache even when incremental
    mode is disabled so it can "warm up" the cache. To disable
    writing to the cache, use ``--cache-dir=/dev/null`` (UNIX)
    or ``--cache-dir=nul`` (Windows).

``--skip-version-check``
    By default, mypy will ignore cache data generated by a different
    version of mypy. This flag disables that behavior.

.. _quick-mode:

``--quick-and-dirty``
    This flag enables a **deprecated**, unsafe variant of incremental mode.
    Quick mode is faster than regular incremental mode because it only
    re-checks modules that were modified since their cache file was
    last written: regular incremental mode also re-checks all modules
    that depend on one or more modules that were re-checked.

    Quick mode is unsafe because it may miss problems caused by a change
    in a dependency.  Quick mode updates the cache, but regular incremental
    mode ignores cache files written by quick mode.

    We recommend that you try using the :ref:`mypy_daemon` before
    attempting to use this feature.
    Quick mode is deprecated and will soon be removed.

.. _advanced-flags:

Advanced flags
**************

The following flags are useful mostly for people who are interested
in developing or debugging mypy internals.

``--pdb``
    This flag will invoke the Python debugger when mypy encounters
    a fatal error.

``--show-traceback``, ``--tb``
    If set, this flag will display a full traceback when mypy
    encounters a fatal error.

``--custom-typing MODULE``
    This flag lets you use a custom module as a substitute for the
    ``typing`` module.

``--custom-typeshed-dir DIR``
    This flag specifies the directory where mypy looks for typeshed
    stubs, instead of the typeshed that ships with mypy.  This is
    primarily intended to make it easier to test typeshed changes before
    submitting them upstream, but also allows you to use a forked version of
    typeshed.

.. _warn-incomplete-stub:

``--warn-incomplete-stub``
    This flag modifies both the ``--disallow-untyped-defs`` and
    ``--disallow-incomplete-defs`` flags so they also report errors
    if stubs in typeshed are missing type annotations or has incomplete
    annotations. If both flags are missing, ``--warn-incomplete-stub``
    also does nothing.

    This flag is mainly intended to be used by people who want contribute
    to typeshed and would like a convenient way to find gaps and omissions.

    If you want mypy to report an error when your codebase *uses* an untyped
    function, whether that function is defined in typeshed or not, use the
    ``--disallow-untyped-call`` flag. See :ref:`untyped-definitions-and-calls`
    for more details.

.. _shadow-file:

``--shadow-file SOURCE_FILE SHADOW_FILE``
    When mypy is asked to type check ``SOURCE_FILE``, this flag makes mypy
    read from and type check the contents of ``SHADOW_FILE`` instead. However,
    diagnostics will continue to refer to ``SOURCE_FILE``.

    Specifying this argument multiple times (``--shadow-file X1 Y1 --shadow-file X2 Y2``)
    will allow mypy to perform multiple substitutions.

    This allows tooling to create temporary files with helpful modifications
    without having to change the source file in place. For example, suppose we
    have a pipeline that adds ``reveal_type`` for certain variables.
    This pipeline is run on ``original.py`` to produce ``temp.py``.
    Running ``mypy --shadow-file original.py temp.py original.py`` will then
    cause mypy to type check the contents of ``temp.py`` instead of  ``original.py``,
    but error messages will still reference ``original.py``.

Report generation
*****************

If these flags are set, mypy will generate a report in the specified
format into the specified directory.

``--any-exprs-report DIR``
    Causes mypy to generate a text file report documenting how many
    expressions of type ``Any`` are present within your codebase.

``--linecount-report DIR``
    Causes mypy to generate a text file report documenting the functions
    and lines that are typed and untyped within your codebase.

``--linecoverage-report DIR``
    Causes mypy to generate a JSON file that maps each source file's
    absolute filename to a list of line numbers that belong to typed
    functions in that file.

``--cobertura-xml-report DIR``
    Causes mypy to generate a Cobertura XML type checking coverage report.

    You must install the `lxml`_ library to generate this report.

``--html-report DIR``, ``--xslt-html-report DIR``
    Causes mypy to generate an HTML type checking coverage report.

    You must install the `lxml`_ library to generate this report.

``--txt-report DIR``, ``--xslt-txt-report DIR``
    Causes mypy to generate a text file type checking coverage report.

    You must install the `lxml`_ library to generate this report.

``--junit-xml JUNIT_XML``
    Causes mypy to generate a JUnit XML test result document with
    type checking results. This can make it easier to integrate mypy
    with continuous integration (CI) tools.


Miscellaneous
*************

``--find-occurrences CLASS.MEMBER``
    This flag will make mypy print out all usages of a class member
    based on static type information. This feature is experimental.

``--scripts-are-modules``
    This flag will give command line arguments that appear to be
    scripts (i.e. files whose name does not end in ``.py``)
    a module name derived from the script name rather than the fixed
    name ``__main__``.

    This lets you check more than one script in a single mypy invocation.
    (The default ``__main__`` is technically more correct, but if you
    have many scripts that import a large package, the behavior enabled
    by this flag is often more convenient.)

.. _PEP 420: https://www.python.org/dev/peps/pep-0420/

.. _PEP 561: https://www.python.org/dev/peps/pep-0561/

.. _lxml: https://pypi.org/project/lxml/

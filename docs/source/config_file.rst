.. _config-file:

The mypy configuration file
===========================

Mypy supports reading configuration settings from a file.  By default
it uses the file ``mypy.ini`` with fallback to ``setup.cfg`` in the current
directory, or ``.mypy.ini`` in the user home directory if none of them are
found; the ``--config-file`` command-line flag can be used to read a different
file instead (see :ref:`--config-file <config-file-flag>`).

It is important to understand that there is no merging of configuration
files, as it would lead to ambiguity.  The ``--config-file`` flag
has the highest precedence and must be correct; otherwise mypy will report
an error and exit.  Without command line option, mypy will look for defaults,
but will use only one of them.  The first one to read is ``mypy.ini``,
and then ``setup.cfg``.

Most flags correspond closely to :ref:`command-line flags
<command-line>` but there are some differences in flag names and some
flags may take a different value based on the module being processed.

Config file format
******************

The configuration file format is the usual
`ini file <https://docs.python.org/3.6/library/configparser.html>`_
format.  It should contain section names in square brackets and flag
settings of the form `NAME = VALUE`.  Comments start with ``#``
characters.

- A section named ``[mypy]`` must be present.  This specifies
  the global flags. The ``setup.cfg`` file is an exception to this.

- Additional sections named ``[mypy-PATTERN1,PATTERN2,...]`` may be
  present, where ``PATTERN1``, ``PATTERN2``, etc., are comma-separated
  patterns of fully-qualified module names, with some components optionally
  replaced by the '*' character (e.g. ``foo.bar``, ``foo.bar.*``, ``foo.*.baz``).
  These sections specify additional flags that only apply to *modules*
  whose name matches at least one of the patterns.

  A pattern of the form ``qualified_module_name`` matches only the named module,
  while ``qualified_module_name.*`` matches ``dotted_module_name`` and any
  submodules (so ``foo.bar.*`` would match all of ``foo.bar``,
  ``foo.bar.baz``, and ``foo.bar.baz.quux``).

  Patterns may also be "unstructured" wildcards, in which stars may
  appear in the middle of a name (e.g
  ``site.*.migrations.*``). Stars match zero or more module
  components (so ``site.*.migrations.*`` can match ``site.migrations``).

  .. _config-precedence:

  When options conflict, the precedence order for the configuration sections is:
    1. Sections with concrete module names (``foo.bar``)
    2. Sections with "unstructured" wildcard patterns (``foo.*.baz``),
       with sections later in the configuration file overriding
       sections earlier.
    3. Sections with "well-structured" wildcard patterns
       (``foo.bar.*``), with more specific overriding more general.
    4. Command line options.
    5. Top-level configuration file options.

The difference in precedence order between "structured" patterns (by
specificity) and "unstructured" patterns (by order in the file) is
unfortunate, and is subject to change in future versions.

.. note::

   The ``warn_unused_configs`` flag may be useful to debug misspelled
   section names.

.. note::

   Configuration flags are liable to change between releases.


Examples
********

Here is an example of a ``mypy.ini`` file. To use this config file, place it at the root
of your repo and run mypy.

.. code-block:: ini

    # Global options:

    [mypy]
    python_version = 2.7
    warn_return_any = True
    warn_unused_configs = True

    # Per-module options:

    [mypy-mycode.foo.*]
    disallow_untyped_defs = True

    [mypy-mycode.bar]
    warn_return_any = False

    [mypy-somelibrary]
    ignore_missing_imports = True

This config file specifies three global options in the ``[mypy]`` section. These three
options will:

1.  Type-check your entire project assuming it will be run using Python 2.7.
    (This is equivalent to using the ``--python-version 2.7`` or ``--2`` flag).

2.  Report an error whenever a function returns a value that is inferred
    to have type ``Any``.

3.  Report any config options that are unused by mypy. (This will help us catch typos
    when making changes to our config file).

Next, this module specifies three per-module options. The first two options change how mypy
type checks code in ``mycode.foo.*`` and ``mycode.bar``, which we assume here are two modules
that you wrote. The final config option changes how mypy type checks ``somelibrary``, which we
assume here is some 3rd party library you've installed and are importing. These options will:

1.  Selectively disallow untyped function definitions only within the ``mycode.foo``
    package -- that is, only for function definitions defined in the
    ``mycode/foo`` directory.
    
2.  Selectively *disable* the "function is returning any" warnings within 
    ``mycode.bar`` only. This overrides the global default we set earlier.

3.  Suppress any error messages generated when your codebase tries importing the
    module ``somelibrary``. This is useful if ``somelibrary`` is some 3rd party library
    missing type hints.

.. _per-module-flags:

Per-module and global options
*****************************

The following config options may be set either globally (in the ``[mypy]`` section)
or on a per-module basis (in sections like ``[mypy-foo.bar]``).

If you set an option both globally and for a specific module, the module configuration
options take precedence. This lets you set global defaults and override them on a
module-by-module basis. If multiple pattern sections match a module, :ref:`the options from the
most specific section are used where they disagree <config-precedence>`.

.. _config-file-import-discovery-per-module:

Import discovery
----------------

For more information, see the :ref:`import discovery <import-discovery>`
section of the command line docs.

Note: this section describes options that can be used both globally and per-module.
See below for a list of import discovery options that may be used
:ref:`only globally <config-file-import-discovery-global>`.

``ignore_missing_imports`` (bool, default False) 
    Suppresses error messages about imports that cannot be resolved.

    If this option is used in a per-module section, the module name should
    match the name of the *imported* module, not the module containing the
    import statement.

``follow_imports`` (string, default ``normal``) 
    Directs what to do with imports when the imported module is found
    as a ``.py`` file and not part of the files, modules and packages 
    provided on the command line.

    The four possible values are ``normal``, ``silent``, ``skip`` and
    ``error``.  For explanations see the discussion for the
    :ref:`--follow-imports <follow-imports>` command line flag. 
    
    If this option is used in a per-module section, the module name should
    match the name of the *imported* module, not the module containing the
    import statement.

``follow_imports_for_stubs`` (bool, default False)
    Determines whether to respect the ``follow_imports`` setting even for
    stub (``.pyi``) files.

    Used in conjunction with ``follow_imports=skip``, this can be used
    to suppress the import of a module from ``typeshed``, replacing it
    with `Any`.

    Used in conjunction with ``follow_imports=error``, this can be used
    to make any use of a particular ``typeshed`` module an error.

Disallow dynamic typing
-----------------------

For more information, see the :ref:`disallowing dynamic typing <disallow-dynamic-typing>`
section of the command line docs.

``disallow_any_unimported`` (bool, default False)
    Disallows usage of types that come from unfollowed imports (anything imported from
    an unfollowed import is automatically given a type of ``Any``).

``disallow_any_expr`` (bool, default False)
    Disallows all expressions in the module that have type ``Any``.

``disallow_any_decorated`` (bool, default False)
    Disallows functions that have ``Any`` in their signature after decorator transformation.

``disallow_any_explicit`` (bool, default False)
    Disallows explicit ``Any`` in type positions such as type annotations and generic
    type parameters.

``disallow_any_generics`` (bool, default False)
    Disallows usage of generic types that do not specify explicit type parameters.

``disallow_subclassing_any`` (bool, default False)
    Disallows subclassing a value of type ``Any``.


Untyped definitions and calls
-----------------------------

For more information, see the :ref:`untyped definitions and calls <untyped-definitions-and-calls>`
section of the command line docs.

``disallow_untyped_calls`` (bool, default False)
    Disallows calling functions without type annotations from functions with type
    annotations.

``disallow_untyped_defs`` (bool, default False)
    Disallows defining functions without type annotations or with incomplete type
    annotations.

``disallow_incomplete_defs`` (bool, default False)
    Disallows defining functions with incomplete type annotations. 

``check_untyped_defs`` (bool, default False)
    Type-checks the interior of functions without type annotations.

``disallow_untyped_decorators`` (bool, default False)
    Reports an error whenever a function with type annotations is decorated with a
    decorator without annotations.

.. _config-file-none-and-optional-handling:

None and optional handling
--------------------------

For more information, see the :ref:`None and optional handling <none-and-optional-handling>`
section of the command line docs.

``no_implicit_optional`` (bool, default False)
    Changes the treatment of arguments with a default value of None by not implicitly
    making their type Optional.

``strict_optional`` (bool, default True)
    Enables or disables strict Optional checks. If False, mypy treats ``None``
    as compatible with every type.

    **Note:** This was False by default in mypy versions earlier than 0.600.


Configuring warnings
--------------------

For more information, see the :ref:`configuring warnings <configuring-warnings>`
section of the command line docs.

``warn_unused_ignores`` (bool, default False)
    Warns about unneeded ``# type: ignore`` comments.

``warn_no_return`` (bool, default True) 
    Shows errors for missing return statements on some execution paths.

``warn_return_any`` (bool, default False)
    Shows a warning when returning a value with type ``Any`` from a function
    declared with a non- ``Any`` return type.

.. _config-file-suppressing-errors:

Suppressing errors
------------------

Note: these configuration options are available in the config file only. There is
no analog available via the command line options.

``show_none_errors`` (bool, default True)
    Shows errors related to strict ``None`` checking, if the global ``strict_optional``
    flag is enabled.

``ignore_errors`` (bool, default False)
    Ignores all non-fatal errors.


Global-only options
*******************

The following options may only be set in the global section (``[mypy]``).

.. _config-file-import-discovery-global:

Import discovery
----------------

For more information, see the :ref:`import discovery <import-discovery>`
section of the command line docs.

Note: this section describes only global-only import discovery options. See above for
a list of import discovery options that may be used 
:ref:`both per-module and globally <config-file-import-discovery-per-module>`.

``namespace_packages`` (bool, default False)
    Enables PEP 420 style namespace packages.  See :ref:`the
    corresponding flag <import-discovery>` for more information.

``python_executable`` (string)
    Specifies the path to the Python executable to inspect to collect
    a list of available :ref:`PEP 561 packages <installed-packages>`. Defaults to
    the executable used to run mypy.

``no_silence_site_packages`` (bool, default False)
    Enables reporting error messages generated within PEP 561 compliant packages.
    Those error messages are suppressed by default, since you are usually
    not able to control errors in 3rd party code.

``mypy_path`` (string)
    Specifies the paths to use, after trying the paths from ``MYPYPATH`` environment
    variable.  Useful if you'd like to keep stubs in your repo, along with the config file.


Platform configuration
----------------------

For more information, see the :ref:`platform configuration <platform-configuration>`
section of the command line docs.

``python_version`` (string) 
    Specifies the Python version used to parse and check the target
    program.  The string should be in the format ``DIGIT.DIGIT`` --
    for example ``2.7``.  The default is the version of the Python
    interpreter used to run mypy.

``platform`` (string)
    Specifies the OS platform for the target program, for example
    ``darwin`` or ``win32`` (meaning OS X or Windows, respectively).
    The default is the current platform as revealed by Python's
    ``sys.platform`` variable.

``always_true`` (comma-separated list of strings)
    Specifies a list of variables that mypy will treat as 
    compile-time constants that are always true.
    
``always_false`` (comma-separated list of strings) 
    Specifies a list of variables that mypy will treat as 
    compile-time constants that are always false.


Incremental mode
----------------

For more information, see the :ref:`incremental mode <incremental>`
section of the command line docs.

``incremental`` (bool, default True) 
    Enables :ref:`incremental mode <incremental>`.

``cache_dir`` (string, default ``.mypy_cache``) 
    Specifies the location where mypy stores incremental cache info.
    Note that the cache is only read when incremental mode is enabled
    but is always written to, unless the value is set to ``/dev/nul``
    (UNIX) or ``nul`` (Windows).

``skip_version_check`` (bool, default False)
    Makes mypy use incremental cache data even if it was generated by a
    different version of mypy. (By default, mypy will perform a version
    check and regenerate the cache if it was written by older versions of mypy.)
    
``quick_and_dirty`` (bool, default False)
    Enables :ref:`quick mode <quick-mode>`.  **Deprecated.**


Configuring error messages
--------------------------

For more information, see the :ref:`configuring error messages <configuring-error-messages>`
section of the command line docs.

``show_error_context`` (bool, default False) 
    Prefixes each error with the relevant context.

``show_column_numbers`` (bool, default False)
    Shows column numbers in error messages.


Advanced options
----------------

For more information, see the :ref:`advanced flags <advanced-flags>`
section of the command line docs.

``pdb`` (bool, default False)
    Invokes pdb on fatal error.

``show_traceback`` (bool, default False)
    Shows traceback on fatal error.

``custom_typing_module`` (string) 
    Specifies a custom module to use as a substitute for the ``typing`` module.

``custom_typeshed_dir`` (string)
    Specifies an alternative directory to look for stubs instead of the
    default ``typeshed`` directory.

``warn_incomplete_stub`` (bool, default False)
    Warns about missing type annotations in typeshed.  This is only relevant
    in combination with ``disallow_untyped_defs`` or ``disallow_incomplete_defs``.


Miscellaneous
-------------

``warn_redundant_casts`` (bool, default False)
    Warns about casting an expression to its inferred type.

``scripts_are_modules`` (bool, default False)
    Makes script ``x`` become module ``x`` instead of ``__main__``.  This is
    useful when checking multiple scripts in a single run.

``warn_unused_configs`` (bool, default False)
    Warns about per-module sections in the config file that do not
    match any files processed when invoking mypy.

``verbosity`` (integer, default 0)
    Controls how much debug output will be generated.  Higher numbers are more verbose.



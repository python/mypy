.. _config-file:

The mypy configuration file
===========================

Mypy supports reading configuration settings from a file.  By default
it uses the file ``mypy.ini`` in the current directory; the
``--config-file`` command-line flag can be used to read a different
file instead (see :ref:`--config-file <config-file-flag>`).

Most flags correspond closely to :ref:`command-line flags
<command-line>` but there are some differences in flag names and some
flags may take a different value based on the module being processed.

The configuration file format is the usual
`ini file <https://docs.python.org/3.6/library/configparser.html>`_
format.  It should contain section names in square brackets and flag
settings of the form `NAME = VALUE`.  Comments start with ``#``
characters.

- A section named ``[mypy]`` must be present.  This specifies
  the global flags.

- Additional sections named ``[mypy-PATTERN1,PATTERN2,...]`` may be
  present, where ``PATTERN1``, ``PATTERN2`` etc. are `fnmatch patterns
  <https://docs.python.org/3.6/library/fnmatch.html>`_
  separated by commas.  These sections specify additional flags that
  only apply to *modules* whose name matches at least one of the patterns.

Global flags
************

The following global flags may only be set in the global section
(``[mypy]``).

- ``python_version`` (string) specifies the Python version used to
  parse and check the target program.  The format is ``DIGIT.DIGIT``
  for example ``2.7``.  The default is the version of the Python
  interpreter used to run mypy.

- ``platform`` (string) specifies the OS platform for the target
  program, for example ``darwin`` or ``win32`` (meaning OS X or
  Windows, respectively).  The default is the current platform as
  revealed by Python's ``sys.platform`` variable.

- ``custom_typing_module`` (string) specifies the name of an
  alternative module which is to be considered equivalent to the
  ``typing`` module.

- ``custom_typeshed_dir`` (string) specifies the name of an
  alternative directory which is used to look for stubs instead of the
  default ``typeshed`` directory.

- ``mypy_path`` (string) specifies the paths to use, after trying the paths
  from ``MYPYPATH`` environment variable.  Useful if you'd like to keep stubs
  in your repo, along with the config file.

- ``warn_incomplete_stub`` (Boolean, default False) warns for missing
  type annotation in typeshed.  This is only relevant in combination
  with ``check_untyped_defs``.

- ``warn_redundant_casts`` (Boolean, default False) warns about
  casting an expression to its inferred type.

- ``warn_unused_ignores`` (Boolean, default False) warns about
  unneeded ``# type: ignore`` comments.

- ``strict_optional`` (Boolean, default False) enables experimental
  strict Optional checks.

- ``scripts_are_modules`` (Boolean, default False) makes script ``x``
  become module ``x`` instead of ``__main__``.  This is useful when
  checking multiple scripts in a single run.

- ``verbosity`` (integer, default 0) controls how much debug output
  will be generated.  Higher numbers are more verbose.

- ``pdb`` (Boolean, default False) invokes pdb on fatal error.

- ``show_traceback`` (Boolean, default False) shows traceback on fatal
  error.

- ``dump_type_stats`` (Boolean, default False) dumps stats about type
  definitions.

- ``dump_inference_stats`` (Boolean, default False) dumps stats about
  type inference.

- ``fast_parser`` (Boolean, default False) enables the experimental
  fast parser.

- ``incremental`` (Boolean, default False) enables the experimental
  module cache.

- ``cache_dir`` (string, default ``.mypy_cache``) stores module cache
  info in the given folder in incremental mode.

- ``show_error_context`` (Boolean, default False) shows
  context notes before errors.

- ``show_column_numbers`` (Boolean, default False) shows column numbers in
  error messages.


.. _per-module-flags:

Per-module flags
****************

The following flags may vary per module.  They may also be specified in
the global section; the global section provides defaults which are
overridden by the pattern sections matching the module name.

.. note::

   If multiple pattern sections match a module they are processed in
   unspecified order.

- ``follow_imports`` (string, default ``normal``) directs what to do
  with imports when the imported module is found as a ``.py`` file and
  not part of the files, modules and packages on the command line.
  The four possible values are ``normal``, ``silent``, ``skip`` and
  ``error``.  For explanations see the discussion for the
  :ref:`--follow-imports <follow-imports>` command line flag.  Note
  that if pattern matching is used, the pattern should match the name
  of the _imported_ module, not the module containing the import
  statement.

- ``ignore_missing_imports`` (Boolean, default False) suppress error
  messages about imports that cannot be resolved.  Note that if
  pattern matching is used, the pattern should match the name of the
  _imported_ module, not the module containing the import statement.

- ``silent_imports`` (Boolean, deprecated) equivalent to
  ``follow_imports=skip`` plus ``ignore_missing_imports=True``.

- ``almost_silent`` (Boolean, deprecated) equivalent to
  ``follow_imports=skip``.

- ``disallow_untyped_calls`` (Boolean, default False) disallows
  calling functions without type annotations from functions with type
  annotations.

- ``disallow_untyped_defs`` (Boolean, default False) disallows
  defining functions without type annotations or with incomplete type
  annotations.

- ``check_untyped_defs`` (Boolean, default False) type-checks the
  interior of functions without type annotations.

- ``debug_cache`` (Boolean, default False) writes the incremental
  cache JSON files using a more readable, but slower format.

- ``show_none_errors`` (Boolean, default True) shows errors related
  to strict ``None`` checking, if the global ``strict_optional`` flag
  is enabled.

- ``ignore_errors`` (Boolean, default False) ignores all non-fatal
  errors.

- ``warn_no_return`` (Boolean, default False) shows errors for
  missing return statements on some execution paths.

Example
*******

You might put this in your ``mypy.ini`` file at the root of your repo:

.. code-block:: text

    [mypy]
    python_version = 2.7
    [mypy-foo.*]
    disallow_untyped_defs = True

This automatically sets ``--python-version 2.7`` (a.k.a. ``--py2``)
for all mypy runs in this tree, and also selectively turns on the
``--disallow-untyped-defs`` flag for all modules in the ``foo``
package.  This issues an error for function definitions without
type annotations in that subdirectory only.

.. note::

   Configuration flags are liable to change between releases.

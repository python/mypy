Revision history
================

List of major changes to this document:

- March 2017
    * Publish ``mypy`` version 0.500 on PyPI.

    * Add :ref:`noreturn`.

    * Add :ref:`generic-subclasses`.

    * Add :ref:`variance-of-generics`.

    * Add :ref:`invariance-vs-covariance`.

    * Updates to :ref:`python-36`.

    * Updates to :ref:`integrating-mypy`.

    * Updates to :ref:`command-line`:

      * Add option ``--warn-return-any``.

      * Add option ``--strict-boolean``.

      * Add option ``--strict``.

    * Updates to :ref:`config-file`:

      * ``warn_no_return`` is on by default.

      * Read settings from ``setup.cfg`` if ``mypy.ini`` does not exist.

      * Add option ``warn_return_any``.

      * Add option ``strict_boolean``.

- January 2017
    * Publish ``mypy`` version 0.470 on PyPI.

    * Change package name from ``mypy-lang`` to ``mypy``.

    * Add :ref:`integrating-mypy`.

    * Add :ref:`cheat-sheet-py3`.

    * Major update to :ref:`finding-imports`.

    * Add :ref:`--ignore-missing-imports <ignore-missing-imports>`.

    * Updates to :ref:`config-file`.

    * Document underscore support in numeric literals.

    * Document that arguments prefixed with ``__`` are positional-only.

    * Document that ``--hide-error-context`` is now on by default,
      and there is a new flag ``--show-error-context``.

    * Add ``ignore_errors`` to :ref:`per-module-flags`.

- November 2016
    * Publish ``mypy-lang`` version 0.4.6 on PyPI.

    * Add :ref:`getting-started`.

    * Add :ref:`generic-methods-and-generic-self` (experimental).

    * Add :ref:`declaring-decorators`.

    * Discuss generic type aliases in :ref:`type-aliases`.

    * Discuss Python 3.6 named tuple syntax in :ref:`named-tuples`.

    * Updates to :ref:`common_issues`.

    * Updates to :ref:`python-36`.

    * Updates to :ref:`command-line`:

      * ``--custom-typeshed-dir``

      * ``--junit-xml``

      * ``--find-occurrences``

      * ``--cobertura-xml-report``

      * ``--warn-no-return``

    * Updates to :ref:`config-file`:

      * Sections with fnmatch patterns now use
        module name patterns (previously they were path patterns).
      * Added ``custom_typeshed_dir``, ``mypy_path`` and ``show_column_numbers``.

    * Mention the magic ``MYPY`` constant in :ref:`import-cycles`.

- October 2016
    * Publish ``mypy-lang`` version 0.4.5 on PyPI.

    * Add :ref:`python-36`.

    * Add :ref:`config-file`.

    * Updates to :ref:`command-line`: ``--strict-optional-white-list``,
      ``--disallow-subclassing-any``, ``--config-file``, ``@flagfile``,
      ``--hide-error-context`` (replaces ``--suppress-error-context``),
      ``--show-column-numbers`` and ``--scripts-are-modules``.

    * Mention ``typing.TYPE_CHECKING`` in :ref:`import-cycles`.

- August 2016
    * Publish ``mypy-lang`` version 0.4.4 on PyPI.

    * Add :ref:`newtypes`.

    * Add :ref:`async-and-await`.

    * Add :ref:`text-and-anystr`.

    * Add :ref:`version_and_platform_checks`.

- July 2016
    * Publish ``mypy-lang`` version 0.4.3 on PyPI.

    * Add :ref:`strict_optional`.

    * Add :ref:`multi_line_annotation`.

- June 2016
    * Publish ``mypy-lang`` version 0.4.2 on PyPI.

    * Add :ref:`type-of-class`.

    * Add :ref:`cheat-sheet-py2`.

    * Add :ref:`reveal-type`.

- May 2016
    * Publish ``mypy-lang`` version 0.4 on PyPI.

    * Add :ref:`type-variable-upper-bound`.

    * Document :ref:`command-line`.

- Feb 2016
    * Publish ``mypy-lang`` version 0.3.1 on PyPI.

    * Document Python 2 support.

- Nov 2015
    Add :ref:`library-stubs`.

- Jun 2015
    Remove ``Undefined`` and ``Dynamic``, as they are not in PEP 484.

- Apr 2015
    Publish ``mypy-lang`` version 0.2.0 on PyPI.

- Mar 2015
    Update documentation to reflect PEP 484:

    * Add :ref:`named-tuples` and :ref:`optional`.

    * Do not mention type application syntax (for
      example, ``List[int]()``), as it's no longer supported,
      due to PEP 484 compatibility.

    * Rename ``typevar`` to ``TypeVar``.

    * Document ``# type: ignore`` which allows
      locally ignoring spurious errors (:ref:`silencing_checker`).

    * No longer mention
      ``Any(x)`` as a valid cast, as it will be phased out soon.

    * Mention the new ``.pyi`` stub file extension. Stubs can live
      in the same directory as the rest of the program.

- Jan 2015
    Mypy moves closer to PEP 484:

    * Add :ref:`type-aliases`.

    * Update discussion of overloading -- it's now only supported in stubs.

    * Rename ``Function[...]`` to ``Callable[...]``.

- Dec 2014
    Publish mypy version 0.1.0 on PyPI.

- Oct 2014
    Major restructuring.
    Split the HTML documentation into
    multiple pages.

- Sep 2014
    Migrated docs to Sphinx.

- Aug 2014
    Don't discuss native semantics. There is only Python
    semantics.

- Jul 2013
    Rewrite to use new syntax. Shift focus to discussing
    Python semantics. Add more content, including short discussions of
    :ref:`generic-functions` and :ref:`union-types`.

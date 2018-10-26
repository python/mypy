Revision history
================

List of major changes (the `Mypy Blog <http://mypy-lang.blogspot.com/>`_ contains more
detailed release notes):

- October 2018
    * Publish ``mypy`` version 0.640 on PyPI.

      * Document final qualifiers.

      * Document ``--namespace-packages``.

      * Remove deprecated options, and mark ``--quick-and-dirty`` as deprecated.

      * Document ``--permissive-toplevel``.

      * Reorganize config file docs.

- September 2018
    * Publish ``mypy`` version 0.630 on PyPI.

      * Document ``--warn-incomplete-stub`` (:ref:`docs <warn-incomplete-stub>`).

      * Document incompatibility of stub-only packages and ``MYPYPATH``
        (:ref:`docs <installed-packages>`).

      * Reorganize command line :ref:`documentation <command-line>`
        (see also :ref:`docs <running-mypy>` and :ref:`more docs <extending-mypy>`).

      * Document :ref:`callback protocols <callback_protocols>`.

- July 2018
    * Publish ``mypy`` version 0.620 on PyPI.

      * Improve support for :ref:`overloads <function-overloading>`.

      * Add support for :ref:`dataclasses <dataclasses_support>`.

- June 2018
    * Publish ``mypy`` version 0.610 on PyPI.

      * Major overhaul of documentation.

      * Add the ``dmypy run`` command to the :ref:`daemon <mypy_daemon>`.

      * Partially revert the prior changes to section pattern semantics in
        configuration files
        (:ref:`docs <config-file>` and :ref:`more docs <per-module-flags>`).

- May 2018
    * Publish ``mypy`` version 0.600 on PyPI.

      * Enable :ref:`strict optional checking <strict_optional>` by default.

      * Document :ref:`disabling strict optional checking <no_strict_optional>`.

      * Add :ref:`mypy_daemon`.

      * Add :ref:`remote-cache`.

      * Support user-specific configuration file (:ref:`docs <config-file>`).

      * Changes to section pattern semantics in configuration files
        (:ref:`docs <config-file>` and :ref:`more docs <per-module-flags>`).

- April 2018
    * Publish ``mypy`` version 0.590 on PyPI.

      * Document :ref:`PEP 561 support <installed-packages>`.

      * Made :ref:`incremental mode <incremental>` the default.

      * Document ``--always-true`` and ``--always-false`` (:ref:`docs <always-true>`).

      * Document ``follow_imports_for_stubs`` (:ref:`docs<per-module-flags>`).

      * Add coroutines to :ref:`Python 3 cheat sheet <cheat-sheet-py3>`.

      * Add ``None`` return/strict-optional to :ref:`common issues <annotations_needed>`.

      * Clarify that ``SupportsInt`` etc. don't support arithmetic operations (see :ref:`docs <supports-int-etc>`).

- March 2018
    * Publish ``mypy`` version 0.580 on PyPI.

      * Allow specifying multiple packages on the command line with ``-p`` and ``-m`` flags.

    * Publish ``mypy`` version 0.570 on PyPI.

      * Add support for :ref:`attrs_package`.

- December 2017
    * Publish ``mypy`` version 0.560 on PyPI.

      * Various types in ``typing`` that used to be ABCs
        :ref:`are now protocols <predefined_protocols>`
        and support :ref:`structural subtyping <protocol-types>`.

      * Explain how to :ref:`silence invalid complaints <silencing-linters>`
        by linters about unused imports due to type comments.

- November 2017
    * Publish ``mypy`` version 0.550 on PyPI.

      * Running mypy now requires Python 3.4 or higher.
        However Python 3.3 is still valid for the target
        of the analysis (i.e. the ``--python-version`` flag).

      * Split ``--disallow-any`` flag into
        :ref:`separate boolean flags <disallow-dynamic-typing>`.

      * The ``--old-html-report`` flag was removed.

- October 2017
    * Publish ``mypy`` version 0.540 on PyPI.

    * Publish ``mypy`` version 0.530 on PyPI.

- August-September 2017
    * Add :ref:`protocol-types`.

    * Other updates to :ref:`command-line`:

      * Add ``--warn-unused-configs``.

      * Add ``--disallow-untyped-decorators``.

      * Add ``--disallow-incomplete-defs``.

- July 2017
    * Publish ``mypy`` version 0.521 on PyPI.

    * Publish ``mypy`` version 0.520 on PyPI.

    * Add :ref:`fine-grained control of Any types <disallow-dynamic-typing>`.

    * Add :ref:`typeddict`.

    * Other updates to :ref:`command-line`:

      * Add ``--no-implicit-optional``.

      * Add ``--shadow-file``.

      * Add ``--no-incremental``.

- May 2017
    * Publish ``mypy`` version 0.510 on PyPI.

    * Remove option ``--no-fast-parser``.

    * Deprecate option ``--strict-boolean``.

    * Drop support for Python 3.2 as type checking target.

    * Add support for :ref:`overloaded functions with implementations <function-overloading>`.

    * Add :ref:`extended_callable`.

    * Add :ref:`async_generators_and_comprehensions`.

    * Add :ref:`ClassVar <class-var>`.

    * Add :ref:`quick mode <quick-mode>`.

- March 2017
    * Publish ``mypy`` version 0.500 on PyPI.

    * Add :ref:`noreturn`.

    * Add :ref:`generic-subclasses`.

    * Add :ref:`variance-of-generics`.

    * Add :ref:`variance`.

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

    * Add Getting started.

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

    * Add :ref:`strict optional checking <strict_optional>`.

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
    Add :ref:`stubs-intro`.

- Jun 2015
    Remove ``Undefined`` and ``Dynamic``, as they are not in PEP 484.

- Apr 2015
    Publish ``mypy-lang`` version 0.2.0 on PyPI.

- Mar 2015
    Update documentation to reflect PEP 484:

    * Add :ref:`named-tuples` and :ref:`Optional types <strict_optional>`.

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

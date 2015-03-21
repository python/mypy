Revision history
================

List of major changes to this document:

.. note::

   Some of the latest changes are not yet supported by the mypy
   version on PyPI. Use the
   `development version on GitHub <https://github.com/JukkaL/mypy>`_ to get
   them.

- Mar 2015
    Update documentation to reflect PEP 484.
    Add :ref:`named-tuples` and :ref:`optional`.
    Do not mention type application syntax (for
    example, ``List[int]()``), as it's no longer supported,
    due to PEP 484 compatibility. Rename ``typevar`` to
    ``TypeVar``.

- Jan 2015
    Mypy moves closer to PEP 484.
    Add :ref:`type-aliases`. Update discussion of
    overloading -- it's now only supported in stubs.
    Rename ``Function[...]`` to ``Callable[...]``.

- Dec 2014
    Publish mypy version 0.1.0 on PyPI.

- Nov 2014
    Add :ref:`library-stubs`.

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

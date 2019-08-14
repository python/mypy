.. _error-codes:

Error codes
===========

Mypy can optionally display an error code after a message. Error
codes serve two purposes:

1. It's possible to silence specific error codes on a line using
   ``# type: ignore[code]``.
2. The error code can be looked up here in the documentation to provide
   additional context.

Displaying error codes
----------------------

Error codes are not displayed by default.  Use ``--show-error-codes``
to display error codes. Error codes are shown inside square brackets:

.. code-block:: text

   $ mypy --show-error-codes prog.py
   prog.py:1: error: "str" has no attribute "trim"  [attr-defined]

Silencing errors based on error codes
-------------------------------------

You can use ``# type: ignore[code, ...]`` to ignore all errors with
specific codes on a line.  This can be used even if you have not
configured mypy to show error codes. Currently it's only possible to
disable arbitrary error codes on individual lines using this comment.

.. note::

  There are command-line flags and config file settings for enabling
  certain optional error codes, such as ``--disallow-untype-defs``,
  which enables the ``no-untyped-def`` error code.

Here is how we ignore an error about an imported name mypy thinks is
undefined:

.. code-block:: python

   # Assume 'foo' is defined in 'foolib', even though mypy
   # can't see the definition.

   from foolib import foo  # type: ignore[attr-defined]

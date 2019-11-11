.. _error-codes:

Error codes
===========

Mypy can optionally display an error code such as ``[attr-defined]``
after each error message. Error codes serve two purposes:

1. It's possible to silence specific error codes on a line using ``#
   type: ignore[code]``. This way you won't accidentally ignore other,
   potentially more serious errors.

2. The error code can be used to find documentation about the error.
   The next two topics (:ref:`error-code-list` and
   :ref:`error-codes-optional`) document the various error codes
   mypy can report.

Most error codes are shared between multiple related error messages.
Error codes may change in future mypy releases.



Displaying error codes
----------------------

Error codes are not displayed by default.  Use :option:`--show-error-codes <mypy --show-error-codes>`
to display error codes. Error codes are shown inside square brackets:

.. code-block:: text

   $ mypy --show-error-codes prog.py
   prog.py:1: error: "str" has no attribute "trim"  [attr-defined]

Silencing errors based on error codes
-------------------------------------

You can use a special comment ``# type: ignore[code, ...]`` to only
ignore errors with a specific error code (or codes) on a particular
line.  This can be used even if you have not configured mypy to show
error codes. Currently it's only possible to disable arbitrary error
codes on individual lines using this comment.

.. note::

  There are command-line flags and config file settings for enabling
  certain optional error codes, such as :option:`--disallow-untyped-defs <mypy --disallow-untyped-defs>`,
  which enables the ``no-untyped-def`` error code.

This example shows how to ignore an error about an imported name mypy
thinks is undefined:

.. code-block:: python

   # 'foo' is defined in 'foolib', even though mypy can't see the
   # definition.
   from foolib import foo  # type: ignore[attr-defined]

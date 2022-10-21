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

Error codes are displayed by default.  Use :option:`--hide-error-codes <mypy --hide-error-codes>`
or config ``hide_error_codes = True`` to hide error codes. Error codes are shown inside square brackets:

.. code-block:: text

   $ mypy prog.py
   prog.py:1: error: "str" has no attribute "trim"  [attr-defined]

It's also possible to require error codes for ``type: ignore`` comments.
See :ref:`ignore-without-code<ignore-without-code>` for more information.


.. _silence-error-codes:

Silencing errors based on error codes
-------------------------------------

You can use a special comment ``# type: ignore[code, ...]`` to only
ignore errors with a specific error code (or codes) on a particular
line.  This can be used even if you have not configured mypy to show
error codes. Currently it's only possible to disable arbitrary error
codes on individual lines using this comment.

You can also use :option:`--disable-error-code <mypy --disable-error-code>`
to disable specific error codes globally.

This example shows how to ignore an error about an imported name mypy
thinks is undefined:

.. code-block:: python

   # 'foo' is defined in 'foolib', even though mypy can't see the
   # definition.
   from foolib import foo  # type: ignore[attr-defined]


Enabling specific error codes
-----------------------------

There are command-line flags and config file settings for enabling
certain optional error codes, such as :option:`--disallow-untyped-defs <mypy --disallow-untyped-defs>`,
which enables the ``no-untyped-def`` error code.

You can use :option:`--enable-error-code <mypy --enable-error-code>` to
enable specific error codes that don't have a dedicated command-line
flag or config file setting.

Per-module enabling/disabling error codes
-----------------------------------------

You can use :ref:`configuration file <config-file>` sections to enable or
disable specific error codes only in some modules. For example, this ``mypy.ini``
config will enable non-annotated empty containers in tests, while keeping
other parts of code checked in strict mode:

.. code-block:: ini

   [mypy]
   strict = True

   [mypy-tests.*]
   allow_untyped_defs = True
   allow_untyped_calls = True
   disable_error_code = var-annotated, has-type

Note that per-module enabling/disabling acts as override over the global
options. So that you don't need to repeat the error code lists for each
module if you have them in global config section. For example:

.. code-block:: ini

   [mypy]
   enable_error_code = truthy-bool, ignore-without-code, unused-awaitable

   [mypy-extensions.*]
   disable_error_code = unused-awaitable

The above config will allow unused awaitables in extension modules, but will
still keep the other two error codes enabled. The overall logic is following:

* Command line and/or config main section set global error codes

* Individual config sections *adjust* them per glob/module

* Inline ``# mypy: ...`` comments can further *adjust* them for a specific
  module

So one can e.g. enable some code globally, disable it for all tests in
the corresponding config section, and then re-enable it with an inline
comment in some specific test.

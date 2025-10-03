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


.. _silence-error-codes:

Silencing errors based on error codes
-------------------------------------

You can use a special comment ``# type: ignore[code, ...]`` to only
ignore errors with a specific error code (or codes) on a particular
line.  This can be used even if you have not configured mypy to show
error codes.

This example shows how to ignore an error about an imported name mypy
thinks is undefined:

.. code-block:: python

   # 'foo' is defined in 'foolib', even though mypy can't see the
   # definition.
   from foolib import foo  # type: ignore[attr-defined]

Enabling/disabling specific error codes globally
------------------------------------------------

There are command-line flags and config file settings for enabling
certain optional error codes, such as :option:`--disallow-untyped-defs <mypy --disallow-untyped-defs>`,
which enables the ``no-untyped-def`` error code.

You can use :option:`--enable-error-code <mypy --enable-error-code>`
and :option:`--disable-error-code <mypy --disable-error-code>`
to enable or disable specific error codes that don't have a dedicated
command-line flag or config file setting.

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

* Inline ``# mypy: disable-error-code="..."`` and ``# mypy: enable-error-code="..."``
  comments can further *adjust* them for a specific file.
  For example:

.. code-block:: python

  # mypy: enable-error-code="truthy-bool, ignore-without-code"

So one can e.g. enable some code globally, disable it for all tests in
the corresponding config section, and then re-enable it with an inline
comment in some specific test.

Subcodes of error codes
-----------------------

In some cases, mostly for backwards compatibility reasons, an error
code may be covered also by another, wider error code. For example, an error with
code ``[method-assign]`` can be ignored by ``# type: ignore[assignment]``.
Similar logic works for disabling error codes globally. If a given error code
is a subcode of another one, it will be mentioned in the documentation for the narrower
code. This hierarchy is not nested: there cannot be subcodes of other
subcodes.


Requiring error codes
---------------------

It's possible to require error codes be specified in ``type: ignore`` comments.
See :ref:`ignore-without-code<code-ignore-without-code>` for more information.

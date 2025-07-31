.. _exit-codes:

Exit codes
===========

Mypy, like all programs, returns an
`exit code <https://en.wikipedia.org/wiki/Exit_status>`_ to the process or shell
that invokes it. The meaning of these codes is thus:

* 0: no type errors

* 1: there are some type errors

* 2: a crash, bad arguments, and other non-standard conditions relating to mypy

There is currently `a bug <https://github.com/python/mypy/issues/19548>`_
in which certain configuration errors will result in an exit code of 0 instead
of 2.

Note: the exit code is completely unrelated to mypy-internal :ref:`error-codes`.

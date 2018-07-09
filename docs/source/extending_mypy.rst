.. _extending-mypy:

Extending and integrating mypy
==============================

.. _integrating-mypy:

Integrating mypy into another Python application
************************************************

It is possible to integrate mypy into another Python 3 application by
importing ``mypy.api`` and calling the ``run`` function with a parameter of type ``List[str]``, containing
what normally would have been the command line arguments to mypy.

Function ``run`` returns a ``Tuple[str, str, int]``, namely
``(<normal_report>, <error_report>, <exit_status>)``, in which ``<normal_report>``
is what mypy normally writes to ``sys.stdout``, ``<error_report>`` is what mypy
normally writes to ``sys.stderr`` and ``exit_status`` is the exit status mypy normally
returns to the operating system.

A trivial example of using the api is the following

.. code-block:: python

    import sys
    from mypy import api

    result = api.run(sys.argv[1:])

    if result[0]:
        print('\nType checking report:\n')
        print(result[0])  # stdout

    if result[1]:
        print('\nError report:\n')
        print(result[1])  # stderr

    print ('\nExit status:', result[2])

Extending mypy using plugins
****************************

Mypy supports a plugin system that lets you customize the way mypy type checks
code. This can be useful if you want to extend mypy so it can type check code
that uses a library that is difficult to express using just PEP 484 types, for
example.

*Warning:* The plugin system is extremely experimental and prone to change. If you want
to contribute a plugin to mypy, we recommend you start by contacting the mypy
core developers either on `gitter <https://gitter.im/python/typing>`_ or on mypy's
`issue tracker <https://github.com/python/mypy/issues>`_.


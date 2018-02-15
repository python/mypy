.. _installed-packages:

Using Installed Packages
========================

`PEP 561 <https://www.python.org/dev/peps/pep-0561/>`_ specifies how to mark
a package as supporting type checking. Below is a summary of how to create
PEP 561 compatible packages and have mypy use them in type checking.

Making PEP 561 compatible packages
**********************************

Packages that must be imported at runtime that supply type information should
put a ``py.typed`` in their package directory. For example, with a directory
structure as follows:

.. code-block:: text

    setup.py
    package_a/
        __init__.py
        lib.py
        py.typed

    the setup.py might look like:

    .. code-block:: python

    from distutils.core import setup

    setup(
        name="SuperPackageA",
        author="Me",
        version="0.1",
        package_data={"package_a": ["py.typed"]},
        packages=["package_a"]
    )

If the package is entirely made up of stub (``*.pyi``) files, the package
should have a suffix of ``-stubs``. For example, if we had stubs for
``package_b``, we might do the following:

.. code-block:: text

    setup.py
    package_b-stubs/
        __init__.pyi
        lib.pyi

    the setup.py might look like:

    .. code-block:: python

    from distutils.core import setup

    setup(
        name="SuperPackageB",
        author="Me",
        version="0.1",
        package_data={"package_b-stubs": ["__init__.pyi", "lib.pyi"]},
        packages=["package_b-stubs"]
    )

Using PEP 561 compatible packages with mypy
*******************************************

Generally, you do not need to do anything to use installed packages for the
Python executable used to run mypy. They should be automatically picked up by
mypy and used for type checking.

If you use mypy to type check a Python other than the version running mypy, you
can use the ``--python-executable`` flag to point to the executable, and mypy
will find packages installed for that python executable.
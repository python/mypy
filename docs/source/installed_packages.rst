.. _installed-packages:

Using Installed Packages
========================

One common pattern of modularizing Python code is through packages, which are
collections of modules (``*.py`` files). Packages usually have ``__init__.py``
files in them.

Packages can be uploaded to PyPi and installed via ``pip`` as part of
distributions. Python installations have special directories to place packages
installed through tools such as ``pip``.

`PEP 561 <https://www.python.org/dev/peps/pep-0561/>`_ specifies how to mark
an installed package as supporting type checking. Supporting type checking
means that the package can be used as a source of type information for tools
like mypy.

There are three main kinds of typed packages. The first is a
package that has only inline type annotations in the code itself. The second is
a package that ships stub files with type information alongside the runtime
code. The third method, also known as a "stub only package" is a package that
ships type information for a package seperately as stub files.

These packages differ from the stubs in typeshed as they are installable
through, for example ``pip``, instead of tied to a mypy release. In addition,
they allow for the distribution of type information seperate from the regular
package itself.

Below is a summary of how to make sure mypy is finding installed typed packages
and how to create PEP 561 compatible packages of your own.

Using PEP 561 compatible packages with mypy
*******************************************

Generally, you do not need to do anything to use installed packages for the
Python executable used to run mypy. They should be automatically picked up by
mypy and used for type checking.

By default, mypy searches for packages installed for the Python executable
running mypy. It is highly unlikely you want this situation if you have
installed typed packages in another Python's package directory.

Generally, you can use the ``--python-version`` flag and mypy will try to find
the correct package directory. If that fails, you can use the
``--python-executable`` flag to point to the exact executable, and mypy will
find packages installed for that Python executable.

Note that mypy does not support some more advanced import features, such as zip
imports, namespace packages, and custom import hooks.

If you do not want to use typed packages, use the ``--no-site-packages`` flag
to disable searching.

Making PEP 561 compatible packages
**********************************

Packages that must be used at runtime and supply type information via type
comments or annotations in the code should put a ``py.typed`` in their package
directory. For example, with a directory structure as follows:

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

Some packages have a mix of stub files and runtime files. These packages also
require a ``py.typed`` file. An example can be seen below:

.. code-block:: text

    setup.py
    package_b/
        __init__.py
        lib.py
        lib.pyi
        py.typed

the setup.py might look like:

.. code-block:: python

    from distutils.core import setup

    setup(
        name="SuperPackageB",
        author="Me",
        version="0.1",
        package_data={"package_b": ["py.typed", "lib.pyi"]},
        packages=["package_b"]
    )

In this example, both ``lib.py`` and ``lib.pyi`` exist. At runtime, the Python
interpeter will use ``lib.py``, but mypy will use ``lib.pyi`` instead.

If the package is stub-only (not imported at runtime), the package should have
a prefix of the runtime package name and a suffix of ``-stubs``.
A ``py.typed`` file is not needed for stub-only packages. For example, if we
had stubs for ``package_c``, we might do the following:

.. code-block:: text

    setup.py
    package_c-stubs/
        __init__.pyi
        lib.pyi

the setup.py might look like:

.. code-block:: python

    from distutils.core import setup

    setup(
        name="SuperPackageC",
        author="Me",
        version="0.1",
        package_data={"package_c-stubs": ["__init__.pyi", "lib.pyi"]},
        packages=["package_c-stubs"]
    )

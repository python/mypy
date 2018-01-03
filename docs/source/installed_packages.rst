Using Installed Packages
========================


Making PEP 561 compatible packages
**********************************

Packages that supply type information should put a ``py.typed`` in their package
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
    name="SuperPackage",
    author="Me",
    version="0.1",
    package_data={"package_a": ["py.typed"]},
    packages=["package_a"]
)


Using PEP 561 compatible packages with mypy
*******************************************

PEP 561 specifies a format to indicate a package installed in site-packages or
dist-packages supports providing type information. Generally, you do not need
to do anything to use these packages. They should be automatically picked up by
mypy and used for type checking.

If you use mypy to type check a Python other than the version running mypy, you
can use the ``--python`` flag to point to the executable, and mypy will pick up
the site/dist-packages for the Python executable pointed to.
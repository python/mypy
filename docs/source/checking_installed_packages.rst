.. _checking-installed-packages:

Using and Creating Typed Packages for Distribution
==================================================

`PEP 561 <https://www.python.org/dev/peps/pep-0561/>`_ specifies how to mark
a package as supporting type checking. Below is a summary of how to use this
feature and create PEP 561 compatible packages.


Creating Typed Packages
***********************

For a typed package to be picked up by mypy, you must put a file named
``py.typed`` in each top level package installed. For example, your directory
structure may look like:

.. code::

    setup.py
    my_pkg/
        __init__.py
        py.typed
        file.py

Note that if ``my_pkg`` has subpackages, they do *not* need to have their own
``py.typed`` file marker.


Checking Typed Packages
***********************

Installed packages for the Python being checked should be picked up if they
opt into type checking. If the Python version being checked is different
from the version running mypy, you also need to point mypy to find it via
``--python``.
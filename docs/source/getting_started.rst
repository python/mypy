.. _getting-started:

Getting started
===============

Installation
************

Mypy requires Python 3.3 or later.  Once you've `installed Python 3 <https://www.python.org/downloads/>`_, you can install mypy with:

.. code-block:: text

    $ python3 -m pip install mypy-lang

Note that the package name is ``mypy-lang`` and not just ``mypy``, as unfortunately the ``mypy`` PyPI name is not available.

Installing from source
**********************

To install mypy from source, clone the github repository and then run pip install locally:

.. code-block:: text

    $ git clone https://github.com/python/mypy.git
    $ cd mypy
    $ sudo python3 -m pip install --upgrade .

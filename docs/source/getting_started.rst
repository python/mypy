.. _getting-started:

Getting started
===============

Installation
************

Mypy requires Python 3.4 or later.  Once you've `installed Python 3 <https://www.python.org/downloads/>`_,
you can install mypy with:

.. code-block:: text

    $ python3 -m pip install mypy

Installing from source
**********************

To install mypy from source, clone the github repository and then run
``pip install`` locally:

.. code-block:: text

    $ git clone --recurse-submodules https://github.com/python/mypy.git
    $ cd mypy
    $ sudo python3 -m pip install --upgrade .

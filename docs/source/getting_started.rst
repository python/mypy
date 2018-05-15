.. _getting-started:

Getting started
===============

Installation
************

Mypy requires Python 3.4 or later to run.  Once you've
`installed Python 3 <https://www.python.org/downloads/>`_,
you can install mypy with:

.. code-block:: text

    $ python3 -m pip install mypy

Note that even though you need Python 3 to run ``mypy``, type checking
Python 2 code is fully supported, as discussed in :ref:`python2`.

Installing from source
**********************

To install mypy from source, clone the
`mypy repository on GitHub <https://github.com/python/mypy>`_ and then run
``pip install`` locally:

.. code-block:: text

    $ git clone --recurse-submodules https://github.com/python/mypy.git
    $ cd mypy
    $ sudo python3 -m pip install --upgrade .

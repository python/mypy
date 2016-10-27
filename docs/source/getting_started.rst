Getting Started
===============

This page will be about getting started with mypy. We will begin by explaining
how to get mypy running on your system and finally how to start working with.

Installation
************

Let’s get into using mypy. First things first—you have to install it.
You can get it a number of ways; the two major ones are to install it
from source or to install an existing package for your platform.

You need Python 3.3 or later to run mypy. You can have multiple
Python versions (2.x and 3.x) installed on the same system without problems.

For Linux flavors, OS X and Windows, packages are available at https://www.python.org/getit.

Installing from Source
**********************

To install mypy, download package, cd to the mypy directory
and run the install command:

.. code-block:: text

    $ git clone https://github.com/python/mypy.git
    $ cd mypy
    $ sudo python3 setup.py install

Installing from Package
***********************

A universal installation method (that works on Windows, Mac OS X, Linux, …,
and provides the latest version) is to use pip3:

.. code-block:: text

    $ pip3 install mypy-lang

On Mac OS X, mypy can be installed via homebrew:

.. code-block:: text

    $ brew install mypy

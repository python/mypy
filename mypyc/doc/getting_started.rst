Getting started
===============

Here you will learn some basic things you need to know to get started with mypyc.

Prerequisites
-------------

You need a Python C extension development environment. The way to set this up
depends on your operating system.

macOS
*****

Install Xcode command line tools:

.. code-block::

    $ xcode-select --install

Linux
*****

You need a C compiler and CPython headers and libraries. The specifcs
of how to instal these varies by distribution. Here are instructions for
Ubuntu 18.04, for example:

.. code-block::

    $ sudo apt install python3-dev

Windows
*******

Install `Visual C++ <https://www.visualstudio.com/downloads/#build-tools-for-visual-studio-2017>`_.

Installation
------------

Mypyc is shipped as part of the mypy distribution. Install mypy like
this (you need Python 3.5 or later):

.. code-block::

    $ python3 -m pip install mypy

On some systems you need to use this instead:

.. code-block::

    $ python -m pip install mypy

Compile and run a program
-------------------------

Let's compile a classic micro-benchmark, recursive fibonacci. Save
this file as ``fib.py``:

.. code-block:: python

   import time

   def fib(n: int) -> int:
       if n <= 1:
           return n
       else:
           return fib(n - 2) + fib(n - 1)

   t0 = time.time()
   fib(32)
   print(time.time() - t0)

Note that we added type annotations to ``fib``. Without them, the
performance will not be improved as much when compiled.  Now we can
run it as a regular, interpreted program using CPython:

.. code-block:: console

    $ python3 fib.py
    0.4125328063964844

It took about 0.41s to run on my computer.

Run ``mypyc`` to compile the program to a C extension:

.. code-block:: console

    $ mypyc fib.py

This will generate a C extension for ``fib`` in the current working
directory.  For example, on a Linux system the generated file may be
called ``fib.cpython-37m-x86_64-linux-gnu.so``.

Since C extensions can't be run as programs, use ``python3 -c`` to run
the compiled module as a program:

.. code-block:: console

    $ python3 -c "import fib"
    0.04097270965576172

After compilation, the program is about 10x faster than previously. Nice!

.. note::

   ``__name__`` in ``fib.py`` would now be ``"fib"``, not ``"__main__"``.


Delete compiled binary
----------------------

You can manually delete the C extension to get back to an interpreted
version (this example works on Linux):

.. code-block::

    $ rm fib.*.so

Compile using setup.py
----------------------

TODO

Recommended workflow
--------------------

TODO

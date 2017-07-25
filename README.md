mypyc: Mypy to Python C Extension Compiler
==========================================

*Mypyc is very early in development and not yet useful for anything.*

Mypyc is a compiler that aims to eventually compile mypy-annotated,
statically typed Python modules into Python C extensions.

MacOS Requirements
------------------

* macOS Sierra

* Xcode command line tools

* Python 3.6 (64-bit) from python.org (other versions likely *won't*
  work right now)

Linux Requirements
------------------

* A recent enough C/C++ build environment

* Python 3.5+ (64-bit)

Windows Requirements
--------------------

Windows is currently unsupported.

Quick Start for Contributors
----------------------------

First clone the mypyc git repository *and git submodules*:

    $ git clone --recurse-submodules https://github.com/JukkaL/mypyc.git

Then install the dependencies:

    $ cd mypyc
    $ python3 -m pip install -r mypy/test-requirements.txt

You need to have the `mypy` subdirectory in your `PYTHONPATH`:

    $ export PYTHONPATH=`pwd`/mypy

Now you can run the tests:

    $ pytest mypyc

Look at the [issue tracker](https://github.com/JukkaL/mypyc/issues)
for things to work on.

Documentation
-------------

We have some [developer documentation](doc/dev-intro.md).

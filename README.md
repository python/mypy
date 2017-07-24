mypyc: Mypy to Python C Extension Compiler
==========================================

*Mypyc is very early in development and not yet useful for anything.*

Mypyc is a compiler that aims to eventually compile mypy-annotated,
statically typed Python modules into Python C extensions.

Quick Start for Contributors
----------------------------

First clone the mypyc git repository:

    $ git clone --recurse-submodules https://github.com/JukkaL/mypyc.git

Then install the dependencies:

    $ cd mypyc
    $ python3 -m pip install -r mypy/test-requirements.txt

You'll also need a working C/C++ build environment. On macOS, you need
the Xcode command line tools. Linux and Windows are currently not
supported as development environments.

Now you can run the tests:

    $ pytest mypyc

Look at the [issue tracker](https://github.com/JukkaL/mypyc/issues)
for things to work on.

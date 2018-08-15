mypyc: Mypy to Python C Extension Compiler
==========================================

*Mypyc is very early in development and not yet useful for anything.*

Mypyc is a compiler that aims to eventually compile mypy-annotated,
statically typed Python modules into Python C extensions.

MacOS Requirements
------------------

* macOS Sierra or later

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
    $ cd mypyc

Optionally create a virtualenv (recommended):

    $ virtualenv -p python3 <directory>
    $ source <directory>/bin/activate

Then install the dependencies:

    $ python3 -m pip install -r external/mypy/test-requirements.txt

You need to have the `mypy` subdirectory in your `PYTHONPATH`:

    $ export PYTHONPATH=`pwd`/external/mypy

Now you can run the tests:

    $ pytest mypyc

Look at the [issue tracker](https://github.com/JukkaL/mypyc/issues)
for things to work on. Please express your interest in working on an
issue by adding a comment before doing any significant work, since
development is currently very active and there is real risk of duplicate
work.

Documentation
-------------

We have some [developer documentation](doc/dev-intro.md).

Development Roadmap
-------------------

These are the current planned major milestones:

1. [DONE] Support a smallish but useful Python subset. Focus on compiling
   single modules, while the rest of the program is interpreted and does not
   need to be type checked.

2. [DONE] Support compiling multiple modules as a single compilation unit (or
   dynamic linking of compiled modules).  Without this inter-module
   calls will use slower Python-level objects, wrapper functions and
   Python namespaces.

3. Self-compilation (at least mypy).

4. Optimize some important performance bottlenecks.

5. Generate useful errors for code that uses unsupported Python
   features instead of crashing or generating bad code.

Future
------

We have some ideas for
[future improvements and optimizations](doc/future.md).

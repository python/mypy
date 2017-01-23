Mypy: Optional Static Typing for Python
=======================================

[![Build Status](https://travis-ci.org/python/mypy.svg)](https://travis-ci.org/python/mypy)
[![Chat at https://gitter.im/python/mypy](https://badges.gitter.im/python/mypy.svg)](https://gitter.im/python/mypy?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)


Got a question? File an issue!
------------------------------

We don't have a mailing list; but we are always happy to answer
questions on [gitter chat](https://gitter.im/python/mypy) or filed as
issues in our trackers:

- [mypy tracker](https://github.com/python/mypy/issues)
  for mypy isues
- [typeshed tracker](https://github.com/python/typeshed/issues)
  for issues with specific modules
- [typing tracker](https://github.com/python/typing/issues)
  for discussion of new type system features (PEP 484 changes) and
  runtime bugs in the typing module

What is mypy?
-------------

Mypy is an optional static type checker for Python.  You can add type
hints to your Python programs using the standard for type
annotations introduced in Python 3.5 ([PEP 484](https://www.python.org/dev/peps/pep-0484/)), and use mypy to
type check them statically. Find bugs in your programs without even
running them!

The type annotation standard has also been backported to earlier
Python 3.x versions.  Mypy supports Python 3.3 and later.

For Python 2.7, you can add annotations as comments (this is also
specified in [PEP 484](https://www.python.org/dev/peps/pep-0484/)).

You can mix dynamic and static typing in your programs. You can always
fall back to dynamic typing when static typing is not convenient, such
as for legacy code.

Here is a small example to whet your appetite:

```python
from typing import Iterator

def fib(n: int) -> Iterator[int]:
    a, b = 0, 1
    while a < n:
        yield a
        a, b = b, a + b
```

Mypy is in development; some features are missing and there are bugs.
See 'Development status' below.


Requirements
------------

You need Python 3.3 or later to run mypy.  You can have multiple Python
versions (2.x and 3.x) installed on the same system without problems.

In Ubuntu, Mint and Debian you can install Python 3 like this:

    $ sudo apt-get install python3 python3-pip

For other Linux flavors, OS X and Windows, packages are available at

  http://www.python.org/getit/


Quick start
-----------

Mypy can be installed using pip:

    $ python3 -m pip install -U mypy

If you want to run the latest version of the code, you can install from git:

    $ python3 -m pip install -U git+git://github.com/python/mypy.git


Now, if Python on your system is configured properly (else see
"Troubleshooting" below), you can type-check the [statically typed parts] of a
program like this:

    $ mypy PROGRAM

You can always use a Python interpreter to run your statically typed
programs, even if they have type errors:

    $ python3 PROGRAM

[statically typed parts]: http://mypy.readthedocs.io/en/latest/basics.html#function-signatures


Web site and documentation
--------------------------

Documentation and additional information is available at the web site:

  http://www.mypy-lang.org/

Or you can jump straight to the documentation:

  http://mypy.readthedocs.io/


Troubleshooting
---------------

Depending on your configuration, you may have to run `pip3` like
this:

    $ python3 -m pip install -U mypy

Except on Windows, it's best to always use the `--fast-parser`
option to mypy; this requires installing `typed-ast`:

    $ python3 -m pip install -U typed-ast

If the `mypy` command isn't found after installation: After either
`pip3 install` or `setup.py install`, the `mypy` script and
dependencies, including the `typing` module, will be installed to
system-dependent locations.  Sometimes the script directory will not
be in `PATH`, and you have to add the target directory to `PATH`
manually or create a symbolic link to the script.  In particular, on
Mac OS X, the script may be installed under `/Library/Frameworks`:

    /Library/Frameworks/Python.framework/Versions/<version>/bin

In Windows, the script is generally installed in
`\PythonNN\Scripts`. So, type check a program like this (replace
`\Python34` with your Python installation path):

    C:\>\Python34\python \Python34\Scripts\mypy PROGRAM

### Working with `virtualenv`

If you are using [`virtualenv`](https://virtualenv.pypa.io/en/stable/),
make sure you are running a python3 environment. Installing via `pip3`
in a v2 environment will not configure the environment to run installed
modules from the command line.

    $ python3 -m pip install -U virtualenv
    $ python3 -m virtualenv env


Quick start for contributing to mypy
------------------------------------

If you want to contribute, first clone the mypy git repository:

    $ git clone --recurse-submodules https://github.com/python/mypy.git

From the mypy directory, use pip to install mypy:

    $ cd mypy
    $ python3 -m pip install -U .

Replace `python3` with your Python 3 interpreter.  You may have to do
the above as root. For example, in Ubuntu:

    $ sudo python3 -m pip install -U .

Now you can use the `mypy` program just as above.  In case of trouble
see "Troubleshooting" above.

The mypy wiki contains some useful information for contributors:

  https://github.com/python/mypy/wiki/Developer-Guides

Working with the git version of mypy
------------------------------------

mypy contains a submodule, "typeshed". See http://github.com/python/typeshed.
This submodule contains types for the Python standard library.

Due to the way git submodules work, you'll have to do
```
  git submodule update typeshed
```
whenever you change branches, merge, rebase, or pull.

(It's possible to automate this: Search Google for "git hook update submodule")

Running tests and linting
-------------------------

First install any additional dependencies needed for testing:

    $ python3 -m pip install -U -r test-requirements.txt

To run all tests, run the script `runtests.py` in the mypy repository:

    $ ./runtests.py

Note that some tests will be disabled for older python versions.

This will run all tests, including integration and regression tests,
and will type check mypy and verify that all stubs are valid.

You can run a subset of test suites by passing positive or negative
filters:

    $ ./runtests.py lex parse -x lint -x stub

For example, to run unit tests only, which run pretty quickly:

    $ ./runtests.py unit-test pytest

The unit test suites are driven by a mixture of test frameworks:
mypy's own `myunit` framework, and `pytest`, which we're in the
process of migrating to.  For finer control over which unit tests are
run and how, you can run `py.test` or `scripts/myunit` directly, or
pass inferior arguments via `-a`:

    $ py.test mypy/test/testcheck.py -v -k MethodCall
    $ ./runtests.py -v 'pytest mypy/test/testcheck' -a -v -a -k -a MethodCall

    $ PYTHONPATH=$PWD scripts/myunit -m mypy.test.testlex -v '*backslash*'
    $ ./runtests.py mypy.test.testlex -a -v -a '*backslash*'

You can also run the type checker for manual testing without
installing anything by setting up the Python module search path
suitably (the lib-typing/3.2 path entry is not needed for Python 3.5
or when you have manually installed the `typing` module):

    $ export PYTHONPATH=$PWD:$PWD/lib-typing/3.2
    $ python<version> -m mypy PROGRAM.py

You can add the entry scripts to PATH for a single python3 version:

    $ export PATH=$PWD/scripts
    $ mypy PROGRAM.py

You can check a module or string instead of a file:

    $ mypy PROGRAM.py
    $ mypy -m MODULE
    $ mypy -c 'import MODULE'

To run the linter:

    $ ./runtests.py lint


Coverage reports
----------------

There is an experimental feature to generate coverage reports.  To use
this feature, you need to `pip install -U lxml`.  This is an extension
module and requires various library headers to install; on a
Debian-derived system the command
  `apt-get install python3-dev libxml2-dev libxslt1-dev`
may provide the necessary dependencies.

To use the feature, pass e.g. `--txt-report "$(mktemp -d)"`.


Development status
------------------

Mypy is work in progress and is not yet production quality, though
mypy development has been done using mypy for a while!

Here are some of the more significant Python features not supported
right now (but all of these will improve):

 - properties with setters not supported
 - limited metaclass support
 - only a subset of Python standard library modules are supported, and some
   only partially
 - 3rd party module support is limited

The current development focus is to have a good coverage of Python
features and the standard library (both 3.x and 2.7).


Issue tracker
-------------

Please report any bugs and enhancement ideas using the mypy issue
tracker:

  https://github.com/python/mypy/issues

Feel free to also ask questions on the tracker.


Help wanted
-----------

Any help in testing, development, documentation and other tasks is
highly appreciated and useful to the project. There are tasks for
contributors of all experience levels. If you're just getting started,
check out the
[difficulty/easy](https://github.com/python/mypy/labels/difficulty%2Feasy)
label.

For more details, see the file [CONTRIBUTING.md](CONTRIBUTING.md).


License
-------

Mypy is licensed under the terms of the MIT License (see the file
LICENSE).

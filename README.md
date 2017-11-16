Mypy: Optional Static Typing for Python
=======================================

[![Build Status](https://api.travis-ci.org/python/mypy.svg?branch=master)](https://travis-ci.org/python/mypy)
[![Chat at https://gitter.im/python/typing](https://badges.gitter.im/python/typing.svg)](https://gitter.im/python/typing?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)


Got a question? Join us on Gitter!
----------------------------------

We don't have a mailing list; but we are always happy to answer
questions on [gitter chat](https://gitter.im/python/typing).  If you are
sure you've found a bug please search our issue trackers for a
duplicate before filing a new issue:

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
hints ([PEP 484](https://www.python.org/dev/peps/pep-0484/)) to your
Python programs, and use mypy to type check them statically.
Find bugs in your programs without even running them!

You can mix dynamic and static typing in your programs. You can always
fall back to dynamic typing when static typing is not convenient, such
as for legacy code.

Here is a small example to whet your appetite (Python 3):

```python
from typing import Iterator

def fib(n: int) -> Iterator[int]:
    a, b = 0, 1
    while a < n:
        yield a
        a, b = b, a + b
```
See [the documentation](http://mypy.readthedocs.io/en/stable/introduction.html) for more examples.

For Python 2.7, the standard annotations are written as comments:
```python
def is_palindrome(s):
    # type: (str) -> bool
    return s == s[::-1]
```

See [the documentation for Python 2 support](http://mypy.readthedocs.io/en/latest/python2.html).

Mypy is in development; some features are missing and there are bugs.
See 'Development status' below.

Requirements
------------

You need Python 3.4 or later to run mypy.  You can have multiple Python
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


IDE & Linter Integrations
-------------------------

Mypy can be integrated into popular IDEs:

* Vim: [vim-mypy](https://github.com/Integralist/vim-mypy)
* Emacs: using [Flycheck](https://github.com/flycheck/) and [Flycheck-mypy](https://github.com/lbolla/emacs-flycheck-mypy)
* Sublime Text: [SublimeLinter-contrib-mypy](https://github.com/fredcallaway/SublimeLinter-contrib-mypy)
* Atom: [linter-mypy](https://atom.io/packages/linter-mypy)
* PyCharm: PyCharm integrates [its own implementation of PEP 484](https://www.jetbrains.com/help/pycharm/2017.1/type-hinting-in-pycharm.html).

Mypy can also be integrated into [Flake8] using [flake8-mypy].

[Flake8]: http://flake8.pycqa.org/
[flake8-mypy]: https://github.com/ambv/flake8-mypy


Web site and documentation
--------------------------

Documentation and additional information is available at the web site:

  http://www.mypy-lang.org/

Or you can jump straight to the documentation:

  http://mypy.readthedocs.io/


Troubleshooting
---------------

Depending on your configuration, you may have to run `pip` like
this:

    $ python3 -m pip install -U mypy

This should automatically installed the appropriate version of
mypy's parser, typed-ast.  If for some reason it does not, you
can install it manually:

    $ python3 -m pip install -U typed-ast

If the `mypy` command isn't found after installation: After
`python3 -m pip install`, the `mypy` script and
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

If you've already cloned the repo without `--recurse-submodules`,
you need to pull in the typeshed repo as follows:

    $ git submodule init
    $ git submodule update

Either way you should now have a subdirectory `typeshed` containing a
clone of the typeshed repo (`https://github.com/python/typeshed`).

From the mypy directory, use pip to install mypy:

    $ cd mypy
    $ python3 -m pip install -U .

Replace `python3` with your Python 3 interpreter.  You may have to do
the above as root. For example, in Ubuntu:

    $ sudo python3 -m pip install -U .

Now you can use the `mypy` program just as above.  In case of trouble
see "Troubleshooting" above.


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


Tests
-----

See [Test README.md](test-data/unit/README.md)


Development status
------------------

Mypy is alpha software, but it has already been used in production
for well over a year at Dropbox, and it has an extensive test suite.

See [the roadmap](ROADMAP.md) if you are interested in plans for the
future.


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
ask on the [gitter chat](https://gitter.im/python/typing) for ideas of good
beginner issues.

For more details, see the file [CONTRIBUTING.md](CONTRIBUTING.md).


License
-------

Mypy is licensed under the terms of the MIT License (see the file
LICENSE).

Mypy Readme
===========

[![Build Status](https://travis-ci.org/JukkaL/mypy.svg)](https://travis-ci.org/JukkaL/mypy)


What is mypy?
-------------

Mypy is an optional static type checker for Python.  You can add type
annotations to your Python programs and use mypy to type check them
statically to find errors before running them.  You can also
seamlessly mix dynamic and static typing in your programs, so you can
always fall back to dynamic typing.  Mypy programs are valid Python
3.x and you use a normal Python interpreter to run them. There is
essentially no performance overhead when using mypy, since mypy does
not introduce additional runtime type checking.

Here is a small example to whet your appetite:

    from typing import Iterator

    def fib(n: int) -> Iterator[int]:
        a, b = 0, 1
        while a < n:
            yield a
            a, b = b, a + b

Mypy is in development; some features are missing and there are bugs.
See 'Development status' below.


Requirements
------------

You need Python 3.2 or later to run mypy.  You can have multiple Python
versions (2.x and 3.x) installed on the same system without problems.

In Ubuntu, Mint and Debian you can install Python 3 like this:

    $ sudo apt-get install python3

For other Linux flavors, OS X and Windows, packages are available at

  http://www.python.org/getit/


Quick start
-----------

If you have git, first clone the mypy git repository:

    $ git clone https://github.com/JukkaL/mypy.git

Alternatively, you can download the latest development version as a
zip archive from this URL:

  https://github.com/JukkaL/mypy/archive/master.zip

Run the supplied setup.py script to install mypy:

    $ python3 setup.py install

Replace 'python3' with your Python 3 interpreter.  You may have to do
the above as root. For example, in Ubuntu and Mac OS X:

    $ sudo python3 setup.py install

This installs the 'mypy' script and dependencies, including the
'typing' module, to system-dependent locations.  Sometimes the script
directory will not be in PATH, and you have to add the target
directory to PATH manually or create a symbolic link to the script.
In particular, on Mac OS X, the script may be installed under
/Library/Frameworks:

    /Library/Frameworks/Python.framework/Versions/<version>/bin

Now, on a Unix-like system, you can type check a program like this:

    $ mypy PROGRAM

In Windows, the script is generally installed in
\PythonNN\Scripts. So, type check a program like this (replace
\Python33 with your Python installation path):

    C:\>\Python33\python \Python33\Scripts\mypy PROGRAM

You can always use a Python interpreter to run your statically typed
programs, even if they have type errors:

    $ python3 PROGRAM


Web site and documentation
--------------------------

Documentation and additional information is available at the web site:

  http://www.mypy-lang.org/


Running tests
-------------

To run tests, run the script 'tests.py' in the mypy repository:

    $ python3 tests.py


Development status
------------------

Mypy is work in progress and is not yet production quality (though
mypy development is already done in mypy!).

Here are some of the more significant Python features not supported
right now (but all of these will improve):

 - Python 2.x support not really yet usable
 - properties with setters not supported
 - relative imports not supported
 - somewhat limited operator overloading
 - only a subset of Python standard library modules are supported, and some
   only partially
 - limited metaclass support

Some mypy-specific features are also not supported or only partially
supported, including these:

 - function overloading does not work properly in all cases, including
   some instances of method overriding, and keyword arguments
 - no 'Dynamic' classes
 - there is no way to use dynamic typing by default for top-level code

The current development focus is to support static type checking with a good
subset of Python features (both 2.x and 3.x).


Issue tracker
-------------

Please report any bugs and enhancement ideas using the mypy issue
tracker:

  https://github.com/JukkaL/mypy/issues


Help wanted
-----------

Any help in testing, development, documentation and other tasks is
highly appreciated and useful to the project.  Contact the developers
to join the project, or just start coding and send pull requests!
There are tasks for contributors of all skill levels.


License
-------

Mypy is licensed under the terms of the MIT License (see the file
LICENSE).

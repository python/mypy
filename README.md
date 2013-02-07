Mypy Readme
===========


What is mypy?
-------------

Mypy is a Python variant with seamless dynamic and static typing.
Currently the mypy implementation lets you mix static types and
dynamic types and translate mypy programs to readable Python.  Type
annotations and casts are treated as comments when translating to
Python.

The main goal of the project is to develop an optimising compiler that
can compile mypy programs to efficient native code.  The compiler is
still early in development.

Mypy is work in progress; many features are missing and there are
still bugs.  See 'Development status' below.


Requirements
------------

You need Python 3.x to run mypy.  You can have multiple Python
versions (2.x and 3.x) installed on the same system without problems.

In Ubuntu, Mint and Debian you can install Python 3 like this:

    $ sudo apt-get install python3

For OS X, Windows and other Linux flavours, packages are available at

  http://www.python.org/getit/


Quick Start
-----------
  
There is a separate repository that contains the mypy implementation
translated to Python.  You need to clone it to actually run mypy:

    $ git clone https://github.com/JukkaL/mypy-py.git

Now you can run mypy programs:

    $ python3 <path-to-repo>/mypy-py/driver.py PROGRAM

Replace 'python3' with your Python 3 interpreter.

The 'mypy-py' repository is only used for running mypy.  For mypy
development, clone the 'mypy' repository:

    $ git clone https://github.com/JukkaL/mypy.git

Remember to keep the two repos in sync by pulling them both; otherwise
you might get mysterious errors.


Web site and documentation
--------------------------

Documentation and additional information is available at the web site:

  http://www.mypy-lang.org/


Running tests
-------------

To run tests, run the script 'tests.py' in the 'mypy' repository using
the 'mypy.py' driver.  (We use the .py extension for mypy programs
even though they are not typically valid Python.  This is handy since
syntax highlighting in editors etc. typically just works.)


Development status
------------------

Mypy is work in progress and is not yet production quality (though
mypy development is already done in mypy!).

Here are some of the more significant Python features not supported
right now (but all of these will improve):

 - no decorators (neither properties)
 - no 'with' statements
 - no nested classes
 - no metaclasses
 - only basic operator overloading
 - only some Python modules are supported, and some only partially

Some mypy-specific features are also not supported or only partially
supported, including these:

 - function overloading does not work properly in all cases, including
   some instances of method overriding
 - no 'dynamic' classes
 - there is no way to use dynamic typing by default for top-level code

The initial development focus is to support a useful subset of Python
features.  The next main task is to implement an efficient native
compiler for this subset.  Other features will be implemented as well,
prioritized based on user feedback.


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

Mypy is licensed under the terms of the MIT license (see the file
LICENSE).

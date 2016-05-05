.. _command-line:

The mypy command line
=====================

This section documents many of mypy's command line flags.  A quick
summary of command line flags can always be printed using the ``-h``
flag (or its long form ``--help``)::

  $ mypy -h
  usage: mypy [-h] [-v] [-V] [--python-version x.y] [--py2] [-s] [--silent]
              [--almost-silent] [--disallow-untyped-calls]
              [--disallow-untyped-defs] [--check-untyped-defs] [--fast-parser]
              [-i] [-f] [--pdb] [--use-python-path] [--stats] [--inferstats]
              [--custom-typing MODULE] [--html-report DIR]
              [--old-html-report DIR] [--xslt-html-report DIR]
              [--xml-report DIR] [--txt-report DIR] [--xslt-txt-report DIR]
              [--linecount-report DIR] [-m MODULES] [-c COMMAND] [-p PACKAGE]
              [files [files ...]]
  (etc., too long to show everything here)

Specifying files and directories to be checked
**********************************************

You've already seen ``mypy program.py`` as a way to type check the
file ``program.py``.  More generally you can pass any number of files
and directories on the command line and they will all be type checked
together.

- Files ending in ``.py`` (and stub files ending in ``.pyi``) are
  checked as Python modules.

- Files not ending in ``.py`` or ``.pyi`` are assumed to be Python
  scripts and checked as such.

- Directories representing Python packages (i.e. containing a
  ``__init__.py[i]`` file) are checked as Python packages; all
  submodules and subpackages will be checked (subpackages must
  themselves have a ``__init__.py[i]`` file).

- Directories that don't represent Python packages (i.e. not directly
  containing an ``__init__.py[i]`` file) are checked as follows:

  - All ``*.py[i]`` files contained directly therein are checked as
    toplevel Python modules;

  - All packages contained directly therein (i.e. immediate
    subdirectories with an ``__init__.py[i]`` file) are checked as
    toplevel Python packages.

One more thing about checking modules and packages: if the directory
*containing* a module or package specified on the command line has an
``__init__.py[i]`` file, mypy assigns these an absolute module name by
crawling up the path until no ``__init__.py[i]`` file is found.  For
example, suppose we run the command ``mypy foo/bar/baz.py`` where
``foo/bar/__init__.py`` exists but ``foo/__init__.py`` does not.  Then
the module name assumed is ``bar.baz`` and the directory ``foo`` is
added to mypy's module search path.  On the other hand, if
``foo/bar/__init__.py`` did not exist, ``foo/bar`` would be added to
the module search path instead, and the module name assumed is just
``baz``.

If a script (a file not ending in ``.py[i]``) is processed, the module
name assumed is always ``__main__`` (matching the behavior of the
Python interpreter).

Other ways of specifying code to be checked
*******************************************

The flag ``-m`` (long form: ``--module``) lets you specify a module
name to be found using the default module search path.  The module
name may contain dots.  For example::

  $ mypy -m html.parser

will type check the module ``html.parser`` (this happens to be a
library stub).

The flag ``-p`` (long form: ``--package``) is similar to ``-m`` but
you give it a package name and it will type check all submodules and
subpackages (recursively) of that package.  (If you pass a package
name to ``-m`` it will just type check the package's ``__init__.py``
and anything imported from there.)  For example::

  $ mypy -p html

will type check the entire ``html`` package (of library stubs).

Finally the flag ``-c`` (long form: ``--command``) will take a string
from the command line and type check it as a small program.  For
example::

  $ mypy -c 'x = [1, 2]; print(x())'

will type check that little program (and complain that ``List[int]``
is not callable).

Following imports or not?
*************************

When you're first attacking a large existing code base (without
annotations) with mypy, you may only want it to type check selected
files (for example, the files to which you have added annotations).
While mypy's command line flags don't (yet) help you choose which
files to type check, you *can* prevent it from type checking other files
that may be imported from the files and/or packages you are explicitly
passing on the command line.  For example, suppose your entire program
consists of the files ``a.py`` and ``b.py``, and ``a.py`` contains
``import b``.  Now let's say you have added annotations to ``a.py``
but not yet to ``b.py``.  However, when you run::

  $ mypy a.py

this will also type check ``b.py`` (because of the import).  There
might be errors in ``b.py`` that you don't care to deal with right
now.  In this case the ``-s`` flag (``--silent-imports``) is handy::

  $ mypy -s a.py

will only type check ``a.py`` and ignore the ``import b``.  When you're
ready to also type check ``b.py``, you can add it to the command line::

  $ mypy -s a.py b.py

or you can of course remove the ``-s`` from the command line::

  $ mypy a.py

However these are not quite equivalent!  If you keep the ``-s`` flag,
any *other* imports in either ``a.py`` or ``b.py`` (say, ``import
pylons``) will still be ignored silently.  On the other hand if you
remove the ``-s`` flag, mypy will try to follow those imports and
issue an error if the target module is not found.  Pick your poison!

The behavior of ``-s`` is actually a bit more subtle that that,
though.  Even with ``-s``, an import that resolve to a stub file
(i.e. a file with a ``.pyi`` extension) will always be followed.  In
particular, this means that imports for which the typeshed package
(see :ref:`library-stubs`) supplies a stub will still be followed.
This is good, because it means mypy will always take the definitions
in stubs into account when it type checks your code.  If mypy decides
not to follow an import (because it leads to a ``.py`` file that
wasn't specified on the command line), it will pretend the module
object itself (and anything imported from it) has type ``Any`` which
pretty much shuts up all uses.  While that's probably what you want
when you're just getting started, it's also sometimes confusing.  For
example, this code::

  from somewhere import BaseClass

  class MyClass(BaseClass):

      def finagle(self) -> int:
          return super().finnagle() + 1

probably contains a subtle misspelling of the super method; however if
``somewhere`` is ignored by ``-s``, the type of ``BaseClass`` will be
``Any``, and mypy will assume there may in fact be a ``finnagle()``
method, so it won't flag the error.

For an effect similar to ``-s`` that's a little less silent you can
use ``--almost-silent``.  This uses the same rules for deciding
whether to check an imported module as ``-s``, but it will issue
errors for those imports so that you can double-check whether maybe
you should add another file to the command line.  This won't directly
flag the error in the above fragment, but it will help you realize
that ``BaseClass`` is not really imported.

Other flags changing what's checked
***********************************

Here are some more useful flags:

- ``--disallow-untyped-calls`` reports an error whenever a function
  with type annotations calls a function defined without annotations.

- ``--disallow-untyped-defs`` reports an error whenever it encounters
  a function definition without type annotations.

- ``--check-untyped-defs`` is less severe than the previous option --
  it type checks the body of every function, regardless of whether it
  has type annotations.  (By default the bodies of functions without
  annotations are not type checked.)  It will assume all arguments
  have type ``Any`` and always infer ``Any`` as the return type.

For the remaining flags you can read the full ``mypy -h`` output.

.. note::

   Command line flags are liable to change between releases.

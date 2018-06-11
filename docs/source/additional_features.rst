Additional features
-------------------

This section discusses various features that did not fit in naturally in one
of the previous sections.

.. _function-overloading:

Function overloading
********************

Sometimes the types in a function depend on each other in ways that
can't be captured with a ``Union``.  For example, the ``__getitem__``
(``[]`` bracket indexing) method can take an integer and return a
single item, or take a ``slice`` and return a ``Sequence`` of items.
You might be tempted to annotate it like so:

.. code-block:: python

    from typing import Sequence, TypeVar, Union
    T = TypeVar('T')

    class MyList(Sequence[T]):
        def __getitem__(self, index: Union[int, slice]) -> Union[T, Sequence[T]]:
            if isinstance(index, int):
                ...  # Return a T here
            elif isinstance(index, slice):
                ...  # Return a sequence of Ts here
            else:
                raise TypeError(...)

But this is too loose, as it implies that when you pass in an ``int``
you might sometimes get out a single item and sometimes a sequence.
The return type depends on the parameter type in a way that can't be
expressed using a type variable.  Instead, we can use `overloading
<https://www.python.org/dev/peps/pep-0484/#function-method-overloading>`_
to give the same function multiple type annotations (signatures) and
accurately describe the function's behavior.

.. code-block:: python

    from typing import overload, Sequence, TypeVar, Union
    T = TypeVar('T')

    class MyList(Sequence[T]):

        # The @overload definitions are just for the type checker,
        # and overwritten by the real implementation below.
        @overload
        def __getitem__(self, index: int) -> T:
            pass  # Don't put code here

        # All overloads and the implementation must be adjacent
        # in the source file, and overload order may matter:
        # when two overloads may overlap, the more specific one
        # should come first.
        @overload
        def __getitem__(self, index: slice) -> Sequence[T]:
            pass  # Don't put code here

        # The implementation goes last, without @overload.
        # It may or may not have type hints; if it does,
        # these are checked against the overload definitions
        # as well as against the implementation body.
        def __getitem__(self, index: Union[int, slice]) -> Union[T, Sequence[T]]:
            # This is exactly the same as before.
            if isinstance(index, int):
                ...  # Return a T here
            elif isinstance(index, slice):
                ...  # Return a sequence of Ts here
            else:
                raise TypeError(...)

Calls to overloaded functions are type checked against the variants,
not against the implementation. A call like ``my_list[5]`` would have
type ``T``, not ``Union[T, Sequence[T]]`` because it matches the
first overloaded definition, and ignores the type annotations on the
implementation of ``__getitem__``. The code in the body of the
definition of ``__getitem__`` is checked against the annotations on
the corresponding declaration. In this case the body is checked
with ``index: Union[int, slice]`` and a return type
``Union[T, Sequence[T]]``. If there are no annotations on the
corresponding definition, then code in the function body is not type
checked.

The annotations on the function body must be compatible with the
types given for the overloaded variants listed above it. The type
checker will verify that all the types for the overloaded variants
are compatible with the types given for the implementation. In this
case it checks that the parameter type ``int`` and the return type
``T`` are compatible with ``Union[int, slice]`` and
``Union[T, Sequence[T]]`` for the first variant. For the second
variant it verifies that the parameter type ``slice`` and the return
type ``Sequence[T]`` are compatible with ``Union[int, slice]`` and
``Union[T, Sequence[T]]``.

Overloaded function variants are still ordinary Python functions and
they still define a single runtime object. There is no automatic
dispatch happening, and you must manually handle the different types
in the implementation (usually with :func:`isinstance` checks, as
shown in the example).

The overload variants must be adjacent in the code. This makes code
clearer, as you don't have to hunt for overload variants across the
file.

Overloads in stub files are exactly the same, except there is no
implementation.

.. note::

   As generic type variables are erased at runtime when constructing
   instances of generic types, an overloaded function cannot have
   variants that only differ in a generic type argument,
   e.g. ``List[int]`` and ``List[str]``.

.. note::

   If you just need to constrain a type variable to certain types or
   subtypes, you can use a :ref:`value restriction
   <type-variable-value-restriction>`.

.. _attrs_package:

The attrs package
*****************

`attrs <https://www.attrs.org/en/stable>`_ is a package that lets you define
classes without writing boilerplate code. Mypy can detect uses of the
package and will generate the necessary method definitions for decorated
classes using the type annotations it finds.
Type annotations can be added as follows:

.. code-block:: python

    import attr

    @attr.s
    class A:
        one: int = attr.ib()          # Variable annotation (Python 3.6+)
        two = attr.ib()  # type: int  # Type comment
        three = attr.ib(type=int)     # type= argument

If you're using ``auto_attribs=True`` you must use variable annotations.

.. code-block:: python

    import attr

    @attr.s(auto_attribs=True)
    class A:
        one: int
        two: int = 7
        three: int = attr.ib(8)

Typeshed has a couple of "white lie" annotations to make type checking
easier. ``attr.ib`` and ``attr.Factory`` actually return objects, but the
annotation says these return the types that they expect to be assigned to.
That enables this to work:

.. code-block:: python

    import attr
    from typing import Dict

    @attr.s(auto_attribs=True)
    class A:
        one: int = attr.ib(8)
        two: Dict[str, str] = attr.Factory(dict)
        bad: str = attr.ib(16)   # Error: can't assign int to str

Caveats/Known Issues
====================

* The detection of attr classes and attributes works by function name only.
  This means that if you have your own helper functions that, for example,
  ``return attr.ib()`` mypy will not see them.

* All boolean arguments that mypy cares about must be literal ``True`` or ``False``.
  e.g the following will not work:

  .. code-block:: python

      import attr
      YES = True
      @attr.s(init=YES)
      class A:
          ...

* Currently, ``converter`` only supports named functions.  If mypy finds something else it
  will complain about not understanding the argument and the type annotation in
  ``__init__`` will be replaced by ``Any``.

* `Validator decorators <http://www.attrs.org/en/stable/examples.html#decorator>`_
  and `default decorators <http://www.attrs.org/en/stable/examples.html#defaults>`_
  are not type-checked against the attribute they are setting/validating.

* Method definitions added by mypy currently overwrite any existing method
  definitions.

.. _remote-cache:

Using a remote cache to speed up mypy runs
******************************************

Mypy performs type checking *incrementally*, reusing results from
previous runs to speed up successive runs. If you are type checking a
large codebase, mypy can still be sometimes slower than desirable. For
example, if you create a new branch based on a much more recent commit
than the target of the previous mypy run, mypy may have to
process almost every file, as a large fraction of source files may
have changed. This can also happen after you've rebased a local
branch.

Mypy supports using a *remote cache* to improve performance in cases
such as the above.  In a large codebase, remote caching can sometimes
speed up mypy runs by a factor of 10, or more.

Mypy doesn't include all components needed to set
this up -- generally you will have to perform some simple integration
with your Continuous Integration (CI) or build system to configure
mypy to use a remote cache. This discussion assumes you have a CI
system set up for the mypy build you want to speed up, and that you
are using a central git repository. Generalizing to different
environments should not be difficult.

Here are the main components needed:

* A shared repository for storing mypy cache files for all landed commits.

* CI build that uploads mypy incremental cache files to the shared repository for
  each commit for which the CI build runs.

* A wrapper script around mypy that developers use to run mypy with remote
  caching enabled.

Below we discuss each of these components in some detail.

Shared repository for cache files
=================================

You need a repository that allows you to upload mypy cache files from
your CI build and make the cache files available for download based on
a commit id.  A simple approach would be to produce an archive of the
``.mypy_cache`` directory (which contains the mypy cache data) as a
downloadable *build artifact* from your CI build (depending on the
capabilities of your CI system).  Alternatively, you could upload the
data to a web server or to S3, for example.

Continuous Integration build
============================

The CI build would run a regular mypy build and create an archive containing
the ``.mypy_cache`` directory produced by the build. Finally, it will produce
the cache as a build artifact or upload it to a repository where it is
accessible by the mypy wrapper script.

Your CI script might work like this:

* Run mypy normally. This will generate cache data under the
  ``.mypy_cache`` directory.

* Create a tarball from the ``.mypy_cache`` directory.

* Determine the current git master branch commit id (say, using
  ``git rev-parse HEAD``).

* Upload the tarball to the shared repository with a name derived from the
  commit id.

Mypy wrapper script
===================

The wrapper script is used by developers to run mypy locally during
development instead of invoking mypy directly.  The wrapper first
populates the local ``.mypy_cache`` directory from the shared
repository and then runs a normal incremental build.

The wrapper script needs some logic to determine the most recent
central repository commit (by convention, the ``origin/master`` branch
for git) the local development branch is based on. In a typical git
setup you can do it like this:

.. code::

    git merge-base HEAD origin/master

The next step is to download the cache data (contents of the
``.mypy_cache`` directory) from the shared repository based on the
commit id of the merge base produced by the git command above. The
script will decompress the data so that mypy will start with a fresh
``.mypy_cache``. Finally, the script runs mypy normally. And that's all!

Caching with mypy daemon
========================

You can also use remote caching with the :ref:`mypy daemon <mypy_daemon>`.
The remote cache will significantly speed up the first ``dmypy check``
run after starting or restarting the daemon.

The mypy daemon requires extra fine-grained dependency data in
the cache files which aren't included by default. To use caching with
the mypy daemon, use the ``--cache-fine-grained`` option in your CI
build::

    $ mypy --cache-fine-grained <args...>

This flag adds extra information for the daemon to the cache. In
order to use this extra information, you will also need to use the
``--use-fine-grained-cache`` option with ``dmypy start`` or
``dmypy restart``. Example::

    $ dmypy start -- --use-fine-grained-cache <options...>

Now your first ``dmypy check`` run should be much faster, as it can use
cache information to avoid processing the whole program.

Refinements
===========

There are several optional refinements that may improve things further,
at least if your codebase is hundreds of thousands of lines or more:

* If the wrapper script determines that the merge base hasn't changed
  from a previous run, there's no need to download the cache data and
  it's better to instead reuse the existing local cache data.

* If you use the mypy daemon, you may want to restart the daemon each time
  after the merge base or local branch has changed to avoid processing a
  potentially large number of changes in an incremental build, as this can
  be much slower than downloading cache data and restarting the daemon.

* If the current local branch is based on a very recent master commit,
  the remote cache data may not yet be available for that commit, as
  there will necessarily be some latency to build the cache files. It
  may be a good idea to look for cache data for, say, the 5 latest
  master commits and use the most recent data that is available.

* If the remote cache is not accessible for some reason (say, from a public
  network), the script can still fall back to a normal incremental build.

* You can have multiple local cache directories for different local branches
  using the ``--cache-dir`` option. If the user switches to an existing
  branch where downloaded cache data is already available, you can continue
  to use the existing cache data instead of redownloading the data.

* You can set up your CI build to use a remote cache to speed up the
  CI build. This would be particularly useful if each CI build starts
  from a fresh state without access to cache files from previous
  builds. It's still recommended to run a full, non-incremental
  mypy build to create the cache data, as repeatedly updating cache
  data incrementally could result in drift over a long time period (due
  to a mypy caching issue, perhaps).

.. _extended_callable:

Extended Callable types
***********************

As an experimental mypy extension, you can specify ``Callable`` types
that support keyword arguments, optional arguments, and more.  When
you specify the arguments of a Callable, you can choose to supply just
the type of a nameless positional argument, or an "argument specifier"
representing a more complicated form of argument.  This allows one to
more closely emulate the full range of possibilities given by the
``def`` statement in Python.

As an example, here's a complicated function definition and the
corresponding ``Callable``:

.. code-block:: python

   from typing import Callable
   from mypy_extensions import (Arg, DefaultArg, NamedArg,
                                DefaultNamedArg, VarArg, KwArg)

   def func(__a: int,  # This convention is for nameless arguments
            b: int,
            c: int = 0,
            *args: int,
            d: int,
            e: int = 0,
            **kwargs: int) -> int:
       ...

   F = Callable[[int,  # Or Arg(int)
                 Arg(int, 'b'),
                 DefaultArg(int, 'c'),
                 VarArg(int),
                 NamedArg(int, 'd'),
                 DefaultNamedArg(int, 'e'),
                 KwArg(int)],
                int]

   f: F = func

Argument specifiers are special function calls that can specify the
following aspects of an argument:

- its type (the only thing that the basic format supports)

- its name (if it has one)

- whether it may be omitted

- whether it may or must be passed using a keyword

- whether it is a ``*args`` argument (representing the remaining
  positional arguments)

- whether it is a ``**kwargs`` argument (representing the remaining
  keyword arguments)

The following functions are available in ``mypy_extensions`` for this
purpose:

.. code-block:: python

   def Arg(type=Any, name=None):
       # A normal, mandatory, positional argument.
       # If the name is specified it may be passed as a keyword.

   def DefaultArg(type=Any, name=None):
       # An optional positional argument (i.e. with a default value).
       # If the name is specified it may be passed as a keyword.

   def NamedArg(type=Any, name=None):
       # A mandatory keyword-only argument.

   def DefaultNamedArg(type=Any, name=None):
       # An optional keyword-only argument (i.e. with a default value).

   def VarArg(type=Any):
       # A *args-style variadic positional argument.
       # A single VarArg() specifier represents all remaining
       # positional arguments.

   def KwArg(type=Any):
       # A **kwargs-style variadic keyword argument.
       # A single KwArg() specifier represents all remaining
       # keyword arguments.

In all cases, the ``type`` argument defaults to ``Any``, and if the
``name`` argument is omitted the argument has no name (the name is
required for ``NamedArg`` and ``DefaultNamedArg``).  A basic
``Callable`` such as

.. code-block:: python

   MyFunc = Callable[[int, str, int], float]

is equivalent to the following:

.. code-block:: python

   MyFunc = Callable[[Arg(int), Arg(str), Arg(int)], float]

A ``Callable`` with unspecified argument types, such as

.. code-block:: python

   MyOtherFunc = Callable[..., int]

is (roughly) equivalent to

.. code-block:: python

   MyOtherFunc = Callable[[VarArg(), KwArg()], int]

.. note::

   This feature is experimental.  Details of the implementation may
   change and there may be unknown limitations. **IMPORTANT:**
   Each of the functions above currently just returns its ``type``
   argument, so the information contained in the argument specifiers
   is not available at runtime.  This limitation is necessary for
   backwards compatibility with the existing ``typing.py`` module as
   present in the Python 3.5+ standard library and distributed via
   PyPI.

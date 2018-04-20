Additional features
-------------------

Several mypy features are not currently covered by this tutorial,
including the following:

- inheritance between generic classes
- compatibility and subtyping of generic types, including covariance of generic types
- ``super()``


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

Refinements
===========

There are several optional refinements that may improve things further,
at least if your codebase is hundreds of thousands of lines or more:

* If the wrapper script determines that the merge base hasn't changed
  from a previous run, there's no need to download the cache data and
  it's better to instead reuse the existing local cache data.

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

.. _existing-code:

Using mypy with an existing codebase
====================================

This section explains how to get started using mypy with an existing,
significant codebase that has little or no type annotations. If you are
a beginner, you can skip this section.

Start small
-----------

If your codebase is large, pick a subset of your codebase (say, 5,000 to 50,000
lines) and get mypy to run successfully only on this subset at first, *before
adding annotations*. This should be doable in a day or two. The sooner you get
some form of mypy passing on your codebase, the sooner you benefit.

You'll likely need to fix some mypy errors, either by inserting
annotations requested by mypy or by adding ``# type: ignore``
comments to silence errors you don't want to fix now.

We'll mention some tips for getting mypy passing on your codebase in various
sections below.

Run mypy consistently and prevent regressions
---------------------------------------------

Make sure all developers on your codebase run mypy the same way.
One way to ensure this is adding a small script with your mypy
invocation to your codebase, or adding your mypy invocation to
existing tools you use to run tests, like ``tox``.

* Make sure everyone runs mypy with the same options. Checking a mypy
  :ref:`configuration file <config-file>` into your codebase is the
  easiest way to do this.

* Make sure everyone type checks the same set of files. See
  :ref:`specifying-code-to-be-checked` for details.

* Make sure everyone runs mypy with the same version of mypy, for instance
  by pinning mypy with the rest of your dev requirements.

In particular, you'll want to make sure to run mypy as part of your
Continuous Integration (CI) system as soon as possible. This will
prevent new type errors from being introduced into your codebase.

A simple CI script could look something like this:

.. code-block:: text

    python3 -m pip install mypy==1.8
    # Run your standardised mypy invocation, e.g.
    mypy my_project
    # This could also look like `scripts/run_mypy.sh`, `tox run -e mypy`, `make mypy`, etc

Ignoring errors from certain modules
------------------------------------

By default mypy will follow imports in your code and try to check everything.
This means even if you only pass in a few files to mypy, it may still process a
large number of imported files. This could potentially result in lots of errors
you don't want to deal with at the moment.

One way to deal with this is to ignore errors in modules you aren't yet ready to
type check. The :confval:`ignore_errors` option is useful for this, for instance,
if you aren't yet ready to deal with errors from ``package_to_fix_later``:

.. code-block:: text

   [mypy-package_to_fix_later.*]
   ignore_errors = True

You could even invert this, by setting ``ignore_errors = True`` in your global
config section and only enabling error reporting with ``ignore_errors = False``
for the set of modules you are ready to type check.

The per-module configuration that mypy's configuration file allows can be
extremely useful. Many configuration options can be enabled or disabled
only for specific modules. In particular, you can also enable or disable
various error codes on a per-module basis, see :ref:`error-codes`.

Fixing errors related to imports
--------------------------------

A common class of error you will encounter is errors from mypy about modules
that it can't find, that don't have types, or don't have stub files:

.. code-block:: text

    core/config.py:7: error: Cannot find implementation or library stub for module named 'frobnicate'
    core/model.py:9: error: Cannot find implementation or library stub for module named 'acme'
    ...

Sometimes these can be fixed by installing the relevant packages or
stub libraries in the environment you're running ``mypy`` in.

See :ref:`fix-missing-imports` for a complete reference on these errors
and the ways in which you can fix them.

You'll likely find that you want to suppress all errors from importing
a given module that doesn't have types. If you only import that module
in one or two places, you can use ``# type: ignore`` comments. For example,
here we ignore an error about a third-party module ``frobnicate`` that
doesn't have stubs using ``# type: ignore``:

.. code-block:: python

   import frobnicate  # type: ignore
   ...
   frobnicate.initialize()  # OK (but not checked)

But if you import the module in many places, this becomes unwieldy. In this
case, we recommend using a :ref:`configuration file <config-file>`. For example,
to disable errors about importing ``frobnicate`` and ``acme`` everywhere in your
codebase, use a config like this:

.. code-block:: text

   [mypy-frobnicate.*]
   ignore_missing_imports = True

   [mypy-acme.*]
   ignore_missing_imports = True

If you get a large number of errors, you may want to ignore all errors
about missing imports, for instance by setting
:option:`--disable-error-code=import-untyped <mypy --ignore-missing-imports>`.
or setting :confval:`ignore_missing_imports` to true globally.
This can hide errors later on, so we recommend avoiding this
if possible.

Finally, mypy allows fine-grained control over specific import following
behaviour. It's very easy to silently shoot yourself in the foot when playing
around with these, so this should be a last resort. For more
details, look :ref:`here <follow-imports>`.

Prioritise annotating widely imported modules
---------------------------------------------

Most projects have some widely imported modules, such as utilities or
model classes. It's a good idea to annotate these pretty early on,
since this allows code using these modules to be type checked more
effectively.

Mypy is designed to support gradual typing, i.e. letting you add annotations at
your own pace, so it's okay to leave some of these modules unannotated. The more
you annotate, the more useful mypy will be, but even a little annotation
coverage is useful.

Write annotations as you go
---------------------------

Consider adding something like these in your code style
conventions:

1. Developers should add annotations for any new code.
2. It's also encouraged to write annotations when you modify existing code.

This way you'll gradually increase annotation coverage in your
codebase without much effort.

Automate annotation of legacy code
----------------------------------

There are tools for automatically adding draft annotations based on simple
static analysis or on type profiles collected at runtime.  Tools include
:doc:`monkeytype:index`, `autotyping`_ and `PyAnnotate`_.

A simple approach is to collect types from test runs. This may work
well if your test coverage is good (and if your tests aren't very
slow).

Another approach is to enable type collection for a small, random
fraction of production network requests.  This clearly requires more
care, as type collection could impact the reliability or the
performance of your service.

.. _getting-to-strict:

Introduce stricter options
--------------------------

Mypy is very configurable. Once you get started with static typing, you may want
to explore the various strictness options mypy provides to catch more bugs. For
example, you can ask mypy to require annotations for all functions in certain
modules to avoid accidentally introducing code that won't be type checked using
:confval:`disallow_untyped_defs`. Refer to :ref:`config-file` for the details.

An excellent goal to aim for is to have your codebase pass when run against ``mypy --strict``.
This basically ensures that you will never have a type related error without an explicit
circumvention somewhere (such as a ``# type: ignore`` comment).

The following config is equivalent to ``--strict`` (as of mypy 1.0):

.. code-block:: text

   # Start off with these
   warn_unused_configs = True
   warn_redundant_casts = True
   warn_unused_ignores = True

   # Getting this passing should be easy
   strict_equality = True

   # Strongly recommend enabling this one as soon as you can
   check_untyped_defs = True

   # These shouldn't be too much additional work, but may be tricky to
   # get passing if you use a lot of untyped libraries
   disallow_subclassing_any = True
   disallow_untyped_decorators = True
   disallow_any_generics = True

   # These next few are various gradations of forcing use of type annotations
   disallow_untyped_calls = True
   disallow_incomplete_defs = True
   disallow_untyped_defs = True

   # This one isn't too hard to get passing, but return on investment is lower
   no_implicit_reexport = True

   # This one can be tricky to get passing if you use a lot of untyped libraries
   warn_return_any = True

   # This one is a catch-all flag for the rest of strict checks that are technically
   # correct but may not be practical
   extra_checks = True

Note that you can also start with ``--strict`` and subtract, for instance:

.. code-block:: text

   strict = True
   warn_return_any = False

Remember that many of these options can be enabled on a per-module basis. For instance,
you may want to enable ``disallow_untyped_defs`` for modules which you've completed
annotations for, in order to prevent new code from being added without annotations.

And if you want, it doesn't stop at ``--strict``. Mypy has additional checks
that are not part of ``--strict`` that can be useful. See the complete
:ref:`command-line` reference and :ref:`error-codes-optional`.

Speed up mypy runs
------------------

You can use :ref:`mypy daemon <mypy_daemon>` to get much faster
incremental mypy runs. The larger your project is, the more useful
this will be.  If your project has at least 100,000 lines of code or
so, you may also want to set up :ref:`remote caching <remote-cache>`
for further speedups.

.. _PyAnnotate: https://github.com/dropbox/pyannotate
.. _autotyping: https://github.com/JelleZijlstra/autotyping

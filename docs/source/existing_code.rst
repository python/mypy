.. _existing-code:

Using mypy with an existing codebase
====================================

This section explains how to get started using mypy with an existing,
significant codebase that has little or no type annotations. If you are
a beginner, you can skip this section.

These steps will get you started with mypy on an existing codebase:

1. Start small -- get a clean mypy build for some files, with few
   annotations

2. Write a mypy runner script to ensure consistent results

3. Run mypy in Continuous Integration to prevent type errors

4. Gradually annotate commonly imported modules

5. Write annotations as you modify existing code and write new code

6. Use :doc:`monkeytype:index` or `PyAnnotate`_ to automatically annotate legacy code

We discuss all of these points in some detail below, and a few optional
follow-up steps.

Start small
-----------

If your codebase is large, pick a subset of your codebase (say, 5,000
to 50,000 lines) and run mypy only on this subset at first,
*without any annotations*. This shouldn't take more than a day or two
to implement, so you start enjoying benefits soon.

You'll likely need to fix some mypy errors, either by inserting
annotations requested by mypy or by adding ``# type: ignore``
comments to silence errors you don't want to fix now.

In particular, mypy often generates errors about modules that it can't
find or that don't have stub files:

.. code-block:: text

    core/config.py:7: error: Cannot find implementation or library stub for module named 'frobnicate'
    core/model.py:9: error: Cannot find implementation or library stub for module named 'acme'
    ...

This is normal, and you can easily ignore these errors. For example,
here we ignore an error about a third-party module ``frobnicate`` that
doesn't have stubs using ``# type: ignore``:

.. code-block:: python

   import frobnicate  # type: ignore
   ...
   frobnicate.initialize()  # OK (but not checked)

You can also use a mypy configuration file, which is convenient if
there are a large number of errors to ignore. For example, to disable
errors about importing ``frobnicate`` and ``acme`` everywhere in your
codebase, use a config like this:

.. code-block:: text

   [mypy-frobnicate.*]
   ignore_missing_imports = True

   [mypy-acme.*]
   ignore_missing_imports = True

You can add multiple sections for different modules that should be
ignored.

If your config file is named ``mypy.ini``, this is how you run mypy:

.. code-block:: text

   mypy --config-file mypy.ini mycode/

If you get a large number of errors, you may want to ignore all errors
about missing imports.  This can easily cause problems later on and
hide real errors, and it's only recommended as a last resort.
For more details, look :ref:`here <follow-imports>`.

Mypy follows imports by default. This can result in a few files passed
on the command line causing mypy to process a large number of imported
files, resulting in lots of errors you don't want to deal with at the
moment. There is a config file option to disable this behavior, but
since this can hide errors, it's not recommended for most users.

Mypy runner script
------------------

Introduce a mypy runner script that runs mypy, so that every developer
will use mypy consistently. Here are some things you may want to do in
the script:

* Ensure that the correct version of mypy is installed.

* Specify mypy config file or command-line options.

* Provide set of files to type check. You may want to implement
  inclusion and exclusion filters for full control of the file
  list.

Continuous Integration
----------------------

Once you have a clean mypy run and a runner script for a part
of your codebase, set up your Continuous Integration (CI) system to
run mypy to ensure that developers won't introduce bad annotations.
A simple CI script could look something like this:

.. code-block:: text

    python3 -m pip install mypy==0.600  # Pinned version avoids surprises
    scripts/mypy  # Runs with the correct options

Annotate widely imported modules
--------------------------------

Most projects have some widely imported modules, such as utilities or
model classes. It's a good idea to annotate these pretty early on,
since this allows code using these modules to be type checked more
effectively. Since mypy supports gradual typing, it's okay to leave
some of these modules unannotated. The more you annotate, the more
useful mypy will be, but even a little annotation coverage is useful.

Write annotations as you go
---------------------------

Now you are ready to include type annotations in your development
workflows. Consider adding something like these in your code style
conventions:

1. Developers should add annotations for any new code.
2. It's also encouraged to write annotations when you modify existing code.

This way you'll gradually increase annotation coverage in your
codebase without much effort.

Automate annotation of legacy code
----------------------------------

There are tools for automatically adding draft annotations
based on type profiles collected at runtime.  Tools include
:doc:`monkeytype:index` (Python 3) and `PyAnnotate`_
(type comments only).

A simple approach is to collect types from test runs. This may work
well if your test coverage is good (and if your tests aren't very
slow).

Another approach is to enable type collection for a small, random
fraction of production network requests.  This clearly requires more
care, as type collection could impact the reliability or the
performance of your service.

Speed up mypy runs
------------------

You can use :ref:`mypy daemon <mypy_daemon>` to get much faster
incremental mypy runs. The larger your project is, the more useful
this will be.  If your project has at least 100,000 lines of code or
so, you may also want to set up :ref:`remote caching <remote-cache>`
for further speedups.

Introduce stricter options
--------------------------

Mypy is very configurable. Once you get started with static typing,
you may want to explore the various
strictness options mypy provides to
catch more bugs. For example, you can ask mypy to require annotations
for all functions in certain modules to avoid accidentally introducing
code that won't be type checked. Refer to :ref:`command-line` for the
details.

.. _PyAnnotate: https://github.com/dropbox/pyannotate

Mypy Documentation
==================

What's this?
------------

This directory contains the source code for Mypy documentation (under `source/`)
and build scripts. The documentation uses Sphinx and reStructuredText. We use
`sphinx-rtd-theme` as the documentation theme.

Building the documentation
--------------------------

Install Sphinx and other dependencies (i.e. theme) needed for the documentation.
From the `docs` directory, use `pip`:

```
$ pip install -r requirements-docs.txt
```

Build the documentation like this:

```
$ make html
```

The built documentation will be placed in the `docs/build` directory. Open
`docs/build/index.html` to view the documentation.

Helpful documentation build commands
------------------------------------

Clean the documentation build:

```
$ make clean
```

Test and check the links found in the documentation:

```
$ make linkcheck
```

Documentation on Read The Docs
------------------------------

The mypy documentation is hosted on Read The Docs, and the latest version
can be found at https://mypy.readthedocs.io/en/latest.

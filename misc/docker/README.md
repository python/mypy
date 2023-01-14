Running mypy and mypyc tests in a Docker container
==================================================

This directory contains scripts for running mypy and mypyc tests in a
Linux Docker container. This allows running Linux tests under a
different operating system that supports Docker, or running tests in
an isolated environment under a Linux host operating system.

Why use Docker?
---------------

Mypyc tests in particular can be much faster in a Docker container
than running on the host operating system.

Also, if it's inconvient to install the necessary dependencies on the
host operating system, or there are issues running some tests on the
host operating system, using a container can help.

How to run tests
----------------

First install Docker.

You need to build the container with all necessary dependencies before
you can run tests:

```
$ python3 misc/docker/build.py
```

This creates a `mypy-test` Docker container that you can use to run
tests.

You may need to run the script as root:

```
$ sudo python3 misc/docker/build.py
```

If you have a stale container which isn't up-to-date, use `--no-cache`
`--pull` to force rebuilding everything:

```
$ python3 misc/docker/build.py --no-cache --pull
```

Now you can run tests by using the `misc/docker/run.sh` script. Give
it the pytest command line you want to run as arguments. For example,
you can run mypyc tests like this:

```
$ misc/docker/run.sh pytest mypyc
```

You can also use `-k <filter>`, `-n0`, `-q`, etc.

Again, you may need to run this as root:

```
$ sudo misc/docker/run.sh pytest mypyc
```

You can also use `runtests.py` in the container. Example:

```
$ misc/docker/run.sh ./runtests.py self lint
```

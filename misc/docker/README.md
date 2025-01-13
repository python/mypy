Running mypy and mypyc tests in a Docker container
==================================================

This directory contains scripts for running mypy and mypyc tests in a
Linux Docker container. This allows running Linux tests on a different
operating system that supports Docker, or running tests in an
isolated, predictable environment on a Linux host operating system.

Why use Docker?
---------------

Mypyc tests can be significantly faster in a Docker container than
running natively on macOS.

Also, if it's inconvenient to install the necessary dependencies on the
host operating system, or there are issues getting some tests to pass
on the host operating system, using a container can be an easy
workaround.

Prerequisites
-------------

First install Docker. On macOS, both Docker Desktop (proprietary, but
with a free of charge subscription for some use cases) and Colima (MIT
license) should work as runtimes.

You may have to explicitly start the runtime first. Colima example
(replace '8' with the number of CPU cores you have):

```
$ colima start -c 8

```

How to run tests
----------------

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

Again, you may need to run `run.sh` as root:

```
$ sudo misc/docker/run.sh pytest mypyc
```

You can also use `runtests.py` in the container. Example:

```
$ misc/docker/run.sh ./runtests.py self lint
```

Notes
-----

File system changes within the container are not visible to the host
system. You can't use the container to format code using Black, for
example.

On a mac, you may want to give additional CPU to the VM used to run
the container. The default allocation may be way too low (e.g. 2 CPU
cores). For example, use the `-c` option when starting the VM if you
use Colima:

```
$ colima start -c 8
```

Giving access to all available CPUs to the Linux VM tends to provide
the best performance. This is not needed on a Linux host, since the
container is not run in a VM.
